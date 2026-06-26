"""
压测脚本 — 白天测试：模拟多个设备同时预测+训练，检查是否会出bug
用法:
  cd backend
  # 快速模式（3轮预测）
  python test/stress_test.py --quick
  # 预测+训练同时
  python test/stress_test.py --predict-devices 2,3,4,5 --train-devices 2,3
  # 仅预测1轮
  python test/stress_test.py --predict-only --predict-devices 2,3,4,5 --predict-rounds 1

错误记录: backend/test/stress_results/errors_{时间戳}.txt
"""
import os
import sys
import time
import glob
import json
import uuid
import argparse
import threading
import logging
import traceback
from datetime import datetime, timedelta

# 确保项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, backend_dir)
sys.path.insert(0, project_root)

os.environ['JOBLIB_TEMP_FOLDER'] = 'C:\\temp_joblib'
os.environ['PYTHONUNBUFFERED'] = '1'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger('stress_test')

# 错误记录目录
STRESS_RESULTS_DIR = os.path.join(current_dir, 'stress_results')


def find_latest_models(device_ids: list, model_dir: str = None) -> dict:
    """查找每个设备的最新模型文件"""
    if model_dir is None:
        candidates = [
            os.path.join(backend_dir, 'ml', 'models', 'saved_models'),
            os.path.join(project_root, 'backend', 'ml', 'models', 'saved_models'),
        ]
        model_dir = next((p for p in candidates if os.path.isdir(p)), None)
    if not model_dir:
        logger.error("未找到模型保存目录")
        return {}

    result = {}
    for did in device_ids:
        pattern = os.path.join(model_dir, f"xgboost_device_{did}_*.pkl")
        files = glob.glob(pattern)
        if files:
            files.sort(key=os.path.getmtime, reverse=True)
            result[did] = files[0]
            logger.info(f"设备 {did} 模型: {os.path.basename(files[0])}")
        else:
            logger.warning(f"设备 {did} 无模型文件")
    return result


def get_device_target_feature(device_id: int) -> str:
    """从数据库获取设备的目标特征名"""
    try:
        from app.database import SessionLocal
        from app import models
        db = SessionLocal()
        try:
            device = db.query(models.Device).filter(models.Device.id == device_id).first()
            if device and device.model_version_id:
                output_feature = db.query(models.Feature).join(
                    models.ModelVersionFeature
                ).filter(
                    models.ModelVersionFeature.version_id == device.model_version_id,
                    models.ModelVersionFeature.is_output == True
                ).first()
                if output_feature:
                    return output_feature.code
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"获取设备 {device_id} 目标特征失败: {e}")
    return None


def run_single_prediction(device_id: int, model_path: str, target_feature: str, run_idx: int) -> dict:
    """
    执行单次预测（force_predict=True 跳过关机检查）
    【关键】每个线程创建独立的 XGBoostPredictor 实例，避免单例并发污染
    """
    from ml.models.predictor import XGBoostPredictor
    start = time.time()
    error_trace = None
    try:
        predictor = XGBoostPredictor()
        predictor.load_model(model_path)
        result = predictor.make_prediction(
            device_id=device_id,
            target_feature=target_feature,
            force_predict=True,
            use_correction=False,
        )
        elapsed = time.time() - start
        pred_val = result.get('prediction')
        if isinstance(pred_val, (list, tuple)):
            preview = list(pred_val)[:3]
        else:
            preview = pred_val

        return {
            'device_id': device_id,
            'run': run_idx + 1,
            'success': result.get('success', False),
            'prediction_preview': preview,
            'device_status': result.get('device_status', '?'),
            'elapsed_s': round(elapsed, 2),
            'save_success': result.get('save_success'),
            'error_trace': None,
        }
    except Exception as e:
        elapsed = time.time() - start
        error_trace = traceback.format_exc()
        return {
            'device_id': device_id,
            'run': run_idx + 1,
            'success': False,
            'error': str(e),
            'error_trace': error_trace,
            'elapsed_s': round(elapsed, 2),
            'save_success': False,
        }


def stress_predict(device_ids: list, model_paths: dict, rounds: int = 10, timeout: int = 120) -> list:
    """压测预测：多设备并发预测 rounds 轮"""
    logger.info(f"===== 预测压测开始: {len(model_paths)} 设备 × {rounds} 轮 =====")
    all_results = []
    expected_total = len(model_paths) * rounds
    start_total = time.time()

    for r in range(rounds):
        round_start = time.time()
        threads = []
        round_results = []

        def _do_thread(did, mp, tf, ri):
            try:
                res = run_single_prediction(did, mp, tf, ri)
            except Exception as ex:
                res = {
                    'device_id': did, 'run': ri + 1, 'success': False,
                    'error': str(ex), 'error_trace': traceback.format_exc(),
                    'elapsed_s': 0, 'save_success': False,
                }
            round_results.append(res)

        for did, mp in model_paths.items():
            tf = get_device_target_feature(did)
            if not tf:
                logger.warning(f"跳过设备 {did}: 无目标特征")
                continue
            t = threading.Thread(target=_do_thread, args=(did, mp, tf, r), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=timeout)
            if t.is_alive():
                logger.error(f"线程超时! 设备可能卡住")

        all_results.extend(round_results)
        elapsed_r = time.time() - round_start
        ok = sum(1 for x in round_results if x.get('success'))
        fail = sum(1 for x in round_results if not x.get('success'))
        launched = len(threads)
        logger.info(f"  第{r+1}轮: 启动{launched}, 成功{ok}, 失败{fail}, 耗时{elapsed_r:.1f}s")

    total_elapsed = time.time() - start_total
    total_ok = sum(1 for x in all_results if x.get('success'))
    total_fail = sum(1 for x in all_results if not x.get('success'))
    actual_total = len(all_results)
    missing = expected_total - actual_total
    avg_time = sum(x.get('elapsed_s', 0) for x in all_results) / max(actual_total, 1)

    logger.info(f"===== 预测压测结束 =====")
    logger.info(f"  预期: {expected_total}  实际: {actual_total}  缺失: {missing}")
    logger.info(f"  成功: {total_ok}  失败: {total_fail}")
    logger.info(f"  总耗时: {total_elapsed:.1f}s  平均每次: {avg_time:.1f}s")
    if missing > 0:
        logger.warning(f"⚠️ 有 {missing} 个任务未返回结果（可能线程卡死或跳过）")

    return all_results, expected_total, missing


def submit_train_task(device_id: int, config: dict = None) -> dict:
    """提交训练任务到任务队列，返回 task_id"""
    from app.services.task_queue_manager import get_task_queue_manager
    from app.services.scheduler import get_scheduler

    task_queue = get_task_queue_manager()
    scheduler = get_scheduler()
    task_id = f"StressTrain-{device_id}-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    added = task_queue.add_task(
        task_id=task_id,
        task_func=scheduler._execute_schedule_with_update,
        args=(None,),
        kwargs={"device_id": device_id, "config": config},
        device_id=device_id,
        task_type='train'
    )
    return {'device_id': device_id, 'task_id': task_id, 'submitted': added}


def stress_train(device_ids: list, wait_timeout: int = 600) -> list:
    """压测训练：提交任务到队列，等待执行结果"""
    from app.services.task_queue_manager import get_task_queue_manager

    task_queue = get_task_queue_manager()
    logger.info(f"===== 训练压测开始: {len(device_ids)} 设备 =====")
    results = []
    expected = len(device_ids)

    for did in device_ids:
        r = submit_train_task(did)
        results.append(r)
        logger.info(f"  设备 {did}: {'已提交' if r['submitted'] else '提交失败'}  task_id={r.get('task_id', 'N/A')}")

    # 等待所有训练任务执行完成
    completed = 0
    failed = 0
    pending_count = expected
    deadline = time.time() + wait_timeout

    logger.info(f"等待训练任务完成（超时 {wait_timeout}s）...")
    while time.time() < deadline and pending_count > 0:
        pending_count = 0
        for r in results:
            if not r.get('submitted'):
                continue
            tid = r.get('task_id')
            status = task_queue.get_task_status(tid)
            if status:
                r['final_status'] = status.get('status', 'unknown')
                r['result'] = status.get('result')
                r['error'] = status.get('error')
                if status.get('status') in ('completed', 'failed'):
                    if status.get('status') == 'completed':
                        completed += 1
                    else:
                        failed += 1
                    continue
            pending_count += 1
        if pending_count > 0:
            time.sleep(2)

    # 超时未完成的
    for r in results:
        if not r.get('final_status'):
            r['final_status'] = 'timeout'
            failed += 1

    # 队列状态快照
    queue_snapshot = task_queue.get_queue_status()

    logger.info(f"===== 训练压测结束 =====")
    logger.info(f"  预期: {expected}  完成: {completed}  失败: {failed}  超时: {sum(1 for r in results if r.get('final_status') == 'timeout')}")
    logger.info(f"  队列等待: {queue_snapshot.get('queue_size', 0)}  活动训练: {queue_snapshot.get('active_train_count', 0)}")

    return results, expected, queue_snapshot


def collect_failures(predict_results: list, train_results: list, predict_expected: int,
                     predict_missing: int, train_expected: int, queue_snapshot: dict) -> list:
    """收集所有失败和异常记录"""
    failures = []

    # 预测缺失
    if predict_missing > 0:
        failures.append({
            'type': 'MISSING_PREDICTION',
            'message': f'预期 {predict_expected} 个预测任务，实际只返回 {len(predict_results)} 个，缺失 {predict_missing} 个'
        })

    # 预测失败
    for r in predict_results:
        if not r.get('success'):
            failures.append({
                'type': 'PREDICT_FAILED',
                'device_id': r.get('device_id'),
                'run': r.get('run'),
                'error': r.get('error', ''),
                'error_trace': r.get('error_trace', ''),
                'elapsed_s': r.get('elapsed_s'),
            })

    # 训练失败/超时
    for r in train_results:
        fs = r.get('final_status')
        if fs == 'timeout':
            failures.append({
                'type': 'TRAIN_TIMEOUT',
                'device_id': r.get('device_id'),
                'task_id': r.get('task_id'),
                'message': '训练任务超时未完成'
            })
        elif fs == 'failed':
            failures.append({
                'type': 'TRAIN_FAILED',
                'device_id': r.get('device_id'),
                'task_id': r.get('task_id'),
                'error': r.get('error', ''),
                'result': r.get('result'),
            })
        elif not r.get('submitted'):
            failures.append({
                'type': 'TRAIN_SUBMIT_FAILED',
                'device_id': r.get('device_id'),
                'message': '训练任务提交失败'
            })

    # 训练总量核对
    train_actual = sum(1 for r in train_results if r.get('final_status') == 'completed')
    if train_actual < train_expected:
        failures.append({
            'type': 'TRAIN_MISSING',
            'message': f'预期 {train_expected} 个训练完成，实际 {train_actual} 个'
        })

    return failures


def write_error_report(predict_results: list, train_results: list, predict_expected: int,
                       predict_missing: int, train_expected: int, queue_snapshot: dict,
                       total_elapsed: float):
    """生成错误报告文件"""
    os.makedirs(STRESS_RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = os.path.join(STRESS_RESULTS_DIR, f"errors_{timestamp}.txt")

    failures = collect_failures(predict_results, train_results, predict_expected,
                                predict_missing, train_expected, queue_snapshot)

    lines = []
    lines.append(f"压测错误报告 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)

    # 汇总
    predict_total = len(predict_results)
    predict_ok = sum(1 for r in predict_results if r.get('success'))
    predict_fail = predict_total - predict_ok
    train_total = sum(1 for r in train_results if r.get('submitted'))
    train_ok = sum(1 for r in train_results if r.get('final_status') == 'completed')
    train_fail = train_total - train_ok

    lines.append(f"")
    lines.append(f"--- 预测汇总 ---")
    lines.append(f"  预期: {predict_expected}  实际: {predict_total}  缺失: {predict_missing}")
    lines.append(f"  成功: {predict_ok}  失败: {predict_fail}")
    lines.append(f"")
    lines.append(f"--- 训练汇总 ---")
    lines.append(f"  预期: {train_expected}  提交: {train_total}  完成: {train_ok}  失败/超时: {train_fail}")
    lines.append(f"  队列等待: {queue_snapshot.get('queue_size', 0)}")
    lines.append(f"  活动训练: {queue_snapshot.get('active_train_count', 0)}")
    lines.append(f"  活动预测: {queue_snapshot.get('active_predict_count', 0)}")
    lines.append(f"")
    lines.append(f"--- 总耗时: {total_elapsed:.1f}s ---")

    # 失败详情
    if failures:
        lines.append(f"")
        lines.append(f"{'=' * 70}")
        lines.append(f"失败/异常详情（共 {len(failures)} 条）")
        lines.append(f"{'=' * 70}")

    for idx, f in enumerate(failures, 1):
        lines.append(f"")
        lines.append(f"[{idx}] {f['type']}")
        if f.get('device_id'):
            lines.append(f"  设备: {f['device_id']}")
        if f.get('run'):
            lines.append(f"  轮次: {f['run']}")
        if f.get('task_id'):
            lines.append(f"  任务ID: {f['task_id']}")
        if f.get('elapsed_s'):
            lines.append(f"  耗时: {f['elapsed_s']}s")
        lines.append(f"  信息: {f.get('message') or f.get('error', '')}")
        if f.get('error_trace'):
            lines.append(f"  完整Traceback:")
            for tb_line in f['error_trace'].strip().split('\n'):
                lines.append(f"    {tb_line}")

    lines.append(f"")
    lines.append(f"{'=' * 70}")
    lines.append(f"报告结束")

    content = '\n'.join(lines)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    logger.info(f"错误报告已生成: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="白天压测脚本")
    parser.add_argument("--predict-devices", type=str, default="2,3,4,5,6,7,8,9,10",
                        help="预测压测的设备ID列表，逗号分隔")
    parser.add_argument("--train-devices", type=str, default="2,3,4,5,6,7,8,9,10",
                        help="训练压测的设备ID列表，逗号分隔")
    parser.add_argument("--predict-rounds", type=int, default=10,
                        help="预测压测轮数（默认10轮）")
    parser.add_argument("--predict-timeout", type=int, default=120,
                        help="单次预测超时秒数（默认120）")
    parser.add_argument("--train-timeout", type=int, default=600,
                        help="训练等待超时秒数（默认600）")
    parser.add_argument("--predict-only", action="store_true", help="只测预测")
    parser.add_argument("--train-only", action="store_true", help="只测训练")
    parser.add_argument("--quick", action="store_true", help="快速模式（预测3轮，不跑训练）")
    parser.add_argument("--model-dir", type=str, default=None, help="模型目录")
    parser.add_argument("--no-report", action="store_true", help="不生成错误报告文件")
    args = parser.parse_args()

    # 快速模式
    if args.quick:
        if not args.predict_only and not args.train_only:
            args.predict_only = True
        if args.predict_rounds == 10:
            args.predict_rounds = 3
        logger.info("⚡ 快速模式: 预测 3 轮")

    predict_devices = [int(x.strip()) for x in args.predict_devices.split(",") if x.strip()] if args.predict_devices else []
    train_devices = [int(x.strip()) for x in args.train_devices.split(",") if x.strip()] if args.train_devices else []

    # 启动任务队列（如果没启动）
    from app.services.task_queue_manager import get_task_queue_manager
    tq = get_task_queue_manager()
    if not tq.is_running:
        tq.start()
        logger.info("已启动任务队列管理器")

    do_predict = not args.train_only
    do_train = not args.predict_only

    predict_results = []
    predict_expected = 0
    predict_missing = 0
    train_results = []
    train_expected = 0
    queue_snapshot = {}
    total_start = time.time()

    if do_predict and predict_devices:
        logger.info(f"预测设备: {predict_devices}")
        model_paths = find_latest_models(predict_devices, args.model_dir)
        if model_paths:
            predict_expected = len(model_paths) * args.predict_rounds
            predict_results, predict_expected, predict_missing = stress_predict(
                predict_devices, model_paths, args.predict_rounds, args.predict_timeout
            )
        else:
            logger.error("没有找到任何模型文件，无法执行预测压测")

    if do_train and train_devices:
        logger.info(f"训练设备: {train_devices}")
        train_expected = len(train_devices)
        train_results, train_expected, queue_snapshot = stress_train(
            train_devices, args.train_timeout
        )

    total_elapsed = time.time() - total_start

    # 生成错误报告
    if not args.no_report and (predict_results or train_results):
        write_error_report(
            predict_results, train_results,
            predict_expected, predict_missing,
            train_expected, queue_snapshot,
            total_elapsed
        )

    # 输出日志路径
    logger.info(f"查看详细日志: backend/logs/predictions_*.jsonl / scheduler_*.log")
    logger.info(f"错误报告目录: {STRESS_RESULTS_DIR}")


if __name__ == "__main__":
    main()
