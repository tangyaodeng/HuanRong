"""
MySQL数据加载器 - 用于从配置的MySQL数据源加载特征数据
backend/ml/data/loader.py
已移除文件处理功能，改为引用FileProcessor
"""

import sys
import os
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timedelta
import logging
from collections import defaultdict

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(current_dir))
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

# 导入文件处理器
from .file_processing import get_file_processor

logger = logging.getLogger(__name__)


class MySQLDataLoader:
    """MySQL数据加载器"""

    def __init__(self, db_session=None):
        self.db_session = db_session
        self._connections = {}  # 缓存MySQL连接

        # 延迟导入models，避免循环依赖
        self.models = None


        # 初始化文件处理器
        self.file_processor = get_file_processor()

        # 基础数据目录（保持向后兼容）
        self.base_data_dir = self.file_processor.base_data_dir

        # 统一时间范围配置 - 只需修改这里即可调整所有数据加载的时间范围
        self.DEFAULT_START_TIME = datetime(2025, 3, 1)
        self.DEFAULT_END_TIME = datetime(2099, 12, 31, 23, 59, 59)

        # 统一最大行数配置 - 只需修改这里即可调整所有数据加载的最大行数限制
        self.MAX_ROWS_DEFAULT = 300000

    def _get_models(self):
        """延迟导入models模块"""
        if self.models is None:
            from app import models
            self.models = models
        return self.models

    def get_device_data_config(self, device_id: int) -> Dict:
        """获取设备的数据加载配置"""
        try:
            models = self._get_models()
            config = self.db_session.query(models.DeviceDataConfig).filter(
                models.DeviceDataConfig.device_id == device_id
            ).first()

            if config:
                return {
                    'data_start_time': config.data_start_time,
                    'data_end_time': config.data_end_time,
                    'max_rows_limit': config.max_rows_limit,
                }
            else:
                # 返回默认配置
                return {
                    'data_start_time': self.DEFAULT_START_TIME,
                    'data_end_time': self.DEFAULT_END_TIME,
                    'max_rows_limit': self.MAX_ROWS_DEFAULT,
                }
        except Exception as e:
            logger.error(f"获取设备 {device_id} 数据配置失败: {e}")
            return {
                'data_start_time': self.DEFAULT_START_TIME,
                'data_end_time': self.DEFAULT_END_TIME,
                'max_rows_limit': self.MAX_ROWS_DEFAULT,
            }

    def update_device_data_config(self, device_id: int, config_data: Dict) -> bool:
        """更新设备的数据加载配置"""
        try:
            models = self._get_models()

            # 查找或创建设备配置
            config = self.db_session.query(models.DeviceDataConfig).filter(
                models.DeviceDataConfig.device_id == device_id
            ).first()

            if not config:
                config = models.DeviceDataConfig(device_id=device_id)
                self.db_session.add(config)

            # 更新配置字段
            for key, value in config_data.items():
                if hasattr(config, key) and value is not None:
                    setattr(config, key, value)

            config.updated_at = datetime.now()
            self.db_session.commit()

            logger.info(f"设备 {device_id} 数据配置已更新")
            return True

        except Exception as e:
            logger.error(f"更新设备 {device_id} 数据配置失败: {e}")
            self.db_session.rollback()
            return False
    def _get_mysql_connection(self, data_source_id: int) -> Optional[any]:
        """获取MySQL数据库连接"""
        if data_source_id in self._connections:
            return self._connections[data_source_id]

        try:
            models = self._get_models()
            # 从PostgreSQL获取数据源配置
            data_source = self.db_session.query(models.DataSources).filter(
                models.DataSources.id == data_source_id,
                models.DataSources.is_active == True
            ).first()

            if not data_source:
                logger.error(f"数据源 {data_source_id} 未找到或未启用")
                return None

            # 对密码进行URL编码，确保特殊字符正确处理
            from urllib.parse import quote_plus
            encoded_password = quote_plus(data_source.password)

            # 创建MySQL连接字符串
            connection_string = f"mysql+pymysql://{data_source.username}:{encoded_password}@{data_source.host}:{data_source.port}/{data_source.database_name}"

            logger.info(
                f"创建MySQL连接: {data_source.name} -> {data_source.host}:{data_source.port}/{data_source.database_name}")

            # 创建SQLAlchemy引擎
            engine = create_engine(
                connection_string,
                connect_args={
                    'charset': data_source.charset,
                    'connect_timeout': data_source.timeout
                },
                pool_recycle=3600,
                echo=False
            )

            self._connections[data_source_id] = engine
            return engine

        except Exception as e:
            logger.error(f"创建MySQL连接失败 (数据源ID: {data_source_id}): {e}")
            return None

    def get_device_features_mappings(self, device_id: int) -> List[Dict]:
        """获取设备的所有特征映射配置"""
        try:
            models = self._get_models()
            mappings = self.db_session.query(
                models.FeatureTableMapping,
                models.Feature,
                models.DataSources
            ).join(
                models.Feature, models.FeatureTableMapping.feature_id == models.Feature.id
            ).join(
                models.DataSources, models.FeatureTableMapping.data_source_id == models.DataSources.id
            ).filter(
                models.FeatureTableMapping.device_id == device_id,
                models.FeatureTableMapping.is_active == True
            ).all()

            result = []
            for mapping, feature, data_source in mappings:
                result.append({
                    'mapping_id': mapping.id,
                    'feature_id': feature.id,
                    'feature_name': feature.name,
                    'feature_code': feature.code,
                    'data_type': feature.data_type,
                    'unit': feature.unit,
                    'data_source_id': data_source.id,
                    'data_source_name': data_source.name,
                    'database_name': mapping.database_name,
                    'table_name': mapping.table_name,
                    'column_name': mapping.column_name,
                    'timestamp_column': mapping.timestamp_column,
                    'last_sync_at': mapping.last_sync_at
                })

            return result

        except Exception as e:
            logger.error(f"获取设备 {device_id} 的特征映射失败: {e}")
            return []

    def steady_state_identification(
            self,
            df: pd.DataFrame,
            power_column: str = 'real_time_power_of_host_meter_1',
            window: int = 4,
            threshold_pct: float = 0.01
    ) -> pd.DataFrame:
        """
        稳态数据识别
        通过连续window行主机功率的变化来判断

        参数:
        ----------
        df : pd.DataFrame
            输入数据框，索引应为时间戳
        power_column : str
            主机功率列名，默认为 'real_time_power_of_host_meter_1'
        window : int
            滑动窗口大小，默认4行（对应约20分钟，如果是5分钟间隔）
        threshold_pct : float
            功率变化阈值百分比，默认1%

        返回:
        ----------
        pd.DataFrame: 稳态数据
        """
        logger.info("\n开始稳态数据识别...")

        # 检查功率列是否存在
        if power_column not in df.columns:
            logger.error(f"❌ 功率列 '{power_column}' 不存在于数据中")
            available_columns = df.columns.tolist()
            logger.info(f"可用列: {available_columns}")
            return df

        logger.info(f"使用 '{power_column}' 列进行稳态识别")
        logger.info(f"窗口大小: {window} 行")
        logger.info(f"功率变化阈值: {threshold_pct * 100}%")

        # 获取功率数据
        power_data = df[power_column]

        # 计算功率变化率（绝对变化量）
        power_change = power_data.diff().abs()

        # 计算滚动窗口内的平均变化
        rolling_change = power_change.rolling(window=window, center=True).mean()

        # 计算功率的平均值作为参考
        power_mean = power_data.mean()

        # 判断稳态：窗口内平均变化小于阈值百分比 * 平均值
        if power_mean > 0:
            is_steady = (rolling_change < threshold_pct * power_mean)
        else:
            logger.warning("功率平均值为0或负值，无法进行百分比计算")
            # 使用绝对阈值替代
            absolute_threshold = 0.5  # 0.5 kW的绝对变化阈值
            is_steady = (rolling_change < absolute_threshold)

        # 将布尔序列转换为稳态标志，填充NaN值为False
        steady_flags = is_steady.fillna(False)

        # 提取稳态数据
        steady_state_df = df[steady_flags].copy()

        # 统计信息
        original_count = len(df)
        steady_count = len(steady_state_df)
        steady_percentage = (steady_count / original_count * 100) if original_count > 0 else 0

        logger.info(f"✅ 稳态识别完成")
        logger.info(f"  原始数据: {original_count} 条")
        logger.info(f"  稳态数据: {steady_count} 条 ({steady_percentage:.1f}%)")

        # 如果有稳态数据，显示统计信息
        if steady_count > 0:
            # 功率统计
            original_power_stats = {
                'min': power_data.min(),
                'max': power_data.max(),
                'mean': power_data.mean(),
                'std': power_data.std()
            }

            steady_power_stats = {
                'min': steady_state_df[power_column].min(),
                'max': steady_state_df[power_column].max(),
                'mean': steady_state_df[power_column].mean(),
                'std': steady_state_df[power_column].std()
            }

            logger.info(f"功率统计 - 原始数据:")
            logger.info(f"  最小值: {original_power_stats['min']:.2f}")
            logger.info(f"  最大值: {original_power_stats['max']:.2f}")
            logger.info(f"  平均值: {original_power_stats['mean']:.2f}")
            logger.info(f"  标准差: {original_power_stats['std']:.2f}")

            logger.info(f"功率统计 - 稳态数据:")
            logger.info(f"  最小值: {steady_power_stats['min']:.2f}")
            logger.info(f"  最大值: {steady_power_stats['max']:.2f}")
            logger.info(f"  平均值: {steady_power_stats['mean']:.2f}")
            logger.info(f"  标准差: {steady_power_stats['std']:.2f}")

            # 计算标准差减少比例
            if original_power_stats['std'] > 0:
                std_reduction = (original_power_stats['std'] - steady_power_stats['std']) / original_power_stats[
                    'std'] * 100
                logger.info(f"✅ 功率标准差减少: {std_reduction:.1f}%")

        return steady_state_df

    def low_power_filter(
            self,
            df: pd.DataFrame,
            power_column: str = 'real_time_power_of_host_meter_1',
            min_power_pct: float = 0.2
    ) -> pd.DataFrame:
        """
        低功率数据过滤 - 基于特定功率特征进行过滤
        只使用real_time_power_of_host_meter_3特征进行过滤，如果没有则跳过过滤

        参数:
        ----------
        df : pd.DataFrame
            输入数据框
        power_column : str
            功率列名，默认为 'real_time_power_of_host_meter_1'
        min_power_pct : float
            最小功率比例，过滤掉功率小于最大功率 * min_power_pct 的数据
            默认0.2，即过滤掉小于最大功率20%的数据

        返回:
        ----------
        pd.DataFrame: 过滤后的数据
        """
        logger.info("\n开始低功率数据过滤...")

        # 检查功率列是否存在
        if power_column not in df.columns:
            logger.warning(f"⚠️ 功率列 '{power_column}' 不存在于数据中，跳过低功率过滤")
            return df

        logger.info(f"使用 '{power_column}' 列进行低功率过滤")

        # 获取功率数据
        power_data = df[power_column]

        # 计算最大功率
        max_power = power_data.max()
        logger.info(f"最大功率: {max_power:.2f}")

        # 计算最小功率阈值
        min_power_threshold = max_power * min_power_pct
        logger.info(f"最小功率阈值: {min_power_threshold:.2f} (最大功率的 {min_power_pct * 100:.0f}%)")

        # 统计原始数据中低功率数据的比例
        low_power_count = (power_data < min_power_threshold).sum()
        total_count = len(df)
        low_power_percentage = (low_power_count / total_count * 100) if total_count > 0 else 0

        logger.info(f"低功率数据统计:")
        logger.info(f"  总数据量: {total_count} 条")
        logger.info(f"  低功率数据: {low_power_count} 条 ({low_power_percentage:.1f}%)")

        # 过滤低功率数据
        filtered_df = df[power_data >= min_power_threshold].copy()

        # 统计过滤后数据
        filtered_count = len(filtered_df)
        filtered_percentage = (filtered_count / total_count * 100) if total_count > 0 else 0

        logger.info(f"✅ 低功率过滤完成")
        logger.info(f"  原始数据: {total_count} 条")
        logger.info(f"  过滤后数据: {filtered_count} 条 ({filtered_percentage:.1f}%)")

        # 显示过滤前后功率统计对比
        if filtered_count > 0:
            original_power_stats = {
                'min': power_data.min(),
                'max': power_data.max(),
                'mean': power_data.mean(),
                'std': power_data.std()
            }

            filtered_power_stats = {
                'min': filtered_df[power_column].min(),
                'max': filtered_df[power_column].max(),
                'mean': filtered_df[power_column].mean(),
                'std': filtered_df[power_column].std()
            }

            logger.info(f"功率统计 - 原始数据:")
            logger.info(f"  范围: {original_power_stats['min']:.2f} - {original_power_stats['max']:.2f}")
            logger.info(f"  平均值: {original_power_stats['mean']:.2f}")
            logger.info(f"  标准差: {original_power_stats['std']:.2f}")

            logger.info(f"功率统计 - 过滤后数据:")
            logger.info(f"  范围: {filtered_power_stats['min']:.2f} - {filtered_power_stats['max']:.2f}")
            logger.info(f"  平均值: {filtered_power_stats['mean']:.2f}")
            logger.info(f"  标准差: {filtered_power_stats['std']:.2f}")

            # 计算平均值变化
            if original_power_stats['mean'] > 0:
                mean_increase = (filtered_power_stats['mean'] - original_power_stats['mean']) / original_power_stats[
                    'mean'] * 100
                logger.info(f"✅ 平均功率增加: {mean_increase:.1f}%")

        return filtered_df

    def load_feature_data(
            self,
            data_source_id: int,
            database_name: str,
            table_name: str,
            timestamp_column: str = 'UpdateDateTime',
            value_column: str = 'PointValue',
            device_id: Optional[int] = None,  # 新增：设备ID参数
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
            max_rows: Optional[int] = None
    ) -> Optional[pd.DataFrame]:
        """加载单个特征表的数据"""
        try:
            # 获取设备配置（如果有设备ID）
            if device_id is not None:
                logger.warning(f"有设备ID")
                device_config = self.get_device_data_config(device_id)
                max_rows = device_config.get('max_rows_limit') or self.MAX_ROWS_DEFAULT
                logger.warning(f"加载最大行数成功")
                start_time = device_config.get('data_start_time') or self.DEFAULT_START_TIME
                logger.warning(f"加载起始时间成功")
                end_time = device_config.get('data_end_time') or self.DEFAULT_END_TIME
                logger.warning(f"加载终止时间成功")
            else:
                logger.warning(f"使用默认配置时间")
                # 使用默认配置
                if max_rows is None:
                    max_rows = self.MAX_ROWS_DEFAULT
                if start_time is None:
                    start_time = self.DEFAULT_START_TIME
                if end_time is None:
                    end_time = self.DEFAULT_END_TIME

            engine = self._get_mysql_connection(data_source_id)
            if not engine:
                logger.error(f"❌ 无法获取数据源 {data_source_id} 的连接")
                return None

            # 确保开始时间不晚于结束时间
            if start_time > end_time:
                logger.warning(f"开始时间 {start_time} 晚于结束时间 {end_time}，交换时间")
                start_time, end_time = end_time, start_time

            # 构建安全的查询条件
            conditions = []
            params = {}

            conditions.append(f"`{timestamp_column}` >= :start_time")
            conditions.append(f"`{timestamp_column}` <= :end_time")
            params['start_time'] = start_time
            params['end_time'] = end_time

            # 构建WHERE子句
            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # 构建查询 - 使用参数化查询防止SQL注入
            query = f"""
            SELECT `{timestamp_column}` as timestamp, `{value_column}` as value 
            FROM `{database_name}`.`{table_name}`
            {where_clause}
            ORDER BY `{timestamp_column}` DESC
            """

            if max_rows:
                query += f" LIMIT {max_rows}"

            logger.info(f"执行SQL查询: {query}")
            logger.info(f"查询参数: 开始时间={start_time}, 结束时间={end_time}")

            # 执行查询
            with engine.connect() as conn:
                result = conn.execute(text(query), params)
                df = pd.DataFrame(result.fetchall(), columns=result.keys())

            if df.empty:
                logger.warning(f"表 {database_name}.{table_name} 在指定时间范围内无数据")
                return None

            # 转换数据类型
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')

            # 检查有多少有效数据
            original_count = len(df)
            df = df.dropna(subset=['value', 'timestamp'])
            valid_count = len(df)

            if valid_count == 0:
                logger.warning(f"表 {table_name} 没有有效数据（全部为NaN）")
                return None

            if valid_count < original_count:
                logger.warning(f"表 {table_name} 有 {original_count - valid_count} 条无效数据被过滤")

            # 将数据按时间升序排列，便于后续处理
            df = df.sort_values('timestamp')

            logger.info(
                f"✅ 从表 {table_name} 加载了 {len(df)} 条有效记录，时间范围: {df['timestamp'].min()} 到 {df['timestamp'].max()}")

            # 显示数据统计
            logger.info(f"  值统计: min={df['value'].min():.4f}, max={df['value'].max():.4f}, "
                        f"mean={df['value'].mean():.4f}, std={df['value'].std():.4f}")

            return df

        except Exception as e:
            logger.error(f"❌ 加载特征数据失败 (表: {database_name}.{table_name}): {e}", exc_info=True)
            return None

    def enhanced_data_processing(
            self,
            df: pd.DataFrame,
            power_column: str = 'real_time_power_of_host_meter_1',
            steady_window: int = 4,
            steady_threshold_pct: float = 0.01,
            min_power_pct: float = 0.2
    ) -> pd.DataFrame:
        """
        增强数据处理的组合函数
        先进行稳态识别，再进行低功率过滤

        参数:
        ----------
        df : pd.DataFrame
            输入数据框
        power_column : str
            主机功率列名，只使用real_time_power_of_host_meter_3
        steady_window : int
            稳态识别窗口大小
        steady_threshold_pct : float
            稳态识别变化阈值百分比
        min_power_pct : float
            低功率过滤的最小功率比例

        返回:
        ----------
        pd.DataFrame: 处理后的数据
        """
        logger.info("\n🚀 开始增强数据处理流程...")
        logger.info(f"功率列: {power_column}")
        logger.info(f"稳态识别: 窗口={steady_window}, 阈值={steady_threshold_pct * 100}%")
        logger.info(f"低功率过滤: 最小比例={min_power_pct * 100}%")

        original_count = len(df)

        # 检查功率列是否存在
        if power_column not in df.columns:
            logger.warning(f"⚠️ 功率列 '{power_column}' 不存在于数据中，跳过增强数据处理")
            return df

        # 步骤1: 稳态识别
        logger.info("\n📊 步骤1: 稳态识别")
        steady_df = self.steady_state_identification(
            df=df,
            power_column=power_column,
            window=steady_window,
            threshold_pct=steady_threshold_pct
        )

        # 步骤2: 低功率过滤（仅当power_column存在时）
        logger.info("\n📊 步骤2: 低功率过滤")
        cleaned_df = self.low_power_filter(
            df=steady_df,
            power_column=power_column,
            min_power_pct=min_power_pct
        )

        # 最终统计
        final_count = len(cleaned_df)
        overall_reduction = ((original_count - final_count) / original_count * 100) if original_count > 0 else 0

        logger.info("\n✅ 增强数据处理完成")
        logger.info(f"  原始数据: {original_count} 条")
        logger.info(f"  处理后数据: {final_count} 条")
        logger.info(f"  总数据减少: {overall_reduction:.1f}%")

        return cleaned_df

    def align_time_series(
            self,
            data_frames: Dict[str, pd.DataFrame],
            tolerance: str = '1min',
            max_rows: int = None
    ) -> pd.DataFrame:
        """
        通用时间序列对齐方法

        参数:
        ----------
        data_frames : Dict[str, pd.DataFrame]
            特征代码到DataFrame的映射，每个DataFrame必须包含'timestamp'和'value'列
        tolerance : str
            时间对齐容差（pandas时间偏移字符串，如'1min', '1min'等）
        max_rows : int
            最大返回行数（最新的数据）

        返回:
        ----------
        pd.DataFrame : 对齐后的时间序列数据，索引为时间戳
        """
        # 使用默认最大行数如果未指定
        if max_rows is None:
            max_rows = self.MAX_ROWS_DEFAULT

        if not data_frames:
            return pd.DataFrame()

        # 为每个特征创建时间序列
        feature_series = {}
        for feature_code, df in data_frames.items():
            if df is not None and not df.empty:
                # 创建以时间戳为索引的Series
                series = pd.Series(
                    df['value'].values,
                    index=pd.DatetimeIndex(df['timestamp'].values),
                    name=feature_code
                )
                # 去重（保留第一条）
                series = series[~series.index.duplicated(keep='first')]
                feature_series[feature_code] = series

        if not feature_series:
            logger.warning("没有有效的数据进行对齐")
            return pd.DataFrame()

        # 创建基准时间轴 - 使用所有时间戳的并集
        all_timestamps = set()
        for series in feature_series.values():
            all_timestamps.update(series.index)

        # 转换为排序后的DatetimeIndex（降序，获取最新的时间戳）
        if not all_timestamps:
            return pd.DataFrame()

        all_timestamps = pd.DatetimeIndex(sorted(all_timestamps, reverse=True))

        # 限制最大行数（最新的数据）
        if len(all_timestamps) > max_rows:
            all_timestamps = all_timestamps[:max_rows]

        # 按升序排列便于对齐
        all_timestamps = all_timestamps.sort_values()

        # 创建空的DataFrame作为基准
        aligned_df = pd.DataFrame(index=all_timestamps)

        # 对每个特征进行时间对齐
        for feature_code, series in feature_series.items():
            try:
                # 方法1：使用reindex + nearest方法进行对齐
                # 首先重采样到1秒精度，便于对齐
                series_1s = series.asfreq('1S', method='pad')

                # 使用reindex + nearest方法进行对齐，设置容差
                aligned_series = series_1s.reindex(all_timestamps, method='nearest', tolerance=pd.Timedelta(tolerance))

                # 方法2：对于reindex失败的部分，使用merge_asof进行补充
                if aligned_series.isna().any():
                    # 创建临时的DataFrame用于merge_asof
                    temp_df = pd.DataFrame({'value': series})
                    temp_df.index.name = 'timestamp'
                    temp_df.reset_index(inplace=True)

                    # 创建目标DataFrame
                    target_df = pd.DataFrame(index=all_timestamps)
                    target_df.reset_index(inplace=True, names=['timestamp'])

                    # 使用merge_asof进行近似匹配
                    merged = pd.merge_asof(
                        target_df.sort_values('timestamp'),
                        temp_df.sort_values('timestamp'),
                        on='timestamp',
                        direction='nearest',
                        tolerance=pd.Timedelta(tolerance)
                    )

                    # 更新缺失的值
                    missing_mask = aligned_series.isna()
                    if missing_mask.any():
                        merged_series = pd.Series(merged['value'].values, index=pd.DatetimeIndex(merged['timestamp'].values))
                        aligned_series[missing_mask] = merged_series.reindex(all_timestamps[missing_mask])

                # 方法3：如果还有缺失值，使用插值法填充
                if aligned_series.isna().any():
                    # 使用时间索引的线性插值
                    aligned_series = aligned_series.interpolate(method='time')

                # 将处理后的序列添加到DataFrame
                aligned_df[feature_code] = aligned_series

                # 统计对齐信息
                non_na_count = aligned_series.count()
                na_count = aligned_series.isna().sum()
                logger.info(f"特征 {feature_code} 对齐完成: {non_na_count} 条有效数据, {na_count} 条缺失数据")

            except Exception as e:
                logger.error(f"特征 {feature_code} 对齐失败: {e}")
                # 如果对齐失败，使用简单重采样
                aligned_series = series.reindex(all_timestamps, method='pad')
                aligned_df[feature_code] = aligned_series

        # 处理缺失值
        # 首先向前填充（最多2个时间点）
        aligned_df = aligned_df.ffill(limit=2)

        # 然后向后填充（最多2个时间点）
        aligned_df = aligned_df.bfill(limit=2)

        # 最后填充剩余缺失值为0
        aligned_df = aligned_df.fillna(0)

        logger.info(f"时间序列对齐完成: {len(aligned_df)} 条记录, {len(aligned_df.columns)} 个特征")
        logger.info(f"时间范围: {aligned_df.index.min()} 到 {aligned_df.index.max()}")

        return aligned_df

    # ========== 新增的数据处理方法 ==========

    def _create_smart_time_features(self, df, target_feature, min_target_value=5.0):
        """创建针对设备运行模式的智能时间特征"""
        df_enhanced = df.copy()

        # 基础时间特征
        df_enhanced['hour'] = df_enhanced.index.hour
        df_enhanced['day_of_week'] = df_enhanced.index.dayofweek
        df_enhanced['is_weekend'] = (df_enhanced['day_of_week'] >= 5).astype(int)

        # 针对您的设备运行模式（早上8点到晚10点通常开机）
        df_enhanced['is_normal_operating_hour'] = (
                (df_enhanced['hour'] >= 8) & (df_enhanced['hour'] <= 22)).astype(int)

        # 创建运行时段特征
        # 早高峰时段 (8:00-12:00)
        df_enhanced['is_morning_peak'] = ((df_enhanced['hour'] >= 8) & (df_enhanced['hour'] <= 12)).astype(int)
        # 午间时段 (12:00-14:00)
        df_enhanced['is_noon'] = ((df_enhanced['hour'] >= 12) & (df_enhanced['hour'] <= 14)).astype(int)
        # 下午高峰时段 (14:00-18:00)
        df_enhanced['is_afternoon_peak'] = ((df_enhanced['hour'] >= 14) & (df_enhanced['hour'] <= 18)).astype(int)
        # 晚间时段 (18:00-22:00)
        df_enhanced['is_evening'] = ((df_enhanced['hour'] >= 18) & (df_enhanced['hour'] <= 22)).astype(int)
        # 夜间时段 (22:00-次日8:00)
        df_enhanced['is_night'] = ((df_enhanced['hour'] >= 22) | (df_enhanced['hour'] < 8)).astype(int)

        # 正弦余弦编码（周期性特征）
        df_enhanced['hour_sin'] = np.sin(2 * np.pi * df_enhanced['hour'] / 24)
        df_enhanced['hour_cos'] = np.cos(2 * np.pi * df_enhanced['hour'] / 24)
        df_enhanced['day_sin'] = np.sin(2 * np.pi * df_enhanced['day_of_week'] / 7)
        df_enhanced['day_cos'] = np.cos(2 * np.pi * df_enhanced['day_of_week'] / 7)

        # 运行持续时间特征（模拟）
        # 这里我们创建一个简化的运行持续时间特征
        # 在实际应用中，您可能需要根据状态特征来计算
        if target_feature in df_enhanced.columns:
            # 计算连续非零段的长度
            is_running = (df_enhanced[target_feature] > min_target_value).astype(int)

            # 计算运行段长度
            run_length = 0
            run_lengths = []
            for val in is_running:
                if val == 1:
                    run_length += 1
                else:
                    run_length = 0
                run_lengths.append(min(run_length, 24))  # 限制最大长度

            df_enhanced['running_duration'] = run_lengths

        logger.info(f"✅ 创建了 {len(df_enhanced.columns) - len(df.columns)} 个智能时间特征")

        return df_enhanced

    def _augment_time_series_simple(self, df, target_feature, config):
        """简单的时间序列数据增强"""
        if df is None or df.empty:
            return df

        # 检查是否需要数据增强
        min_samples = 500  # 当数据少于500条时进行增强
        if len(df) >= min_samples:
            return df

        logger.info(f"数据量较少({len(df)})，进行简单数据增强...")

        augmented_dfs = [df.copy()]

        # 1. 添加轻微噪声
        noise_df = df.copy()
        for col in df.columns:
            if df[col].std() > 0:
                noise_std = df[col].std() * 0.01  # 1%的噪声
                noise = np.random.normal(0, noise_std, len(df))
                noise_df[col] = df[col] + noise
        augmented_dfs.append(noise_df)

        # 2. 时间窗口滑动（如果数据量足够）
        look_back = config.get('look_back', 12)
        if len(df) > look_back * 2:
            shift_amount = look_back // 2
            shift_df = df.copy()
            # 对目标特征进行滑动
            if target_feature in shift_df.columns:
                shift_df[target_feature] = df[target_feature].shift(shift_amount, fill_value=df[target_feature].mean())
            augmented_dfs.append(shift_df)

        # 合并数据
        combined_df = pd.concat(augmented_dfs, ignore_index=False)
        combined_df = combined_df.drop_duplicates()

        logger.info(f"数据增强完成: {len(df)} -> {len(combined_df)} 条记录")
        return combined_df

    def _augment_for_operating_data(self, df, target_feature, config):
        """针对开机数据的针对性增强"""
        if df is None or df.empty or target_feature not in df.columns:
            return df

        logger.info(f"进行开机数据针对性增强，当前数据量: {len(df)}")

        augmented_dfs = [df.copy()]

        # 1. 基于时间模式的增强
        # 分析设备运行的时间模式
        if 'hour' in df.columns and target_feature in df.columns:
            # 按小时统计平均功率
            hourly_avg = df.groupby('hour')[target_feature].mean()

            # 找出高功率时段
            high_power_hours = hourly_avg[hourly_avg > hourly_avg.median()].index.tolist()

            if high_power_hours:
                logger.info(f"高功率时段: {high_power_hours}")

                # 创建高功率时段的模拟数据
                for hour in high_power_hours[:3]:  # 取前3个高功率时段
                    hour_data = df[df['hour'] == hour].copy()
                    if not hour_data.empty:
                        # 添加轻微的时间偏移（±1小时）
                        hour_data_shifted = hour_data.copy()
                        hour_data_shifted.index = hour_data_shifted.index + pd.Timedelta(
                            hours=np.random.choice([-1, 1]))
                        augmented_dfs.append(hour_data_shifted)

        # 2. 基于运行持续时间的增强
        if 'running_duration' in df.columns:
            # 找出长时间运行的段
            long_runs = df[df['running_duration'] >= 4]  # 连续运行4小时以上

            if not long_runs.empty:
                # 创建分段增强
                for i in range(min(3, len(long_runs) // 100)):  # 最多增强3次
                    segment = long_runs.iloc[i * 100:(i + 1) * 100].copy()
                    if len(segment) > 20:
                        # 添加噪声
                        noise_std = segment[target_feature].std() * 0.02
                        segment[target_feature] = segment[target_feature] + np.random.normal(0, noise_std, len(segment))
                        augmented_dfs.append(segment)

        # 3. 合并增强数据
        combined_df = pd.concat(augmented_dfs, ignore_index=False)
        combined_df = combined_df.drop_duplicates()

        # 按时间排序
        if isinstance(combined_df.index, pd.DatetimeIndex):
            combined_df = combined_df.sort_index()

        logger.info(f"针对性增强完成: {len(df)} -> {len(combined_df)} 条记录")
        return combined_df

    def _remove_status_features(self, df, status_features):
        """移除状态特征列"""
        if not status_features:
            return df

        # 从特征代码列表中获取状态特征代码
        status_codes = status_features  # 直接使用状态特征代码列表

        # 从数据集中移除状态特征列
        columns_to_remove = [code for code in status_codes if code in df.columns]
        if columns_to_remove:
            df = df.drop(columns=columns_to_remove, errors='ignore')
            logger.info(f"✅ 已移除 {len(columns_to_remove)} 个状态特征: {columns_to_remove}")

        return df
    def _remove_target_feature(self, df, target_feature):
        """移除状态特征列"""
        if not target_feature:
            return df

        # 从特征代码列表中获取状态特征代码
        target_codes = target_feature  # 直接使用状态特征代码列表

        # 从数据集中移除状态特征列
        columns_to_remove = [code for code in target_codes if code in df.columns]
        if columns_to_remove:
            df = df.drop(columns=columns_to_remove, errors='ignore')
            logger.info(f"✅ 已移除 {len(columns_to_remove)} 个状态特征: {columns_to_remove}")

        return df

    def _check_target_feature_quality(self, df, target_feature):
        """检查目标特征质量"""
        if target_feature not in df.columns:
            return {}

        target_series = df[target_feature]

        # 计算统计量
        stats = {
            'mean': target_series.mean(),
            'std': target_series.std(),
            'min': target_series.min(),
            'max': target_series.max(),
            'range': target_series.max() - target_series.min(),
            'cv': target_series.std() / target_series.mean() if target_series.mean() != 0 else 0,
        }

        # 检查数据变化性
        if stats['std'] < 5:
            logger.warning(f"⚠️ 目标特征变化性不足: std={stats['std']:.2f}")

        # 检查异常值
        Q1 = target_series.quantile(0.25)
        Q3 = target_series.quantile(0.75)
        IQR = Q3 - Q1
        outlier_count = ((target_series < (Q1 - 1.5 * IQR)) |
                         (target_series > (Q3 + 1.5 * IQR))).sum()

        if outlier_count > len(target_series) * 0.05:
            logger.warning(f"⚠️ 异常值过多: {outlier_count}/{len(target_series)}")

        return stats

    # ========== 主要数据加载方法 ==========

    def load_device_data(
            self,
            device_id: int,
            feature_codes: Optional[List[str]] = None,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None,
            lookback_days: int = 400,
            max_rows_per_feature: int = None,
            alignment_tolerance: str = '1min',
            save_to_csv: bool = True,
            csv_custom_name: Optional[str] = None
    ) -> Tuple[Optional[pd.DataFrame], Optional[Dict], Optional[str]]:
        """
        加载设备的所有特征数据并合并 - 修改为只查询2025年3月到4月的数据

        参数:
        ----------
        device_id : int
            设备ID
        feature_codes : Optional[List[str]]
            要加载的特征代码列表
        start_time : Optional[datetime]
            开始时间
        end_time : Optional[datetime]
            结束时间
        lookback_days : int
            回溯天数（主要用于限制最大行数）
        max_rows_per_feature : int
            每个特征最大行数
        alignment_tolerance : str
            时间对齐容差
        save_to_csv : bool
            是否保存为CSV文件
        csv_custom_name : Optional[str]
            自定义CSV文件名

        返回:
        ----------
        Tuple[Optional[pd.DataFrame], Optional[Dict], Optional[str]]:
            (数据框, 文件信息字典, 消息)
        """
        try:
            # 使用默认最大行数如果未指定
            if max_rows_per_feature is None:
                max_rows_per_feature = self.MAX_ROWS_DEFAULT

            models = self._get_models()
            # 获取设备信息
            device = self.db_session.query(models.Device).filter(models.Device.id == device_id).first()
            if not device:
                error_msg = f"设备 {device_id} 未找到"
                logger.error(error_msg)
                return None, None, error_msg

            # 获取项目信息
            project = self.db_session.query(models.Project).filter(models.Project.id == device.project_id).first()
            project_info = {
                'project_id': project.id if project else None,
                'project_name': project.name if project else '未知项目',
                'project_code': project.code if project else f'project_{device.project_id}'
            }

            # 准备设备信息
            device_info = {
                "device_id": device_id,
                "device_name": device.name,
                "project_id": device.project_id,
                "project_info": project_info
            }

            # 获取特征映射
            mappings = self.get_device_features_mappings(device_id)
            if not mappings:
                error_msg = f"设备 {device_id} 没有配置特征映射"
                logger.error(error_msg)
                return None, None, error_msg

            # 如果指定了特征代码，只加载这些特征
            if feature_codes:
                mappings = [m for m in mappings if m['feature_code'] in feature_codes]

            if not mappings:
                error_msg = f"设备 {device_id} 没有找到指定的特征"
                logger.error(error_msg)
                return None, None, error_msg

            # 使用统一配置的时间范围
            base_start_time = self.DEFAULT_START_TIME
            base_end_time = self.DEFAULT_END_TIME

            # 如果有传入的start_time和end_time，但限制在统一配置范围内
            if start_time:
                # 如果传入的start_time早于配置的起始时间，使用配置的起始时间
                if start_time < base_start_time:
                    start_time = base_start_time
                # 如果传入的start_time晚于配置的结束时间，返回空数据
                if start_time > base_end_time:
                    error_msg = f"请求的起始时间 {start_time} 晚于{base_end_time.date()}，无数据"
                    logger.warning(error_msg)
                    return None, None, error_msg
            else:
                start_time = base_start_time

            if end_time:
                # 如果传入的end_time晚于配置的结束时间，使用配置的结束时间
                if end_time > base_end_time:
                    end_time = base_end_time
                # 如果传入的end_time早于配置的起始时间，返回空数据
                if end_time < base_start_time:
                    error_msg = f"请求的结束时间 {end_time} 早于{base_start_time.date()}，无数据"
                    logger.warning(error_msg)
                    return None, None, error_msg
            else:
                end_time = base_end_time

            # 确保开始时间不晚于结束时间
            if start_time > end_time:
                error_msg = f"开始时间 {start_time} 晚于结束时间 {end_time}"
                logger.error(error_msg)
                return None, None, error_msg

            logger.info(f"【修改】固定查询{base_start_time.date()}到{base_end_time.date()}数据: {start_time} 到 {end_time}")
            logger.info(f"每个特征最多加载 {max_rows_per_feature} 条记录")
            logger.info(f"时间对齐容差: {alignment_tolerance}")

            # 为每个特征加载数据
            data_frames = {}

            for mapping in mappings:
                logger.info(f"加载特征 {mapping['feature_code']} 的数据...")

                df = self.load_feature_data(
                    data_source_id=mapping['data_source_id'],
                    database_name=mapping['database_name'],
                    table_name=mapping['table_name'],
                    timestamp_column=mapping['timestamp_column'],
                    value_column=mapping['column_name'],
                    device_id=device_id,
                    start_time=start_time,
                    end_time=end_time,
                    max_rows=max_rows_per_feature
                )

                if df is not None and not df.empty:
                    data_frames[mapping['feature_code']] = df
                    logger.info(f"特征 {mapping['feature_code']} 加载完成: {len(df)} 条记录")

            if not data_frames:
                error_msg = f"设备 {device_id} 在{base_start_time.date()}到{base_end_time.date()}没有成功加载任何特征数据"
                logger.error(error_msg)
                return None, None, error_msg

            # 使用通用时间序列对齐方法
            merged_df = self.align_time_series(
                data_frames=data_frames,
                tolerance=alignment_tolerance,
                max_rows=max_rows_per_feature
            )

            if merged_df.empty:
                error_msg = f"设备 {device_id} 数据对齐失败"
                logger.error(error_msg)
                return None, None, error_msg

            logger.info(f"设备 {device_id} 数据合并完成，共 {len(merged_df)} 条记录，{len(merged_df.columns)} 个特征")
            logger.info(f"最终数据时间范围: {merged_df.index.min()} 到 {merged_df.index.max()}")

            # 显示数据统计信息
            for col in merged_df.columns:
                non_zero = (merged_df[col] != 0).sum()
                logger.info(f"特征 {col}: {non_zero}/{len(merged_df)} 条非零数据")

            # 保存到CSV文件（如果启用）
            file_info = None

            if save_to_csv:
                # 准备特征信息
                feature_info = []
                for mapping in mappings:
                    if mapping['feature_code'] in merged_df.columns:
                        feature_info.append({
                            "feature_id": mapping['feature_id'],
                            "feature_name": mapping['feature_name'],
                            "feature_code": mapping['feature_code'],
                            "data_type": mapping['data_type'],
                            "unit": mapping['unit'],
                            "data_source_id": mapping['data_source_id'],
                            "data_source_name": mapping['data_source_name'],
                            "database_name": mapping['database_name'],
                            "table_name": mapping['table_name'],
                            "column_name": mapping['column_name'],
                            "timestamp_column": mapping['timestamp_column']
                        })

                # 使用文件处理器保存数据
                success, msg, file_info = self.file_processor.save_raw_data_with_metadata(
                    df=merged_df,
                    device_info=device_info,
                    feature_info=feature_info,
                    custom_filename=csv_custom_name
                )

                if success:
                    logger.info(f"✅ 数据已成功保存到: {file_info.get('csv_path', '未知路径')}")
                else:
                    logger.warning(f"数据未保存到CSV文件: {msg}")

            return merged_df, file_info, "数据加载成功"

        except Exception as e:
            error_msg = f"加载设备 {device_id} 数据失败: {e}"
            logger.error(error_msg, exc_info=True)
            return None, None, error_msg

    def load_training_data(
            self,
            device_id: int,
            target_feature: str,
            feature_codes: Optional[List[str]] = None,
            config: Optional[Dict] = None,
            train_ratio: float = 0.7,
            val_ratio: float = 0.15,
            test_ratio: float = 0.15,
            lookback_days: int = 400,
            max_rows_per_feature: int = None,
            alignment_tolerance: str = '1min',
            random_split: bool = True,
            save_raw_csv: bool = True,
            save_datasets: bool = True,
            dataset_name: Optional[str] = None,
            # 新增参数
            enable_steady_state_filter: bool = True,
            steady_window: int = 4,
            steady_threshold_pct: float = 0.01,
            min_power_pct: float = 0.2
    ) -> Dict[str, Union[pd.DataFrame, str, Dict]]:
        """
        加载训练数据并分割为训练集、验证集和测试集 - 简化版，只使用稳态识别和real_time_power_of_host_meter_3低功率过滤

        新增参数:
        ----------
        enable_steady_state_filter : bool
            是否启用稳态识别过滤
        steady_window : int
            稳态识别窗口大小
        steady_threshold_pct : float
            稳态识别变化阈值百分比
        min_power_pct : float
            低功率过滤的最小功率比例（基于real_time_power_of_host_meter_3）
        """
        try:
            # 使用默认最大行数如果未指定
            if max_rows_per_feature is None:
                max_rows_per_feature = self.MAX_ROWS_DEFAULT

            logger.info(f"加载设备 {device_id} 的训练数据...")
            logger.info(f"📅 使用{self.DEFAULT_START_TIME.date()} - {self.DEFAULT_END_TIME.date()}数据范围")
            logger.info(
                f"📊 目标分割比例: 训练集={train_ratio * 100:.1f}%, 验证集={val_ratio * 100:.1f}%, 测试集={test_ratio * 100:.1f}%")

            # 获取设备信息（用于构建目录结构）
            models = self._get_models()
            device = self.db_session.query(models.Device).filter(models.Device.id == device_id).first()
            if not device:
                logger.error(f"设备 {device_id} 未找到")
                return {}

            # 获取项目信息
            project = self.db_session.query(models.Project).filter(models.Project.id == device.project_id).first()
            project_info = {
                'project_id': project.id if project else None,
                'project_name': project.name if project else '未知项目',
                'project_code': project.code if project else f'project_{device.project_id}'
            }

            device_info = {
                "device_id": device_id,
                "device_name": device.name,
                "project_id": device.project_id,
                "project_info": project_info
            }

            # 加载配置
            data_filtering_config = config.get('data_filtering', {}) if config else {}
            preprocessing_config = config.get('preprocessing_config', {}) if config else {}
            status_features = config.get('status_features', []) if config else []

            min_target_value = data_filtering_config.get('min_target_value', 5.0)
            filter_zero_target = data_filtering_config.get('filter_zero_target', True)
            create_smart_time_features = preprocessing_config.get('create_smart_time_features', True)

            # 加载设备所有特征数据
            merged_df, file_info, msg = self.load_device_data(
                device_id=device_id,
                feature_codes=feature_codes,
                lookback_days=lookback_days,
                max_rows_per_feature=max_rows_per_feature,
                alignment_tolerance=alignment_tolerance,
                save_to_csv=False,
                csv_custom_name=f"training_raw_{target_feature}"
            )

            if merged_df is None or merged_df.empty:
                logger.error(f"设备 {device_id} 在{self.DEFAULT_START_TIME.date()} - {self.DEFAULT_END_TIME.date()}数据加载失败")
                return {}

            # 检查目标特征是否存在
            if target_feature not in merged_df.columns:
                logger.error(f"目标特征 {target_feature} 不在数据中")
                return {}
            # ========== 自动重采样到目标特征频率 ==========
            resample_to_target_freq = config.get('resample_to_target_freq', True) if config else True

            if resample_to_target_freq and target_feature in merged_df.columns:
                # 第一步：确定目标特征的真实频率（基于它的原始数据，而不是 merged_df）
                # 由于 merged_df 已被其他特征污染，我们需要从原始的 feature_data 中获取目标特征的原始 DataFrame
                # 但当前函数没有保存原始的 feature_data，我们可以重新加载一次目标特征（或在此之前将原始数据缓存）
                # 简便方法：从 merged_df 中提取目标特征的非空值，计算其时间间隔的众数
                target_series = merged_df[target_feature].dropna()

                if len(target_series) > 1:
                    diffs = target_series.index.to_series().diff().dropna()
                    # 转换为分钟数
                    minutes = diffs.dt.total_seconds() / 60

                    # 过滤掉可能是由于缺失填充造成的极短间隔（如 0 分钟）
                    valid_minutes = minutes[minutes >= 1]  # 至少 1 分钟间隔
                    if not valid_minutes.empty:
                        most_common_minutes = valid_minutes.mode().iloc[0]
                    else:
                        most_common_minutes = minutes.median()

                    # 固定规则：如果目标特征是 hourly_cooling_energy 或间隔 ≥ 50 分钟，则视为小时级
                    if target_feature == 'hourly_cooling_energy' or most_common_minutes >= 50:
                        resample_rule = '1H'
                        logger.info(
                            f"强制将目标特征 '{target_feature}' 重采样到小时频率 (1H)，原始间隔={most_common_minutes:.1f}分钟")
                    else:
                        # 转换为 pandas 可识别的频率字符串
                        if most_common_minutes == 60:
                            resample_rule = '1H'
                        elif most_common_minutes == 30:
                            resample_rule = '30T'
                        elif most_common_minutes == 15:
                            resample_rule = '15T'
                        elif most_common_minutes == 5:
                            resample_rule = '5T'
                        else:
                            resample_rule = f'{int(most_common_minutes)}T'
                        logger.info(
                            f"检测到目标特征 '{target_feature}' 的采样间隔为 {most_common_minutes:.1f} 分钟，重采样规则 '{resample_rule}'")
                else:
                    logger.warning("目标特征有效数据不足，无法推断间隔，使用默认小时重采样")
                    resample_rule = '1H'

                # 第二步：对合并后的 DataFrame 进行重采样
                # 注意：对于累计量（如 hourly_cooling_energy）应当使用 last() 而不是 mean()
                if target_feature == 'hourly_cooling_energy':
                    # 累计冷量使用 last()，其他特征使用 mean()
                    agg_dict = {col: 'last' if col == target_feature else 'mean' for col in merged_df.columns}
                    merged_df = merged_df.resample(resample_rule).agg(agg_dict)
                else:
                    merged_df = merged_df.resample(resample_rule).mean()

                # 前向填充缺失值（避免引入未来信息）
                merged_df = merged_df.ffill()
                logger.info(
                    f"重采样后数据形状: {merged_df.shape}, 时间范围: {merged_df.index.min()} 到 {merged_df.index.max()}")
            # ========== 简化版数据处理：只使用稳态识别和低功率过滤 ==========
            # ========== 简化版数据处理：只使用稳态识别和real_time_power_of_host_meter_3低功率过滤 ==========
            logger.info("\n🔧 开始简化数据处理...")

            original_count = len(merged_df)

            # 检查是否有real_time_power_of_host_meter_3特征
            power_column = 'real_time_power_of_host_meter_1'
            has_power_feature = power_column in merged_df.columns

            if has_power_feature:
                logger.info(f"✅ 发现real_time_power_of_host_meter_3特征，将基于此特征进行数据处理")

                # 执行增强数据处理（稳态识别 + 低功率过滤）
                if enable_steady_state_filter:
                    processed_df = self.enhanced_data_processing(
                        df=merged_df,
                        power_column=power_column,
                        steady_window=steady_window,
                        steady_threshold_pct=steady_threshold_pct,
                        min_power_pct=min_power_pct
                    )

                    # 更新merged_df为处理后的数据
                    merged_df = processed_df
                    logger.info(f"✅ 已完成稳态识别和低功率过滤")
                else:
                    logger.info("⏭️  跳过稳态识别，只进行低功率过滤")
                    # 只进行低功率过滤
                    processed_df = self.low_power_filter(
                        df=merged_df,
                        power_column=power_column,
                        min_power_pct=min_power_pct
                    )
                    merged_df = processed_df
            else:
                logger.warning(f"⚠️ 未发现real_time_power_of_host_meter_3特征，跳过所有过滤处理")

            # 确保处理后的数据仍然有效
            if merged_df.empty:
                logger.error("❌ 数据处理后数据为空")
                return {}

            # 检查目标特征质量
            target_series = merged_df[target_feature]
            if target_series.isna().all() or (target_series == 0).all():
                logger.error(f"目标特征 {target_feature} 数据无效")
                return {}

            # ========== 数据过滤：只进行零值目标特征过滤 ==========
            logger.info("\n🔍 开始数据过滤...")

            # 保存原始数据量用于日志
            original_count_before_filter = len(merged_df)

            # 过滤零值目标特征（如果配置）
            if filter_zero_target and target_feature in merged_df.columns:
                before_zero_filter = len(merged_df)
                merged_df = merged_df[merged_df[target_feature] > 0]
                after_zero_filter = len(merged_df)
                filtered_zero = before_zero_filter - after_zero_filter
                if filtered_zero > 0:
                    logger.info(f"零值目标特征过滤: 过滤了{filtered_zero}条记录")
            # ========== 针对 hourly_cooling_energy 的额外过滤 ==========
            if target_feature == 'hourly_cooling_energy' and target_feature in merged_df.columns:
                before_extra = len(merged_df)
                # 过滤掉 <=0 或 >=1000 的记录（保留 0~1000 之间的正常值）
                merged_df = merged_df[(merged_df[target_feature] > 0) & (merged_df[target_feature] < 1000)]
                after_extra = len(merged_df)
                if after_extra < before_extra:
                    logger.info(
                        f"针对 hourly_cooling_energy 额外过滤: 过滤了 {before_extra - after_extra} 条记录 (值≤0 或 ≥1000)")
            # 最终过滤后的数据量
            filtered_count = len(merged_df)
            logger.info(f"✅ 数据过滤完成: 原始 {original_count_before_filter} 条 -> 过滤后 {filtered_count} 条")

            if filtered_count == 0:
                logger.error("❌ 过滤后数据为空")
                return {}

            # ========== 数据分割 ==========
            logger.info("\n📊 开始数据分割...")
            total_len = len(merged_df)

            # 计算分割点
            train_end = int(total_len * train_ratio)
            val_end = train_end + int(total_len * val_ratio)

            if random_split:
                # 随机打乱
                shuffled_df = merged_df.sample(frac=1, random_state=42)
                train_df = shuffled_df.iloc[:train_end].sort_index()
                val_df = shuffled_df.iloc[train_end:val_end].sort_index()
                test_df = shuffled_df.iloc[val_end:].sort_index()
            else:
                # 按时间顺序分割（默认）
                train_df = merged_df.iloc[:train_end]
                val_df = merged_df.iloc[train_end:val_end]
                test_df = merged_df.iloc[val_end:]

            logger.info(f"✅ 数据分割完成:")
            logger.info(f"  总数据量（过滤后）: {total_len} 条")
            logger.info(f"  训练集: {len(train_df)} 条 ({len(train_df) / total_len * 100:.1f}%)")
            logger.info(f"  验证集: {len(val_df)} 条 ({len(val_df) / total_len * 100:.1f}%)")
            logger.info(f"  测试集: {len(test_df)} 条 ({len(test_df) / total_len * 100:.1f}%)")

            # ========== 检查目标特征质量 ==========

            def check_dataset_quality(df, dataset_name):
                """检查数据集质量"""
                if len(df) == 0 or target_feature not in df.columns:
                    return {}

                stats = self._check_target_feature_quality(df, target_feature)
                if stats:
                    logger.info(
                        f"{dataset_name}目标特征统计: "
                        f"均值={stats['mean']:.2f}, 标准差={stats['std']:.2f}, "
                        f"范围={stats['range']:.2f}"
                    )
                return stats

            train_stats = check_dataset_quality(train_df, "训练集")
            val_stats = check_dataset_quality(val_df, "验证集")
            test_stats = check_dataset_quality(test_df, "测试集")

            # ========== 数据增强（只对训练集） ==========

            # 如果训练集数据量少，进行增强
            if len(train_df) < 500:
                logger.info(f"训练集数据量较少({len(train_df)})，进行数据增强...")
                train_df = self._augment_time_series_simple(train_df, target_feature, config or {})
                logger.info(f"数据增强后训练集: {len(train_df)} 条记录")

                # 如果数据仍然少，进行针对性增强
                if len(train_df) < 2000:
                    logger.info(f"训练集数据量仍然较少({len(train_df)})，进行针对性增强...")
                    train_df = self._augment_for_operating_data(train_df, target_feature, config or {})
                    logger.info(f"针对性增强后训练集: {len(train_df)} 条记录")

            # ========== 创建智能时间特征 ==========

            if create_smart_time_features:
                logger.info("创建智能时间特征...")

                # 对训练集创建时间特征
                train_df = self._create_smart_time_features(train_df, target_feature, min_target_value)

                # 对验证集创建相同的时间特征
                if len(val_df) > 0:
                    val_df = self._create_smart_time_features(val_df, target_feature, min_target_value)

                # 对测试集创建相同的时间特征
                if len(test_df) > 0:
                    test_df = self._create_smart_time_features(test_df, target_feature, min_target_value)

            # ========== 移除状态特征列 ==========

            if status_features:
                logger.info(f"移除状态特征列...")
                status_codes = status_features

                train_df = self._remove_status_features(train_df, status_codes)
                if len(val_df) > 0:
                    val_df = self._remove_status_features(val_df, status_codes)
                if len(test_df) > 0:
                    test_df = self._remove_status_features(test_df, status_codes)

                # 从特征代码列表中移除状态特征
                if feature_codes:
                    feature_codes = [code for code in feature_codes if code not in status_codes]


            # ========== 数据质量检查 ==========

            logger.info(f"✅ 最终数据集统计:")
            logger.info(f"  训练集: {len(train_df)} 条记录")
            logger.info(f"  验证集: {len(val_df)} 条记录")
            logger.info(f"  测试集: {len(test_df)} 条记录")

            if len(train_df) > 0:
                logger.info(f"  训练集时间范围: {train_df.index.min()} 到 {train_df.index.max()}")
                if target_feature in train_df.columns:
                    logger.info(
                        f"  训练集目标特征统计: "
                        f"均值={train_df[target_feature].mean():.2f}, "
                        f"标准差={train_df[target_feature].std():.2f}"
                    )

            # ========== 获取特征信息 ==========
            # 用于保存文件的元数据
            feature_info = []
            mappings = self.get_device_features_mappings(device_id)
            if mappings:
                for mapping in mappings:
                    if mapping['feature_code'] in merged_df.columns:
                        feature_info.append({
                            "feature_id": mapping['feature_id'],
                            "feature_name": mapping['feature_name'],
                            "feature_code": mapping['feature_code'],
                            "data_type": mapping['data_type'],
                            "unit": mapping['unit'],
                            "data_source_id": mapping['data_source_id'],
                            "data_source_name": mapping['data_source_name'],
                            "database_name": mapping['database_name'],
                            "table_name": mapping['table_name'],
                            "column_name": mapping['column_name'],
                            "timestamp_column": mapping['timestamp_column']
                        })

            # ========== 使用新格式保存文件到项目-设备-时间戳目录 ==========

            # 先初始化 result 变量
            result = {}

            # 准备数据集信息
            dataset_info = {
                "device_id": device_id,
                "target_feature": target_feature,
                "feature_codes": feature_codes,
                "split_method": "random" if random_split else "time_sequential",
                "split_ratios": {
                    "train": train_ratio,
                    "val": val_ratio,
                    "test": test_ratio
                },
                "filtering_config": data_filtering_config,
                "config": config  # 保存完整配置
            }

            # 计算实际分割比例
            split_ratios = {
                'train': len(train_df) / total_len if total_len > 0 else 0,
                'val': len(val_df) / total_len if total_len > 0 else 0,
                'test': len(test_df) / total_len if total_len > 0 else 0
            }

            # 使用新方法保存所有训练管道文件
            if save_datasets:
                logger.info("📁 使用新目录结构保存训练管道文件...")

                success, msg, pipeline_file_info = self.file_processor.save_training_pipeline_files(
                    raw_df=merged_df,
                    processed_df=merged_df,  # 注意：这里原始数据和处理后数据相同，实际处理在后续步骤
                    train_df=train_df,
                    val_df=val_df,
                    test_df=test_df,
                    project_info=project_info,
                    device_info=device_info,
                    feature_info=feature_info,
                    dataset_info=dataset_info,
                    split_ratios=split_ratios
                )

                if success:
                    logger.info(f"✅ 训练管道文件保存成功: {pipeline_file_info.get('save_dir', '未知路径')}")
                    result['pipeline_file_info'] = pipeline_file_info
                    result['datasets_saved'] = True
                else:
                    logger.warning(f"训练管道文件保存失败: {msg}")
                    result['datasets_saved'] = False

            # ========== 构建返回结果 ==========

            # 更新 result 字典（注意：使用 update 方法，不要覆盖已有的键）
            result.update({
                'full_data': merged_df,
                'train_data': train_df,
                'val_data': val_df,
                'test_data': test_df,
                'target_feature': target_feature,
                'feature_names': list(train_df.columns) if len(train_df) > 0 else list(merged_df.columns),
                'split_info': {
                    'train_ratio': train_ratio,
                    'val_ratio': val_ratio,
                    'test_ratio': test_ratio,
                    'train_size': len(train_df),
                    'val_size': len(val_df),
                    'test_size': len(test_df),
                    'total_size': total_len,
                    'original_before_filter': original_count,
                    'filtered_count': filtered_count
                },
                'filtering_info': {
                    'min_target_value': min_target_value,
                    'filter_zero_target': filter_zero_target,
                    'status_features': status_features,
                    'enable_steady_state_filter': enable_steady_state_filter,
                    'steady_window': steady_window,
                    'steady_threshold_pct': steady_threshold_pct,
                    'min_power_pct': min_power_pct,
                    'has_power_feature': has_power_feature,
                    'power_filter_feature': power_column if has_power_feature else None,
                    'power_filter_threshold': merged_df[power_column].max() * min_power_pct if has_power_feature else None
                },
                'project_info': project_info,
                'device_info': device_info,
                'feature_info': feature_info
            })

            return result

        except Exception as e:
            logger.error(f"加载训练数据失败 (设备 {device_id}): {e}", exc_info=True)
            return {}

    def get_data_statistics(self, device_id: int) -> Dict:
        """获取设备数据统计信息 - 使用统一配置的时间范围"""
        try:
            # 获取特征映射
            mappings = self.get_device_features_mappings(device_id)
            if not mappings:
                return {}

            # 使用统一配置的时间范围
            start_time = self.DEFAULT_START_TIME
            end_time = self.DEFAULT_END_TIME

            # 计算每个特征的统计信息
            stats = {}
            for mapping in mappings:
                df = self.load_feature_data(
                    data_source_id=mapping['data_source_id'],
                    database_name=mapping['database_name'],
                    table_name=mapping['table_name'],
                    timestamp_column=mapping['timestamp_column'],
                    value_column=mapping['column_name'],
                    start_time=start_time,
                    end_time=end_time,
                    max_rows=self.MAX_ROWS_DEFAULT
                )

                if df is not None and not df.empty:
                    stats[mapping['feature_code']] = {
                        'data_type': mapping['data_type'],
                        'unit': mapping['unit'],
                        'sample_count': len(df),
                        'time_range': {
                            'start': df['timestamp'].min().strftime('%Y-%m-%d %H:%M:%S'),
                            'end': df['timestamp'].max().strftime('%Y-%m-%d %H:%M:%S')
                        },
                        'value_stats': {
                            'min': float(df['value'].min()),
                            'max': float(df['value'].max()),
                            'mean': float(df['value'].mean()),
                            'std': float(df['value'].std())
                        },
                        'missing_rate': float(df['value'].isna().sum() / len(df)) if len(df) > 0 else 0.0
                    }
                    logger.info(f"特征 {mapping['feature_code']}: {len(df)} 条记录, "
                                f"时间范围: {df['timestamp'].min().date()} 到 {df['timestamp'].max().date()}")

            return stats

        except Exception as e:
            logger.error(f"获取数据统计信息失败: {e}")
            return {}

    def test_connection(self, data_source_id: int) -> Tuple[bool, str]:
        """测试MySQL连接"""
        try:
            engine = self._get_mysql_connection(data_source_id)
            if not engine:
                return False, "无法创建连接"

            # 执行简单查询测试连接
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    return True, "连接成功"
                else:
                    return False, "连接测试失败"

        except Exception as e:
            return False, f"连接失败: {str(e)}"

    def list_saved_files(self, device_id: Optional[int] = None) -> List[Dict]:
        """
        列出已保存的原始数据文件

        参数:
        ----------
        device_id : Optional[int]
            设备ID，如果为None则列出所有设备文件

        返回:
        ----------
        List[Dict]: 文件信息列表
        """
        try:
            # 使用文件处理器列出文件
            files_info = self.file_processor.list_data_files(
                data_type='raw',
                sort_by='modified',
                descending=True
            )

            # 如果指定了设备ID，筛选该设备的文件
            if device_id is not None:
                filtered_files = []
                for file_info in files_info:
                    # 尝试从文件名中提取设备信息
                    filename = file_info['filename']
                    if f'device_{device_id}' in filename or f'_device_{device_id}_' in filename:
                        filtered_files.append(file_info)
                return filtered_files

            return files_info

        except Exception as e:
            logger.error(f"列出已保存文件失败: {e}")
            return []

    def load_saved_csv(self, filepath: str) -> Tuple[Optional[pd.DataFrame], str]:
        """
        加载已保存的CSV文件

        参数:
        ----------
        filepath : str
            CSV文件路径

        返回:
        ----------
        Tuple[Optional[pd.DataFrame], str]: (数据框, 消息)
        """
        try:
            # 使用文件处理器加载CSV
            df, msg = self.file_processor.load_dataframe_from_csv(filepath)
            return df, msg

        except Exception as e:
            error_msg = f"加载CSV文件失败: {e}"
            logger.error(error_msg)
            return None, error_msg

    def close_connections(self):
        """关闭所有MySQL连接"""
        for engine in self._connections.values():
            engine.dispose()
        self._connections.clear()
        logger.info("所有MySQL连接已关闭")


# 单例模式
_data_loader = None


def get_data_loader(db_session=None) -> MySQLDataLoader:
    """获取数据加载器单例"""
    global _data_loader
    if _data_loader is None:
        _data_loader = MySQLDataLoader(db_session)
    elif db_session and _data_loader.db_session is None:
        _data_loader.db_session = db_session
    return _data_loader
