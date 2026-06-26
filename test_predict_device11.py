# -*- coding: utf-8 -*-
"""
设备3 XGBoost预测器测试脚本
对比：偏差校正（use_correction）开关的效果 + 残差模型历史队列效果
"""

import os
import sys
import logging
import glob
import xgboost as xgb
import numpy as np

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, 'backend')
sys.path.insert(0, backend_dir)
sys.path.insert(0, current_dir)

try:
    from ml.models.predictor import get_predictor
except ImportError as e:
    print(f"❌ 导入预测器失败: {e}")
    sys.exit(1)


def find_latest_model(device_id=3, model_dir=None):
    """查找指定设备的最新模型文件（不预设特征名）"""
    if model_dir is None:
        possible_paths = [
            os.path.join(current_dir, 'backend', 'ml', 'models', 'saved_models'),
            os.path.join(current_dir, 'ml', 'models', 'saved_models'),
            os.path.join(backend_dir, 'ml', 'models', 'saved_models')
        ]
        for path in possible_paths:
            if os.path.exists(path):
                model_dir = path
                break
        else:
            print("❌ 未找到模型保存目录")
            return None

    pattern = f"xgboost_device_{device_id}_*.pkl"
    model_files = glob.glob(os.path.join(model_dir, pattern))
    if not model_files:
        print(f"❌ 未找到设备 {device_id} 的模型文件，模式: {pattern}")
        return None

    # 按修改时间排序，取最新的
    model_files.sort(key=os.path.getmtime, reverse=True)
    latest = model_files[0]
    print(f"✅ 找到最新模型: {latest}")
    return latest


def main():
    device_id = 3
    print("=" * 60)
    print("🚀 设备3 XGBoost预测器综合测试")
    print("=" * 60)

    predictor = get_predictor()
    if predictor is None:
        print("❌ 无法获取预测器实例")
        return

    model_path = find_latest_model(device_id)
    if not model_path:
        print("\n⚠️ 没有找到模型文件，请先训练设备3的模型。")
        return

    print(f"📂 加载模型: {model_path}")
    success = predictor.load_model(model_path)
    if not success:
        print("❌ 模型加载失败")
        return

    # 打印模型信息
    target_feature = predictor.active_target_feature or "未知"
    print(f"📊 模型信息:")
    print(f"   - 目标特征: {target_feature}")
    print(f"   - look_back: {predictor.active_look_back}")
    print(f"   - 特征数量: {len(predictor.feature_names) if predictor.feature_names else 0}")
    print(f"   - 残差模型: {'有' if predictor.residual_model else '无'}")
    print(f"   - 静态偏差 (avg_bias): {getattr(predictor, 'avg_bias', 0.0):.4f}")

    # ========== 第一部分：偏差校正（use_correction）对比 ==========
    print("\n" + "=" * 40)
    print("🔍 偏差校正（use_correction）对比")
    print("=" * 40)

    # 第一次预测：不启用校正，仅用于填充历史记录
    print("\n[第1次预测] 无校正 (use_correction=False) - 填充历史...")
    result1 = predictor.make_prediction(device_id=device_id, use_correction=False)

    if not result1.get('success'):
        print("❌ 第一次预测失败")
        return

    actual1 = result1.get('actual')
    pred1 = result1['prediction']
    print(f"  预测值: {pred1:.4f}, 实际值: {actual1}")

    # 第二次预测：启用校正
    print("\n[第2次预测] 有校正 (use_correction=True)")
    result2 = predictor.make_prediction(device_id=device_id, use_correction=True)

    if not result2.get('success'):
        print("❌ 第二次预测失败")
        return

    actual2 = result2.get('actual')
    pred2 = result2['prediction']
    corr_info = result2.get('correction_info', {})
    print(f"  预测值: {pred2:.4f}, 实际值: {actual2}")
    if corr_info.get('was_corrected'):
        print(f"  校正信息: {corr_info['reason']}, 因子={corr_info.get('correction_factor', 1.0):.3f}")
    else:
        print(f"  校正信息: 未校正（{corr_info.get('reason')}）")

    # 计算误差改善
    if actual1 is not None and actual2 is not None:
        error1 = abs(pred1 - actual1) / actual1 * 100
        error2 = abs(pred2 - actual2) / actual2 * 100
        print(f"  误差: 无校正 {error1:.2f}% → 有校正 {error2:.2f}%")

    # ========== 第二部分：残差修正模型（历史队列）对比 ==========
    print("\n" + "=" * 40)
    print("🔍 残差修正模型对比：有历史队列 vs 无历史队列")
    print("=" * 40)

    # 获取最新的预测数据（用于对比）
    prediction_data = predictor.prepare_prediction_data(device_id, predictor.active_target_feature,
                                                        predictor.active_look_back)
    if not prediction_data:
        print("❌ 无法准备预测数据")
        return

    X_seq = prediction_data['X_seq']
    y_actual = prediction_data.get('y_actual')

    # 1. 有历史队列的预测
    pred_with_history = predictor.predict(X_seq, device_id=device_id)
    pred_with_history_value = predictor._inverse_transform(float(pred_with_history[0]))

    # 2. 临时清空历史队列（模拟无历史情况）
    backup_actual = predictor.actual_history.get(device_id, [])
    backup_pred = predictor.prediction_history.get(device_id, [])

    predictor.actual_history[device_id] = []
    predictor.prediction_history[device_id] = []

    pred_without_history = predictor.predict(X_seq, device_id=device_id)
    pred_without_history_value = predictor._inverse_transform(float(pred_without_history[0]))

    # 恢复历史
    predictor.actual_history[device_id] = backup_actual
    predictor.prediction_history[device_id] = backup_pred

    # 3. 基础预测（无残差修正）
    base_pred = predictor.model.predict(xgb.DMatrix(predictor._flatten_X(X_seq), feature_names=predictor.feature_names))
    base_value = predictor._inverse_transform(float(base_pred[0]))

    print(f"基础预测值                : {base_value:.4f}")
    print(f"无历史队列的修正值        : {pred_without_history_value:.4f}")
    print(f"有历史队列的修正值        : {pred_with_history_value:.4f}")
    if y_actual is not None:
        print(f"实际值                    : {predictor.round_to_decimal(y_actual, predictor.active_target_feature)}")

    # 如果残差模型有滞后，打印最近的历史残差队列
    if predictor.residual_model is not None and predictor.residual_lags > 0:
        hist_residuals = predictor._get_residuals_history(device_id, predictor.residual_lags)
        print(f"最近历史残差队列          : {[f'{r:.4f}' for r in hist_residuals]}")

    print("=" * 60)


if __name__ == "__main__":
    main()