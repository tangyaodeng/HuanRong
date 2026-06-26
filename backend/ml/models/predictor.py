"""
XGBoost模型预测器 - 重构版，动态数据库连接
backend/ml/models/predictor.py
"""
import pickle
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta
import time
from sqlalchemy import create_engine, text
import xgboost as xgb
import threading
import schedule
import os
import json
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class XGBoostPredictor:
    """XGBoost模型预测器 - 动态数据库连接版，支持残差修正"""

    def __init__(self):
        self.model = None
        self.residual_model = None   # 新增：残差修正模型
        self.model_info = {}
        self.is_running = False
        self.prediction_thread = None
        self.predictions_history = []
        self.debug_residual = True  # 默认为关闭，需要时外部开启
        self.output_dim = 1  # 默认为单输出

        # 动态配置（从模型文件中加载）
        self.active_device_id = None
        self.active_target_feature = None
        self.active_look_back = None
        self.active_target_feature_id = None
        self.active_model_version_id = None
        self.active_training_config = None

        self.residual_lags = 0
        self.residual_mean = 0.0
        self.residual_std = 1.0
        self.use_standardize = False
        self.best_alpha = 1.0  # 残差修正收缩系数，默认不收缩

        # 预测值小数位数配置
        self.decimal_places = {
            'default': 1,  # 默认保留1位小数
            'power': 1,    # 功率：1位小数
            'temperature': 1,  # 温度：1位小数
            'pressure': 1,  # 压力：1位小数
            'humidity': 1,  # 湿度：1位小数
            'flow': 2,     # 流量：2位小数（可能需要更精确）
            'voltage': 2,  # 电压：2位小数
            'current': 2,  # 电流：2位小数
        }

        # 数据库连接缓存
        self.connection_cache = {}

        # 现有初始化代码...
        self.correction_history = {}  # 存储历史校正记录
        self.actual_history = {}  # 存储历史实际值
        self.prediction_history = {}  # 存储历史预测值
        self.correction_config = {
            'threshold_percentage': 3.0,  # 偏差阈值百分比
            'min_samples_for_correction': 5,  # 最小样本数才进行校正
            'max_history_size': 100,  # 最大历史记录数
            'correction_method': 'moving_average',  # 校正方法：moving_average, linear_regression, weighted_average
            'correction_aggressiveness': 0.7,  # 校正强度（0-1）
        }
        self.physical_constraints = {
            'power': {'min': 0, 'max': 300},
            'temperature': {'min': -20, 'max': 50},
            'pressure': {'min': 0, 'max': 1000},
            'humidity': {'min': 0, 'max': 100},
            'default': {'min': 0, 'max': 1000}
        }
        # 导入数据库模型
        try:
            from app import models
            self.models = models
        except ImportError:
            self.models = None

    @staticmethod
    def _write_prediction_log(entry: dict) -> None:
        """将预测结果追加写入当日 JSONL 日志文件"""
        try:
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            # 清理超过7天的旧预测日志
            try:
                from app.utils.log_cleanup import cleanup_old_logs
                cleanup_old_logs(log_dir, "predictions_", keep_days=7)
            except Exception:
                pass
            log_file = os.path.join(log_dir, f"predictions_{datetime.now().strftime('%Y-%m-%d')}.jsonl")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')
        except Exception as e:
            logger.warning(f"写入预测日志文件失败: {e}")

    def _log_prediction_result(self, result: dict, start_time: float) -> None:
        """根据 make_prediction 返回的 result 构造并写入 JSONL 日志"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'device_id': result.get('device_id'),
            'target_feature': result.get('target_feature'),
            'success': result.get('success', False),
            'prediction': result.get('prediction'),
            'actual': result.get('actual'),
            'device_status': result.get('device_status', 'unknown'),
            'execution_time_s': round(time.time() - start_time, 3),
            'save_success': result.get('save_success'),
            'error': result.get('error'),
            'correction_applied': (result.get('correction_info') or {}).get('was_corrected', False),
            'skip_reason': result.get('skip_reason'),
        }
        self._write_prediction_log(entry)

    def round_to_decimal(self, value: float, feature_name: str) -> float:
        """根据特征类型四舍五入到指定小数位数"""
        feature_type = self.detect_feature_type(feature_name)
        decimal_places = self.decimal_places.get(feature_type, self.decimal_places['default'])

        # 特殊处理：对于小于1的值，保持更多精度
        if abs(value) < 1.0:
            decimal_places = min(3, decimal_places + 1)

        # 四舍五入
        rounded_value = round(value, decimal_places)

        # 对于接近整数的值，使用整数表示
        if abs(rounded_value - int(rounded_value)) < 0.001:
            rounded_value = int(rounded_value)

        return rounded_value

    def detect_feature_type(self, feature_name: str) -> str:
        """根据特征名称自动识别特征类型"""
        feature_lower = feature_name.lower()

        if any(word in feature_lower for word in ['power', '功率', 'pwr', '能耗', 'watt', 'kw']):
            return 'power'
        elif any(word in feature_lower for word in ['temp', '温度', 'temperature']):
            return 'temperature'
        elif any(word in feature_lower for word in ['pressure', '压力', '压强']):
            return 'pressure'
        elif any(word in feature_lower for word in ['humidity', '湿度', 'humid']):
            return 'humidity'
        elif any(word in feature_lower for word in ['flow', '流量', '流速']):
            return 'flow'
        elif any(word in feature_lower for word in ['voltage', '电压', 'volt']):
            return 'voltage'
        elif any(word in feature_lower for word in ['current', '电流', 'ampere']):
            return 'current'
        else:
            return 'default'

    def apply_physical_constraints(self, value: float, feature_name: str) -> float:
        """应用物理约束"""
        feature_type = self.detect_feature_type(feature_name)
        constraints = self.physical_constraints.get(feature_type, self.physical_constraints['default'])

        # 应用约束
        constrained_value = max(constraints['min'], min(value, constraints['max']))

        # 记录约束应用情况
        if constrained_value != value:
            logger.info(f"物理约束: {feature_name}({feature_type}) {value:.2f} -> {constrained_value:.2f} "
                        f"范围[{constraints['min']}, {constraints['max']}]")

        # 四舍五入到指定小数位数
        rounded_value = self.round_to_decimal(constrained_value, feature_name)

        if rounded_value != constrained_value:
            logger.debug(f"四舍五入: {constrained_value} -> {rounded_value}")

        return rounded_value

    def update_prediction_history(self, device_id: int, base_prediction_value: float,
                                  actual_value: Optional[float] = None) -> None:
        """更新历史记录：存储基础预测值（未校正）和实际值"""
        if device_id not in self.prediction_history:
            self.prediction_history[device_id] = []
        if device_id not in self.actual_history:
            self.actual_history[device_id] = []

        self.prediction_history[device_id].append({
            'timestamp': datetime.now(),
            'value': base_prediction_value,
            'value_rounded': self.round_to_decimal(base_prediction_value, self.active_target_feature or 'default')
        })

        if actual_value is not None:
            self.actual_history[device_id].append({
                'timestamp': datetime.now(),
                'value': actual_value,
                'value_rounded': self.round_to_decimal(actual_value, self.active_target_feature or 'default')
            })

        # 保持最大长度
        max_size = self.correction_config['max_history_size']
        self.prediction_history[device_id] = self.prediction_history[device_id][-max_size:]
        if actual_value is not None:
            self.actual_history[device_id] = self.actual_history[device_id][-max_size:]

    def calculate_deviation_percentage(self, predicted: float, actual: float) -> float:
        """计算偏差百分比"""
        if actual == 0:
            return float('inf') if predicted != 0 else 0.0
        return abs((predicted - actual) / actual) * 100.0

    def calculate_moving_average_correction(self, device_id: int, window_size: int = 10) -> float:
        """计算移动平均校正因子"""
        if device_id not in self.actual_history or device_id not in self.prediction_history:
            return 1.0

        actuals = [item['value'] for item in self.actual_history[device_id]]
        predictions = [item['value'] for item in self.prediction_history[device_id]]

        if len(actuals) < window_size or len(predictions) < window_size:
            return 1.0

        # 计算最近窗口期的平均偏差
        recent_actuals = actuals[-window_size:]
        recent_predictions = predictions[-window_size:]

        deviations = []
        for i in range(min(len(recent_actuals), len(recent_predictions))):
            if recent_actuals[i] != 0:
                deviation = (recent_actuals[i] - recent_predictions[i]) / recent_actuals[i]
                deviations.append(deviation)

        if not deviations:
            return 1.0

        avg_deviation = np.mean(deviations)
        correction_factor = 1.0 + avg_deviation * self.correction_config['correction_aggressiveness']

        # 限制校正因子范围
        correction_factor = max(0.5, min(correction_factor, 1.5))

        return correction_factor

    def calculate_linear_regression_correction(self, device_id: int) -> float:
        """计算线性回归校正因子"""
        if device_id not in self.actual_history or device_id not in self.prediction_history:
            return 1.0

        actuals = [item['value'] for item in self.actual_history[device_id]]
        predictions = [item['value'] for item in self.prediction_history[device_id]]

        if len(actuals) < 10 or len(predictions) < 10:
            return 1.0

        # 使用最近的数据进行线性回归
        X = np.array(predictions[-20:]).reshape(-1, 1)
        y = np.array(actuals[-20:])

        from sklearn.linear_model import LinearRegression
        model = LinearRegression()
        model.fit(X, y)

        # 计算平均预测值的校正因子
        avg_pred = np.mean(X)
        corrected_avg = model.predict([[avg_pred]])[0]

        if avg_pred != 0:
            correction_factor = corrected_avg / avg_pred
        else:
            correction_factor = 1.0

        # 限制校正因子范围
        correction_factor = max(0.7, min(correction_factor, 1.3))

        return correction_factor

    def calculate_weighted_average_correction(self, device_id: int) -> float:
        """计算加权平均校正因子（最近的数据权重更高）"""
        if device_id not in self.actual_history or device_id not in self.prediction_history:
            return 1.0

        actuals = [item['value'] for item in self.actual_history[device_id]]
        predictions = [item['value'] for item in self.prediction_history[device_id]]

        if len(actuals) < 5 or len(predictions) < 5:
            return 1.0

        n = min(len(actuals), len(predictions))
        weights = np.exp(np.linspace(0, 1, n))  # 指数权重，最近的权重最大

        deviations = []
        for i in range(n):
            if actuals[i] != 0:
                deviation = (actuals[i] - predictions[i]) / actuals[i]
                deviations.append(deviation * weights[i])

        if not deviations:
            return 1.0

        weighted_avg_deviation = np.sum(deviations) / np.sum(weights[:len(deviations)])
        correction_factor = 1.0 + weighted_avg_deviation * self.correction_config['correction_aggressiveness']

        # 限制校正因子范围
        correction_factor = max(0.6, min(correction_factor, 1.4))

        return correction_factor

    def apply_safety_correction(self, device_id: int, predicted_value: float,
                                target_feature: str) -> float:
        """应用安全校正机制"""
        if device_id not in self.actual_history or len(self.actual_history[device_id]) < 3:
            return predicted_value

        # 获取历史实际值的统计
        recent_actuals = [item['value'] for item in self.actual_history[device_id][-10:]]

        if not recent_actuals:
            return predicted_value

        avg_actual = np.mean(recent_actuals)
        std_actual = np.std(recent_actuals) if len(recent_actuals) > 1 else 0

        # 检查预测值是否在合理范围内
        if std_actual > 0:
            # 计算Z分数
            z_score = abs(predicted_value - avg_actual) / std_actual

            # 如果Z分数过高（异常值），使用历史平均值
            if z_score > 3.0:
                logger.warning(f"预测值异常 (Z-score={z_score:.2f})，使用历史平均值替代")
                corrected_value = avg_actual

                # 添加随机噪声避免完全一致
                noise = np.random.normal(0, std_actual * 0.1)
                corrected_value += noise

                # 应用物理约束和四舍五入
                return self.apply_physical_constraints(corrected_value, target_feature)

        return predicted_value

    def apply_bias_correction(self, device_id: int, predicted_value: float,
                              target_feature: str, device_status: str = 'on') -> Dict:
        """
        应用智能偏差校正 - 针对PLC数据滞后性的改进版本
        返回: {'corrected_value': float, 'correction_factor': float, 'was_corrected': bool}
        """
        original_prediction = predicted_value

        # 如果设备关机，直接返回0
        if device_status == 'off':
            return {
                'corrected_value': 0.0,
                'correction_factor': 0.0,
                'was_corrected': True,
                'reason': 'device_off'
            }

        # 获取最近的实际值
        if device_id not in self.actual_history or len(self.actual_history[device_id]) == 0:
            return {
                'corrected_value': predicted_value,
                'correction_factor': 1.0,
                'was_corrected': False,
                'reason': 'no_actual_history'
            }

        # 计算偏差百分比
        latest_actual = self.actual_history[device_id][-1]['value']
        deviation_pct = self.calculate_deviation_percentage(predicted_value, latest_actual)

        # 如果偏差小于阈值，不进行校正
        if deviation_pct <= self.correction_config['threshold_percentage']:
            return {
                'corrected_value': predicted_value,
                'correction_factor': 1.0,
                'was_corrected': False,
                'reason': f'deviation_within_threshold_{deviation_pct:.1f}%'
            }

        logger.info(f"🚨 偏差超过阈值: 预测值={predicted_value:.2f}, 实际值={latest_actual:.2f}, "
                    f"偏差={deviation_pct:.1f}% > {self.correction_config['threshold_percentage']}%")

        # 【关键修复】优先使用最近的实际值进行校正
        # 首先尝试获取前15分钟的历史实际值
        recent_actuals = self._get_recent_actual_values(device_id, minutes_back=15)

        # 如果没有足够的历史数据，但当前实际值可用，使用当前实际值
        if len(recent_actuals) == 0 and latest_actual is not None:
            # 使用当前实际值直接替换预测值
            corrected_value = latest_actual
            correction_factor = latest_actual / predicted_value if predicted_value != 0 else 1.0

            logger.info(f"📊 使用当前实际值直接校正: {predicted_value:.2f} → {corrected_value:.2f}")
            logger.info(f"  校正因子: {correction_factor:.3f}")

            # 应用物理约束和四舍五入
            corrected_value = self.apply_physical_constraints(corrected_value, target_feature)

            return {
                'corrected_value': corrected_value,
                'correction_factor': correction_factor,
                'was_corrected': True,
                'reason': f'use_current_actual_directly_deviation_{deviation_pct:.1f}%'
            }

        if len(recent_actuals) >= 1:  # 【修改】只要有1个数据点就使用
            # 使用前15分钟实际值的平均值
            recent_avg = np.mean(recent_actuals)

            # 计算数据稳定性（标准差）
            if len(recent_actuals) >= 2:
                std_dev = np.std(recent_actuals)
                stability = 1.0 - min(std_dev / recent_avg, 1.0) if recent_avg > 0 else 1.0
                logger.info(f"📊 数据稳定性: {stability:.2f}, 标准差: {std_dev:.2f}")
            else:
                stability = 1.0

            # 根据稳定性调整校正值
            if stability > 0.9:  # 数据非常稳定，直接使用平均值
                adjusted_value = recent_avg
                correction_type = "稳定平均值"
            else:
                # 计算移动趋势
                if len(recent_actuals) >= 3:
                    trend = self._calculate_trend(recent_actuals[-3:])  # 使用最近3个点计算趋势

                    # 根据趋势调整校正值
                    if abs(trend) > 0.05:  # 趋势明显
                        if trend > 0:
                            adjusted_value = recent_avg * (1 + min(trend * 0.3, 0.1))
                            correction_type = f"上升趋势调整(+{trend:.1%})"
                        else:
                            adjusted_value = recent_avg * (1 - min(abs(trend) * 0.3, 0.1))
                            correction_type = f"下降趋势调整(-{abs(trend):.1%})"
                    else:
                        adjusted_value = recent_avg
                        correction_type = "稳定平均值"
                else:
                    adjusted_value = recent_avg
                    correction_type = "简单平均值"

            # 如果平均值与实际值的偏差很大，直接使用平均值
            avg_actual_diff = abs(recent_avg - latest_actual) / latest_actual if latest_actual != 0 else 0
            if avg_actual_diff < 0.05:  # 平均值与当前值偏差小于5%
                # 直接使用平均值
                corrected_value = recent_avg
                correction_factor = recent_avg / predicted_value if predicted_value != 0 else 1.0

                logger.info(f"📊 智能校正: 使用前{len(recent_actuals)}个实际值的{correction_type}")
                logger.info(f"  - 前15分钟实际值: {recent_actuals}")
                logger.info(f"  - 平均值: {recent_avg:.2f} (与当前值偏差: {avg_actual_diff:.1%})")
                logger.info(f"  - 校正后值: {corrected_value:.2f}")
                logger.info(f"  - 校正因子: {correction_factor:.3f}")

                reason = f"smart_correction_{correction_type}_deviation_{deviation_pct:.1f}%"
            else:
                # 平均值与当前值差异较大，使用加权平均
                weight = 0.7  # 给平均值70%的权重
                corrected_value = recent_avg * weight + latest_actual * (1 - weight)
                correction_factor = corrected_value / predicted_value if predicted_value != 0 else 1.0

                logger.info(
                    f"📊 加权校正: 平均值{recent_avg:.2f} × {weight:.0%} + 当前值{latest_actual:.2f} × {1 - weight:.0%}")
                logger.info(f"  - 校正后值: {corrected_value:.2f}")
                logger.info(f"  - 校正因子: {correction_factor:.3f}")

                reason = f"weighted_correction_deviation_{deviation_pct:.1f}%_avg_diff_{avg_actual_diff:.1%}"

        else:
            # 没有历史数据，使用当前实际值直接校正
            if latest_actual > 0 and predicted_value > 0:
                correction_factor = latest_actual / predicted_value
                corrected_value = latest_actual

                logger.info(f"📊 直接校正: 使用当前实际值 {latest_actual:.2f}")
                logger.info(f"  - 校正因子: {correction_factor:.3f}")
                reason = f"direct_correction_deviation_{deviation_pct:.1f}%_no_history"
            else:
                # 无法计算比例，使用移动平均校正
                correction_factor = self.calculate_moving_average_correction(device_id, window_size=5)
                corrected_value = predicted_value * correction_factor

                logger.info(f"📊 移动平均校正: 因子={correction_factor:.3f}")
                reason = f"moving_average_correction_deviation_{deviation_pct:.1f}%"

        # 应用安全校正
        corrected_value = self.apply_safety_correction(device_id, corrected_value, target_feature)

        # 应用物理约束和四舍五入
        corrected_value = self.apply_physical_constraints(corrected_value, target_feature)

        # 记录校正历史
        if device_id not in self.correction_history:
            self.correction_history[device_id] = []

        self.correction_history[device_id].append({
            'timestamp': datetime.now(),
            'original': predicted_value,
            'corrected': corrected_value,
            'actual': latest_actual,
            'correction_factor': correction_factor,
            'deviation_pct_before': deviation_pct,
            'deviation_pct_after': self.calculate_deviation_percentage(corrected_value, latest_actual),
            'correction_type': reason
        })

        # 保持历史记录大小
        max_size = self.correction_config['max_history_size']
        self.correction_history[device_id] = self.correction_history[device_id][-max_size:]

        logger.info(f"✅ 校正完成: 原始={original_prediction:.2f} → 校正={corrected_value:.2f}, "
                    f"偏差从{deviation_pct:.1f}% → {self.calculate_deviation_percentage(corrected_value, latest_actual):.1f}%")

        return {
            'corrected_value': corrected_value,
            'correction_factor': correction_factor,
            'was_corrected': True,
            'reason': reason
        }

    def _get_recent_actual_values(self, device_id: int, minutes_back: int = 15) -> List[float]:
        """获取最近指定分钟内的实际值"""
        if device_id not in self.actual_history:
            return []

        # 计算截止时间
        cutoff_time = datetime.now() - timedelta(minutes=minutes_back)
        recent_values = []

        # 从最新到最旧遍历，找到最近15分钟的数据
        for record in self.actual_history[device_id][::-1]:  # 从最新开始遍历
            if record['timestamp'] >= cutoff_time:
                recent_values.append(record['value'])
            else:
                break

        # 返回按时间顺序排列的值
        return recent_values[::-1]  # 反转回时间顺序

    def _get_all_recent_actuals(self, device_id: int) -> List[float]:
        """获取所有可用的实际值"""
        if device_id not in self.actual_history:
            return []

        # 返回所有的实际值
        return [record['value'] for record in self.actual_history[device_id]]

    def _calculate_trend(self, values: List[float]) -> float:
        """计算数值序列的趋势（线性回归斜率）"""
        if len(values) < 2:
            return 0.0

        try:
            # 使用简单线性回归计算趋势
            x = np.arange(len(values))
            y = np.array(values)

            # 计算斜率和截距
            A = np.vstack([x, np.ones(len(x))]).T
            slope, _ = np.linalg.lstsq(A, y, rcond=None)[0]

            # 标准化趋势（相对于平均值）
            if np.mean(y) != 0:
                normalized_trend = slope / np.mean(y)
            else:
                normalized_trend = 0.0

            return normalized_trend
        except Exception as e:
            logger.warning(f"趋势计算失败: {e}")
            return 0.0

    def update_correction_threshold(self, device_id: int, adaptive: bool = True):
        """动态调整校正阈值"""
        if device_id not in self.correction_history or len(self.correction_history[device_id]) < 10:
            return

        if adaptive:
            # 计算历史校正效果
            corrections = self.correction_history[device_id][-20:]  # 最近20次校正

            deviations_before = [c['deviation_pct_before'] for c in corrections]
            deviations_after = [c['deviation_pct_after'] for c in corrections]

            avg_before = np.mean(deviations_before)
            avg_after = np.mean(deviations_after)

            # 如果校正后平均偏差仍高于目标，降低阈值
            target_threshold = 3.0
            if avg_after > target_threshold * 1.5:
                new_threshold = max(1.0, target_threshold * 0.8)
                self.correction_config['threshold_percentage'] = new_threshold
                logger.info(f"📉 动态调整校正阈值: {target_threshold}% → {new_threshold:.1f}%")

            # 如果校正效果很好，可以适当放宽阈值
            elif avg_after < target_threshold * 0.5:
                new_threshold = min(5.0, target_threshold * 1.2)
                self.correction_config['threshold_percentage'] = new_threshold
                logger.info(f"📈 动态放宽校正阈值: {target_threshold}% → {new_threshold:.1f}%")

    def get_correction_statistics(self, device_id: int) -> Dict:
        """获取校正统计信息"""
        if device_id not in self.correction_history or not self.correction_history[device_id]:
            return {}

        corrections = self.correction_history[device_id]

        # 计算校正前后的平均偏差
        deviations_before = [c['deviation_pct_before'] for c in corrections]
        deviations_after = [c['deviation_pct_after'] for c in corrections]

        # 计算校正效果
        if deviations_before and deviations_after:
            avg_before = np.mean(deviations_before)
            avg_after = np.mean(deviations_after)
            improvement_pct = (avg_before - avg_after) / avg_before * 100 if avg_before > 0 else 0

            return {
                'total_corrections': len(corrections),
                'avg_deviation_before_correction': f"{avg_before:.2f}%",
                'avg_deviation_after_correction': f"{avg_after:.2f}%",
                'improvement': f"{improvement_pct:.1f}%",
                'recent_corrections': corrections[-5:]  # 最近5次校正
            }

        return {}

    def _create_lag_features_all(self, df: pd.DataFrame, lag_periods: List[int]) -> pd.DataFrame:
        """为所有数值特征创建滞后特征"""
        df_lagged = df.copy()
        for col in df.columns:
            # 排除时间特征等非数值列（根据实际情况调整）
            if col in ['hour', 'day_of_week', 'is_weekend', 'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
                       'running_duration']:
                continue
            for lag in lag_periods:
                df_lagged[f'{col}_lag_{lag}'] = df[col].shift(lag)
        return df_lagged.ffill().bfill()

    def _create_rolling_features_all(self, df: pd.DataFrame, windows: List[int], stats: List[str]) -> pd.DataFrame:
        """为所有数值特征创建滚动特征"""
        df_rolling = df.copy()
        for col in df.columns:
            if col in ['hour', 'day_of_week', 'is_weekend', 'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
                       'running_duration']:
                continue
            for window in windows:
                if 'mean' in stats:
                    df_rolling[f'{col}_roll_mean_{window}'] = df[col].rolling(window).mean()
                if 'std' in stats:
                    df_rolling[f'{col}_roll_std_{window}'] = df[col].rolling(window).std()
        return df_rolling.ffill().bfill()

    def _recursive_forecast(self, X_seq, device_id, target_feature, look_back, prediction_data, steps, start_time):
        """递归预测 steps 步，返回多步预测结果（格式与多输出分支一致）"""
        # 处理输入维度：如果是2D，转换为3D (1, 1, n_features)，并强制 look_back=1
        if X_seq.ndim == 2:
            X_seq = X_seq.reshape(1, 1, -1)
            look_back = 1
            logger.info(f"递归预测：输入为2D，已重置 look_back=1，新形状 {X_seq.shape}")

        recursive_predictions = []
        current_X = X_seq.copy()  # shape (1, look_back, n_features)
        feature_columns = prediction_data['feature_columns']

        # ========== 1. 用最新实际值更新输入序列中的目标特征（或滞后特征） ==========
        y_actual = prediction_data.get('y_actual')
        if y_actual is not None:
            lag_feature = f"{target_feature}_lag_1"
            target_idx = None
            if lag_feature in feature_columns:
                target_idx = feature_columns.index(lag_feature)
                logger.info(f"找到滞后特征 {lag_feature}，将用实际值 {y_actual:.2f} 更新其最后一时间步的值")
            elif target_feature in feature_columns:
                target_idx = feature_columns.index(target_feature)
                logger.info(f"找到目标特征 {target_feature}，将用实际值 {y_actual:.2f} 更新其最后一时间步的值")
            else:
                logger.warning(
                    f"未在特征列中找到 {target_feature} 或其滞后特征，跳过实际值更新。特征列前10个: {feature_columns[:10]}")
            if target_idx is not None:
                current_X[0, -1, target_idx] = y_actual
                logger.info(f"已用实际值 {y_actual:.2f} 更新索引 {target_idx} 的特征")
        # ========================================================================

        # 识别时间特征索引（递归时需要更新时间）
        time_feature_names = ['hour', 'day_of_week', 'is_weekend',
                              'hour_sin', 'hour_cos', 'day_sin', 'day_cos']
        time_indices = [feature_columns.index(name) for name in time_feature_names if name in feature_columns]
        current_timestamp = prediction_data['timestamp']

        # 获取第一个预测值
        y_pred_scaled = self.predict(current_X, device_id=device_id)
        y_pred_value = self._inverse_transform(float(y_pred_scaled[0]))
        original_first_pred = y_pred_value  # 保存原始值，用于计算等比因子

        # ========== 2. 激进首步校正 ==========
        correction_factor = 1.0
        if y_actual is not None and y_actual != 0:
            deviation_pct = abs((y_pred_value - y_actual) / y_actual) * 100
            threshold = self.correction_config.get('threshold_percentage', 3.0)
            if deviation_pct > threshold:
                # 使用完全实际值替换（最激进）
                corrected_value = y_actual
                # 可选混合模式： corrected_value = y_actual * aggressiveness + y_pred_value * (1 - aggressiveness)
                logger.info(
                    f"递归预测首步实时校正: 原始={y_pred_value:.2f}, 实际={y_actual:.2f}, 偏差率={deviation_pct:.1f}%, 校正后={corrected_value:.2f} (完全替换)")
                y_pred_value = corrected_value
                # 计算等比因子（校正后 / 校正前）
                correction_factor = y_pred_value / original_first_pred
            else:
                logger.info(f"递归预测首步偏差在阈值内({deviation_pct:.1f}%)，不校正")
        else:
            logger.info("无最新实际值，跳过首步实时校正")

        recursive_predictions.append(y_pred_value)

        # ========== 3. 后续步长等比缩放 ==========
        for step in range(1, steps):
            # 更新时间戳（加1小时，根据采样频率调整）
            next_timestamp = current_timestamp + timedelta(hours=1)
            current_timestamp = next_timestamp

            # 生成新的时间步特征（复制最后一行，仅更新时间特征）
            last_row = current_X[0, -1, :].copy()
            new_row = last_row.copy()
            for idx in time_indices:
                col = feature_columns[idx]
                if col == 'hour':
                    new_row[idx] = next_timestamp.hour
                elif col == 'day_of_week':
                    new_row[idx] = next_timestamp.weekday()
                elif col == 'is_weekend':
                    new_row[idx] = 1 if next_timestamp.weekday() >= 5 else 0
                elif col == 'hour_sin':
                    new_row[idx] = np.sin(2 * np.pi * next_timestamp.hour / 24)
                elif col == 'hour_cos':
                    new_row[idx] = np.cos(2 * np.pi * next_timestamp.hour / 24)
                elif col == 'day_sin':
                    new_row[idx] = np.sin(2 * np.pi * next_timestamp.weekday() / 7)
                elif col == 'day_cos':
                    new_row[idx] = np.cos(2 * np.pi * next_timestamp.weekday() / 7)

            # 更新输入序列
            if look_back > 1:
                current_X = np.roll(current_X, -1, axis=1)
                current_X[0, -1, :] = new_row
            else:
                current_X[0, 0, :] = new_row

            # 下一步预测
            next_pred_scaled = self.predict(current_X, device_id=device_id)
            next_pred_value = self._inverse_transform(float(next_pred_scaled[0]))

            # 应用等比缩放因子（若首步已校正）
            if correction_factor != 1.0:
                next_pred_value = next_pred_value * correction_factor
                logger.debug(f"第{step + 1}步预测缩放: 原始={next_pred_value:.2f}, 缩放后={next_pred_value:.2f}")

            recursive_predictions.append(next_pred_value)

        # 保存多步预测结果
        target_mapping = prediction_data.get('target_mapping')
        forecast_start = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        save_success = self._save_multistep_predictions(
            device_id=device_id,
            target_feature=target_feature,
            target_mapping=target_mapping,
            prediction_values=np.array(recursive_predictions),
            forecast_start_time=forecast_start,
            step_minutes=60,
            actual_values=None,
            device_status='on'
        )

        return {
            'success': True,
            'device_id': device_id,
            'target_feature': target_feature,
            'target_feature_id': self.active_target_feature_id,
            'prediction': recursive_predictions,
            'prediction_scaled': None,
            'actual': None,
            'prediction_time': forecast_start.isoformat(),
            'execution_time_seconds': time.time() - start_time,
            'save_success': save_success,
            'device_status': 'on',
            'correction_info': {
                'was_corrected': (y_actual is not None and y_actual != 0 and deviation_pct > self.correction_config.get(
                    'threshold_percentage', 3.0)) if 'y_actual' in locals() else False,
                'reason': 'recursive_forecast_with_aggressive_correction'
            },
            'data_info': {
                'look_back': look_back,
                'feature_count': len(feature_columns),
                'sequence_shape': current_X.shape,
                'output_dim': steps
            }
        }
    def enhanced_make_prediction(
            self,
            device_id: int = None,
            target_feature: str = None,
            look_back: int = None
    ) -> Dict:
        """增强版预测方法 - 包含偏差校正机制"""
        try:
            start_time = time.time()

            # 使用已保存的设备ID（如果未提供）
            if device_id is None and self.active_device_id:
                device_id = self.active_device_id
            elif device_id is None:
                logger.error("❌ 未提供设备ID")
                return {
                    'success': False,
                    'error': '未提供设备ID',
                    'device_id': None
                }

            # 优先使用已保存的配置
            if target_feature is None and self.active_target_feature:
                target_feature = self.active_target_feature

            if look_back is None and self.active_look_back:
                look_back = self.active_look_back
            elif look_back is None:
                look_back = 24

            logger.info(f"🚀 开始执行增强预测 - 设备: {device_id}, 特征: {target_feature}")

            # 检查模型是否已加载
            if self.model is None:
                logger.error("❌ 模型未加载")
                return {
                    'success': False,
                    'error': '模型未加载',
                    'device_id': device_id
                }

            # 准备预测数据（包含开关机状态检查）
            prediction_data = self.prepare_prediction_data(device_id, target_feature, look_back)
            if not prediction_data:
                logger.warning("⚠️ 无法准备预测数据")
                result = {
                    'success': True,
                    'device_id': device_id,
                    'target_feature': target_feature or "PointValue",
                    'prediction': 0.0,
                    'actual': None,
                    'prediction_time': (datetime.now() + timedelta(minutes=5)).isoformat(),
                    'execution_time_seconds': time.time() - start_time,
                    'save_success': False,
                    'device_status': 'unknown',
                    'correction_info': {
                        'was_corrected': False,
                        'reason': 'no_prediction_data'
                    }
                }

            # 检查设备是否关机
            if not prediction_data.get('is_device_on', True):
                logger.info(f"⚡ 设备 {device_id} 处于关机状态，直接预测为 0")
                target_mapping = prediction_data.get('target_mapping')
                output_dim = getattr(self, 'output_dim', 1)
                if output_dim > 1:
                    # 多输出：生成全零数组
                    prediction_array = np.zeros(output_dim)
                    # 保存多步预测结果
                    forecast_start = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                    save_success = self._save_multistep_predictions(
                        device_id=device_id,
                        target_feature=prediction_data.get('target_feature', target_feature),
                        target_mapping=target_mapping,
                        prediction_values=prediction_array,
                        forecast_start_time=forecast_start,
                        step_minutes=60,
                        actual_values=None,
                        device_status='off'
                    )
                    execution_time = time.time() - start_time
                    result_off = {
                        'success': True,
                        'device_id': device_id,
                        'target_feature': prediction_data.get('target_feature', target_feature),
                        'target_feature_id': self.active_target_feature_id,
                        'prediction': prediction_array.tolist(),
                        'prediction_scaled': prediction_array.tolist(),
                        'actual': None,
                        'prediction_time': forecast_start.isoformat(),
                        'execution_time_seconds': execution_time,
                        'save_success': save_success,
                        'device_status': 'off',
                        'skip_reason': 'device_off',
                        'correction_info': {'was_corrected': True, 'reason': 'device_off'}
                    }
                    self._log_prediction_result(result_off, start_time)
                    return result_off
                else:
                    # 单输出：保持原有逻辑
                    prediction_time = datetime.now() + timedelta(minutes=5)
                    save_success = self.save_prediction_to_mysql(
                        device_id=device_id,
                        target_feature=prediction_data.get('target_feature', target_feature),
                        target_mapping=target_mapping,
                        prediction_value=0.0,
                        prediction_time=prediction_time,
                        actual_value=None,
                        device_status='off'
                    )
                    execution_time = time.time() - start_time
                    result_off2 = {
                        'success': True,
                        'device_id': device_id,
                        'target_feature': prediction_data.get('target_feature', target_feature),
                        'target_feature_id': self.active_target_feature_id,
                        'prediction': 0.0,
                        'prediction_scaled': 0.0,
                        'actual': None,
                        'prediction_time': prediction_time.isoformat(),
                        'execution_time_seconds': execution_time,
                        'save_success': save_success,
                        'device_status': 'off',
                        'skip_reason': 'device_off',
                        'correction_info': {'was_corrected': True, 'reason': 'device_off'}
                    }
                    self._log_prediction_result(result_off2, start_time)
                    return result_off2

            # 设备开机，正常进行预测
            X_seq = prediction_data['X_seq']
            y_pred = self.predict(X_seq, device_id=device_id)
            output_dim = getattr(self, 'output_dim', 1)

            if output_dim > 1:
                # ========== 多输出模式 ==========
                y_pred_scaled = y_pred.flatten()  # shape (output_dim,)
                logger.info(f"📊 多输出预测值（前3个）: {y_pred_scaled[:3]}")
                y_pred_value = y_pred_scaled

                # 多输出模式下暂时禁用偏差校正（仅记录日志）
                y_actual = prediction_data.get('y_actual')
                correction_result = {'was_corrected': False, 'reason': 'multistep_no_correction'}

                # 更新历史记录（仅记录第一个预测值作为代表）
                if y_actual is not None:
                    self.update_prediction_history(device_id, y_pred_value[0], y_actual)

                # 对每个预测值应用物理约束和四舍五入
                y_pred_value = np.array([
                    self.apply_physical_constraints(v, target_feature) for v in y_pred_value
                ])

                # 保存多步预测结果
                target_mapping = prediction_data.get('target_mapping')
                forecast_start = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                save_success = self._save_multistep_predictions(
                    device_id=device_id,
                    target_feature=target_feature,
                    target_mapping=target_mapping,
                    prediction_values=y_pred_value,
                    forecast_start_time=forecast_start,
                    step_minutes=60,
                    actual_values=None,
                    device_status='on'
                )

                # 记录预测历史（仅保留整体记录）
                prediction_record = {
                    'device_id': device_id,
                    'target_feature': target_feature,
                    'prediction_value': y_pred_value.tolist(),
                    'actual_value': y_actual,
                    'prediction_time': datetime.now(),
                    'timestamp': datetime.now(),
                    'save_success': save_success,
                    'device_status': 'on',
                    'model_output_scaled': y_pred_scaled.tolist(),
                    'correction_info': correction_result
                }
                self.predictions_history.append(prediction_record)
                if len(self.predictions_history) > 1000:
                    self.predictions_history = self.predictions_history[-1000:]

                execution_time = time.time() - start_time
                result = {
                    'success': True,
                    'device_id': device_id,
                    'target_feature': target_feature,
                    'target_feature_id': self.active_target_feature_id,
                    'prediction': y_pred_value.tolist(),
                    'prediction_scaled': y_pred_scaled.tolist(),
                    'actual': None,  # 多输出时实际值无法单点对比
                    'prediction_time': forecast_start.isoformat(),
                    'execution_time_seconds': execution_time,
                    'save_success': save_success,
                    'device_status': 'on',
                    'correction_info': correction_result,
                    'data_info': {
                        'look_back': prediction_data.get('look_back', look_back),
                        'feature_count': len(prediction_data.get('feature_columns', [])),
                        'sequence_shape': X_seq.shape,
                        'output_dim': output_dim
                    }
                }
                logger.info(f"✅ 多步预测完成，共 {output_dim} 个值")
                self._log_prediction_result(result, start_time)
                return result

            else:
                # ========== 单输出模式（原逻辑保持不变） ==========
                y_pred_scaled = float(y_pred[0]) if len(y_pred.shape) > 0 else float(y_pred)
                logger.info(f"📊 模型预测的标准化值: {y_pred_scaled:.6f}")
                y_pred_value = self._inverse_transform(y_pred_scaled)
                # 检查是否启用递归预测（仅当 output_dim==1 且 self.recursive_forecast 存在且 enabled）
                if hasattr(self, 'recursive_forecast') and self.recursive_forecast and self.recursive_forecast.get(
                        'enabled'):
                    steps = self.recursive_forecast.get('steps', 24)
                    logger.info(f"🔄 递归预测模式开启，步数={steps}")
                    # 执行递归预测（代码见下文）
                    recursive_result = self._recursive_forecast(
                        X_seq, device_id, target_feature,
                        look_back, prediction_data, steps, start_time
                    )
                    return recursive_result
                y_actual = prediction_data.get('y_actual')
                if y_actual is not None:
                    logger.info(f"📊 当前预测: {y_pred_value:.2f}, 实际值: {y_actual:.2f}")
                    if 'raw_data' in prediction_data and target_feature in prediction_data['raw_data']:
                        raw_df = prediction_data['raw_data']
                        target_col = prediction_data.get('target_feature', target_feature)
                        if target_col in raw_df.columns:
                            recent_raw_data = raw_df.iloc[-6:]
                            recent_actuals = recent_raw_data[target_col].tolist()
                    self.update_prediction_history(device_id, y_pred_value, y_actual)
                    self.update_correction_threshold(device_id)

                    all_actuals = self._get_all_recent_actuals(device_id)
                    logger.info(f"📊 可用历史实际值数量: {len(all_actuals)}")
                    if len(all_actuals) > 0:
                        logger.info(f"📊 历史实际值: {all_actuals}")

                    recent_actuals_15min = self._get_recent_actual_values(device_id, minutes_back=15)
                    logger.info(f"📊 最近15分钟实际值数量: {len(recent_actuals_15min)}")
                    if len(recent_actuals_15min) > 0:
                        logger.info(f"📊 最近15分钟实际值: {recent_actuals_15min}")

                    correction_result = self.apply_bias_correction(
                        device_id=device_id,
                        predicted_value=y_pred_value,
                        target_feature=target_feature,
                        device_status='on'
                    )
                    y_pred_value = correction_result['corrected_value']
                    if correction_result['was_corrected']:
                        logger.info(f"✅ 智能校正应用: {correction_result.get('reason', '未知原因')}")
                        logger.info(f"  校正因子: {correction_result.get('correction_factor', 1.0):.3f}")
                else:
                    y_pred_value = self.apply_physical_constraints(y_pred_value, target_feature)
                    correction_result = {'was_corrected': False, 'reason': 'no_actual_value'}

                y_pred_value = self.apply_physical_constraints(y_pred_value, target_feature)
                prediction_time = datetime.now() + timedelta(minutes=5)
                target_mapping = prediction_data.get('target_mapping')
                save_success = self.save_prediction_to_mysql(
                    device_id=device_id,
                    target_feature=target_feature,
                    target_mapping=target_mapping,
                    prediction_value=y_pred_value,
                    prediction_time=prediction_time,
                    actual_value=y_actual,
                    device_status='on'
                )
                prediction_record = {
                    'device_id': device_id,
                    'target_feature': target_feature,
                    'prediction_value': y_pred_value,
                    'actual_value': y_actual,
                    'prediction_time': prediction_time,
                    'timestamp': datetime.now(),
                    'save_success': save_success,
                    'device_status': 'on',
                    'model_output_scaled': y_pred_scaled,
                    'correction_info': correction_result
                }
                self.predictions_history.append(prediction_record)
                if len(self.predictions_history) > 1000:
                    self.predictions_history = self.predictions_history[-1000:]

                execution_time = time.time() - start_time
                y_actual_formatted = None
                if y_actual is not None:
                    y_actual_formatted = self.round_to_decimal(y_actual, target_feature)

                result = {
                    'success': True,
                    'device_id': device_id,
                    'target_feature': target_feature,
                    'target_feature_id': self.active_target_feature_id,
                    'prediction': y_pred_value,
                    'prediction_scaled': y_pred_scaled,
                    'actual': y_actual_formatted,
                    'prediction_time': prediction_time.isoformat(),
                    'execution_time_seconds': execution_time,
                    'save_success': save_success,
                    'device_status': 'on',
                    'correction_info': correction_result,
                    'data_info': {
                        'look_back': prediction_data.get('look_back', look_back),
                        'feature_count': len(prediction_data.get('feature_columns', [])),
                        'sequence_shape': X_seq.shape
                    }
                }
                if y_actual is not None and y_actual != 0:
                    error_percent = abs((y_pred_value - y_actual) / y_actual * 100)
                    logger.warning(
                        f"✅ 预测完成: 预测值={y_pred_value:.4f}, 实际值={y_actual}, 误差={error_percent:.1f}%")
                    if error_percent <= 3.0:
                        logger.info("✅ 误差控制在3%以内，达到预期目标")
                    else:
                        logger.warning(f"⚠️ 误差({error_percent:.1f}%)仍超过3%，需要进一步优化")
                else:
                    logger.info(f"✅ 预测完成: 预测值={y_pred_value:.4f}")

                correction_stats = self.get_correction_statistics(device_id)
                if correction_stats:
                    logger.info(f"📊 校正统计: {correction_stats}")
                    result['correction_stats'] = correction_stats
                self._log_prediction_result(result, start_time)
                return result

        except Exception as e:
            logger.error(f"❌ 增强预测执行失败: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'device_id': device_id,
                'target_feature': target_feature,
                'correction_info': {
                    'was_corrected': False,
                    'reason': f'error: {str(e)}'
                }
            }

    def start_enhanced_periodic_prediction(
            self,
            device_id: int = None,
            target_feature: str = None,
            interval_minutes: int = 5,
            look_back: int = None,
            correction_config: Optional[Dict] = None
    ) -> bool:
        """启动增强版周期性预测（带偏差校正）"""
        if self.is_running:
            logger.warning("⚠️ 预测器已经在运行中")
            return False

        # 更新校正配置
        if correction_config:
            self.correction_config.update(correction_config)

        logger.info(f"🎯 启用预测保底机制，配置: {self.correction_config}")

        # 使用已保存的配置或参数
        if device_id is None and self.active_device_id:
            device_id = self.active_device_id
        elif device_id is None:
            logger.error("❌ 未提供设备ID")
            return False

        # 优先使用已保存的配置
        if target_feature is None and self.active_target_feature:
            target_feature = self.active_target_feature
        elif target_feature is None:
            target_feature = "PointValue"

        if look_back is None and self.active_look_back:
            look_back = self.active_look_back
        elif look_back is None:
            look_back = 24

        # 保存配置信息
        self.active_device_id = device_id
        self.active_target_feature = target_feature
        self.active_look_back = look_back

        self.is_running = True

        def enhanced_prediction_job():
            """增强版预测任务"""
            try:
                logger.info(f"⏰ 执行增强定时预测任务 - 设备 {device_id}")
                result = self.enhanced_make_prediction(device_id, target_feature, look_back)
                if result.get('success'):
                    device_status = result.get('device_status', 'unknown')
                    if device_status == 'off':
                        logger.info(f"✅ 设备关机状态检测，预测值为0")
                    else:
                        pred_value = result.get('prediction', 0)
                        actual_value = result.get('actual')
                        correction_info = result.get('correction_info', {})

                        if actual_value is not None and actual_value != 0:
                            error_pct = abs((pred_value - actual_value) / actual_value * 100)

                            if correction_info.get('was_corrected', False):
                                logger.info(f"✅ 增强预测完成: 预测值={pred_value:.2f}, "
                                            f"实际值={actual_value:.2f}, 误差={error_pct:.1f}% (已校正)")
                            else:
                                logger.info(f"✅ 增强预测完成: 预测值={pred_value:.2f}, "
                                            f"实际值={actual_value:.2f}, 误差={error_pct:.1f}% (未校正)")
                        else:
                            logger.info(f"✅ 增强预测完成: 预测值={pred_value:.2f}")
                else:
                    logger.error(f"❌ 增强定时预测失败: {result.get('error', '未知错误')}")
            except Exception as e:
                logger.error(f"❌ 增强定时预测任务异常: {e}")

        def run_enhanced_scheduler():
            """运行增强版调度器"""
            # 立即执行一次
            logger.info(f"🚀 启动增强预测器，立即执行第一次预测... (look_back={look_back})")
            enhanced_prediction_job()

            # 设置定时任务
            schedule.every(interval_minutes).minutes.do(enhanced_prediction_job)

            logger.info(f"⏰ 启动增强周期性预测，每 {interval_minutes} 分钟执行一次，带偏差校正")

            while self.is_running:
                try:
                    schedule.run_pending()
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"❌ 调度器运行异常: {e}")
                    time.sleep(5)

            logger.info("🛑 增强预测器已停止")

        # 启动预测线程
        self.prediction_thread = threading.Thread(
            target=run_enhanced_scheduler,
            daemon=True,
            name=f"EnhancedPredictor-Device-{device_id}"
        )
        self.prediction_thread.start()

        logger.info(f"✅ 已启动设备 {device_id} 的增强周期性预测 (带偏差校正)")
        return True

    def _get_db_session(self):
        """获取新的数据库会话"""
        try:
            from app.database import SessionLocal
            return SessionLocal()
        except Exception as e:
            logger.error(f"创建数据库会话失败: {e}")
            return None

    def load_model(self, model_path: str) -> bool:
        """加载训练好的XGBoost模型 - 兼容残差模型"""
        try:
            logger.info(f"📂 正在加载模型: {model_path}")

            # 检查模型文件是否存在
            if not os.path.exists(model_path):
                logger.error(f"❌ 模型文件不存在: {model_path}")
                return False

            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)

            # 1. 加载基础模型
            if 'model' not in model_data:
                logger.error("❌ 模型文件中没有找到'model'字段")
                return False
            # 在 load_model 方法中添加
            self.output_dim = model_data.get('output_dim', 1)  # 默认为1（单输出）
            logger.info(f"模型输出维度: {self.output_dim}")
            self.model = model_data['model']
            self.residual_model = model_data.get('residual_model')  # 加载残差模型（可能为None）
            logger.info(f"✅ 基础模型加载成功 (残差模型: {self.residual_model is not None})")
            # 新增：读取残差模型配置
            self.residual_lags = model_data.get('residual_lags', 0)
            self.use_standardize = model_data.get('use_standardize', False)
            self.residual_mean = model_data.get('residual_mean', 0.0)
            self.residual_std = model_data.get('residual_std', 1.0)
            self.avg_bias = model_data.get('avg_bias', 0.0)  # 新增
            self.abs_avg_bias = model_data.get('abs_avg_bias', 0.0)  # 新增
            self.best_alpha = model_data.get('best_alpha', 1.0)
            logger.info(f"加载残差收缩系数 best_alpha = {self.best_alpha}")
            # 2. 加载模型信息和特征名称
            self.model_info = {
                'model_params': model_data.get('model_params', {}),
                'training_stats': model_data.get('training_stats', {}),
                'feature_importance': model_data.get('feature_importance', {}),
                'loaded_at': datetime.now().isoformat(),
                'model_path': model_path,
            }

            # 3. 【关键】加载特征名称
            self.feature_names = model_data.get('feature_names', [])
            if self.feature_names:
                logger.info(f"✅ 加载特征名称: {len(self.feature_names)} 个特征")
                logger.debug(f"前5个特征: {self.feature_names[:5]}")
            else:
                logger.warning("⚠️ 模型中没有保存特征名称，将使用默认特征名称")

            # 4. 加载scaler和统计信息
            self._load_scaler_and_stats(model_data)

            # 5. 加载训练配置
            training_config = model_data.get('training_config', {})
            if training_config:
                self._load_training_config(training_config)
                # 新增：从训练配置中获取采样间隔（分钟）
                self.freq_minutes = training_config.get('freq_minutes', 5)
            else:
                logger.warning("⚠️ 模型文件中没有训练配置，使用默认值")
                self._set_default_config()
                self.freq_minutes = 5  # 默认5分钟
            # 在 load_model 中，加载 training_config 后
            recursive_cfg = training_config.get('recursive_forecast')
            if recursive_cfg and recursive_cfg.get('enabled'):
                self.recursive_forecast = recursive_cfg
                logger.info(f"设备 {self.active_device_id} 启用递归预测，步数={self.recursive_forecast['steps']}")
            else:
                self.recursive_forecast = None
            # 6. 验证加载的配置
            self._validate_loaded_config()

            logger.info(f"✅ 模型已从 {model_path} 成功加载")
            logger.info(f"模型加载后 active_look_back = {self.active_look_back}")
            return True

        except Exception as e:
            logger.error(f"❌ 加载模型失败: {e}", exc_info=True)
            return False

    def _get_residuals_history(self, device_id: int, lags: int) -> List[float]:
        """获取最近 lags 个残差（实际值 - 基础预测值），按时间顺序返回（最新的在最后）"""
        residuals = []
        if device_id in self.actual_history and device_id in self.prediction_history:
            actuals = self.actual_history[device_id]
            preds = self.prediction_history[device_id]
            n = min(len(actuals), len(preds))
            # 取最后 lags 个残差，并保持最新在最后
            recent_residuals = []
            for i in range(-1, -n - 1, -1):
                if len(recent_residuals) >= lags:
                    break
                recent_residuals.append(actuals[i]['value'] - preds[i]['value'])
            recent_residuals.reverse()  # 现在最新在最后
            residuals = recent_residuals
            # 输出历史残差队列（使用 WARNING 级别）
            logger.warning(f"设备 {device_id} 历史残差队列 (最近 {lags} 步): {residuals}")
        # 不足 lags 时，用0填充前面
        if len(residuals) < lags:
            residuals = [0.0] * (lags - len(residuals)) + residuals
        return residuals[-lags:]

    def _load_scaler_and_stats(self, model_data: Dict) -> None:
        """加载scaler和统计信息（兼容标量和多输出数组）"""
        # 第一优先级：直接加载scaler对象
        self.scaler = model_data.get('scaler')

        # 第二优先级：直接保存的统计量（可能是标量或数组）
        target_mean = model_data.get('target_mean')
        target_std = model_data.get('target_std')

        # 第三优先级：从训练统计中获取统计信息（备用）
        training_stats = model_data.get('training_stats', {})
        standardization_stats = training_stats.get('standardization_stats', {})

        if standardization_stats:
            if target_mean is None:
                target_mean = standardization_stats.get('target_mean')
            if target_std is None:
                target_std = standardization_stats.get('target_std')
            self.y_train_mean = standardization_stats.get('y_train_mean')
            self.y_train_std = standardization_stats.get('y_train_std')

        # 第四优先级：检查是否有y_train_mean和y_train_std的直接保存
        if target_mean is None:
            target_mean = model_data.get('y_train_mean')
        if target_std is None:
            target_std = model_data.get('y_train_std')

        # 关键：保留标量形式，不强制转换为数组（避免0维数组问题）
        # 只有当统计量是列表或数组且长度>1时才作为多输出处理
        if target_mean is not None:
            if isinstance(target_mean, (list, tuple, np.ndarray)) and len(target_mean) == 1:
                # 长度为1的序列转换为标量
                self.target_mean = float(target_mean[0])
                self.target_std = float(target_std[0]) if target_std is not None else None
            elif isinstance(target_mean, (list, tuple, np.ndarray)) and len(target_mean) > 1:
                # 多输出，保留为数组
                self.target_mean = np.array(target_mean)
                self.target_std = np.array(target_std) if target_std is not None else None
            else:
                # 已经是标量
                self.target_mean = target_mean
                self.target_std = target_std
        else:
            self.target_mean = None
            self.target_std = None

        # 记录加载的scaler和统计信息
        logger.info("📊 加载的scaler和统计信息:")

        if self.scaler is not None:
            scaler_type = type(self.scaler).__name__
            logger.info(f"  - Scaler类型: {scaler_type}")
            try:
                if hasattr(self.scaler, 'mean_'):
                    mean_val = self.scaler.mean_
                    if isinstance(mean_val, np.ndarray) and len(mean_val) > 0:
                        logger.info(f"  - Scaler均值: {mean_val[0]:.4f}")
                if hasattr(self.scaler, 'scale_'):
                    scale_val = self.scaler.scale_
                    if isinstance(scale_val, np.ndarray) and len(scale_val) > 0:
                        logger.info(f"  - Scaler标准差: {scale_val[0]:.4f}")
            except Exception as e:
                logger.debug(f"获取scaler属性失败: {e}")

        # 输出统计量信息（兼容标量和数组）
        if self.target_mean is not None and self.target_std is not None:
            if isinstance(self.target_mean, np.ndarray):
                # 多输出数组
                logger.info(f"  - 统计量类型: 多输出数组，形状={self.target_mean.shape}")
                mean_preview = self.target_mean[:3] if len(self.target_mean) > 3 else self.target_mean
                std_preview = self.target_std[:3] if len(self.target_std) > 3 else self.target_std
                logger.info(f"  - 均值(前3): {mean_preview}")
                logger.info(f"  - 标准差(前3): {std_preview}")
                logger.info(f"  - 逆变换公式: y = x * σ + μ (按步长)")
            else:
                # 标量
                logger.info(f"  - 统计量: 均值={self.target_mean:.4f}, 标准差={self.target_std:.4f}")
                logger.info(
                    f"  - 计算比例: 1个标准差 = {self.target_std:.4f}, 逆变换公式: y = x × {self.target_std:.4f} + {self.target_mean:.4f}")

        # 验证统计量
        if self.target_mean is None or self.target_std is None:
            logger.warning("⚠️ 统计量不完整: 均值或标准差为None")
        else:
            if isinstance(self.target_std, np.ndarray):
                if np.any(self.target_std <= 0):
                    logger.warning(f"⚠️ 标准差异常值: {self.target_std[self.target_std <= 0]}")
                    self.target_std[self.target_std <= 0] = 1.0
            else:
                if self.target_std <= 0:
                    logger.warning(f"⚠️ 标准差异常: {self.target_std:.4f} <= 0，将设为1.0")
                    self.target_std = 1.0

    def _load_training_config(self, training_config: Dict) -> None:
        """加载训练配置"""
        # 获取基本配置
        self.active_look_back = training_config.get('look_back', 24)
        self.active_target_feature = training_config.get('target_feature', 'PointValue')
        self.active_target_feature_id = training_config.get('output_feature_id')
        self.active_model_version_id = training_config.get('model_version_id')
        self.active_device_id = training_config.get('device_id')
        self.active_training_config = training_config

        # 获取预处理配置
        self.preprocessing_config = training_config.get('preprocessing_config', {})

        # 记录特征数量信息
        if 'feature_importance' in self.model_info:
            feature_importance = self.model_info['feature_importance']
            if 'total_features' in feature_importance:
                logger.info(f"✅ 训练模型特征数量: {feature_importance['total_features']}")

        logger.info(f"✅ 加载训练配置:")
        logger.info(f"  - 设备ID: {self.active_device_id}")
        logger.info(f"  - 目标特征: {self.active_target_feature} (ID: {self.active_target_feature_id})")
        logger.info(f"  - 模型版本ID: {self.active_model_version_id}")
        logger.info(f"  - look_back: {self.active_look_back}")
        logger.info(f"  - 预处理配置: {list(self.preprocessing_config.keys())}")

    def _set_default_config(self) -> None:
        """设置默认配置"""
        self.active_look_back = 24
        self.active_target_feature = 'PointValue'
        self.preprocessing_config = {}
        logger.info("ℹ️ 使用默认配置: look_back=24, target_feature='PointValue'")

    def _validate_loaded_config(self) -> None:
        """验证加载的配置"""
        validation_passed = True

        # 验证模型
        if self.model is None:
            logger.error("❌ 模型未成功加载")
            validation_passed = False

        # 验证统计量
        if self.target_mean is None or self.target_std is None:
            logger.warning("⚠️ 统计量信息不完整，可能影响预测值逆变换")

        # 验证必要配置
        if not self.active_target_feature:
            logger.warning("⚠️ 目标特征未设置")
            self.active_target_feature = 'PointValue'

        if not self.active_look_back:
            logger.warning("⚠️ look_back未设置")
            self.active_look_back = 24

        # 验证scaler
        if self.scaler is not None:
            try:
                # 测试scaler是否可用
                test_input = np.array([[0.0]])
                test_output = self.scaler.inverse_transform(test_input)
                logger.info(f"✅ Scaler可用性测试通过: {test_output[0][0]:.4f}")
            except Exception as e:
                logger.warning(f"⚠️ Scaler测试失败: {e}")

        if validation_passed:
            logger.info("✅ 配置验证通过")

    def _get_database_connection(self, data_source_info: Dict) -> Optional[Any]:
        """根据数据源信息创建数据库连接"""
        try:
            # 生成连接缓存键
            cache_key = f"{data_source_info.get('data_source_id')}_{data_source_info.get('database')}"

            # 检查缓存
            if cache_key in self.connection_cache:
                connection_info = self.connection_cache[cache_key]
                last_used = connection_info.get('last_used', 0)

                # 检查连接是否过期（1小时）
                if time.time() - last_used < 3600:
                    logger.debug(f"使用缓存的数据库连接: {cache_key}")
                    self.connection_cache[cache_key]['last_used'] = time.time()
                    return connection_info['engine']

            # 创建新的数据库连接
            db_session = self._get_db_session()
            if not db_session:
                logger.error("无法获取数据库会话")
                return None

            try:
                # 获取数据源详细信息
                data_source_id = data_source_info.get('data_source_id')
                database_name = data_source_info.get('database')

                if not data_source_id:
                    logger.error("未提供数据源ID")
                    return None

                # 查询数据源配置
                data_source = db_session.query(self.models.DataSources).filter(
                    self.models.DataSources.id == data_source_id
                ).first()

                if not data_source:
                    logger.error(f"数据源 {data_source_id} 未找到")
                    return None

                # 构建连接字符串
                from urllib.parse import quote_plus
                encoded_password = quote_plus(data_source.password)

                # 使用配置中的数据库名或目标数据库
                actual_database = database_name or data_source.database_name

                connection_string = (
                    f"mysql+pymysql://{data_source.username}:{encoded_password}"
                    f"@{data_source.host}:{data_source.port}/{actual_database}"
                )

                # 创建SQLAlchemy引擎
                engine = create_engine(
                    connection_string,
                    connect_args={'charset': data_source.charset},
                    pool_recycle=300,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10
                )

                # 缓存连接
                self.connection_cache[cache_key] = {
                    'engine': engine,
                    'last_used': time.time(),
                    'data_source': {
                        'id': data_source.id,
                        'database': actual_database,
                        'host': data_source.host,
                        'port': data_source.port
                    }
                }

                logger.info(f"✅ 创建数据库连接: {data_source.host}:{data_source.port}/{actual_database}")
                return engine

            finally:
                db_session.close()

        except Exception as e:
            logger.error(f"❌ 创建数据库连接失败: {e}")
            return None

    def _get_target_database_connection(self, device_id: int, target_feature: str = None) -> Optional[Any]:
        """获取目标特征的数据库连接"""
        try:
            # 如果训练配置中有数据源信息，使用它
            if self.active_training_config and self.active_target_feature:
                data_sources = self.active_training_config.get('data_sources', [])

                # 查找目标特征的数据源
                for ds_info in data_sources:
                    if ds_info.get('feature') == self.active_target_feature:
                        return self._get_database_connection(ds_info)

            # 否则，查询数据库获取数据源信息
            db_session = self._get_db_session()
            if not db_session:
                return None

            try:
                # 获取设备的目标特征映射
                if self.active_target_feature_id:
                    # 使用已知的目标特征ID
                    mapping = db_session.query(self.models.FeatureTableMapping).filter(
                        self.models.FeatureTableMapping.device_id == device_id,
                        self.models.FeatureTableMapping.feature_id == self.active_target_feature_id,
                        self.models.FeatureTableMapping.is_active == True
                    ).first()
                elif target_feature:
                    # 根据特征代码查找
                    feature = db_session.query(self.models.Feature).filter(
                        self.models.Feature.code == target_feature
                    ).first()

                    if feature:
                        mapping = db_session.query(self.models.FeatureTableMapping).filter(
                            self.models.FeatureTableMapping.device_id == device_id,
                            self.models.FeatureTableMapping.feature_id == feature.id,
                            self.models.FeatureTableMapping.is_active == True
                        ).first()
                    else:
                        mapping = None
                else:
                    # 使用设备的第一个映射
                    mapping = db_session.query(self.models.FeatureTableMapping).filter(
                        self.models.FeatureTableMapping.device_id == device_id,
                        self.models.FeatureTableMapping.is_active == True
                    ).first()

                if not mapping:
                    logger.error(f"设备 {device_id} 没有配置特征映射")
                    return None

                # 获取数据源信息
                data_source = db_session.query(self.models.DataSources).filter(
                    self.models.DataSources.id == mapping.data_source_id
                ).first()

                if not data_source:
                    logger.error(f"数据源 {mapping.data_source_id} 未找到")
                    return None

                # 构建连接信息
                connection_info = {
                    'data_source_id': mapping.data_source_id,
                    'database': mapping.database_name or data_source.database_name,
                    'table': mapping.table_name
                }

                return self._get_database_connection(connection_info)

            finally:
                db_session.close()

        except Exception as e:
            logger.error(f"❌ 获取目标数据库连接失败: {e}")
            return None

    def _flatten_X(self, X: np.ndarray) -> np.ndarray:
        """
        如果X是3D，展平为2D；否则原样返回（与训练器保持一致）
        """
        if X is None:
            return None
        if len(X.shape) == 3:
            n_samples, look_back, n_features = X.shape
            return X.reshape(n_samples, look_back * n_features)
        return X

    def predict(self, X: np.ndarray, device_id: Optional[int] = None,
                override_residuals: Optional[List[float]] = None,
                use_static_bias: bool = False,
                alpha: Optional[float] = None) -> np.ndarray:
        if self.model is None:
            raise ValueError("模型未加载")

        alpha = alpha if alpha is not None else getattr(self, 'best_alpha', 1.0)
        X_flat = self._flatten_X(X)

        # 判断模型是否为多输出（例如 MultiOutputRegressor）
        is_multioutput = hasattr(self.model, 'estimators_')
        output_dim = getattr(self, 'output_dim', 1)

        # ========== 1. 基础预测 ==========
        if is_multioutput:
            base_pred = self.model.predict(X_flat)  # shape (n_samples, output_dim)
        else:
            dmatrix = xgb.DMatrix(X_flat, feature_names=self.feature_names)
            base_pred = self.model.predict(dmatrix)  # shape (n_samples,)
            if base_pred.ndim == 1:
                base_pred = base_pred.reshape(-1, 1)  # 统一为2D便于处理

        # ========== 2. 静态偏差修正 ==========
        if use_static_bias and hasattr(self, 'avg_bias'):
            base_pred = base_pred + self.avg_bias  # 广播适用于标量和数组

        # ========== 3. 残差模型修正 ==========
        if self.residual_model is not None:
            X_res = X_flat.copy()

            # 3.1 如果需要滞后特征，构造历史残差矩阵
            if self.residual_lags > 0:
                # 获取历史残差队列
                if override_residuals is not None:
                    hist_residuals = override_residuals
                else:
                    did = device_id or self.active_device_id
                    hist_residuals = self._get_residuals_history(did, self.residual_lags)

                # 构造滞后特征矩阵（与训练时格式一致）
                # 假设 X_flat 形状为 (n_samples, n_features)
                # 滞后特征形状为 (n_samples, residual_lags)
                if X_flat.shape[0] == 1:
                    lag_features = np.array([hist_residuals])
                else:
                    lag_features = np.tile(hist_residuals, (X_flat.shape[0], 1))
                X_res = np.hstack([X_flat, lag_features])

            # 3.2 预测残差
            residual_pred_scaled = self.residual_model.predict(X_res)

            # 3.3 反标准化残差
            if self.use_standardize:
                residual_pred = residual_pred_scaled * self.residual_std + self.residual_mean
            else:
                residual_pred = residual_pred_scaled

            # 3.4 形状对齐
            if base_pred.ndim == 1 and residual_pred.ndim == 2 and residual_pred.shape[1] == 1:
                residual_pred = residual_pred.ravel()
            elif base_pred.ndim == 2 and residual_pred.ndim == 1:
                residual_pred = residual_pred.reshape(-1, 1)

            # 3.5 多输出时检查维度匹配
            if is_multioutput and residual_pred.shape[1] != base_pred.shape[1]:
                logger.warning(
                    f"残差预测输出维度 {residual_pred.shape[1]} 与基础预测 {base_pred.shape[1]} 不匹配，忽略残差")
            else:
                base_pred = base_pred + alpha * residual_pred

        # ========== 4. 返回结果 ==========
        # 单输出且形状为 (n_samples,1) 时压扁为一维，保持兼容
        if not is_multioutput and base_pred.shape[1] == 1:
            return base_pred.ravel()
        return base_pred
    def _resolve_target_feature(self, device_id: int, db_session) -> Tuple[Optional[str], Optional[int]]:
        """
        解析目标特征 - 与训练器相同的逻辑
        返回: (目标特征代码, 目标特征ID)
        """
        try:
            if self.active_target_feature and self.active_target_feature_id:
                logger.info(f"使用已配置的目标特征: {self.active_target_feature} (ID: {self.active_target_feature_id})")
                return self.active_target_feature, self.active_target_feature_id

            # 获取设备信息
            device = db_session.query(self.models.Device).filter(
                self.models.Device.id == device_id
            ).first()

            if not device or not device.model_version_id:
                logger.error(f"设备 {device_id} 未找到或未关联模型版本")
                return None, None

            # 查询模型版本中的输出特征
            output_features = db_session.query(
                self.models.ModelVersionFeature,
                self.models.Feature
            ).join(
                self.models.Feature, self.models.ModelVersionFeature.feature_id == self.models.Feature.id
            ).filter(
                self.models.ModelVersionFeature.version_id == device.model_version_id,
                self.models.ModelVersionFeature.is_output == True
            ).all()

            if not output_features:
                logger.error(f"模型版本 {device.model_version_id} 没有设置输出特征")
                return None, None

            # 使用第一个输出特征作为目标特征
            output_feature = output_features[0][1]  # Feature对象
            target_feature_name = output_feature.code
            target_feature_id = output_feature.id

            logger.info(f"✅ 从模型版本解析目标特征: {target_feature_name} (ID: {target_feature_id})")

            # 更新活动配置
            self.active_target_feature = target_feature_name
            self.active_target_feature_id = target_feature_id
            self.active_model_version_id = device.model_version_id

            return target_feature_name, target_feature_id

        except Exception as e:
            logger.error(f"解析目标特征失败: {e}")
            return None, None

    def _get_target_feature_mapping(self, device_id: int, target_feature_id: int, db_session):
        """获取目标特征的映射配置"""
        try:
            mapping = db_session.query(self.models.FeatureTableMapping).filter(
                self.models.FeatureTableMapping.device_id == device_id,
                self.models.FeatureTableMapping.feature_id == target_feature_id,
                self.models.FeatureTableMapping.is_active == True
            ).first()

            if not mapping:
                logger.error(f"目标特征 {target_feature_id} 没有配置映射")
                return None

            return mapping

        except Exception as e:
            logger.error(f"获取目标特征映射失败: {e}")
            return None

    def _get_status_features_info(self, device_id: int, db_session):
        """获取设备的所有开关机状态特征信息（返回列表）"""
        try:
            # 获取设备关联的模型版本
            device = db_session.query(self.models.Device).filter(
                self.models.Device.id == device_id
            ).first()
            if not device or not device.model_version_id:
                return []

            # 查询模型版本中标记为开关机状态的所有特征
            status_features = db_session.query(
                self.models.ModelVersionFeature,
                self.models.Feature
            ).join(
                self.models.Feature, self.models.ModelVersionFeature.feature_id == self.models.Feature.id
            ).filter(
                self.models.ModelVersionFeature.version_id == device.model_version_id,
                self.models.ModelVersionFeature.is_status == True
            ).all()

            if not status_features:
                logger.info(f"设备 {device_id} 没有配置开关机状态特征")
                return []

            status_info_list = []
            for _, feature in status_features:
                # 获取每个状态特征的映射配置
                mapping = db_session.query(self.models.FeatureTableMapping).filter(
                    self.models.FeatureTableMapping.device_id == device_id,
                    self.models.FeatureTableMapping.feature_id == feature.id,
                    self.models.FeatureTableMapping.is_active == True
                ).first()
                if mapping:
                    status_info_list.append({
                        'feature': feature,
                        'mapping': mapping,
                        'feature_id': feature.id,
                        'feature_code': feature.code
                    })
                    logger.info(
                        f"✅ 找到开关机状态特征: {feature.code} (ID: {feature.id}), 表={mapping.table_name}, 列={mapping.column_name}")

            return status_info_list
        except Exception as e:
            logger.error(f"获取开关机状态特征信息失败: {e}")
            return []

    def _check_device_status(self, device_id: int, db_session):
        """检查设备当前开关机状态（多个状态点：全0才关机，否则开机）"""
        try:
            # 获取所有状态特征信息
            status_info_list = self._get_status_features_info(device_id, db_session)
            if not status_info_list:
                logger.warning(f"[状态检查] 设备 {device_id} 未配置开关机状态特征(is_status=True)，默认开机")
                return True  # 默认开机

            # 收集每个状态特征的最新值
            status_values_summary = {}  # 收集所有特征的值用于汇总日志
            all_zero = True  # 假设全0
            at_least_one_data = False  # 至少有一个特征有数据

            for status_info in status_info_list:
                mapping = status_info['mapping']
                # 获取数据库连接
                engine = self._get_database_connection({
                    'data_source_id': mapping.data_source_id,
                    'database': mapping.database_name
                })
                if not engine:
                    logger.warning(f"[状态检查] 无法连接到状态特征 {status_info['feature_code']} 的数据库 (data_source_id={mapping.data_source_id}, database={mapping.database_name})，跳过")
                    status_values_summary[status_info['feature_code']] = 'CONN_FAILED'
                    continue

                # 查询该特征的最新值
                query = f"SELECT {mapping.column_name} FROM `{mapping.table_name}` ORDER BY {mapping.timestamp_column} DESC LIMIT 1"
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text(query)).fetchone()
                    if result:
                        at_least_one_data = True
                        status_value = float(result[0])
                        status_values_summary[status_info['feature_code']] = status_value
                        logger.warning(f"[状态检查] 设备 {device_id} 状态特征 {status_info['feature_code']} (表={mapping.table_name}, 列={mapping.column_name}) 最新值: {status_value}")
                        if status_value != 0:
                            # 只要有非0值，即可判定为开机，直接返回True
                            logger.warning(
                                f"[状态检查] 设备 {device_id} 检测到开机状态 (特征 {status_info['feature_code']} = {status_value})，汇总: {status_values_summary}")
                            return True
                        # 值为0，继续检查其他特征
                    else:
                        status_values_summary[status_info['feature_code']] = 'NO_DATA'
                        logger.warning(f"[状态检查] 状态特征 {status_info['feature_code']} (表={mapping.table_name}) 无数据")
                except Exception as e:
                    status_values_summary[status_info['feature_code']] = f'QUERY_ERROR: {str(e)[:80]}'
                    logger.warning(f"[状态检查] 查询状态特征 {status_info['feature_code']} 失败: {e}")

            # 循环结束
            if not at_least_one_data:
                # 没有任何特征有数据，保守起见认为开机
                logger.warning(f"[状态检查] 设备 {device_id} 所有状态特征均无数据 (共{len(status_info_list)}个: {status_values_summary})，默认开机")
                return True

            # 所有有数据的特征值都是0，且至少有一个有数据 → 判定为关机
            logger.warning(f"[状态检查] ⚠️ 设备 {device_id} 所有状态特征均为0，判定为关机！汇总: {status_values_summary}")
            return False

        except Exception as e:
            logger.error(f"[状态检查] 设备 {device_id} 检查状态时异常: {e}", exc_info=True)
            return True  # 异常时默认开机

    def prepare_prediction_data(
            self,
            device_id: int,
            target_feature: str = None,
            look_back: int = None
    ) -> Optional[Dict]:
        """准备预测数据 - 确保与训练时特征一致"""
        db_session = None
        try:

            # 1. 使用已保存的配置或参数
            if look_back is None and self.active_look_back:
                look_back = self.active_look_back
            elif look_back is None:
                look_back = 24

            logger.info(f"🔍 准备预测数据 - 设备: {device_id}, look_back: {look_back}")

            # 2. 获取数据库会话
            db_session = self._get_db_session()
            if db_session is None:
                logger.error("无法获取数据库会话")
                return None

            # 3. 检查设备开关机状态
            device_status = self._check_device_status(device_id, db_session)
            if not device_status:
                logger.info(f"⚡ 设备 {device_id} 当前为关机状态，跳过预测数据准备")

                # 仍然获取目标特征信息，用于保存预测结果
                target_feature_name, target_feature_id = self._resolve_target_feature(device_id, db_session)
                if target_feature_name and target_feature_id:
                    target_feature_mapping = self._get_target_feature_mapping(device_id, target_feature_id, db_session)

                    return {
                        'is_device_on': False,
                        'device_id': device_id,
                        'target_feature': target_feature_name,
                        'target_feature_id': target_feature_id,
                        'target_mapping': target_feature_mapping,
                        'look_back': look_back,
                        'timestamp': datetime.now(),
                        'skip_reason': 'device_off'
                    }
                else:
                    logger.warning("无法获取目标特征信息，无法保存关机状态预测")
                    return None

            # 4. 创建新的数据加载器
            from ..data.loader import MySQLDataLoader
            data_loader = MySQLDataLoader(db_session)

            if data_loader is None:
                logger.error("数据加载器未初始化")
                return None

            # 5. 解析目标特征
            target_feature_name, target_feature_id = self._resolve_target_feature(device_id, db_session)
            if not target_feature_name or not target_feature_id:
                logger.error("无法解析目标特征")
                return None

            # 6. 获取目标特征的映射
            target_feature_mapping = self._get_target_feature_mapping(device_id, target_feature_id, db_session)
            if not target_feature_mapping:
                logger.error(f"目标特征 {target_feature_name} 没有配置映射")
                return None

            logger.info(
                f"✅ 目标特征映射: 表={target_feature_mapping.table_name}, 列={target_feature_mapping.column_name}")

            # 7. 【关键修复】使用训练时的特征列表
            if hasattr(self, 'feature_names') and self.feature_names:
                # 直接从模型的特征名称中提取原始特征
                original_features = []
                for feature_name in self.feature_names:
                    # 去除时间特征和衍生特征，只保留原始特征
                    if not any(keyword in feature_name for keyword in
                               ['hour', 'day', 'is_', 'sin', 'cos', 'running', 'lag_', 'roll_']):
                        original_features.append(feature_name)

                # 添加目标特征（如果不在列表中）
                if target_feature_name not in original_features:
                    original_features.append(target_feature_name)

                logger.info(f"📊 使用模型训练时的特征列表: {len(original_features)} 个原始特征")
                feature_codes = original_features
            else:
                # 如果没有保存的特征名称，使用默认逻辑
                device = db_session.query(self.models.Device).filter(
                    self.models.Device.id == device_id
                ).first()

                if not device or not device.model_version_id:
                    logger.error(f"设备 {device_id} 未找到或未关联模型版本")
                    return None

                # 获取模型版本中的所有特征
                all_model_features = db_session.query(
                    self.models.ModelVersionFeature,
                    self.models.Feature
                ).join(
                    self.models.Feature, self.models.ModelVersionFeature.feature_id == self.models.Feature.id
                ).filter(
                    self.models.ModelVersionFeature.version_id == device.model_version_id
                ).all()

                # 特征代码列表
                feature_codes = []
                for _, feature in all_model_features:
                    feature_codes.append(feature.code)

            logger.info(f"📊 设备 {device_id} 的特征列表 ({len(feature_codes)} 个): {feature_codes}")

            # 8. 加载数据的时间范围
            end_time = datetime.now()
            # 使用已加载的 freq_minutes（默认5分钟）
            freq_minutes = getattr(self, 'freq_minutes', 5)
            required_minutes = (look_back * freq_minutes) + (4 * 60)  # 加4小时缓冲
            start_time = end_time - timedelta(minutes=required_minutes)

            logger.info(f"⏰ 加载数据时间范围: {start_time} 到 {end_time}")

            # 9. 批量加载特征数据
            all_dataframes = []
            features_loaded = 0

            # 首先加载目标特征的数据
            logger.info(f"📥 加载目标特征 {target_feature_name} 的数据...")
            try:
                df_target = data_loader.load_feature_data(
                    data_source_id=target_feature_mapping.data_source_id,
                    database_name=target_feature_mapping.database_name,
                    table_name=target_feature_mapping.table_name,
                    timestamp_column=target_feature_mapping.timestamp_column,
                    value_column=target_feature_mapping.column_name,
                    start_time=start_time,
                    end_time=end_time,
                    max_rows=2000
                )

                if df_target is not None and not df_target.empty:
                    # 【修复】设置时间戳为索引
                    df_target = df_target.set_index('timestamp')
                    df_target = df_target.rename(columns={'value': target_feature_name})

                    # 确保索引是 DatetimeIndex
                    if not isinstance(df_target.index, pd.DatetimeIndex):
                        logger.info(f"将目标特征索引转换为 DatetimeIndex")
                        df_target.index = pd.to_datetime(df_target.index)

                    logger.info(f"目标特征重采样前: 索引类型={type(df_target.index)}, 形状={df_target.shape}")
                    df_resampled = df_target.resample('5T').mean().ffill().bfill()
                    logger.info(f"目标特征重采样后: 形状={df_resampled.shape}")

                    if len(df_resampled) >= look_back:
                        all_dataframes.append(df_resampled)
                        features_loaded += 1
                        logger.info(f"✅ 目标特征加载成功: {len(df_resampled)} 条记录")
                    else:
                        logger.warning(f"⚠️ 目标特征数据不足: {len(df_resampled)} 条，需要至少 {look_back} 条")
                        return None
                else:
                    logger.error(f"❌ 目标特征数据为空")
                    return None

            except Exception as e:
                logger.error(f"❌ 加载目标特征失败: {e}")
                return None

            # 10. 加载其他特征的数据
            all_mappings = data_loader.get_device_features_mappings(device_id)

            # 2. 加载其他特征的数据
            for mapping_dict in all_mappings:
                # 跳过目标特征
                if mapping_dict.get('feature_code') == target_feature_name:
                    continue

                try:
                    feature_code = mapping_dict.get('feature_code', 'unknown')

                    # 只加载在特征代码列表中的特征
                    if feature_code not in feature_codes:
                        continue

                    logger.info(f"📥 加载输入特征 {feature_code} 的数据...")

                    df = data_loader.load_feature_data(
                        data_source_id=mapping_dict.get('data_source_id'),
                        database_name=mapping_dict.get('database_name'),
                        table_name=mapping_dict.get('table_name'),
                        timestamp_column=mapping_dict.get('timestamp_column'),
                        value_column=mapping_dict.get('column_name'),
                        start_time=start_time,
                        end_time=end_time,
                        max_rows=2000
                    )

                    if df is not None and not df.empty:
                        # 【修复】设置时间戳为索引
                        df = df.set_index('timestamp')
                        df = df.rename(columns={'value': feature_code})

                        # 确保索引是 DatetimeIndex
                        if not isinstance(df.index, pd.DatetimeIndex):
                            logger.info(f"将特征 {feature_code} 索引转换为 DatetimeIndex")
                            df.index = pd.to_datetime(df.index)

                        logger.info(f"特征 {feature_code} 重采样前: 索引类型={type(df.index)}, 形状={df.shape}")
                        df_resampled = df.resample('5T').mean().ffill().bfill()
                        logger.info(f"特征 {feature_code} 重采样后: 形状={df_resampled.shape}")

                        if len(df_resampled) >= look_back:
                            all_dataframes.append(df_resampled)
                            features_loaded += 1
                            logger.info(f"✅ 特征 {feature_code} 加载成功: {len(df_resampled)} 条记录")
                        else:
                            logger.warning(f"⚠️ 特征 {feature_code} 数据不足")
                    else:
                        logger.warning(f"⚠️ 特征 {feature_code} 数据为空")

                except Exception as e:
                    logger.warning(f"⚠️ 加载特征 {feature_code} 失败: {e}")
                    continue

            # 11. 检查是否有足够的数据
            if features_loaded < 2:
                logger.error(f"❌ 加载的特征数量不足: {features_loaded} 个")
                return None

            # 12. 合并数据
            try:
                merged_df = all_dataframes[0]
                for i in range(1, len(all_dataframes)):
                    merged_df = pd.merge(
                        merged_df,
                        all_dataframes[i],
                        left_index=True,
                        right_index=True,
                        how='outer'
                    )

                logger.info(f"✅ 数据合并完成: {len(merged_df)} 条记录, {len(merged_df.columns)} 个特征")

            except Exception as e:
                logger.error(f"❌ 合并数据失败: {e}")
                return None

            # 13. 填充缺失值
            merged_df = merged_df.ffill().bfill().fillna(0)

            # 14. 确保有足够的数据
            if len(merged_df) < look_back:
                logger.error(f"❌ 数据不足，需要至少 {look_back} 条记录，实际 {len(merged_df)} 条")
                return None

            # 【关键修复】应用与训练时相同的特征工程
            logger.info("🔧 应用与训练时相同的特征工程...")

            # 确保特征工程与训练时一致
            if hasattr(self, 'active_training_config'):
                preprocessing_config = self.active_training_config.get('preprocessing_config', {})
                # 创建时间特征（如果需要）
                if preprocessing_config.get('create_time_features', False):
                    merged_df = self._create_time_features(merged_df)
                # 创建滞后特征（对所有数值特征）
                lag_periods = preprocessing_config.get('lag_periods', [])
                if lag_periods:
                    merged_df = self._create_lag_features_all(merged_df, lag_periods)
                # 创建滚动特征（对所有数值特征）
                rolling_windows = preprocessing_config.get('rolling_windows', [])
                rolling_stats = preprocessing_config.get('rolling_stats', ['mean'])
                if rolling_windows:
                    merged_df = self._create_rolling_features_all(merged_df, rolling_windows, rolling_stats)
            else:
                # 如果没有训练配置，使用默认的特征工程
                if hasattr(self, 'feature_names') and self.feature_names:
                    # 从特征名称中推断需要创建的特征类型
                    time_features_needed = any(
                        'hour' in fn or 'day' in fn or 'is_' in fn or 'sin' in fn or 'cos' in fn for fn in
                        self.feature_names)
                    lag_features_needed = any('lag_' in fn for fn in self.feature_names)
                    rolling_features_needed = any('roll_' in fn for fn in self.feature_names)

                    if time_features_needed:
                        merged_df = self._create_time_features(merged_df)
                        logger.info(f"✅ 创建时间特征，特征数: {len(merged_df.columns)}")

                    if lag_features_needed and target_feature_name in merged_df.columns:
                        merged_df = self._create_lag_features(merged_df, target_feature_name, [1, 3, 6, 12])
                        logger.info(f"✅ 创建滞后特征，特征数: {len(merged_df.columns)}")

                    if rolling_features_needed and target_feature_name in merged_df.columns:
                        merged_df = self._create_rolling_features(merged_df, target_feature_name, [3, 6, 12], ['mean'])
                        logger.info(f"✅ 创建滚动特征，特征数: {len(merged_df.columns)}")
            if self.active_training_config:
                preprocessing_config = self.active_training_config.get('preprocessing_config', {})

                # 创建时间特征
                if preprocessing_config.get('create_time_features', False):
                    merged_df = self._create_time_features(merged_df)

                # 创建滞后特征
                lag_periods = preprocessing_config.get('lag_periods', [])
                if lag_periods:
                    merged_df = self._create_lag_features_all(merged_df, lag_periods)

                # 创建滚动特征
                rolling_windows = preprocessing_config.get('rolling_windows', [])
                rolling_stats = preprocessing_config.get('rolling_stats', ['mean'])
                if rolling_windows:
                    merged_df = self._create_rolling_features_all(merged_df, rolling_windows, rolling_stats)

            # 15. 【关键修复】确保最终特征与训练时相同
            if hasattr(self, 'feature_names') and self.feature_names:
                # 检查哪些特征缺失
                missing_features = []
                for feature_name in self.feature_names:
                    if feature_name not in merged_df.columns:
                        missing_features.append(feature_name)
                        # 添加缺失的特征列，填充为0
                        merged_df[feature_name] = 0

                if missing_features:
                    logger.warning(f"⚠️ 以下训练特征在预测数据中缺失，已用0填充: {missing_features}")

                # 确保特征顺序与训练时一致
                final_feature_columns = []
                for feature_name in self.feature_names:
                    if feature_name in merged_df.columns:
                        final_feature_columns.append(feature_name)

                # 添加不在训练特征列表中的其他特征
                other_features = [col for col in merged_df.columns if col not in final_feature_columns]
                final_feature_columns.extend(other_features)

                # 重新排列列顺序
                merged_df = merged_df[final_feature_columns]

                logger.info(f"✅ 确保特征与训练时一致: {len(self.feature_names)} 个训练特征")
                logger.info(f"📊 最终特征列表: {self.feature_names}")
            else:
                logger.warning("⚠️ 无法获取训练特征列表，使用所有特征")
                self.feature_names = list(merged_df.columns)

            # 使用全部特征进行预测
            logger.info(f"✅ 使用 {len(merged_df.columns)} 个特征进行预测")
            # 【关键修复】保存使用的特征列到类属性中，供后续使用
            self.active_feature_columns = [col for col in merged_df.columns if col != target_feature_name]

            logger.info(f"🎯 最终特征数量: {len(merged_df.columns)}，输入特征: {len(self.active_feature_columns)}")

            # 检查目标特征是否存在
            if target_feature_name not in merged_df.columns:
                logger.error(f"❌ 目标特征 {target_feature_name} 不在数据中")
                return None

            # 16. 准备序列数据
            recent_data = merged_df.iloc[-look_back:].copy()

            # 17. 创建特征列 - 使用保存的特征列
            if hasattr(self, 'active_feature_columns') and self.active_feature_columns:
                feature_columns = self.active_feature_columns
            else:
                feature_columns = [col for col in recent_data.columns if col != target_feature_name]

            if not feature_columns:
                logger.error("❌ 没有可用的特征列")
                return None

            # 根据模型期望的输入模式构造 X_seq
            # 判断是否为多输出模型（多步预测）
            is_multistep = getattr(self, 'output_dim', 1) > 1 or hasattr(self.model, 'estimators_')

            if is_multistep and look_back > 1:
                # 多输出模式：强制使用 3D 序列（历史窗口）
                X_seq = recent_data[feature_columns].values.reshape(1, look_back, len(feature_columns))
                logger.info(f"✅ 多输出模式，使用 3D 序列，形状: {X_seq.shape}")
            else:
                # 单输出模式：根据特征数量判断
                if len(self.feature_names) == len(feature_columns):
                    X_seq = recent_data[feature_columns].iloc[-1:].values
                    logger.info(f"✅ 单输出模式，使用 2D 输入，形状: {X_seq.shape}")
                else:
                    X_seq = recent_data[feature_columns].values.reshape(1, look_back, len(feature_columns))
                    logger.info(f"✅ 单输出模式，使用 3D 序列，形状: {X_seq.shape}")

            # 验证总特征数是否匹配模型期望
            total_input_features = X_seq.shape[1] if X_seq.ndim == 2 else X_seq.shape[1] * X_seq.shape[2]
            # 多输出模型（多步预测）期望输入是展平后的特征，跳过此检查
            if not is_multistep and total_input_features != len(self.feature_names):
                logger.error(f"❌ 总特征数不匹配: 模型期望 {len(self.feature_names)}，实际 {total_input_features}")
                return None

            # 记录特征信息
            feature_info = {
                'total_features': len(merged_df.columns),
                'input_features': total_input_features,
                'feature_names': feature_columns,
                'target_feature': target_feature_name,
                'input_shape': X_seq.shape
            }
            logger.info(f"📊 特征信息: {feature_info}")

            # 19. 获取实际值
            y_actual_raw = recent_data[target_feature_name].values[-1]

            # 处理实际值类型
            if isinstance(y_actual_raw, np.ndarray):
                y_actual = float(y_actual_raw[0]) if len(y_actual_raw) == 1 else float(np.mean(y_actual_raw))
            elif isinstance(y_actual_raw, (list, tuple)):
                y_actual = float(y_actual_raw[0]) if len(y_actual_raw) == 1 else float(
                    sum(y_actual_raw) / len(y_actual_raw))
            else:
                y_actual = float(y_actual_raw)

            logger.info(f"✅ 预测数据准备完成:")
            logger.info(f"  - X_seq形状: {X_seq.shape}")
            logger.info(f"  - 目标特征: {target_feature_name}")
            logger.info(f"  - 特征列: {len(feature_columns)} 个")
            logger.info(f"  - 实际值: {y_actual:.4f}")
            logger.info(f"  - 特征名称: {feature_columns}")

            return {
                'is_device_on': True,
                'X_seq': X_seq,
                'y_actual': y_actual,
                'feature_columns': feature_columns,
                'target_feature': target_feature_name,
                'target_feature_id': target_feature_id,
                'target_mapping': target_feature_mapping,
                'look_back': look_back,
                'timestamp': end_time,
                'raw_data': merged_df,
                'processed_data': recent_data,
                'feature_info': feature_info  # 添加特征信息
            }

        except Exception as e:
            logger.error(f"❌ 准备预测数据失败: {e}", exc_info=True)
            return None
        finally:
            if db_session:
                try:
                    db_session.close()
                except:
                    pass

    def _create_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """创建时间特征（与训练时一致）"""
        if df is None or df.empty:
            return df

        df_enhanced = df.copy()

        # 与训练时相同的时间特征
        df_enhanced['hour'] = df_enhanced.index.hour
        df_enhanced['day_of_week'] = df_enhanced.index.dayofweek
        df_enhanced['is_weekend'] = (df_enhanced['day_of_week'] >= 5).astype(int)
        df_enhanced['hour_sin'] = np.sin(2 * np.pi * df_enhanced['hour'] / 24)
        df_enhanced['hour_cos'] = np.cos(2 * np.pi * df_enhanced['hour'] / 24)

        return df_enhanced

    def _create_lag_features(
            self,
            df: pd.DataFrame,
            target_column: str,
            lag_periods: List[int] = [1, 3, 6, 12]
    ) -> pd.DataFrame:
        """创建滞后特征（与训练时一致）"""
        if df is None or df.empty or target_column not in df.columns:
            return df

        df_lagged = df.copy()

        # 为目标特征创建滞后特征
        for lag in lag_periods:
            df_lagged[f'{target_column}_lag_{lag}'] = df_lagged[target_column].shift(lag)

        # 删除包含NaN的行（由于shift操作）
        df_lagged = df_lagged.ffill().bfill()

        return df_lagged

    def _create_rolling_features(
            self,
            df: pd.DataFrame,
            target_column: str,
            windows: List[int] = [3, 6, 12],
            stats: List[str] = ['mean']
    ) -> pd.DataFrame:
        """创建滚动特征（与训练时一致）"""
        if df is None or df.empty or target_column not in df.columns:
            return df

        df_rolling = df.copy()

        for window in windows:
            if 'mean' in stats:
                df_rolling[f'{target_column}_roll_mean_{window}'] = (
                    df_rolling[target_column].rolling(window=window, min_periods=1).mean()
                )

        # 填充滚动特征的NaN值
        rolling_columns = [col for col in df_rolling.columns if 'roll_' in col]
        for col in rolling_columns:
            df_rolling[col] = df_rolling[col].ffill().bfill()

        return df_rolling

    def _select_top_features(
            self,
            df: pd.DataFrame,
            target_feature: str,
            max_features: int = 25
    ) -> pd.DataFrame:
        """特征选择（与训练时一致）"""
        if len(df.columns) <= max_features:
            return df

        # 1. 目标特征必须保留
        important_features = [target_feature]

        # 2. 保留原始特征
        original_features = [col for col in df.columns if
                             col != target_feature and '_lag_' not in col and '_roll_' not in col]

        # 3. 选择与目标特征相关性最高的特征
        corr_features = []
        if len(original_features) > 0:
            correlations = {}
            for col in original_features:
                if col != target_feature:
                    try:
                        corr = abs(df[[col, target_feature]].corr().iloc[0, 1])
                        if not np.isnan(corr):
                            correlations[col] = corr
                    except:
                        pass

            # 按相关性排序，选择前N个
            sorted_correlations = sorted(correlations.items(), key=lambda x: x[1], reverse=True)
            corr_features = [col for col, _ in sorted_correlations[:max(5, max_features // 3)]]

        # 4. 从衍生特征中选择
        derived_features = [col for col in df.columns if
                            col != target_feature and (col.endswith('_lag_') or '_roll_' in col)]

        # 5. 组合所有特征
        selected_features = important_features + corr_features + derived_features[
                                                                 :max_features - len(important_features) - len(
                                                                     corr_features)]

        # 确保不超过最大特征数
        selected_features = selected_features[:max_features]

        # 返回选择的特征
        result = df[selected_features].copy()
        logger.info(f"特征选择: 从 {len(df.columns)} 个特征中选择 {len(result.columns)} 个最重要特征")

        return result

    def save_prediction_to_mysql(
            self,
            device_id: int,
            target_feature: str,
            target_mapping,
            prediction_value: float,
            prediction_time: datetime,
            actual_value: Optional[Any] = None,
            device_status: str = 'on'  # 新增参数：设备状态，'on' 或 'off'
    ) -> bool:
        """将预测结果保存到目标特征所在的数据库，添加设备状态信息"""
        try:
            if not target_mapping:
                logger.error("❌ 未提供目标特征映射")
                return False

            # 构建预测表名
            base_table_name = target_mapping.table_name
            if base_table_name.startswith('dev-'):
                prediction_table = f"pre-{base_table_name}"
            else:
                prediction_table = f"pre-{base_table_name}"

            logger.info(f"📊 使用预测表: {prediction_table}")

            # 获取数据库连接
            engine = self._get_target_database_connection(device_id, target_feature)
            if engine is None:
                logger.error(f"❌ 无法连接到目标数据库")
                return False

            # 创建预测表（如果不存在）
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS `{prediction_table}` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `UpdateDateTime` datetime DEFAULT NULL COMMENT '预测时间点',
                `PointValue` float DEFAULT NULL COMMENT '预测值',
                `ActualValue` float DEFAULT NULL COMMENT '实际值',
                `DeviceID` int DEFAULT NULL COMMENT '设备ID',
                `TargetFeature` varchar(100) DEFAULT NULL COMMENT '目标特征',
                `TargetFeatureID` int DEFAULT NULL COMMENT '目标特征ID',
                `PredictionTime` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '预测生成时间',
                `DeviceStatus` varchar(10) DEFAULT 'on' COMMENT '设备状态: on/off',
                `CreatedAt` timestamp DEFAULT CURRENT_TIMESTAMP,
                INDEX `idx_device_time` (`DeviceID`, `UpdateDateTime`),
                INDEX `idx_prediction_time` (`PredictionTime`),
                INDEX `idx_feature` (`TargetFeatureID`),
                INDEX `idx_device_status` (`DeviceStatus`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """

            try:
                with engine.connect() as conn:
                    conn.execute(text(create_table_sql))
                    conn.commit()
                    logger.info(f"✅ 预测表 {prediction_table} 已创建或已存在")
            except Exception as e:
                logger.warning(f"⚠️ 创建表可能已存在或失败: {e}")

            # 处理实际值
            actual_value_processed = None
            if actual_value is not None:
                if isinstance(actual_value, np.ndarray):
                    actual_value_processed = float(actual_value[0]) if len(actual_value) == 1 else float(actual_value[-1])
                elif isinstance(actual_value, (list, tuple)):
                    actual_value_processed = float(actual_value[0]) if len(actual_value) == 1 else float(actual_value[-1])
                else:
                    actual_value_processed = float(actual_value)

            # 四舍五入预测值和实际值
            prediction_rounded = self.round_to_decimal(prediction_value, target_feature)
            if actual_value_processed is not None:
                actual_value_rounded = self.round_to_decimal(actual_value_processed, target_feature)
            else:
                actual_value_rounded = None

            # 记录四舍五入信息
            if prediction_rounded != prediction_value:
                logger.info(f"📊 预测值四舍五入: {prediction_value:.4f} -> {prediction_rounded}")
            if actual_value_processed is not None and actual_value_rounded != actual_value_processed:
                logger.info(f"📊 实际值四舍五入: {actual_value_processed:.4f} -> {actual_value_rounded}")

            # 插入预测数据，包括设备状态
            insert_sql = f"""
            INSERT INTO `{prediction_table}` 
            (UpdateDateTime, PointValue, ActualValue, DeviceID, TargetFeature, TargetFeatureID, PredictionTime, DeviceStatus)
            VALUES (:prediction_time, :prediction_value, :actual_value, :device_id, :target_feature, :target_feature_id, NOW(), :device_status)
            """

            with engine.connect() as conn:
                conn.execute(
                    text(insert_sql),
                    {
                        'prediction_time': prediction_time,
                        'prediction_value': float(prediction_rounded),
                        'actual_value': actual_value_rounded,
                        'device_id': device_id,
                        'target_feature': target_feature,
                        'target_feature_id': getattr(self, 'active_target_feature_id', 0),
                        'device_status': device_status
                    }
                )
                conn.commit()

            status_text = "开机" if device_status == 'on' else "关机"
            logger.info(f"✅ 预测结果已保存到 {prediction_table} (设备状态: {status_text})")
            logger.info(f"  预测值={prediction_rounded}, 实际值={actual_value_rounded}")
            return True

        except Exception as e:
            logger.error(f"❌ 保存预测结果失败: {e}", exc_info=True)
            return False

    def make_prediction(
            self,
            device_id: int = None,
            target_feature: str = None,
            look_back: int = None,
            use_correction: bool = True
    ) -> Dict:
        """执行单次预测，支持开关机状态检查"""
        try:
            look_back = self.active_look_back  # 强制使用模型配置
            logger.info(
                f"make_prediction: device={device_id}, look_back={look_back}, self.active_look_back={self.active_look_back}")
            start_time = time.time()

            if device_id is None and self.active_device_id:
                device_id = self.active_device_id
            elif device_id is None:
                logger.error("❌ 未提供设备ID")
                return {'success': False, 'error': '未提供设备ID', 'device_id': None}

            if target_feature is None and self.active_target_feature:
                target_feature = self.active_target_feature

            if look_back is None and self.active_look_back:
                look_back = self.active_look_back
            elif look_back is None:
                look_back = 24

            logger.info(f"🚀 开始执行预测 - 设备: {device_id}, 特征: {target_feature}, look_back: {look_back}")

            if self.model is None:
                logger.error("❌ 模型未加载")
                return {'success': False, 'error': '模型未加载', 'device_id': device_id}

            prediction_data = self.prepare_prediction_data(device_id, target_feature, look_back)
            if not prediction_data:
                logger.warning("⚠️ 无法准备预测数据")
                return {
                    'success': True,
                    'device_id': device_id,
                    'target_feature': target_feature or "PointValue",
                    'prediction': 0.0,
                    'actual': None,
                    'prediction_time': (datetime.now() + timedelta(minutes=5)).isoformat(),
                    'execution_time_seconds': time.time() - start_time,
                    'save_success': False,
                    'device_status': 'unknown',
                    'data_info': {'look_back': look_back or 24, 'feature_count': 0, 'sequence_shape': (0, 0, 0)}
                }
                self._log_prediction_result(result, start_time)
                return result

            # 检查设备是否关机
            if not prediction_data.get('is_device_on', True):
                logger.info(f"⚡ 设备 {device_id} 处于关机状态，直接预测为 0")
                target_mapping = prediction_data.get('target_mapping')
                output_dim = getattr(self, 'output_dim', 1)
                if output_dim > 1:
                    prediction_array = np.zeros(output_dim)
                    forecast_start = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                    save_success = self._save_multistep_predictions(
                        device_id=device_id,
                        target_feature=prediction_data.get('target_feature', target_feature),
                        target_mapping=target_mapping,
                        prediction_values=prediction_array,
                        forecast_start_time=forecast_start,
                        step_minutes=60,
                        actual_values=None,
                        device_status='off'
                    )
                    execution_time = time.time() - start_time
                    return {
                        'success': True,
                        'device_id': device_id,
                        'target_feature': prediction_data.get('target_feature', target_feature),
                        'target_feature_id': self.active_target_feature_id,
                        'prediction': prediction_array.tolist(),
                        'prediction_scaled': prediction_array.tolist(),
                        'actual': None,
                        'prediction_time': forecast_start.isoformat(),
                        'execution_time_seconds': execution_time,
                        'save_success': save_success,
                        'device_status': 'off',
                        'skip_reason': 'device_off',
                        'correction_info': {'was_corrected': True, 'reason': 'device_off'}
                    }
                else:
                    prediction_time = datetime.now() + timedelta(minutes=5)
                    save_success = self.save_prediction_to_mysql(
                        device_id=device_id,
                        target_feature=prediction_data.get('target_feature', target_feature),
                        target_mapping=target_mapping,
                        prediction_value=0.0,
                        prediction_time=prediction_time,
                        actual_value=None,
                        device_status='off'
                    )
                    execution_time = time.time() - start_time
                    return {
                        'success': True,
                        'device_id': device_id,
                        'target_feature': prediction_data.get('target_feature', target_feature),
                        'target_feature_id': self.active_target_feature_id,
                        'prediction': 0.0,
                        'prediction_scaled': 0.0,
                        'actual': None,
                        'prediction_time': prediction_time.isoformat(),
                        'execution_time_seconds': execution_time,
                        'save_success': save_success,
                        'device_status': 'off',
                        'skip_reason': 'device_off',
                        'correction_info': {'was_corrected': True, 'reason': 'device_off'}
                    }

            # 设备开机，正常预测
            X_seq = prediction_data['X_seq']
            y_pred = self.predict(X_seq, device_id=device_id)
            output_dim = getattr(self, 'output_dim', 1)

            if output_dim > 1:
                # ========== 多输出模式 ==========
                y_pred_scaled = y_pred.flatten()
                logger.info(f"📊 多输出预测值（前3个）: {y_pred_scaled[:3]}")
                y_pred_value = y_pred_scaled  # 直接使用模型输出
                y_actual = prediction_data.get('y_actual')

                # 多输出模式不进行偏差校正（因为校正逻辑是单值）
                correction_result = {'was_corrected': False, 'reason': 'multistep_no_correction'}

                if y_actual is not None:
                    self.update_prediction_history(device_id, y_pred_value[0], y_actual)

                # 物理约束逐元素
                y_pred_value = np.array([
                    self.apply_physical_constraints(v, target_feature) for v in y_pred_value
                ])

                # 保存多步结果
                target_mapping = prediction_data.get('target_mapping')
                forecast_start = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
                save_success = self._save_multistep_predictions(
                    device_id=device_id,
                    target_feature=target_feature,
                    target_mapping=target_mapping,
                    prediction_values=y_pred_value,
                    forecast_start_time=forecast_start,
                    step_minutes=60,
                    actual_values=None,
                    device_status='on'
                )

                prediction_record = {
                    'device_id': device_id,
                    'target_feature': target_feature,
                    'prediction_value': y_pred_value.tolist(),
                    'actual_value': y_actual,
                    'prediction_time': datetime.now(),
                    'timestamp': datetime.now(),
                    'save_success': save_success,
                    'device_status': 'on',
                    'model_output_scaled': y_pred_scaled.tolist(),
                    'correction_info': correction_result
                }
                self.predictions_history.append(prediction_record)
                if len(self.predictions_history) > 1000:
                    self.predictions_history = self.predictions_history[-1000:]

                execution_time = time.time() - start_time
                result = {
                    'success': True,
                    'device_id': device_id,
                    'target_feature': target_feature,
                    'target_feature_id': self.active_target_feature_id,
                    'prediction': y_pred_value.tolist(),
                    'prediction_scaled': y_pred_scaled.tolist(),
                    'actual': None,
                    'prediction_time': forecast_start.isoformat(),
                    'execution_time_seconds': execution_time,
                    'save_success': save_success,
                    'device_status': 'on',
                    'correction_info': correction_result,
                    'data_info': {
                        'look_back': prediction_data.get('look_back', look_back),
                        'feature_count': len(prediction_data.get('feature_columns', [])),
                        'sequence_shape': X_seq.shape,
                        'output_dim': output_dim
                    }
                }
                logger.info(f"✅ 多步预测完成，共 {output_dim} 个值")
                return result

            else:
                # ========== 单输出模式（原逻辑保持不变） ==========
                y_pred_scaled = float(y_pred[0]) if len(y_pred.shape) > 0 else float(y_pred)
                logger.info(f"📊 模型预测的标准化值: {y_pred_scaled:.6f}")
                y_pred_value = self._inverse_transform(y_pred_scaled)
                # 检查是否启用递归预测（仅当 output_dim==1 且 self.recursive_forecast 存在且 enabled）
                if hasattr(self, 'recursive_forecast') and self.recursive_forecast and self.recursive_forecast.get(
                        'enabled'):
                    steps = self.recursive_forecast.get('steps', 24)
                    logger.info(f"🔄 递归预测模式开启，步数={steps}")
                    # 执行递归预测（代码见下文）
                    recursive_result = self._recursive_forecast(
                        X_seq, device_id, target_feature,
                        look_back, prediction_data, steps, start_time
                    )
                    return recursive_result
                y_actual = prediction_data.get('y_actual')
                if self.debug_residual and self.residual_model is not None and self.residual_lags > 0:
                    try:
                        zero_residuals = [0.0] * self.residual_lags
                        pred_no_history_scaled = self.predict(X_seq, device_id=device_id,
                                                              override_residuals=zero_residuals)
                        pred_no_history = self._inverse_transform(float(pred_no_history_scaled[0]))
                        actual_str = f"{y_actual:.4f}" if y_actual is not None else "N/A"
                        logger.warning(
                            f"🔍 残差对比 - 有历史队列: {y_pred_value:.4f}, "
                            f"无历史队列: {pred_no_history:.4f}, "
                            f"差值: {y_pred_value - pred_no_history:.4f}, "
                            f"实际值: {actual_str}"
                        )
                    except Exception as e:
                        logger.warning(f"残差对比计算失败: {e}")

                base_pred_value = self._inverse_transform(y_pred_scaled)
                if y_actual is not None:
                    self.update_prediction_history(device_id, y_pred_value, y_actual)

                correction_result = {'was_corrected': False, 'reason': 'no_correction_applied'}
                if use_correction and y_actual is not None and y_actual != 0:
                    deviation_pct = self.calculate_deviation_percentage(y_pred_value, y_actual)
                    logger.info(f"📈 预测偏差: {deviation_pct:.1f}%")
                    if deviation_pct > self.correction_config['threshold_percentage']:
                        logger.info(f"🚨 偏差超过{self.correction_config['threshold_percentage']}%，进行校正")
                        correction_result = self.apply_bias_correction(
                            device_id=device_id,
                            predicted_value=y_pred_value,
                            target_feature=target_feature,
                            device_status='on'
                        )
                        if correction_result['was_corrected']:
                            y_pred_value = correction_result['corrected_value']
                            logger.info(
                                f"✅ 校正应用: 原始={y_pred_value:.2f}, 校正后={y_pred_value:.2f}, 因子={correction_result['correction_factor']:.3f}")
                    else:
                        correction_result = {'was_corrected': False,
                                             'reason': f'deviation_within_threshold_{deviation_pct:.1f}%'}
                        logger.info(f"✅ 偏差在允许范围内({deviation_pct:.1f}%)，无需校正")
                else:
                    if y_actual is None:
                        logger.warning("⚠️ 无实际值，无法进行偏差校正")
                    else:
                        logger.info("⚠️ 校正功能已禁用或实际值为0")

                y_pred_value = self.apply_physical_constraints(y_pred_value, target_feature)
                y_actual_for_display = y_actual if y_actual is None else self.round_to_decimal(y_actual, target_feature)
                prediction_time = datetime.now() + timedelta(minutes=5)
                target_mapping = prediction_data.get('target_mapping')
                save_success = self.save_prediction_to_mysql(
                    device_id=device_id,
                    target_feature=target_feature,
                    target_mapping=target_mapping,
                    prediction_value=y_pred_value,
                    prediction_time=prediction_time,
                    actual_value=y_actual,
                    device_status='on'
                )
                prediction_record = {
                    'device_id': device_id,
                    'target_feature': target_feature,
                    'prediction_value': y_pred_value,
                    'actual_value': y_actual_for_display,
                    'prediction_time': prediction_time,
                    'timestamp': datetime.now(),
                    'save_success': save_success,
                    'device_status': 'on',
                    'model_output_scaled': y_pred_scaled,
                    'correction_info': correction_result
                }
                self.predictions_history.append(prediction_record)
                if len(self.predictions_history) > 1000:
                    self.predictions_history = self.predictions_history[-1000:]

                execution_time = time.time() - start_time
                result = {
                    'success': True,
                    'device_id': device_id,
                    'target_feature': target_feature,
                    'target_feature_id': self.active_target_feature_id,
                    'prediction': y_pred_value,
                    'prediction_scaled': y_pred_scaled,
                    'actual': y_actual_for_display,
                    'prediction_time': prediction_time.isoformat(),
                    'execution_time_seconds': execution_time,
                    'save_success': save_success,
                    'device_status': 'on',
                    'correction_info': correction_result,
                    'data_info': {
                        'look_back': prediction_data.get('look_back', look_back),
                        'feature_count': len(prediction_data.get('feature_columns', [])),
                        'sequence_shape': X_seq.shape
                    }
                }
                if y_actual_for_display is not None and y_actual_for_display != 0:
                    error_percent = abs((y_pred_value - y_actual_for_display) / y_actual_for_display * 100)
                    logger.info(
                        f"✅ 预测完成: 预测值={y_pred_value:.4f}, 实际值={y_actual_for_display}, 误差={error_percent:.1f}%")
                    if correction_result['was_corrected']:
                        logger.info(f"  校正信息: {correction_result['reason']}")
                else:
                    logger.info(f"✅ 预测完成: 预测值={y_pred_value:.4f}")
                return result

        except Exception as e:
            logger.error(f"❌ 预测执行失败: {e}", exc_info=True)
            result_err = {
                'success': False,
                'error': str(e),
                'device_id': device_id,
                'target_feature': target_feature
            }
            self._log_prediction_result(result_err, start_time)
            return result_err

    def _inverse_transform(self, scaled_value):
        """
        逆标准化，支持标量或数组，兼容单输出（标量统计量）和多输出（数组统计量）
        """
        try:
            # 处理数组输入（多输出预测结果）
            if isinstance(scaled_value, np.ndarray):
                mean = getattr(self, 'target_mean', None)
                std = getattr(self, 'target_std', None)

                if mean is not None and std is not None:
                    # 如果统计量是标量，直接广播
                    if not isinstance(mean, np.ndarray):
                        result = scaled_value * std + mean
                    else:
                        # 多输出数组：要求长度匹配
                        if len(mean) == len(scaled_value):
                            result = scaled_value * std + mean
                        else:
                            logger.error(
                                f"❌ 逆变换维度不匹配: scaled_value长度={len(scaled_value)}, 统计量长度={len(mean)}")
                            # 降级：只使用第一个统计量
                            result = scaled_value * std[0] + mean[0]
                    logger.debug(f"✅ 向量化逆变换: shape={result.shape}")
                    return result
                else:
                    logger.info(f"ℹ️ 无scaler/统计量，直接返回数组: shape={scaled_value.shape}")
                    return scaled_value
            else:
                # 标量处理
                return self._inverse_transform_single(scaled_value)
        except Exception as e:
            logger.error(f"❌ 逆变换失败: {e}", exc_info=True)
            return scaled_value

    def _save_multistep_predictions(
            self,
            device_id: int,
            target_feature: str,
            target_mapping,
            prediction_values: np.ndarray,
            forecast_start_time: datetime,
            step_minutes: int = 60,
            actual_values: Optional[np.ndarray] = None,
            device_status: str = 'on'
    ) -> bool:
        try:
            if not target_mapping:
                logger.error("❌ 未提供目标特征映射")
                return False

            base_table_name = target_mapping.table_name
            prediction_table = f"pre-multistep_{base_table_name}"
            engine = self._get_target_database_connection(device_id, target_feature)
            if engine is None:
                return False

            # 创建表（如果不存在）
            create_sql = f"""
            CREATE TABLE IF NOT EXISTS `{prediction_table}` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `DeviceID` INT NOT NULL,
                `TargetFeatureID` INT NOT NULL,
                `ForecastStartTime` DATETIME NOT NULL,
                `StepMinutes` INT DEFAULT 60,
                `PredictionArray` JSON NOT NULL,
                `ActualArray` JSON DEFAULT NULL,
                `PredictionTime` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `DeviceStatus` VARCHAR(10) DEFAULT 'on',
                `CreatedAt` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY `uk_device_feature_start` (`DeviceID`, `TargetFeatureID`, `ForecastStartTime`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            with engine.connect() as conn:
                conn.execute(text(create_sql))
                conn.commit()

            # 四舍五入数组元素
            rounded_values = [self.round_to_decimal(v, target_feature) for v in prediction_values]
            prediction_json = json.dumps(rounded_values)

            actual_json = None
            if actual_values is not None:
                actual_rounded = [self.round_to_decimal(v, target_feature) for v in actual_values]
                actual_json = json.dumps(actual_rounded)

            # 插入或替换（使用 ON DUPLICATE KEY UPDATE）
            upsert_sql = f"""
            INSERT INTO `{prediction_table}`
            (DeviceID, TargetFeatureID, ForecastStartTime, StepMinutes, PredictionArray, ActualArray, PredictionTime, DeviceStatus)
            VALUES (:device_id, :target_feature_id, :forecast_start, :step_minutes, :pred_array, :actual_array, NOW(), :device_status)
            ON DUPLICATE KEY UPDATE
            PredictionArray = VALUES(PredictionArray),
            ActualArray = VALUES(ActualArray),
            PredictionTime = VALUES(PredictionTime),
            DeviceStatus = VALUES(DeviceStatus)
            """
            with engine.connect() as conn:
                conn.execute(
                    text(upsert_sql),
                    {
                        'device_id': device_id,
                        'target_feature_id': getattr(self, 'active_target_feature_id', 0),
                        'forecast_start': forecast_start_time,
                        'step_minutes': step_minutes,
                        'pred_array': prediction_json,
                        'actual_array': actual_json,
                        'device_status': device_status
                    }
                )
                conn.commit()

            logger.info(f"✅ 多步预测数组已保存到 {prediction_table}，共 {len(prediction_values)} 个值")
            return True

        except Exception as e:
            logger.error(f"❌ 保存多步预测失败: {e}", exc_info=True)
            return False

    def _inverse_transform_single(self, scaled_value: float) -> float:
        """标量逆变换（兼容标量统计量和多输出统计量取第一个值）"""
        try:
            # 方法1：优先使用scaler对象
            if hasattr(self, 'scaler') and self.scaler is not None:
                try:
                    input_data = np.array([[scaled_value]])
                    result = self.scaler.inverse_transform(input_data)[0][0]
                    logger.debug(f"✅ scaler逆变换: {scaled_value:.6f} -> {result:.4f}")
                    return result
                except Exception as e:
                    logger.warning(f"⚠️ scaler逆变换失败: {e}")

            # 方法2：使用保存的统计量
            mean = getattr(self, 'target_mean', None)
            std = getattr(self, 'target_std', None)
            if mean is not None and std is not None:
                # 如果是数组，取第一个元素（用于单值预测或第一个步长）
                if isinstance(mean, np.ndarray):
                    mean = mean[0] if len(mean) > 0 else 0.0
                if isinstance(std, np.ndarray):
                    std = std[0] if len(std) > 0 else 1.0
                if std > 0:
                    result = scaled_value * std + mean
                    logger.debug(f"✅ 统计量逆变换: {scaled_value:.6f} -> {result:.4f}")
                    return result

            logger.info(f"ℹ️ 无scaler/统计量，直接返回: {scaled_value:.4f}")
            return scaled_value
        except Exception as e:
            logger.error(f"❌ 逆变换失败: {e}")
            return scaled_value

    def _validate_prediction_value(self, value: float) -> bool:
        """验证预测值是否合理"""
        if value is None or np.isnan(value) or np.isinf(value):
            return False

        # 检查是否在合理范围内（根据物理约束）
        feature_type = self.detect_feature_type(self.active_target_feature or 'power')
        constraints = self.physical_constraints.get(feature_type, self.physical_constraints['default'])

        if value < constraints['min'] * 0.5 or value > constraints['max'] * 1.5:
            logger.warning(
                f"⚠️ 预测值超出合理范围: {value:.2f}, 期望范围: [{constraints['min']}, {constraints['max']}]")
            return False

        return True

    def _apply_physical_constraints(self, y_pred: float, target_feature: str) -> float:
        """应用物理约束"""
        if not target_feature:
            return max(y_pred, 0)

        feature_lower = target_feature.lower()

        if 'power' in feature_lower:
            if y_pred < 0:
                clamped = 0
                logger.info(f"⚡ 功率负值调整为0: {y_pred:.4f} -> 0")
            elif y_pred > 300:
                clamped = min(y_pred, 200)
                logger.warning(f"⚡ 功率过大限制为200: {y_pred:.4f} -> {clamped:.4f}")
            else:
                clamped = y_pred

        elif 'temp' in feature_lower or 'temperature' in feature_lower:
            clamped = max(min(y_pred, 50), -20)
            if clamped != y_pred:
                logger.info(f"🌡️ 温度约束调整: {y_pred:.4f} -> {clamped:.4f}")

        elif 'pressure' in feature_lower:
            clamped = max(y_pred, 0)
            if y_pred < 0:
                logger.info(f"💨 压力负值调整为0: {y_pred:.4f} -> 0")
            else:
                clamped = y_pred

        else:
            clamped = max(y_pred, 0)
            if y_pred < 0:
                logger.info(f"📊 负值调整为0: {y_pred:.4f} -> 0")

        return clamped

    def start_periodic_prediction(
            self,
            device_id: int = None,
            target_feature: str = None,
            interval_minutes: int = 5,
            look_back: int = None,
            enable_correction: bool = False  # 新增参数，默认启用校正
    ) -> bool:
        """启动周期性预测"""
        if self.is_running:
            logger.warning("⚠️ 预测器已经在运行中")
            return False

        # 使用已保存的配置或参数
        if device_id is None and self.active_device_id:
            device_id = self.active_device_id
        elif device_id is None:
            logger.error("❌ 未提供设备ID")
            return False

        # 优先使用已保存的配置
        if target_feature is None and self.active_target_feature:
            target_feature = self.active_target_feature
        elif target_feature is None:
            target_feature = "PointValue"

        if look_back is None and self.active_look_back:
            look_back = self.active_look_back
        elif look_back is None:
            look_back = 24

        # 保存配置信息
        self.active_device_id = device_id
        self.active_target_feature = target_feature
        self.active_look_back = look_back

        # 启用校正
        if enable_correction:
            logger.info(f"🎯 启用预测校正机制，阈值={self.correction_config['threshold_percentage']}%")

        self.is_running = True

        def prediction_job():
            """预测任务"""
            try:
                logger.info(f"⏰ 执行定时预测任务 - 设备 {device_id}")
                result = self.make_prediction(device_id, target_feature, look_back, use_correction=enable_correction)
                if result.get('success'):
                    device_status = result.get('device_status', 'unknown')
                    if device_status == 'off':
                        logger.info(f"✅ 设备关机状态检测，预测值为0")
                    else:
                        pred_value = result.get('prediction', 0)
                        actual_value = result.get('actual')
                        correction_info = result.get('correction_info', {})

                        if actual_value is not None and actual_value != 0:
                            error_pct = abs((pred_value - actual_value) / actual_value * 100)

                            if correction_info.get('was_corrected', False):
                                logger.info(f"✅ 预测完成: 预测值={pred_value:.2f}, 误差={error_pct:.1f}% (已校正)")
                            else:
                                logger.info(f"✅ 预测完成: 预测值={pred_value:.2f}, 误差={error_pct:.1f}% (未校正)")
                        else:
                            logger.info(f"✅ 预测完成: 预测值={pred_value:.2f}")
                else:
                    logger.error(f"❌ 定时预测失败: {result.get('error', '未知错误')}")
            except Exception as e:
                logger.error(f"❌ 定时预测任务异常: {e}")

        def run_scheduler():
            """运行调度器"""
            # 立即执行一次
            logger.info(f"🚀 启动预测器，立即执行第一次预测... (look_back={look_back})")
            prediction_job()

            # 设置定时任务
            schedule.every(interval_minutes).minutes.do(prediction_job)

            logger.info(f"⏰ 启动周期性预测，每 {interval_minutes} 分钟执行一次")

            while self.is_running:
                try:
                    schedule.run_pending()
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"❌ 调度器运行异常: {e}")
                    time.sleep(5)

            logger.info("🛑 预测器已停止")

        # 启动预测线程
        self.prediction_thread = threading.Thread(
            target=run_scheduler,
            daemon=True,
            name=f"Predictor-Device-{device_id}"
        )
        self.prediction_thread.start()

        logger.info(f"✅ 已启动设备 {device_id} 的周期性预测")
        return True

    def stop_periodic_prediction(self):
        """停止周期性预测"""
        self.is_running = False
        if self.prediction_thread and self.prediction_thread.is_alive():
            self.prediction_thread.join(timeout=5)
        logger.info("🛑 周期性预测已停止")

    def get_prediction_history(self, limit: int = 100) -> List[Dict]:
        """获取预测历史"""
        return self.predictions_history[-limit:] if self.predictions_history else []

    def get_model_info(self) -> Dict:
        """获取模型信息"""
        return self.model_info

    def get_active_config(self) -> Dict:
        """获取当前激活的配置"""
        return {
            'device_id': self.active_device_id,
            'target_feature': self.active_target_feature,
            'target_feature_id': self.active_target_feature_id,
            'model_version_id': self.active_model_version_id,
            'look_back': self.active_look_back,
            'is_running': self.is_running,
            'model_loaded': self.model is not None,
            'has_residual_model': self.residual_model is not None,
            'connection_cache_size': len(self.connection_cache)
        }

    def cleanup_connections(self):
        """清理数据库连接"""
        try:
            logger.info(f"清理数据库连接缓存，当前数量: {len(self.connection_cache)}")

            # 关闭所有引擎连接
            for cache_key, connection_info in list(self.connection_cache.items()):
                try:
                    engine = connection_info.get('engine')
                    if engine:
                        engine.dispose()
                    logger.debug(f"已关闭数据库连接: {cache_key}")
                except Exception as e:
                    logger.warning(f"关闭数据库连接失败 {cache_key}: {e}")

                # 移除缓存
                del self.connection_cache[cache_key]

            logger.info("✅ 数据库连接已清理")

        except Exception as e:
            logger.error(f"清理数据库连接失败: {e}")


# 单例模式
_predictor = None

def get_predictor() -> XGBoostPredictor:
    """获取预测器单例"""
    global _predictor
    if _predictor is None:
        _predictor = XGBoostPredictor()
    return _predictor