"""
压测脚本 — 白天测试：模拟多个设备同时预测+训练，检查是否会出bug
用法:
  cd backend
  python test/stress_test.py --predict-devices 2,3,4,5,6,7,8,9,10 --train-devices 2,3,4,5,6,7,8,9,10
  python test/stress_test.py --predict-only --predict-devices 2,3  # 只测预测
  python test/stress_test.py --train-only --train-devices 2,3       # 只测训练
"""
import os
import sys
import time
import glob
import json
import argparse
import threading
import logging
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


def run_single_prediction(predictor, device_id: int, model_path: str, target_feature: str, run_idx: int) -> dict:
    """执行单次预测（force_predict=True 跳过关机检查）"""
    start = time.time()
    try:
        predictor.load_model(model_path)
        result = predictor.make_prediction(
            device_id=device_id,
            target_feature=target_feature,
            force_predict=True,
            use_correction=False,
        )
        elapsed = time.time() - start
        pred_val = result.get('prediction')
        if isinstance(pred_val, list):
            preview = pred_val[:3] if len(pred_val) > 3 else pred_val
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
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            'device_id': device_id,
            'run': run_idx + 1,
            'success': False,
            'error': str(e)[:120],
            'elapsed_s': round(elapsed, 2),
        }


def stress_predict(device_ids: list, model_paths: dict, rounds: int = 10):
    """压测预测：多设备并发预测 rounds 轮"""
    from ml.models.predictor import get_predictor

    logger.info(f"===== 预测压测开始: {len(device_ids)} 设备 × {rounds} 轮 =====")
    all_results = []
    start_total = time.time()

    for r in range(rounds):
        round_start = time.time()
        threads = []

        def _do(did, mp, tf, ri):
            predictor = get_predictor()
            res = run_single_prediction(predictor, did, mp, tf, ri)
            all_results.append(res)

        for did, mp in model_paths.items():
            tf = get_device_target_feature(did)
            if not tf:
                logger.warning(f"跳过设备 {did}: 无目标特征")
                continue
            t = threading.Thread(target=_do, args=(did, mp, tf, r), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=120)

        elapsed_r = time.time() - round_start
        ok = sum(1 for r2 in all_results if r2.get('success') and r2['run'] == r + 1)
        fail = sum(1 for r2 in all_results if not r2.get('success') and r2['run'] == r + 1)
        logger.info(f"  第{r+1}轮: {ok} 成功, {fail} 失败, 耗时 {elapsed_r:.1f}s")

    total_elapsed = time.time() - start_total
    total_ok = sum(1 for r2 in all_results if r2.get('success'))
    total_fail = sum(1 for r2 in all_results if not r2.get('success'))
    avg_time = sum(r2.get('elapsed_s', 0) for r2 in all_results) / max(len(all_results), 1)

    logger.info(f"===== 预测压测结束 =====")
    logger.info(f"  总计: {total_ok} 成功, {total_fail} 失败, 总耗时 {total_elapsed:.1f}s, 平均每次 {avg_time:.1f}s")

    return all_results


def submit_train_task(device_id: int, config: dict = None):
    """提交训练任务到任务队列"""
    from app.services.task_queue_manager import get_task_queue_manager
    from app.services.scheduler import get_scheduler
    import uuid

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
    return added


def stress_train(device_ids: list):
    """压测训练：提交训练任务到队列"""
    logger.info(f"===== 训练压测开始: {len(device_ids)} 设备 =====")
    results = []
    for did in device_ids:
        success = submit_train_task(did)
        results.append({'device_id': did, 'submitted': success})
        logger.info(f"  设备 {did}: {'已提交' if success else '提交失败'}")

    ok = sum(1 for r in results if r['submitted'])
    logger.info(f"===== 训练压测结束: {ok}/{len(results)} 已提交 =====")
    return results


def main():
    parser = argparse.ArgumentParser(description="白天压测脚本")
    parser.add_argument("--predict-devices", type=str, default="2,3,4,5,6,7,8,9,10",
                        help="预测压测的设备ID列表，逗号分隔")
    parser.add_argument("--train-devices", type=str, default="2,3,4,5,6,7,8,9,10",
                        help="训练压测的设备ID列表，逗号分隔")
    parser.add_argument("--predict-rounds", type=int, default=10,
                        help="预测压测轮数（默认10轮）")
    parser.add_argument("--predict-only", action="store_true", help="只测预测")
    parser.add_argument("--train-only", action="store_true", help="只测训练")
    parser.add_argument("--model-dir", type=str, default=None, help="模型目录")
    args = parser.parse_args()

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

    if do_predict and predict_devices:
        logger.info(f"预测设备: {predict_devices}")
        model_paths = find_latest_models(predict_devices, args.model_dir)
        if not model_paths:
            logger.error("没有找到任何模型文件，无法执行预测压测")
            return
        stress_predict(predict_devices, model_paths, args.predict_rounds)

    if do_train and train_devices:
        logger.info(f"训练设备: {train_devices}")
        stress_train(train_devices)

    # 输出日志路径
    log_dir = os.path.join(backend_dir, 'logs')
    logger.info(f"查看详细日志: {log_dir}/predictions_*.jsonl / scheduler_*.log")


if __name__ == "__main__":
    main()
