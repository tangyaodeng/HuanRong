"""
复合特征处理器同步规则分析与修复
cd backend/ml/data
python composite_feature_processor.py --mode historical --verbose
python composite_feature_processor.py --mode sync
原代码中同步规则的问题：
1. 同步模式只处理最新的数据，几个月前的历史数据不会被同步
2. 缺乏历史数据补全机制
3. 时间范围控制不够灵活

修复后的同步规则：
1. 支持历史数据补全模式
2. 可配置时间范围同步
3. 支持增量同步和全量同步
"""

import yaml
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Callable
import logging
import logging.handlers
import time
import threading
import schedule
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import warnings

warnings.filterwarnings('ignore')


# 配置日志
def setup_logging(config: Dict) -> logging.Logger:
    """设置日志配置"""
    log_level = getattr(logging, config.get('level', 'INFO'))

    # 创建日志记录器
    logger = logging.getLogger('composite_feature')
    logger.setLevel(log_level)

    # 清除现有处理器
    logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果配置了文件路径）
    file_path = config.get('file_path')
    if file_path:
        try:
            max_size_mb = config.get('max_size_mb', 10)
            backup_count = config.get('backup_count', 5)

            file_handler = logging.handlers.RotatingFileHandler(
                file_path,
                maxBytes=max_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

            logger.info(f"日志文件配置完成: {file_path}")
        except Exception as e:
            logger.warning(f"无法创建日志文件处理器: {e}")

    return logger


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_config: Dict, logger: logging.Logger):
        self.db_config = db_config
        self.logger = logger
        self.engine = None
        self.connection_cache = {}

    def get_connection(self) -> Optional[Any]:
        """获取数据库连接"""
        try:
            if self.engine is None:
                from urllib.parse import quote_plus

                # 构建连接字符串
                password = quote_plus(self.db_config['password'])
                connection_string = (
                    f"mysql+pymysql://{self.db_config['username']}:{password}"
                    f"@{self.db_config['host']}:{self.db_config['port']}"
                    f"/{self.db_config['database_name']}"
                )

                # 创建引擎
                self.engine = create_engine(
                    connection_string,
                    connect_args={'charset': self.db_config.get('charset', 'utf8mb4')},
                    pool_recycle=300,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10,
                    echo=False
                )

                self.logger.info(
                    f"数据库连接创建成功: "
                    f"{self.db_config['host']}:{self.db_config['port']}/"
                    f"{self.db_config['database_name']}"
                )

            return self.engine
        except Exception as e:
            self.logger.error(f"创建数据库连接失败: {e}")
            return None

    def execute_query(self, query: str, params: Dict = None) -> Optional[List[Dict]]:
        """执行查询并返回结果"""
        try:
            engine = self.get_connection()
            if engine is None:
                return None

            with engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                rows = result.fetchall()

                # 转换为字典列表
                columns = result.keys()
                return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            self.logger.error(f"执行查询失败: {e}\n查询: {query}")
            return None

    def execute_update(self, query: str, params: List = None) -> bool:
        """执行更新操作（支持参数化查询）"""
        try:
            engine = self.get_connection()
            if engine is None:
                return False

            with engine.connect() as conn:
                if params:
                    conn.execute(text(query), params)
                else:
                    conn.execute(text(query))
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"执行更新失败: {e}\n查询: {query}")
            return False

    def table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        try:
            engine = self.get_connection()
            if engine is None:
                return False

            return inspect(engine).has_table(table_name)
        except Exception as e:
            self.logger.error(f"检查表是否存在失败: {e}")
            return False

    def create_table_if_not_exists(self, table_name: str) -> bool:
        """创建表（如果不存在）"""
        try:
            if self.table_exists(table_name):
                self.logger.info(f"表 {table_name} 已存在")
                return True

            create_sql = f"""
            CREATE TABLE `{table_name}` (
              `UpdateDateTime` datetime DEFAULT NULL,
              `PointValue` float DEFAULT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
            """

            return self.execute_update(create_sql)
        except Exception as e:
            self.logger.error(f"创建表失败: {e}")
            return False

    def get_latest_timestamp(self, table_name: str) -> Optional[datetime]:
        """获取表中最新时间戳"""
        try:
            query = f"""
            SELECT MAX(UpdateDateTime) as latest_time
            FROM `{table_name}`
            WHERE UpdateDateTime IS NOT NULL
            """

            result = self.execute_query(query)
            if result and result[0] and result[0]['latest_time']:
                return result[0]['latest_time']
            return None
        except Exception as e:
            self.logger.error(f"获取最新时间戳失败: {e}")
            return None

    def get_earliest_timestamp(self, table_name: str) -> Optional[datetime]:
        """获取表中最早时间戳"""
        try:
            query = f"""
            SELECT MIN(UpdateDateTime) as earliest_time
            FROM `{table_name}`
            WHERE UpdateDateTime IS NOT NULL
            """

            result = self.execute_query(query)
            if result and result[0] and result[0]['earliest_time']:
                return result[0]['earliest_time']
            return None
        except Exception as e:
            self.logger.error(f"获取最早时间戳失败: {e}")
            return None


class FeatureCalculator:
    """特征计算器"""

    @staticmethod
    def cumulative_diff(values: List[float], params: Dict = None) -> Optional[List[float]]:
        """
        计算累计值差分，用于求时间段内的消耗量
        注意：此方法直接传入单列数据，但这里我们会在处理器层面处理整个DataFrame。
        因此实际计算逻辑将在 CompositeFeatureProcessor 中单独实现，这里留作占位。
        """
        # 实际上该方法不会被直接调用，因为需要整表操作
        raise NotImplementedError("请使用专门的时间差分处理方法")

    @staticmethod
    def add(values: List[float], weights: List[float] = None) -> float:
        """加法运算"""
        if not values:
            return 0.0

        if weights and len(weights) == len(values):
            return sum(v * w for v, w in zip(values, weights))
        return sum(values)

    @staticmethod
    def subtract(values: List[float], weights: List[float] = None) -> float:
        """减法运算（第一个值减去其余所有值）"""
        if not values:
            return 0.0

        if len(values) == 1:
            return values[0]

        result = values[0]
        if weights:
            for i in range(1, len(values)):
                result -= values[i] * (weights[i] if i < len(weights) else 1.0)
        else:
            result -= sum(values[1:])

        return result

    @staticmethod
    def multiply(values: List[float], weights: List[float] = None) -> float:
        """乘法运算"""
        if not values:
            return 0.0

        result = 1.0
        for i, v in enumerate(values):
            weight = weights[i] if weights and i < len(weights) else 1.0
            result *= v * weight

        return result

    @staticmethod
    def divide(values: List[float], weights: List[float] = None,
               params: Dict = None) -> Optional[float]:
        """除法运算（分子/分母）"""
        params = params or {}

        if len(values) != 2:
            raise ValueError("除法运算需要且仅需要2个值")

        numerator, denominator = values[0], values[1]

        # 检查分母是否为零
        if denominator == 0:
            allow_zero = params.get('allow_zero_denominator', False)
            if allow_zero:
                return params.get('zero_denominator_value')
            return None

        # 应用权重
        if weights and len(weights) >= 2:
            numerator *= weights[0]
            denominator *= weights[1]

        result = numerator / denominator

        # 应用值限制
        min_val = params.get('min_value')
        max_val = params.get('max_value')

        if min_val is not None and result < min_val:
            result = min_val
        if max_val is not None and result > max_val:
            result = max_val

        return result

    @staticmethod
    def weighted_average(values: List[float], weights: List[float] = None) -> Optional[float]:
        """加权平均"""
        if not values:
            return None

        if not weights:
            weights = [1.0] * len(values)

        if len(values) != len(weights):
            raise ValueError("值和权重数量必须相等")

        # 计算加权和
        weighted_sum = sum(v * w for v, w in zip(values, weights))
        weight_sum = sum(weights)

        if weight_sum == 0:
            return None

        return weighted_sum / weight_sum

    @staticmethod
    def average(values: List[float], weights: List[float] = None) -> Optional[float]:
        """算术平均"""
        if not values:
            return None

        return sum(values) / len(values)

    @staticmethod
    def min_value(values: List[float], weights: List[float] = None) -> Optional[float]:
        """最小值"""
        if not values:
            return None

        return min(values)

    @staticmethod
    def max_value(values: List[float], weights: List[float] = None) -> Optional[float]:
        """最大值"""
        if not values:
            return None

        return max(values)

    @staticmethod
    def custom_formula(values: List[float], weights: List[float] = None,
                       formula: str = None) -> Optional[float]:
        """自定义公式计算"""
        if not formula:
            return None

        try:
            # 创建局部变量
            locals_dict = {}

            # 添加值作为变量
            for i, v in enumerate(values):
                locals_dict[f'x{i + 1}'] = v

            # 添加权重作为变量
            if weights:
                for i, w in enumerate(weights):
                    locals_dict[f'w{i + 1}'] = w

            # 添加数学函数
            import math
            locals_dict.update(math.__dict__)

            # 执行公式
            result = eval(formula, {"__builtins__": {}}, locals_dict)

            return float(result) if result is not None else None
        except Exception as e:
            raise ValueError(f"自定义公式计算失败: {e}")


class CompositeFeatureProcessor:
    """复合特征处理器 - 修复同步规则"""

    def __init__(self, config_path: str):
        """初始化处理器"""
        # 加载配置
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # 设置日志
        self.logger = setup_logging(self.config.get('logging', {}))

        # 初始化数据库管理器
        self.db_manager = DatabaseManager(self.config['database'], self.logger)

        # 初始化特征计算器
        self.calculator = FeatureCalculator()

        # 计算方法映射
        self.method_map = {
            'add': self.calculator.add,
            'subtract': self.calculator.subtract,
            'multiply': self.calculator.multiply,
            'divide': self.calculator.divide,
            'weighted_average': self.calculator.weighted_average,
            'average': self.calculator.average,
            'min': self.calculator.min_value,
            'max': self.calculator.max_value,
            'custom': self.calculator.custom_formula,
        }

        # 同步状态
        self.sync_enabled = self.config.get('global_sync', {}).get('enabled', False)
        self.sync_thread = None
        self.is_running = False

        self.logger.info("复合特征处理器初始化完成")

    def load_feature_data(self, table_name: str, field_name: str,
                          timestamp_field: str, time_range: Dict = None,
                          stale_threshold_minutes: int = 10) -> Optional[pd.DataFrame]:
        """加载特征数据 - 增强日志版，包含源表全局新鲜度检查"""
        try:
            where_conditions = []
            params = {}
            start_str = '无限制'
            end_str = '无限制'

            if time_range:
                if 'start_time' in time_range and time_range['start_time']:
                    where_conditions.append(f"{timestamp_field} >= :start_time")
                    params['start_time'] = time_range['start_time']
                    start_str = str(time_range['start_time'])
                if 'end_time' in time_range and time_range['end_time']:
                    where_conditions.append(f"{timestamp_field} <= :end_time")
                    params['end_time'] = time_range['end_time']
                    end_str = str(time_range['end_time'])

            where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

            query = f"""
            SELECT 
                {timestamp_field} as timestamp,
                {field_name} as value
            FROM `{table_name}`
            WHERE {where_clause}
            ORDER BY {timestamp_field}
            """

            self.logger.debug(f"加载数据: 表={table_name}, 字段={field_name}, 时间范围=[{start_str} ~ {end_str}]")

            result = self.db_manager.execute_query(query, params)

            # 查询源表全局最新时间（不受时间范围限制）
            global_status = self.check_source_table_status(table_name, timestamp_field)

            if not result:
                self.logger.warning(
                    f"表 {table_name} 在时间范围 [{start_str} ~ {end_str}] 内没有数据！"
                    f"字段={field_name}。源表状态: {global_status}"
                )
                return None

            df = pd.DataFrame(result)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

            self.logger.info(
                f"从表 {table_name} 加载了 {len(df)} 条数据 (时间范围: {start_str} ~ {end_str})"
            )

            # === 关键改进：基于源表全局最新时间的新鲜度检查（10分钟） ===
            now = datetime.now()
            if global_status and "最新时间:" in global_status:
                # 解析出最新时间字符串
                try:
                    latest_str = global_status.split("最新时间: ")[1].split(",")[0]
                    if latest_str != "None" and latest_str != "无数据":
                        latest_global = pd.to_datetime(latest_str)
                        time_diff_minutes = (now - latest_global).total_seconds() / 60
                        if time_diff_minutes > stale_threshold_minutes:
                            self.logger.warning(
                                f"⚠️ 表 {table_name} 数据可能未更新！"
                                f"源表最新数据时间: {latest_global}，"
                                f"距今已 {time_diff_minutes:.1f} 分钟（阈值 {stale_threshold_minutes} 分钟）"
                            )
                        else:
                            self.logger.info(
                                f"表 {table_name} 源表最新时间: {latest_global} (正常)"
                            )
                except Exception as parse_err:
                    self.logger.debug(f"解析源表最新时间失败: {parse_err}")

            return df
        except Exception as e:
            self.logger.error(f"加载特征数据失败 {table_name}: {e}")
            return None

    def process_cumulative_diff(self, feature_config: Dict, time_range: Dict = None) -> Optional[pd.DataFrame]:
        """处理累计值差分计算 - 增强版：使用整点附近±5分钟最近值"""
        try:
            output_table = feature_config['output_table']
            if not self.db_manager.create_table_if_not_exists(output_table):
                self.logger.error(f"无法创建或访问输出表 {output_table}")
                return None

            feature_name = feature_config['name']
            params = feature_config.get('calculation_params', {})
            window_minutes = params.get('nearest_window_minutes', 5)  # 整点搜索窗口（分钟）
            precision = params.get('precision', 2)
            min_val = params.get('min_value')
            max_val = params.get('max_value')

            # 获取输入特征（只有一个）
            if len(feature_config['input_features']) != 1:
                self.logger.error("cumulative_diff 只支持单个输入特征")
                return None
            input_cfg = feature_config['input_features'][0]
            table_name = input_cfg['table_name']
            field_name = input_cfg['field_name']
            timestamp_field = input_cfg['timestamp_field']

            # 加载原始数据
            df = self.load_feature_data(table_name, field_name, timestamp_field, time_range)
            if df is None or df.empty:
                return None

            # 确保时间索引
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # 获取源表实际数据的时间范围（重要：用于裁剪整点列表）
            data_min_time = df.index.min()
            data_max_time = df.index.max()
            self.logger.info(f"源表数据时间范围: {data_min_time} 到 {data_max_time}")

            # 确定需要计算的整点时间范围（默认从数据最早整点到最晚整点）
            start_time = None
            end_time = None
            if time_range:
                if 'start_time' in time_range and time_range['start_time']:
                    start_time = pd.to_datetime(time_range['start_time']).floor('H')
                if 'end_time' in time_range and time_range['end_time']:
                    end_time = pd.to_datetime(time_range['end_time']).ceil('H')
            if start_time is None:
                start_time = data_min_time.floor('H')
            if end_time is None:
                end_time = data_max_time.ceil('H')

            # 【关键修复】裁剪到实际数据范围内，避免遍历无数据的空白区间（如2025年）
            start_time = max(start_time, data_min_time.floor('H'))
            end_time = min(end_time, data_max_time.ceil('H'))

            if start_time >= end_time:
                self.logger.warning(f"有效时间范围为空，开始时间 {start_time} >= 结束时间 {end_time}")
                return None

            hourly_timestamps = pd.date_range(start=start_time, end=end_time, freq='1H', inclusive='left')
            self.logger.info(f"将处理 {len(hourly_timestamps)} 个整点时间点，范围 {start_time} 到 {end_time}")

            # 定义获取最近值的函数（修复 Index.abs 错误）
            def get_nearest_value(target_time: pd.Timestamp, df: pd.DataFrame, window_minutes: int = 5) -> Optional[
                float]:
                start = target_time - pd.Timedelta(minutes=window_minutes)
                end = target_time + pd.Timedelta(minutes=window_minutes)
                mask = (df.index >= start) & (df.index <= end)
                if not mask.any():
                    return None
                window_df = df[mask].copy()
                # 计算与目标时间差的绝对值（秒）
                # 【修复】total_seconds() 返回 Index，不能直接 .abs()，转为 numpy 数组再取绝对值
                time_diffs = (window_df.index - target_time).total_seconds()
                # 确保转为 numpy 数组
                if hasattr(time_diffs, 'values'):
                    time_diffs = time_diffs.values
                abs_diffs = np.abs(time_diffs)
                idx_min = np.argmin(abs_diffs)
                return window_df.iloc[idx_min]['value']

            hourly_values = []
            valid_times = []

            for t in hourly_timestamps:
                val = get_nearest_value(t, df, window_minutes)
                if val is not None:
                    hourly_values.append(val)
                    valid_times.append(t)
                else:
                    # 改为 debug 级别，避免大量警告（如果确实缺失会记录）
                    self.logger.debug(f"在 {t} ±{window_minutes}分钟内未找到数据，该整点跳过")

            if len(hourly_values) < 2:
                self.logger.warning(f"有效整点数据不足2个，无法计算差分")
                return None

            hourly_df = pd.DataFrame({
                'timestamp': valid_times,
                'cumulative_value': hourly_values
            })

            # 计算差分（每小时消耗）
            hourly_df['value'] = hourly_df['cumulative_value'].diff()
            hourly_df = hourly_df.dropna(subset=['value'])

            # 值域限制和精度
            if min_val is not None:
                hourly_df.loc[hourly_df['value'] < min_val, 'value'] = min_val
            if max_val is not None:
                hourly_df.loc[hourly_df['value'] > max_val, 'value'] = max_val
            if precision is not None:
                hourly_df['value'] = hourly_df['value'].round(precision)

            result_df = hourly_df[['timestamp', 'value']].copy()
            result_df['source_tables'] = table_name
            result_df['calculation_method'] = 'cumulative_diff_nearest'

            self.logger.info(f"累计差分计算完成（最近值窗口{window_minutes}分钟）：{len(result_df)} 条小时记录")
            return result_df

        except Exception as e:
            self.logger.error(f"累计差分处理失败: {e}", exc_info=True)
            return None

    def process_time_aggregation(self, feature_config: Dict, time_range: Dict = None) -> Optional[pd.DataFrame]:
        """处理时间聚合：将细粒度数据（如小时）聚合成粗粒度（天/周/月）"""
        try:
            output_table = feature_config['output_table']
            if not self.db_manager.create_table_if_not_exists(output_table):
                self.logger.error(f"无法创建或访问输出表 {output_table}")
                return None
            params = feature_config.get('calculation_params', {})
            rule = params.get('resample_rule', '1D')
            agg_func = params.get('aggregation_func', 'sum')
            precision = params.get('precision', 2)
            min_val = params.get('min_value')
            max_val = params.get('max_value')

            # 只有一个输入特征（小时表）
            if len(feature_config['input_features']) != 1:
                self.logger.error("time_aggregation 只支持单个输入特征")
                return None

            input_cfg = feature_config['input_features'][0]
            table_name = input_cfg['table_name']
            field_name = input_cfg['field_name']
            timestamp_field = input_cfg['timestamp_field']

            # 加载原始数据
            df = self.load_feature_data(table_name, field_name, timestamp_field, time_range)
            if df is None or df.empty:
                return None

            # 确保时间索引
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

            # 重采样聚合
            # Pandas 的 resample 要求索引单调且无时区问题，这里直接聚合
            if agg_func == 'sum':
                resampled = df.resample(rule).sum()
            elif agg_func == 'mean':
                resampled = df.resample(rule).mean()
            elif agg_func == 'max':
                resampled = df.resample(rule).max()
            elif agg_func == 'min':
                resampled = df.resample(rule).min()
            else:
                self.logger.error(f"不支持的聚合函数: {agg_func}")
                return None

            # 只保留非空行
            resampled = resampled.dropna(subset=['value'])

            # 应用值域限制和精度
            if min_val is not None:
                resampled.loc[resampled['value'] < min_val, 'value'] = min_val
            if max_val is not None:
                resampled.loc[resampled['value'] > max_val, 'value'] = max_val
            if precision is not None:
                resampled['value'] = resampled['value'].round(precision)

            # 构建输出 DataFrame
            result_df = resampled.reset_index()
            result_df.rename(columns={'index': 'timestamp'}, inplace=True)
            result_df['source_tables'] = table_name
            result_df['calculation_method'] = f'time_aggregation_{agg_func}_{rule}'

            self.logger.info(f"时间聚合完成（{rule}/{agg_func}）：{len(result_df)} 条记录")
            return result_df

        except Exception as e:
            self.logger.error(f"时间聚合处理失败: {e}", exc_info=True)
            return None

    def align_dataframes(self, dataframes: List[pd.DataFrame],
                         require_all: bool = True,
                         tolerance_seconds: int = 300,
                         method: str = 'nearest') -> Optional[pd.DataFrame]:
        """对齐多个DataFrame的时间戳 - 修复版"""
        if not dataframes:
            self.logger.warning("数据框列表为空")
            return None

        try:
            # 检查数据框是否为空
            valid_dataframes = []
            for i, df in enumerate(dataframes):
                if df is None or df.empty:
                    self.logger.warning(f"第 {i} 个数据框为空，跳过")
                    continue
                valid_dataframes.append(df)
                self.logger.info(f"第 {i} 个数据框: {len(df)} 条记录")

            if not valid_dataframes:
                self.logger.error("没有有效的数据框")
                return None

            if require_all and len(valid_dataframes) != len(dataframes):
                self.logger.error("缺少必需的输入数据")
                return None

            # 如果只有一个数据框，直接返回
            if len(valid_dataframes) == 1:
                return valid_dataframes[0]

            # 合并数据框 - 修复关键代码
            try:
                # 创建所有DataFrame的列表，使用重采样确保时间对齐
                resampled_dfs = []

                for i, df in enumerate(valid_dataframes):
                    # 确保DataFrame有value列
                    if 'value' not in df.columns:
                        self.logger.error(f"第 {i} 个数据框没有'value'列")
                        continue

                    # 重采样到5分钟频率
                    df_resampled = df.resample('5T').mean()

                    # 填充缺失值
                    df_resampled = df_resampled.ffill().bfill()

                    # 重命名列以避免冲突
                    df_resampled = df_resampled.rename(columns={'value': f'value_{i}'})
                    resampled_dfs.append(df_resampled)
                    self.logger.info(f"第 {i} 个数据框重采样后: {len(df_resampled)} 条记录")

                if not resampled_dfs:
                    self.logger.error("重采样后没有有效数据")
                    return None

                # 使用concat合并
                combined = pd.concat(resampled_dfs, axis=1, join='inner')

                if combined.empty:
                    self.logger.warning("合并后数据为空，尝试outer join")
                    combined = pd.concat(resampled_dfs, axis=1, join='outer')
                    # 填充缺失值
                    combined = combined.ffill().bfill()

                # 删除全部为NaN的行
                combined = combined.dropna(how='all')

                self.logger.info(f"对齐后数据: {len(combined)} 条记录，{combined.shape[1]} 个特征")

                return combined

            except Exception as e:
                self.logger.error(f"数据合并失败: {e}", exc_info=True)
                return None

        except Exception as e:
            self.logger.error(f"数据对齐失败: {e}", exc_info=True)
            return None

    def check_source_table_status(self, table_name: str, timestamp_field: str) -> str:
        """检查源表的最新数据时间，用于诊断"""
        try:
            query = f"""
            SELECT MAX({timestamp_field}) as latest_time, COUNT(*) as total_count
            FROM `{table_name}`
            WHERE {timestamp_field} IS NOT NULL
            """
            result = self.db_manager.execute_query(query)
            if result and result[0]:
                latest = result[0]['latest_time']
                count = result[0]['total_count']
                return f"最新时间: {latest}, 总记录数: {count}"
            else:
                return "无数据或查询失败"
        except Exception as e:
            return f"查询异常: {e}"
    def calculate_composite_feature(self, feature_config: Dict,
                                    time_range: Dict = None) -> Optional[pd.DataFrame]:
        """计算复合特征 - 修复版"""
        try:
            feature_name = feature_config['name']
            self.logger.info(f"开始计算复合特征: {feature_name}")

            # 检查输出表
            output_table = feature_config['output_table']
            if not self.db_manager.create_table_if_not_exists(output_table):
                self.logger.error(f"无法创建或访问输出表 {output_table}")
                return None

            # 加载所有输入特征数据
            input_dfs = []
            source_tables = []
            missing_features = []  # 新增：记录缺失的特征

            for input_feature in feature_config['input_features']:
                table_name = input_feature['table_name']
                field_name = input_feature['field_name']
                timestamp_field = input_feature['timestamp_field']

                self.logger.info(f"加载特征 {input_feature['feature_name']} 从表 {table_name}")

                df = self.load_feature_data(table_name, field_name, timestamp_field, time_range)
                if df is not None and not df.empty:
                    input_dfs.append(df)
                    source_tables.append(table_name)
                    self.logger.info(f"特征 {input_feature['feature_name']} 加载成功: {len(df)} 条记录")
                else:
                    self.logger.warning(f"特征 {input_feature['feature_name']} 数据加载失败或为空")

            # 验证数据
            validation_rules = feature_config.get('validation_rules', {})
            require_all = validation_rules.get('require_all_inputs', True)
            min_points = validation_rules.get('min_data_points', 10)

            # 检查每个输入特征的数据量
            for i, input_feature in enumerate(feature_config['input_features']):
                if i < len(input_dfs):
                    df_len = len(input_dfs[i])
                    if df_len < min_points:
                        self.logger.warning(
                            f"特征 {input_feature['feature_name']} (表:{input_feature['table_name']}) "
                            f"数据点不足: {df_len} < {min_points}，可能影响计算结果"
                        )
            if require_all and len(input_dfs) != len(feature_config['input_features']):
                self.logger.error(
                    f"缺少必需的输入特征数据: 需要 {len(feature_config['input_features'])} 个，实际 {len(input_dfs)} 个。"
                    f"缺失特征: {', '.join(missing_features)}"
                )
                return None

            # 对齐数据
            aligned_df = self.align_dataframes(input_dfs, require_all=require_all)

            if aligned_df is None:
                self.logger.error("数据对齐失败")
                return None

            if aligned_df.empty:
                self.logger.error("对齐后数据为空")
                return None

            if len(aligned_df) < min_points:
                self.logger.warning(f"有效数据点不足: {len(aligned_df)} < {min_points}")
                # 不直接返回None，尝试继续计算
                # return None

            self.logger.info(f"对齐后数据形状: {aligned_df.shape}")

            # 提取值和权重
            values_list = []
            weights = []

            for i, input_feature in enumerate(feature_config['input_features']):
                column_name = f'value_{i}'
                if column_name in aligned_df.columns:
                    column_values = aligned_df[column_name].values
                    values_list.append(column_values)

                    weight = input_feature.get('weight', 1.0)
                    weights.append(weight)
                else:
                    self.logger.warning(f"列 {column_name} 不在对齐后的数据中")

            if not values_list:
                self.logger.error("没有有效的值列表")
                return None

            # 转置值列表
            try:
                # 确保所有数组长度相同
                min_length = min(len(v) for v in values_list)
                truncated_values = [v[:min_length] for v in values_list]
                row_values = list(zip(*truncated_values))
            except Exception as e:
                self.logger.error(f"转置数据失败: {e}")
                return None

            if not row_values:
                self.logger.warning("转置后数据为空")
                return None

            # 计算方法
            method_name = feature_config['calculation_method']
            calculation_params = feature_config.get('calculation_params', {})

            if method_name not in self.method_map:
                self.logger.error(f"不支持的计算方法: {method_name}")
                return None

            calculation_func = self.method_map[method_name]

            # 计算每个时间点的复合特征值
            composite_values = []
            valid_indices = []

            for idx, values in enumerate(row_values):
                try:
                    # 准备参数
                    func_params = {'values': list(values)}

                    # 添加权重
                    if method_name in ['weighted_average', 'add', 'multiply']:
                        func_params['weights'] = weights

                    # 添加计算参数
                    if method_name == 'divide':
                        func_params['params'] = calculation_params

                    # 执行计算
                    result = calculation_func(**func_params)

                    if result is not None:
                        # 确保结果是数值类型
                        try:
                            result_float = float(result)
                            if not pd.isna(result_float):
                                composite_values.append(result_float)
                                valid_indices.append(idx)
                        except (ValueError, TypeError):
                            continue

                except Exception as e:
                    self.logger.debug(f"计算失败于索引 {idx}: {e}")
                    continue

            if not composite_values:
                self.logger.warning("没有有效的计算结果")
                return None

            # 创建结果DataFrame
            result_df = pd.DataFrame({
                'timestamp': aligned_df.index[valid_indices],
                'value': composite_values,
                'source_tables': ','.join(source_tables),
                'calculation_method': method_name
            })

            # 应用精度限制
            precision = calculation_params.get('precision')
            if precision is not None:
                result_df['value'] = result_df['value'].round(precision)

            self.logger.info(f"特征 {feature_name} 计算完成: {len(result_df)} 条记录")
            return result_df

        except Exception as e:
            self.logger.error(f"计算复合特征失败 {feature_config.get('name')}: {e}", exc_info=True)
            return None

    def save_composite_feature(self, feature_name: str, output_table: str,
                               result_df: pd.DataFrame) -> bool:
        """保存复合特征结果到数据库 - 使用原生 SQL 批量插入"""
        try:
            if result_df.empty:
                self.logger.warning(f"特征 {feature_name} 没有数据需要保存")
                return False

            # 检查是否有重复数据
            latest_time = self.db_manager.get_latest_timestamp(output_table)
            if latest_time:
                # 正确比较时间戳
                latest_timestamp = pd.Timestamp(latest_time)

                # 只保存新数据（严格大于，避免重复）
                new_data_df = result_df[result_df['timestamp'] > latest_timestamp]

                if new_data_df.empty:
                    self.logger.info(f"特征 {feature_name} 没有新数据")
                    # 这里返回 True，因为没有新数据是正常情况，不是失败
                    return True

                result_df = new_data_df
                self.logger.info(f"特征 {feature_name} 有 {len(result_df)} 条新数据需要保存")

            # 使用原生 SQL 批量插入
            try:
                engine = self.db_manager.get_connection()
                if engine is None:
                    return False

                # 准备数据 - 只包含两个字段
                values_list = []
                for _, row in result_df.iterrows():
                    timestamp_str = row['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                    value = float(row['value'])

                    values_list.append(
                        f"('{timestamp_str}', {value})"
                    )

                if not values_list:
                    return False

                # 分批处理
                batch_size = 500
                total_inserted = 0

                for i in range(0, len(values_list), batch_size):
                    batch_values = values_list[i:i + batch_size]

                    # 【修复】插入语句只包含两个字段
                    insert_sql = f"""
                    INSERT INTO `{output_table}` 
                    (UpdateDateTime, PointValue)
                    VALUES {','.join(batch_values)}
                    ON DUPLICATE KEY UPDATE
                    PointValue = VALUES(PointValue)
                    """

                    try:
                        with engine.connect() as conn:
                            result = conn.execute(text(insert_sql))
                            conn.commit()
                            # 获取实际插入的行数
                            inserted_in_batch = result.rowcount
                            total_inserted += inserted_in_batch
                            self.logger.debug(f"批量插入 {len(batch_values)} 条记录，实际影响 {inserted_in_batch} 行")
                    except Exception as e:
                        self.logger.error(f"批量插入失败: {e}")
                        # 尝试逐条插入
                        for value_str in batch_values:
                            try:
                                # 【修复】单条插入也只包含两个字段
                                single_insert_sql = f"""
                                INSERT INTO `{output_table}` 
                                (UpdateDateTime, PointValue)
                                VALUES {value_str}
                                ON DUPLICATE KEY UPDATE
                                PointValue = VALUES(PointValue)
                                """
                                with engine.connect() as conn:
                                    result = conn.execute(text(single_insert_sql))
                                    conn.commit()
                                    total_inserted += result.rowcount
                            except Exception as e2:
                                self.logger.warning(f"单条插入失败: {e2}")
                                continue

                self.logger.info(f"特征 {feature_name} 保存完成: 新增 {total_inserted} 条记录")
                # 即使 total_inserted 为 0，只要没有错误也返回 True
                # 因为可能所有数据都是重复的（ON DUPLICATE KEY UPDATE）
                return True

            except Exception as e:
                self.logger.error(f"保存复合特征失败 {feature_name}: {e}")
                return False

        except Exception as e:
            self.logger.error(f"保存复合特征失败 {feature_name}: {e}")
            return False

    def process_feature(self, feature_config: Dict, sync_mode: bool = False) -> bool:
        """处理单个复合特征 - 修复版：解决历史数据同步问题"""
        try:
            feature_name = feature_config['name']

            # 确定时间范围
            time_range = {}

            # 批处理模式
            if not sync_mode:
                if 'time_range' in feature_config:
                    time_range = feature_config['time_range'].copy()
                    # 清理空值
                    if 'start_time' in time_range and not time_range['start_time']:
                        del time_range['start_time']
                    if 'end_time' in time_range and not time_range['end_time']:
                        del time_range['end_time']

                    # 如果设置了auto_detect，则自动检测最新时间
                    if time_range.get('auto_detect'):
                        output_table = feature_config['output_table']
                        latest_time = self.db_manager.get_latest_timestamp(output_table)
                        if latest_time:
                            time_range = {'start_time': latest_time}
                            self.logger.info(f"自动检测: 处理 {feature_name} 从 {latest_time} 开始")
                        else:
                            time_range = {}
                            self.logger.info(f"自动检测: 处理 {feature_name} 所有数据")

            elif sync_mode:
                # 同步模式 - 修复历史数据同步逻辑
                output_table = feature_config['output_table']
                sync_settings = feature_config.get('sync', {})

                # 检查是否启用了历史数据补全
                if sync_settings.get('historical_fill_enabled', False):
                    historical_start = sync_settings.get('historical_start_date')

                    if historical_start:
                        try:
                            # 【重要修复】验证日期格式并修正
                            try:
                                start_date = datetime.strptime(historical_start, '%Y-%m-%d')
                            except ValueError as e:
                                # 尝试自动修正日期
                                if "day is out of range" in str(e):
                                    # 如果是日期超出范围，尝试调整为当月的最后一天
                                    from calendar import monthrange
                                    year_month = historical_start[:7]
                                    year = int(year_month.split('-')[0])
                                    month = int(year_month.split('-')[1])
                                    last_day = monthrange(year, month)[1]
                                    start_date = datetime(year, month, last_day)
                                    self.logger.warning(f"修正历史开始日期: {historical_start} -> {start_date.date()}")
                                else:
                                    raise e

                            # 获取历史结束日期，如果没有则使用当前时间
                            historical_end = sync_settings.get('historical_end_date')
                            if historical_end:
                                try:
                                    end_date = datetime.strptime(historical_end, '%Y-%m-%d')
                                except ValueError as e:
                                    if "day is out of range" in str(e):
                                        from calendar import monthrange
                                        year_month = historical_end[:7]
                                        year = int(year_month.split('-')[0])
                                        month = int(year_month.split('-')[1])
                                        last_day = monthrange(year, month)[1]
                                        end_date = datetime(year, month, last_day)
                                        self.logger.warning(f"修正历史结束日期: {historical_end} -> {end_date.date()}")
                                    else:
                                        raise e
                            else:
                                end_date = datetime.now()

                            # 【关键修复】检查历史数据是否已经同步
                            self.logger.info(f"检查历史数据同步状态: {feature_name}")
                            historical_data_count = self._get_data_count_in_range(
                                output_table, start_date, end_date
                            )

                            self.logger.info(
                                f"历史数据统计: 时间范围 {start_date.date()} 到 {end_date.date()}, "
                                f"已有数据 {historical_data_count} 条"
                            )

                            # 判断是否需要历史数据补全
                            if historical_data_count > 100:
                                # 已有足够历史数据，进行增量同步
                                self.logger.info(f"历史数据已同步完成，进行增量同步")
                                latest_time = self.db_manager.get_latest_timestamp(output_table)
                                if latest_time:
                                    time_range['start_time'] = latest_time
                                    self.logger.info(f"增量同步: 处理 {feature_name} 从 {latest_time} 开始")
                                else:
                                    hours_back = sync_settings.get('hours_back', 24)
                                    time_range['start_time'] = datetime.now() - timedelta(hours=hours_back)
                                    self.logger.info(f"增量同步: 处理 {feature_name} 最近 {hours_back} 小时数据")
                            else:
                                # 历史数据不足，进行历史数据补全
                                self.logger.info(f"历史数据不足，进行历史数据补全")
                                time_range['start_time'] = start_date
                                time_range['end_time'] = end_date
                                self.logger.info(
                                    f"历史数据补全: {feature_name} 从 {start_date.date()} 到 {end_date.date()}"
                                )

                                # 验证源数据是否可用
                                self._validate_historical_data_sources(feature_config, start_date, end_date)

                        except ValueError as ve:
                            self.logger.error(f"历史日期处理失败: {ve}")
                            # 日期处理失败，使用增量同步
                            latest_time = self.db_manager.get_latest_timestamp(output_table)
                            if latest_time:
                                time_range['start_time'] = latest_time
                                self.logger.info(f"日期错误，增量同步: 从 {latest_time} 开始")
                            else:
                                hours_back = sync_settings.get('hours_back', 24)
                                time_range['start_time'] = datetime.now() - timedelta(hours=hours_back)
                                self.logger.info(f"日期错误，增量同步: 最近 {hours_back} 小时数据")

                    else:
                        # 没有历史开始日期，使用增量同步
                        latest_time = self.db_manager.get_latest_timestamp(output_table)
                        if latest_time:
                            time_range['start_time'] = latest_time
                            self.logger.info(f"无历史日期，增量同步: 从 {latest_time} 开始")
                        else:
                            hours_back = sync_settings.get('hours_back', 24)
                            time_range['start_time'] = datetime.now() - timedelta(hours=hours_back)
                            self.logger.info(f"无历史日期，增量同步: 最近 {hours_back} 小时数据")

                else:
                    # 没有启用历史数据补全，使用增量同步
                    latest_time = self.db_manager.get_latest_timestamp(output_table)
                    if latest_time:
                        time_range['start_time'] = latest_time
                        self.logger.info(f"普通同步: 处理 {feature_name} 从 {latest_time} 开始")
                    else:
                        hours_back = sync_settings.get('hours_back', 24)
                        time_range['start_time'] = datetime.now() - timedelta(hours=hours_back)
                        self.logger.info(f"普通同步: 处理 {feature_name} 最近 {hours_back} 小时数据")

            # 记录时间范围
            if time_range:
                start_str = time_range.get('start_time', '无限制')
                end_str = time_range.get('end_time', '无限制')
                self.logger.info(f"处理时间范围: {start_str} 到 {end_str}")

            # 计算复合特征
            method = feature_config['calculation_method']
            if method == 'cumulative_diff':
                result_df = self.process_cumulative_diff(feature_config, time_range)
            elif method == 'time_aggregation':
                result_df = self.process_time_aggregation(feature_config, time_range)
            else:
                result_df = self.calculate_composite_feature(feature_config, time_range)

            if result_df is None:
                self.logger.warning(f"特征 {feature_name} 计算失败")
                return False

            if result_df.empty:
                self.logger.info(f"特征 {feature_name} 计算完成但无数据")
                return True

            # 保存结果
            saved = self.save_composite_feature(
                feature_name,
                feature_config['output_table'],
                result_df
            )

            if saved:
                self.logger.info(f"特征 {feature_name} 处理完成")
            else:
                self.logger.warning(f"特征 {feature_name} 保存失败")

            return saved

        except Exception as e:
            self.logger.error(f"处理特征失败 {feature_config.get('name')}: {e}", exc_info=True)
            return False

    def _validate_historical_data_sources(self, feature_config: Dict, start_date: datetime, end_date: datetime) -> bool:
        feature_name = feature_config['name']
        available_sources = 0
        total_sources = len(feature_config['input_features'])

        self.logger.info(f"验证 {feature_name} 的历史数据源...")

        for input_feature in feature_config['input_features']:
            table_name = input_feature['table_name']
            timestamp_field = input_feature['timestamp_field']

            # 查询总数据量
            query_total = f"""
            SELECT COUNT(*) as total_count, MAX({timestamp_field}) as latest_time
            FROM `{table_name}`
            """
            total_result = self.db_manager.execute_query(query_total)
            total_info = ""
            if total_result and total_result[0]:
                total_info = f"总记录: {total_result[0]['total_count']}, 最新时间: {total_result[0]['latest_time']}"

            # 查询指定范围内的数据量
            query = f"""
            SELECT COUNT(*) as data_count
            FROM `{table_name}`
            WHERE {timestamp_field} >= :start_date 
              AND {timestamp_field} <= :end_date
              AND {timestamp_field} IS NOT NULL
            """
            params = {'start_date': start_date, 'end_date': end_date}

            try:
                result = self.db_manager.execute_query(query, params)
                if result and result[0]:
                    count = result[0]['data_count']  # 这里定义了 count
                    if count > 0:
                        available_sources += 1
                        self.logger.info(f"✓ 源表 {table_name} 有 {count} 条历史数据。{total_info}")
                    else:
                        self.logger.warning(f"✗ 源表 {table_name} 没有历史数据。{total_info}")
                else:
                    self.logger.warning(f"✗ 源表 {table_name} 查询失败")
            except Exception as e:
                self.logger.warning(f"源表 {table_name} 验证失败: {e}")

        # ... 后续逻辑不变
    def _get_data_count_in_range(self, table_name: str, start_time: datetime, end_time: datetime) -> int:
        """获取指定时间范围内的数据条数"""
        try:
            query = f"""
            SELECT COUNT(*) as data_count
            FROM `{table_name}`
            WHERE UpdateDateTime >= :start_time 
              AND UpdateDateTime <= :end_time
              AND UpdateDateTime IS NOT NULL
            """

            params = {
                'start_time': start_time,
                'end_time': end_time
            }

            result = self.db_manager.execute_query(query, params)

            if result and result[0]:
                return result[0]['data_count']
            return 0

        except Exception as e:
            self.logger.error(f"获取数据条数失败: {e}")
            return 0

    def _handle_incremental_sync(self, feature_config: Dict, time_range: Dict) -> None:
        """处理增量同步"""
        feature_name = feature_config['name']
        output_table = feature_config['output_table']
        sync_settings = feature_config.get('sync', {})

        # 获取最新时间戳
        latest_time = self.db_manager.get_latest_timestamp(output_table)

        if latest_time:
            time_range['start_time'] = latest_time
            self.logger.info(f"增量同步: 处理 {feature_name} 从 {latest_time} 开始")
        else:
            # 没有历史数据，处理最近的数据
            hours_back = sync_settings.get('hours_back', 24)
            time_range['start_time'] = datetime.now() - timedelta(hours=hours_back)
            self.logger.info(f"增量同步: 处理 {feature_name} 最近 {hours_back} 小时数据")

    def _validate_source_data_range(self, feature_config: Dict, start_date: datetime, end_date: datetime) -> None:
        """验证源数据是否包含指定时间范围的数据"""
        feature_name = feature_config['name']

        for input_feature in feature_config['input_features']:
            table_name = input_feature['table_name']

            # 检查源数据表是否存在该时间范围的数据
            query = f"""
            SELECT COUNT(*) as data_count
            FROM `{table_name}`
            WHERE UpdateDateTime >= :start_date 
              AND UpdateDateTime <= :end_date
              AND UpdateDateTime IS NOT NULL
            LIMIT 1
            """

            params = {
                'start_date': start_date,
                'end_date': end_date
            }

            try:
                result = self.db_manager.execute_query(query, params)
                if result and result[0]:
                    count = result[0]['data_count']
                    if count > 0:
                        self.logger.info(
                            f"源数据表 {table_name} 在指定时间范围内有 {count} 条数据"
                        )
                    else:
                        self.logger.warning(
                            f"源数据表 {table_name} 在指定时间范围内没有数据"
                        )
            except Exception as e:
                self.logger.warning(f"检查源数据表 {table_name} 数据范围失败: {e}")

    def process_all_features(self, sync_mode: bool = False) -> Dict:
        """处理所有复合特征"""
        results = {}

        if 'composite_features' not in self.config:
            self.logger.error("配置中没有定义复合特征")
            return results

        for feature_config in self.config['composite_features']:
            feature_name = feature_config['name']

            # 检查是否启用了同步
            if sync_mode and not feature_config.get('sync', {}).get('enabled', False):
                self.logger.debug(f"特征 {feature_name} 同步未启用，跳过")
                continue

            try:
                self.logger.info(f"开始处理特征: {feature_name}")
                success = self.process_feature(feature_config, sync_mode)
                results[feature_name] = {
                    'success': success,
                    'feature': feature_name
                }

                if success:
                    self.logger.info(f"特征 {feature_name} 处理成功")
                else:
                    self.logger.warning(f"特征 {feature_name} 处理失败")

            except Exception as e:
                self.logger.error(f"处理特征 {feature_name} 时发生异常: {e}")
                results[feature_name] = {
                    'success': False,
                    'error': str(e),
                    'feature': feature_name
                }

        return results

    def sync_job(self):
        """同步任务"""
        try:
            self.logger.info("开始执行同步任务")

            if not self.sync_enabled:
                self.logger.warning("同步功能未启用")
                return

            # 处理所有启用了同步的特征
            results = self.process_all_features(sync_mode=True)

            # 统计结果
            success_count = sum(1 for r in results.values() if r.get('success'))
            total_count = len(results)

            self.logger.info(f"同步任务完成: 成功 {success_count}/{total_count}")

        except Exception as e:
            self.logger.error(f"同步任务异常: {e}")

    def start_sync_service(self):
        """启动同步服务"""
        if not self.sync_enabled:
            self.logger.warning("同步功能未启用，无法启动服务")
            return False

        if self.is_running:
            self.logger.warning("同步服务已经在运行中")
            return False

        self.is_running = True

        def run_scheduler():
            """运行调度器"""
            # 立即执行一次
            self.logger.info("同步服务启动，立即执行第一次同步")
            self.sync_job()

            # 设置定时任务
            interval = self.config['global_sync'].get('check_interval_seconds', 60)
            schedule.every(interval).seconds.do(self.sync_job)

            self.logger.info(f"同步服务已启动，每 {interval} 秒检查一次")

            while self.is_running:
                try:
                    schedule.run_pending()
                    time.sleep(1)
                except Exception as e:
                    self.logger.error(f"调度器运行异常: {e}")
                    time.sleep(5)

            self.logger.info("同步服务已停止")

        # 启动同步线程
        self.sync_thread = threading.Thread(
            target=run_scheduler,
            daemon=True,
            name="CompositeFeatureSync"
        )
        self.sync_thread.start()

        self.logger.info("同步服务启动成功")
        return True

    def stop_sync_service(self):
        """停止同步服务"""
        self.is_running = False

        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=10)

        self.logger.info("同步服务已停止")

    def run_once(self):
        """执行一次批处理"""
        self.logger.info("开始执行批处理")
        results = self.process_all_features(sync_mode=False)

        # 打印统计信息
        success_count = sum(1 for r in results.values() if r.get('success'))
        total_count = len(results)

        self.logger.info(f"批处理完成: 成功 {success_count}/{total_count}")

        return results

    def run_historical_sync(self, feature_name: str = None):
        """运行历史数据同步"""
        self.logger.info("开始执行历史数据同步")

        results = {}
        features_to_process = self.config.get('composite_features', [])

        if feature_name:
            features_to_process = [f for f in features_to_process if f['name'] == feature_name]

        for feature_config in features_to_process:
            # 检查是否启用了历史数据补全
            if not feature_config.get('sync', {}).get('historical_fill_enabled', False):
                continue

            feature_name = feature_config['name']
            try:
                self.logger.info(f"开始历史数据补全: {feature_name}")
                success = self.process_feature(feature_config, sync_mode=True)
                results[feature_name] = {
                    'success': success,
                    'feature': feature_name
                }

                if success:
                    self.logger.info(f"历史数据补全成功: {feature_name}")
                else:
                    self.logger.warning(f"历史数据补全失败: {feature_name}")

            except Exception as e:
                self.logger.error(f"历史数据补全异常 {feature_name}: {e}")
                results[feature_name] = {
                    'success': False,
                    'error': str(e),
                    'feature': feature_name
                }

        # 统计结果
        success_count = sum(1 for r in results.values() if r.get('success'))
        total_count = len(results)
        self.logger.info(f"历史数据同步完成: 成功 {success_count}/{total_count}")

        return results


def main():
    """主函数"""
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='复合特征处理器')
    parser.add_argument('--config', '-c', default='composite_features_config.yaml',
                        help='配置文件路径 (默认: composite_features_config.yaml)')
    parser.add_argument('--mode', '-m', choices=['batch', 'sync', 'test', 'historical'],
                        default='batch',
                        help='运行模式: batch=批处理, sync=同步模式, test=测试, historical=历史数据同步')
    parser.add_argument('--feature', '-f', help='指定处理的特征名称')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')

    args = parser.parse_args()

    try:
        # 创建处理器
        processor = CompositeFeatureProcessor(args.config)

        if args.verbose:
            # 提高日志级别
            processor.logger.setLevel(logging.DEBUG)
            for handler in processor.logger.handlers:
                handler.setLevel(logging.DEBUG)

        if args.mode == 'batch':
            # 批处理模式
            processor.run_once()

        elif args.mode == 'sync':
            # 同步模式
            print("启动同步服务，按Ctrl+C停止...")
            try:
                processor.start_sync_service()

                # 保持主线程运行
                while True:
                    time.sleep(1)

            except KeyboardInterrupt:
                print("\n正在停止同步服务...")
                processor.stop_sync_service()

        elif args.mode == 'historical':
            # 历史数据同步模式
            print("执行历史数据同步...")
            processor.run_historical_sync(args.feature)

        elif args.mode == 'test':
            # 测试模式
            print("测试模式:")
            print(f"配置文件: {args.config}")
            print(f"数据库连接: {processor.config['database']['host']}:{processor.config['database']['port']}")
            print(f"复合特征数量: {len(processor.config.get('composite_features', []))}")

            # 测试数据库连接
            print("\n测试数据库连接...")
            if processor.db_manager.get_connection():
                print("✓ 数据库连接成功")
            else:
                print("✗ 数据库连接失败")

    except Exception as e:
        print(f"程序执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
