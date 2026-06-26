"""
数据预处理器 - 用于时间序列数据的预处理和特征工程 backend/ml/data/preprocessor.py
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging
from sklearn.preprocessing import StandardScaler, MinMaxScaler
import warnings

warnings.filterwarnings('ignore')

logger = logging.getLogger(__name__)


class TimeSeriesPreprocessor:
    """时间序列预处理器"""

    def __init__(self):
        self.scalers = {}  # 存储每个特征的缩放器
        self.feature_stats = {}  # 存储特征统计信息

    def _validate_data(self, df: pd.DataFrame) -> bool:
        """验证数据有效性"""
        if df is None or df.empty:
            logger.error("数据为空")
            return False

        if len(df) < 10:  # 最小数据量要求
            logger.warning(f"数据量不足，只有 {len(df)} 条记录")
            return False

        # 检查索引是否为时间戳
        if not isinstance(df.index, pd.DatetimeIndex):
            logger.error("数据索引必须是时间戳")
            return False

        return True

    def handle_missing_values(
            self,
            df: pd.DataFrame,
            method: str = 'interpolate',
            max_missing_rate: float = 0.95,  # 新增参数：最大允许缺失率
            fill_value: float = 0.0
    ) -> pd.DataFrame:
        """处理缺失值"""
        if df is None or df.empty:
            return df

        df_processed = df.copy()
        dropped_features = []
        kept_features = []

        for column in df_processed.columns:
            # 计算缺失率
            missing_rate = df_processed[column].isna().sum() / len(df_processed)

            if missing_rate > max_missing_rate:
                # 缺失率过高，删除该列
                logger.warning(f"特征 {column} 缺失率过高 ({missing_rate:.1%} > {max_missing_rate:.0%})，已删除")
                dropped_features.append(column)
                continue

            kept_features.append(column)

            if missing_rate > 0:
                logger.info(f"特征 {column} 缺失率: {missing_rate:.1%}，使用 {method} 方法填充")

            if method == 'interpolate':
                # 尝试不同的插值方法
                try:
                    # 先尝试时间序列插值
                    df_processed[column] = df_processed[column].interpolate(
                        method='time',
                        limit=int(10 * (1 - missing_rate)),  # 根据缺失率调整限制
                        limit_direction='both'
                    )
                except:
                    # 如果时间插值失败，使用线性插值
                    df_processed[column] = df_processed[column].interpolate(
                        method='linear',
                        limit=10,
                        limit_direction='both'
                    )

                # 剩余的NaN用前后值填充
                df_processed[column] = df_processed[column].ffill().bfill()

                # 如果还有缺失值，用均值填充
                if df_processed[column].isna().any():
                    mean_val = df_processed[column].mean()
                    df_processed[column] = df_processed[column].fillna(mean_val)

            elif method == 'forward_fill':
                # 前向填充
                df_processed[column] = df_processed[column].ffill(limit=10).bfill()
                if df_processed[column].isna().any():
                    df_processed[column] = df_processed[column].fillna(fill_value)

            elif method == 'mean':
                # 用均值填充
                mean_val = df_processed[column].mean()
                df_processed[column] = df_processed[column].fillna(mean_val)
            else:
                # 用指定值填充
                df_processed[column] = df_processed[column].fillna(fill_value)

            # 最后检查是否还有缺失值
            if df_processed[column].isna().any():
                df_processed[column] = df_processed[column].fillna(fill_value)
                logger.warning(f"特征 {column} 仍有缺失值，已用 {fill_value} 填充")

        # 删除指定列
        if dropped_features:
            df_processed = df_processed.drop(columns=dropped_features)

        # 删除全是NaN的行
        df_processed = df_processed.dropna(how='all')

        logger.info(
            f"缺失值处理完成: 原始 {len(df.columns)} 个特征，删除 {len(dropped_features)} 个，保留 {len(kept_features)} 个")
        logger.info(f"数据量: 原始 {len(df)} 条，处理后 {len(df_processed)} 条")

        return df_processed

    def remove_outliers(
            self,
            df: pd.DataFrame,
            method: str = 'iqr',
            threshold: float = 3.0
    ) -> pd.DataFrame:
        """去除异常值"""
        if df is None or df.empty:
            return df

        df_processed = df.copy()

        for column in df_processed.columns:
            if df_processed[column].dtype in [np.float64, np.int64]:
                if method == 'iqr':
                    # IQR方法
                    Q1 = df_processed[column].quantile(0.25)
                    Q3 = df_processed[column].quantile(0.75)
                    IQR = Q3 - Q1
                    lower_bound = Q1 - threshold * IQR
                    upper_bound = Q3 + threshold * IQR

                    # 将异常值替换为边界值
                    df_processed[column] = df_processed[column].clip(lower_bound, upper_bound)

                elif method == 'zscore':
                    # Z-score方法
                    mean = df_processed[column].mean()
                    std = df_processed[column].std()

                    if std > 0:  # 避免除零
                        z_scores = np.abs((df_processed[column] - mean) / std)
                        outliers = z_scores > threshold

                        if outliers.any():
                            # 用中位数替换异常值
                            median = df_processed[column].median()
                            df_processed.loc[outliers, column] = median
                            logger.info(f"特征 {column} 移除了 {outliers.sum()} 个异常值")

        return df_processed

    def create_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """创建时间特征"""
        if df is None or df.empty:
            return df

        df_enhanced = df.copy()

        # 提取时间特征
        df_enhanced['hour'] = df_enhanced.index.hour
        df_enhanced['day_of_week'] = df_enhanced.index.dayofweek
        df_enhanced['day_of_month'] = df_enhanced.index.day
        df_enhanced['month'] = df_enhanced.index.month
        df_enhanced['is_weekend'] = (df_enhanced['day_of_week'] >= 5).astype(int)

        # 创建周期特征（正弦余弦编码）
        df_enhanced['hour_sin'] = np.sin(2 * np.pi * df_enhanced['hour'] / 24)
        df_enhanced['hour_cos'] = np.cos(2 * np.pi * df_enhanced['hour'] / 24)
        df_enhanced['day_sin'] = np.sin(2 * np.pi * df_enhanced['day_of_week'] / 7)
        df_enhanced['day_cos'] = np.cos(2 * np.pi * df_enhanced['day_of_week'] / 7)

        logger.info(f"创建了 {len(df_enhanced.columns) - len(df.columns)} 个时间特征")
        return df_enhanced

    def create_lag_features(
            self,
            df: pd.DataFrame,
            target_column: str,
            lag_periods: List[int] = [1, 2, 3, 6, 12, 24]
    ) -> pd.DataFrame:
        """创建滞后特征"""
        if df is None or df.empty or target_column not in df.columns:
            return df

        df_lagged = df.copy()

        # 为目标特征创建滞后特征
        for lag in lag_periods:
            df_lagged[f'{target_column}_lag_{lag}'] = df_lagged[target_column].shift(lag)

        # 删除包含NaN的行（由于shift操作）
        df_lagged = df_lagged.dropna()

        logger.info(f"为目标特征 {target_column} 创建了 {len(lag_periods)} 个滞后特征")
        return df_lagged

    def create_rolling_features(
            self,
            df: pd.DataFrame,
            target_column: str,
            windows: List[int] = [3, 6, 12, 24]
    ) -> pd.DataFrame:
        """创建滚动统计特征"""
        if df is None or df.empty or target_column not in df.columns:
            return df

        df_rolling = df.copy()

        for window in windows:
            df_rolling[f'{target_column}_roll_mean_{window}'] = (
                df_rolling[target_column].rolling(window=window, min_periods=1).mean()
            )
            df_rolling[f'{target_column}_roll_std_{window}'] = (
                df_rolling[target_column].rolling(window=window, min_periods=1).std()
            )
            df_rolling[f'{target_column}_roll_min_{window}'] = (
                df_rolling[target_column].rolling(window=window, min_periods=1).min()
            )
            df_rolling[f'{target_column}_roll_max_{window}'] = (
                df_rolling[target_column].rolling(window=window, min_periods=1).max()
            )

        # 填充滚动特征的NaN值（使用当前值填充）
        rolling_columns = [col for col in df_rolling.columns if 'roll_' in col]
        for col in rolling_columns:
            df_rolling[col] = df_rolling[col].ffill().bfill()

        logger.info(f"为目标特征 {target_column} 创建了 {len(windows) * 4} 个滚动特征")
        return df_rolling

    def scale_features(
            self,
            df: pd.DataFrame,
            method: str = 'standard',
            fit_on_train: bool = True,
            feature_columns: Optional[List[str]] = None,
            return_scalers: bool = True  # 新增参数
    ) -> Tuple[pd.DataFrame, Dict]:
        """特征缩放"""
        if df is None or df.empty:
            return df, {}

        df_scaled = df.copy()

        # 确定需要缩放的特征列
        if feature_columns is None:
            # 排除时间特征和已经创建的特征
            time_features = ['hour', 'day_of_week', 'day_of_month', 'month', 'is_weekend',
                             'hour_sin', 'hour_cos', 'day_sin', 'day_cos']
            feature_columns = [col for col in df.columns if col not in time_features]

        # 存储缩放器
        scalers = {}

        for column in feature_columns:
            if column in df_scaled.columns and df_scaled[column].dtype in [np.float64, np.int64]:
                if method == 'standard':
                    scaler = StandardScaler()
                elif method == 'minmax':
                    scaler = MinMaxScaler()
                else:
                    logger.warning(f"未知的缩放方法: {method}，使用标准化")
                    scaler = StandardScaler()

                # 拟合和转换
                if fit_on_train or column not in self.scalers:
                    scaler.fit(df_scaled[[column]])
                    self.scalers[column] = scaler
                else:
                    scaler = self.scalers[column]

                df_scaled[column] = scaler.transform(df_scaled[[column]])

                # 如果是目标特征，返回scaler
                if return_scalers:
                    scalers[column] = scaler  # 直接保存scaler对象，而不是字典

        logger.info(f"缩放完成，处理了 {len(feature_columns)} 个特征")
        return df_scaled, scalers

    def prepare_for_training(
            self,
            data_dict: Dict[str, pd.DataFrame],
            target_feature: str,
            look_back: int = 24,
            forecast_horizon: int = 1
    ) -> Dict[str, np.ndarray]:
        """准备训练数据（转换为监督学习格式），支持多步预测"""
        try:
            train_df = data_dict.get('train_data')
            test_df = data_dict.get('test_data')

            if train_df is None or train_df.empty:
                logger.error("训练数据为空")
                return {}

            # 确保目标特征存在
            if target_feature not in train_df.columns:
                logger.error(f"目标特征 {target_feature} 不在训练数据中")
                return {}

            # 确保索引是 DatetimeIndex（便于时间序列切片）
            if not isinstance(train_df.index, pd.DatetimeIndex):
                logger.warning("训练数据索引不是 DatetimeIndex，尝试转换")
                train_df.index = pd.to_datetime(train_df.index)
            if test_df is not None and not test_df.empty and not isinstance(test_df.index, pd.DatetimeIndex):
                test_df.index = pd.to_datetime(test_df.index)

            # 特征列（排除目标特征）
            feature_columns = [col for col in train_df.columns if col != target_feature]

            def create_sequences(
                    data: pd.DataFrame,
                    features: List[str],
                    target: str,
                    look_back: int,
                    horizon: int
            ) -> Tuple[np.ndarray, np.ndarray]:
                """创建时间序列数据，支持多步"""
                X, y = [], []
                missing_features = [f for f in features if f not in data.columns]
                if missing_features:
                    logger.error(f"以下特征不在数据中: {missing_features}")
                    return np.array([]), np.array([])

                required = look_back + horizon
                if len(data) < required:
                    logger.error(f"数据不足: 需要至少 {required} 条记录，实际 {len(data)} 条")
                    return np.array([]), np.array([])

                for i in range(look_back, len(data) - horizon + 1):
                    try:
                        # 特征窗口 (look_back 个时间步)
                        X_seq = data[features].iloc[i - look_back:i].values
                        # 目标窗口 (horizon 个未来值)
                        y_seq = data[target].iloc[i:i + horizon].values
                        # 确保 y_seq 是一维（长度 horizon）
                        if y_seq.ndim > 1:
                            y_seq = y_seq.flatten()
                        X.append(X_seq)
                        y.append(y_seq)
                    except Exception as e:
                        logger.warning(f"创建序列时出错 (i={i}): {e}")
                        continue

                if len(X) == 0:
                    logger.error("未能创建任何有效序列")
                    return np.array([]), np.array([])

                X_arr = np.array(X)
                y_arr = np.array(y)
                logger.info(f"序列构造: X.shape={X_arr.shape}, y.shape={y_arr.shape}, horizon={horizon}")
                return X_arr, y_arr

            # 创建训练集序列
            X_train, y_train = create_sequences(
                train_df, feature_columns, target_feature, look_back, forecast_horizon
            )
            if X_train.size == 0 or y_train.size == 0:
                logger.error("无法创建训练序列，可能数据不足")
                return {}

            # 创建测试集序列
            X_test, y_test = None, None
            if test_df is not None and not test_df.empty:
                X_test, y_test = create_sequences(
                    test_df, feature_columns, target_feature, look_back, forecast_horizon
                )
                if X_test.size == 0 or y_test.size == 0:
                    logger.warning("无法创建测试序列，忽略测试集")
                    X_test, y_test = None, None

            # 【兼容性处理】单步预测时，将 y 压缩为一维数组（与旧版行为一致）
            if forecast_horizon == 1:
                y_train = y_train.squeeze()  # 形状从 (n,1) 变为 (n,)
                if y_test is not None:
                    y_test = y_test.squeeze()

            logger.info(f"数据准备完成: X_train形状 {X_train.shape}, y_train形状 {y_train.shape}")
            if X_test is not None:
                logger.info(f"X_test形状 {X_test.shape}, y_test形状 {y_test.shape}")

            return {
                'X_train': X_train,
                'y_train': y_train,
                'X_test': X_test,
                'y_test': y_test,
                'feature_columns': feature_columns,
                'target_feature': target_feature,
                'look_back': look_back,
                'forecast_horizon': forecast_horizon
            }

        except Exception as e:
            logger.error(f"准备训练数据失败: {e}", exc_info=True)
            return {}

    def preprocess_pipeline(
            self,
            df: pd.DataFrame,
            target_feature: str,
            config: Optional[Dict] = None,
            fit_scaler: bool = True  # 添加参数控制是否拟合缩放器
    ) -> Dict:
        """完整的预处理流水线"""
        # 先验证数据
        if df is None or df.empty:
            logger.error("数据为空")
            return {}

        # 默认配置 - 简化版
        default_config = {
            'missing_value_method': 'interpolate',
            'outlier_method': 'iqr',
            'outlier_threshold': 3.0,
            'create_time_features': False,  # 暂时不创建时间特征
            'create_smart_time_features': False,  # 新增
            'lag_periods': [],  # 不创建滞后特征
            'rolling_windows': [],  # 不创建滚动特征
            'scaling_method': 'standard',  # 可以改成None不缩放
            'look_back': 24,
            'forecast_horizon': 1
        }

        if config:
            default_config.update(config)

        config = default_config

        logger.info("开始简化版数据预处理流水线...")
        logger.info(f"原始数据形状: {df.shape}")
        if config.get('create_smart_time_features', False):
            logger.info("创建智能时间特征...")
        # 1. 确保索引是时间戳
        if not isinstance(df.index, pd.DatetimeIndex):
            logger.warning("数据索引不是时间戳，尝试转换...")
            # 检查是否有时间列
            for col in df.columns:
                if 'time' in col.lower() or 'date' in col.lower():
                    try:
                        df.index = pd.to_datetime(df[col])
                        df = df.drop(columns=[col])
                        logger.info(f"使用列 {col} 作为时间索引")
                        break
                    except:
                        continue

        # 2. 处理缺失值
        df_processed = self.handle_missing_values(
            df, method=config['missing_value_method']
        )

        if df_processed.empty:
            logger.error("缺失值处理后数据为空")
            return {}

        # 3. 去除异常值
        df_processed = self.remove_outliers(
            df_processed,
            method=config['outlier_method'],
            threshold=config['outlier_threshold']
        )

        logger.info(f"缺失值和异常值处理后形状: {df_processed.shape}")


        # 4. 特征缩放（可选）
        if config.get('scaling_method') and config['scaling_method'] != 'none':
            logger.info(f"进行特征缩放: {config['scaling_method']}")
            df_scaled, scalers = self.scale_features(
                df_processed,
                method=config['scaling_method'],
                fit_on_train=fit_scaler  # 使用新参数
            )
        else:
            logger.info("跳过特征缩放")
            df_scaled = df_processed
            scalers = {}

        # 存储特征统计信息
        self.feature_stats = {
            'original_shape': df.shape,
            'processed_shape': df_scaled.shape,
            'features_count': len(df_scaled.columns),
            'scalers': scalers,
            'config': config
        }

        logger.info(f"预处理完成，原始数据 {df.shape} → 处理后 {df_scaled.shape}")

        return {
            'processed_data': df_scaled,
            'feature_stats': self.feature_stats,
            'target_feature': target_feature
        }
    def inverse_transform_target(self, y_pred: np.ndarray, target_feature: str) -> np.ndarray:
        """将预测值反向转换回原始尺度"""
        if target_feature in self.scalers:
            scaler = self.scalers[target_feature]['scaler']
            # 需要将一维数组转换为二维
            if len(y_pred.shape) == 1:
                y_pred_2d = y_pred.reshape(-1, 1)
            else:
                y_pred_2d = y_pred

            y_pred_inv = scaler.inverse_transform(y_pred_2d)

            # 转换回原始形状
            if len(y_pred.shape) == 1:

                return y_pred_inv.flatten()
            else:
                return y_pred_inv
        else:
            logger.warning(f"没有找到目标特征 {target_feature} 的缩放器")
            return y_pred


# 单例模式
_preprocessor = None


def get_preprocessor() -> TimeSeriesPreprocessor:
    """获取预处理器单例"""
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = TimeSeriesPreprocessor()
    return _preprocessor