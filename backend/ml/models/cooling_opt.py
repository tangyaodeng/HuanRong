"""
冷却水回水温度对系统功率影响的探索器（总功率模型版本）- 定时运行版（直接修正模式）
适配新项目 config.py 和 PostgreSQL 表结构
backend/ml/models/cooling_opt.py
"""
import pickle
import numpy as np
import pandas as pd
import os
import sys
from typing import Dict, List, Tuple, Optional, Any
import logging
from datetime import datetime, timedelta
import time
from sqlalchemy import create_engine, text, inspect
from urllib.parse import quote_plus
import xgboost as xgb
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import threading
import signal
import redis
import json
import random
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
# 导入新项目配置
from app.config import settings
from ml.utils.heartbeat_utils import update_heartbeat

# 设置日志（修复Windows控制台编码问题）
class UnicodeSafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except UnicodeEncodeError:
            # 如果编码失败，使用替换字符
            try:
                msg = self.format(record)
                msg = msg.encode('gbk', errors='replace').decode('gbk')
                stream = self.stream
                stream.write(msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)
        except Exception:
            self.handleError(record)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cooling_optimization_total.log', encoding='utf-8'),
        UnicodeSafeStreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)   # <--- 在这里添加


class CoolingTempSchedulerTotal:
    """冷却水系统优化调度器（总功率模型版本，直接修正模式，无平滑）"""

    def __init__(self):
        # ========== 从 settings 读取数据库配置 ==========
        # MySQL数据库配置（实时数据）
        self.mysql_config = {
            'host': settings.MYSQL_HOST,
            'port': settings.MYSQL_PORT,
            'user': settings.MYSQL_USER,
            'password': settings.MYSQL_PASSWORD,
            'database': settings.MYSQL_DATABASE,
            'charset': settings.MYSQL_CHARSET
        }
        # 数据时效性阈值（分钟），可根据现场情况调整
        self.data_recency_minutes = 10
        # PostgreSQL数据库配置（配置和结果存储）
        self.postgres_config = {
            'url': settings.DATABASE_URL
        }
        # 新增：历史残差队列（每个模型独立）
        self.historical_residuals = {
            'host_total': [],
            'cooling_pump_total': [],
            'cooling_tower_total': []
        }
        # 新增：静态偏差（从模型加载）
        self.avg_bias = {
            'host_total': 0.0,
            'cooling_pump_total': 0.0,
            'cooling_tower_total': 0.0
        }

        # ========== 构建点位映射 ==========
        # 从 settings 中提取所有可能用到的点位 ID（字符串类型字段）
        # 注意：settings 中有些字段是数字或字典，我们需要过滤出字符串类型的点位
        self.point_ids = []
        # 手动列出需要用到的点位（也可以自动扫描，但手动更可控）
        # 总功率点位
        self.point_ids.append(settings.composite_total_host_meter)
        self.point_ids.append(settings.composite_total_cooling_tower_meter)
        self.point_ids.append(settings.composite_total_cooling_pump_meter)
        # 主机状态点
        self.point_ids.append(settings.host_1_running_status)
        self.point_ids.append(settings.host_2_running_status)
        # 冷却塔状态点
        self.point_ids.append(settings.cooling_tower_1_running_status)
        self.point_ids.append(settings.cooling_tower_2_running_status)
        self.point_ids.append(settings.cooling_tower_3_running_status)
        self.point_ids.append(settings.cooling_tower_4_running_status)
        # 冷却泵状态点
        self.point_ids.append(settings.cooling_pump_1_running_status)
        self.point_ids.append(settings.cooling_pump_2_running_status)
        self.point_ids.append(settings.cooling_pump_3_running_status)
        self.point_ids.append(settings.cooling_pump_4_running_status)
        # 温度、湿度等
        self.point_ids.append(settings.total_cooling_inlet_temp)
        self.point_ids.append(settings.total_cooling_return_temp)
        self.point_ids.append(settings.total_chilled_inlet_temp)
        self.point_ids.append(settings.total_chilled_return_temp)
        self.point_ids.append(settings.wet_bulb_temperature)
        self.point_ids.append(settings.outdoor_temperature)
        self.point_ids.append(settings.outdoor_humidity)
        self.point_ids.append(settings.instant_cooling_capacity)
        self.point_ids.append(settings.total_1_instantaneous_flow)
        self.point_ids.append(settings.system_heat_dissipation)  # composite_system_heat_dissipation
        # 可能还有蒸发器压力等，但根据模型需要添加，此处先不加
        # ===== 新增：主机模型所需点位 =====
        host_related = [
            settings.host_1_chilled_inlet_temp,
            settings.host_1_chilled_return_temp,
            settings.host_1_cooling_inlet_temp,
            settings.host_1_cooling_return_temp,
            settings.host_2_chilled_inlet_temp,
            settings.host_2_chilled_return_temp,
            settings.host_2_cooling_inlet_temp,
            settings.host_2_cooling_return_temp,
            settings.host_1_evaporator_pressure,
            settings.host_1_condenser_pressure,
            settings.host_2_evaporator_pressure,
            settings.host_2_condenser_pressure,
        ]
        self.point_ids.extend(host_related)
        # 去重
        self.point_ids = list(set(self.point_ids))
                # ========== 状态点白名单（避免散热量等连续值被误判） ==========
        self.status_point_ids = {
            settings.host_1_running_status,
            settings.host_2_running_status,
            settings.cooling_tower_1_running_status,
            settings.cooling_tower_2_running_status,
            settings.cooling_tower_3_running_status,
            settings.cooling_tower_4_running_status,
            settings.cooling_pump_1_running_status,
            settings.cooling_pump_2_running_status,
            settings.cooling_pump_3_running_status,
            settings.cooling_pump_4_running_status,
            # 以下为冷冻侧状态点，保留以防扩展，不会影响当前逻辑
            settings.chilled_pump_1_running_status,
            settings.chilled_pump_2_running_status,
            settings.chilled_pump_3_running_status,
            settings.chilled_pump_4_running_status,
        }

        # ========== 模型文件路径 ==========
        self.model_dir = os.path.join(os.path.dirname(__file__), "saved_models")

        # ========== 模型对象字典 - 三个总功率模型 ==========
        self.models = {
            'host_total': None,
            'cooling_tower_total': None,
            'cooling_pump_total': None
        }

        self.residual_models = {
            'host_total': None,
            'cooling_tower_total': None,
            'cooling_pump_total': None
        }
        self.residual_model_params = {}  # 存储每个模型的残差参数
        self.model_feature_names = {
            'host_total': [],
            'cooling_tower_total': [],
            'cooling_pump_total': []
        }
        self.model_info = {
            'host_total': {},
            'cooling_tower_total': {},
            'cooling_pump_total': {}
        }

        # ========== 模型文件前缀（从 settings 读取） ==========
        self.model_prefixes = {
            'host_total': settings.MODEL_PREFIX_HOST_TOTAL,
            'cooling_tower_total': settings.MODEL_PREFIX_COOLING_TOWER_TOTAL,
            'cooling_pump_total': settings.MODEL_PREFIX_COOLING_PUMP_TOTAL
        }

        # ========== 默认特征值（使用新点位ID作为键） ==========
        # 注意：默认值需要根据物理意义设定，这里沿用旧代码的数值，但键改为点位ID
        self.default_feature_values = {
            settings.total_chilled_return_temp: 12.0,
            settings.total_chilled_inlet_temp: 7.0,
            settings.total_cooling_inlet_temp: 32.0,
            settings.total_cooling_return_temp: 28.0,
            settings.instant_cooling_capacity: 1000.0,
            settings.coefficient_of_performance: 5.0,
            settings.host_1_running_status: 1.0,
            settings.host_2_running_status: 1.0,
            settings.cooling_pump_1_running_status: 1.0,
            settings.cooling_pump_2_running_status: 1.0,
            settings.cooling_pump_3_running_status: 1.0,
            settings.cooling_pump_4_running_status: 1.0,
            settings.cooling_tower_1_running_status: 1.0,
            settings.cooling_tower_2_running_status: 1.0,
            settings.cooling_tower_3_running_status: 1.0,
            settings.cooling_tower_4_running_status: 1.0,
            settings.outdoor_humidity: 60.0,
            settings.outdoor_temperature: 25.0,
            settings.wet_bulb_temperature: 20.0,
            settings.total_1_instantaneous_flow: 100.0,
            settings.composite_total_host_meter: 300.0,
            settings.composite_total_cooling_pump_meter: 100.0,
            settings.composite_total_cooling_tower_meter: 60.0,
            settings.system_heat_dissipation: 2000.0,
            # ===== 新增主机相关默认值 =====
            settings.host_1_chilled_inlet_temp: 7.0,
            settings.host_1_chilled_return_temp: 12.0,
            settings.host_1_cooling_inlet_temp: 32.0,
            settings.host_1_cooling_return_temp: 28.0,
            settings.host_2_chilled_inlet_temp: 7.0,
            settings.host_2_chilled_return_temp: 12.0,
            settings.host_2_cooling_inlet_temp: 32.0,
            settings.host_2_cooling_return_temp: 28.0,
            settings.host_1_evaporator_pressure: 0.5,
            settings.host_1_condenser_pressure: 1.0,
            settings.host_2_evaporator_pressure: 0.5,
            settings.host_2_condenser_pressure: 1.0,
        }

        # 步长
        self.STEP_SIZE = 0.1

        # 调度器
        self.scheduler = None
        self.is_running = False

        # 数据库连接
        self.mysql_engine = None
        self.postgres_engine = None

        # 优化配置（从数据库读取）
        self.optimization_config = None

        # Redis 客户端
        self.redis_client = None
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=2
            )
            self.redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as e:
            logger.warning(f"Redis 连接失败，将不会缓存迭代数据: {e}")

        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)

    def update_heartbeat(self):
        """更新冷却水优化表的心跳"""
        update_heartbeat(self.postgres_engine, 'cooling_opt_parameters_total', logger)
    def signal_handler(self, signum, frame):
        """处理Ctrl+C信号"""
        logger.info("接收到Ctrl+C信号，正在停止调度器...")
        self.stop_scheduler()
        sys.exit(0)

    def connect_databases(self):
        """连接MySQL和PostgreSQL数据库"""
        try:
            # 连接MySQL
            encoded_password = quote_plus(self.mysql_config['password'])
            mysql_connection_string = (
                f"mysql+pymysql://{self.mysql_config['user']}:{encoded_password}"
                f"@{self.mysql_config['host']}:{self.mysql_config['port']}/{self.mysql_config['database']}"
                f"?charset={self.mysql_config['charset']}"
            )
            self.mysql_engine = create_engine(
                mysql_connection_string,
                pool_recycle=300,
                pool_pre_ping=True,
                echo=False
            )
            with self.mysql_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("成功连接到MySQL数据库（历史数据）")

            # 连接PostgreSQL
            self.postgres_engine = create_engine(
                self.postgres_config['url'],
                pool_recycle=300,
                pool_pre_ping=True,
                echo=False
            )
            with self.postgres_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("成功连接到PostgreSQL数据库（配置和结果）")
            return True
        except Exception as e:
            logger.error(f"连接数据库失败: {e}")
            return False

    def load_optimization_config(self):
        """从cooling_opt_config表加载优化配置（id=1）"""
        try:
            if self.postgres_engine is None:
                logger.error("PostgreSQL数据库未连接")
                return False

            query = """
            SELECT 
                return_temp_lower_limit,
                return_temp_upper_limit,
                supply_temp_lower_limit,
                supply_temp_upper_limit,
                temp_diff_lower_limit,
                temp_diff_upper_limit,
                heat_dissipation_lower_limit,
                heat_dissipation_upper_limit,
                optimization_cycle_minutes,
                r2_threshold,
                energy_saving_threshold                    -- 新增
            FROM cooling_opt_config 
            WHERE id = 1
            """

            with self.postgres_engine.connect() as conn:
                result = conn.execute(text(query)).fetchone()

            if result:
                self.optimization_config = {
                    'return_temp_lower_limit': float(result[0]),
                    'return_temp_upper_limit': float(result[1]),
                    'supply_temp_lower_limit': float(result[2]),
                    'supply_temp_upper_limit': float(result[3]),
                    'temp_diff_lower_limit': float(result[4]),
                    'temp_diff_upper_limit': float(result[5]),
                    'heat_dissipation_lower_limit': float(result[6]) / 100.0,
                    'heat_dissipation_upper_limit': float(result[7]) / 100.0,
                    'optimization_cycle_minutes': int(result[8]) if result[8] is not None else 5,
                    'r2_threshold': float(result[9]) if result[9] is not None else 0.6,
                    'energy_saving_threshold': float(result[10]) if result[10] is not None else 0.0   # 新增
                }
                logger.info(f"成功加载优化配置，优化周期: {self.optimization_config['optimization_cycle_minutes']}分钟, "
                            f"R²阈值: {self.optimization_config['r2_threshold']}, 节能率阈值: {self.optimization_config['energy_saving_threshold']}%")
                return True
            else:
                logger.error("未找到id=1的优化配置")
                return False
        except Exception as e:
            logger.error(f"加载优化配置失败: {e}")
            return False   
    def get_recent_power_series(self, point_id: str, window_minutes: int = 5) -> List[float]:
        """从MySQL获取最近N分钟内的功率时间序列"""
        try:
            # 检查表是否存在
            check_query = f"SHOW TABLES LIKE '{point_id}'"
            with self.mysql_engine.connect() as conn:
                table_exists = conn.execute(text(check_query)).fetchone()
            if not table_exists:
                logger.warning(f"表 {point_id} 不存在，无法获取历史功率数据")
                return []

            query = f"""
            SELECT PointValue FROM `{point_id}`
            WHERE UpdateDateTime >= NOW() - INTERVAL {window_minutes} MINUTE
            ORDER BY UpdateDateTime ASC
            """
            with self.mysql_engine.connect() as conn:
                rows = conn.execute(text(query)).fetchall()
            values = [float(r[0]) for r in rows if r[0] is not None]
            return values
        except Exception as e:
            logger.error(f"获取 {point_id} 历史功率序列失败: {e}")
            return []

    def is_power_stable(self, point_id: str, window_minutes: int = 5,
                        std_threshold: float = None, cv_threshold: float = 0.05) -> Tuple[bool, str]:
        """
        判断功率是否稳定，返回 (是否稳定, 失败原因描述)
        :param point_id: 点位ID
        :param window_minutes: 滑动窗口时长（分钟）
        :param std_threshold: 标准差阈值（kW），若为None则使用cv_threshold
        :param cv_threshold: 变异系数阈值
        """
        powers = self.get_recent_power_series(point_id, window_minutes)
        if len(powers) < 3:  # 至少需要3个点
            reason = f"点位{point_id}历史数据不足({len(powers)}个点)，无法判断稳态"
            logger.warning(reason)
            return False, reason

        mean_val = np.mean(powers)
        std_val = np.std(powers)

        if std_threshold is not None:
            if std_val > std_threshold:
                reason = f"点位{point_id}功率不稳定(标准差{std_val:.2f}kW > 阈值{std_threshold:.2f}kW)"
                logger.warning(reason)
                return False, reason
        else:
            cv = std_val / mean_val if mean_val > 0 else 0
            if cv > cv_threshold:
                reason = f"点位{point_id}功率不稳定(变异系数{cv:.3f} > 阈值{cv_threshold})"
                logger.warning(reason)
                return False, reason
        return True, ""

    def check_all_running_devices_stable(self, feature_values: Dict) -> Tuple[bool, List[str]]:
        failure_reasons = []
        all_stable = True

        # ---------- 主机稳态检查 ----------
        host1_running = feature_values.get(settings.host_1_running_status, 0) == 1.0
        host2_running = feature_values.get(settings.host_2_running_status, 0) == 1.0

        if host1_running:
            stable, reason = self.is_power_stable(
                settings.real_time_power_of_host_meter_1,
                window_minutes=5,
                std_threshold=30.0
            )
            if not stable:
                all_stable = False
                failure_reasons.append(reason)

        if host2_running:
            stable, reason = self.is_power_stable(
                settings.real_time_power_of_host_meter_2,
                window_minutes=5,
                std_threshold=30.0
            )
            if not stable:
                all_stable = False
                failure_reasons.append(reason)

        if not (host1_running or host2_running):
            logger.info("所有主机均未运行，跳过主机稳态检查")

        # ---------- 冷却塔稳态检查（注意 1/2 共用表，3/4 共用表） ----------
        tower1_running = feature_values.get(settings.cooling_tower_1_running_status, 0) == 1.0
        tower2_running = feature_values.get(settings.cooling_tower_2_running_status, 0) == 1.0
        tower3_running = feature_values.get(settings.cooling_tower_3_running_status, 0) == 1.0
        tower4_running = feature_values.get(settings.cooling_tower_4_running_status, 0) == 1.0

        # 只要 1 或 2 运行，就检查 1/2 共用功率表
        if tower1_running or tower2_running:
            stable, reason = self.is_power_stable(
                settings.cooling_tower_1_2_power_meter_real_time_power,
                window_minutes=5,
                std_threshold=3.0
            )
            if not stable:
                all_stable = False
                failure_reasons.append(reason)

        # 只要 3 或 4 运行，就检查 3/4 共用功率表
        if tower3_running or tower4_running:
            stable, reason = self.is_power_stable(
                settings.cooling_tower_3_4_power_meter_real_time_power,
                window_minutes=5,
                std_threshold=3.0
            )
            if not stable:
                all_stable = False
                failure_reasons.append(reason)

        if not (tower1_running or tower2_running or tower3_running or tower4_running):
            logger.info("所有冷却塔均未运行，跳过冷却塔稳态检查")

        # ---------- 冷却泵稳态检查 ----------
        pump1_running = feature_values.get(settings.cooling_pump_1_running_status, 0) == 1.0
        pump2_running = feature_values.get(settings.cooling_pump_2_running_status, 0) == 1.0
        pump3_running = feature_values.get(settings.cooling_pump_3_running_status, 0) == 1.0
        pump4_running = feature_values.get(settings.cooling_pump_4_running_status, 0) == 1.0

        if pump1_running:
            stable, reason = self.is_power_stable(
                settings.cooling_pump_1_power_meter_real_time_power,
                window_minutes=5,
                std_threshold=2.0
            )
            if not stable:
                all_stable = False
                failure_reasons.append(reason)

        if pump2_running:
            stable, reason = self.is_power_stable(
                settings.cooling_pump_2_power_meter_real_time_power,
                window_minutes=5,
                std_threshold=2.0
            )
            if not stable:
                all_stable = False
                failure_reasons.append(reason)

        if pump3_running:
            stable, reason = self.is_power_stable(
                settings.cooling_pump_3_power_meter_real_time_power,
                window_minutes=5,
                std_threshold=2.0
            )
            if not stable:
                all_stable = False
                failure_reasons.append(reason)

        # 4#冷却泵无功率表，跳过检查

        if not (pump1_running or pump2_running or pump3_running or pump4_running):
            logger.info("所有冷却泵均未运行，跳过冷却泵稳态检查")

        return all_stable, failure_reasons

    
    def check_model_r2(self) -> Tuple[bool, List[str]]:
        """检查三个总模型的R²是否均大于等于阈值（从数据库 model_evaluations 表获取）"""
        if self.optimization_config is None:
            return False, ["优化配置未加载"]
        threshold = self.optimization_config['r2_threshold']
        failure_reasons = []
        all_pass = True

        # 直接映射模型关键字到设备 ID（根据您的查询结果：1=主机总功率，2=冷却塔总功率，3=冷却泵总功率）
        model_device_id_map = {
            'host_total': 1,
            'cooling_tower_total': 2,
            'cooling_pump_total': 3
        }

        for model_key, device_id in model_device_id_map.items():
            r2 = self._get_latest_r2_for_device_id(device_id)
            if r2 is None:
                all_pass = False
                failure_reasons.append(f"{model_key}模型无R²评估记录")
            elif r2 < threshold:
                all_pass = False
                failure_reasons.append(f"{model_key}模型R²({r2:.3f}) < 阈值({threshold})")
            else:
                logger.info(f"{model_key}模型R²({r2:.3f}) ≥ 阈值({threshold})")
        return all_pass, failure_reasons

    def _get_latest_r2_for_device_id(self, device_id: int) -> Optional[float]:
        """根据设备 ID 从 PostgreSQL 获取最新的 R² 值"""
        try:
            query = """
            SELECT r_squared
            FROM model_evaluations
            WHERE model_id = :model_id
            ORDER BY created_at DESC
            LIMIT 1
            """
            with self.postgres_engine.connect() as conn:
                result = conn.execute(text(query), {"model_id": device_id}).fetchone()
                if result:
                    return float(result[0])
        except Exception as e:
            logger.error(f"获取设备 ID {device_id} 的 R² 失败: {e}")
        return None
       
    def load_models(self):
        """依次加载三个总功率模型（包括残差模型）"""
        try:
            if not os.path.exists(self.model_dir):
                logger.error(f"模型目录不存在: {self.model_dir}")
                return False

            for model_key, model_prefix in self.model_prefixes.items():
                model_path = None
                for file in os.listdir(self.model_dir):
                    if file.startswith(model_prefix):
                        model_path = os.path.join(self.model_dir, file)
                        logger.info(f"找到{model_key}模型文件: {file}")
                        break
                if not model_path:
                    logger.error(f"未找到{model_key}模型文件: {model_prefix}")
                    return False

                logger.info(f"加载{model_key}模型: {model_path}")
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)

                self.models[model_key] = model_data['model']
                self.residual_models[model_key] = model_data.get('residual_model')
                self.model_feature_names[model_key] = model_data.get('feature_names', [])
                self.model_info[model_key] = {
                    'model_params': model_data.get('model_params', {}),
                    'training_stats': model_data.get('training_stats', {}),
                    'feature_importance': model_data.get('feature_importance', {})
                }
                # 加载残差模型参数
                self.residual_model_params[model_key] = {
                    'residual_lags': model_data.get('residual_lags', 0),
                    'use_standardize': model_data.get('use_standardize', False),
                    'residual_mean': model_data.get('residual_mean', 0.0),
                    'residual_std': model_data.get('residual_std', 1.0)
                }
                # 新增：加载 avg_bias
                self.avg_bias[model_key] = model_data.get('avg_bias', 0.0)
                has_residual = self.residual_models[model_key] is not None
                logger.info(
                    f"{model_key}模型加载成功，特征数: {len(self.model_feature_names[model_key])}, 含残差模型: {has_residual}")
                logger.info(f"{model_key} 残差滞后步数: {self.residual_model_params[model_key]['residual_lags']}")
                # 新增：打印特征名称列表，以便检查是否包含正确的温度点位ID
                logger.info(f"{model_key} 特征名称列表: {self.model_feature_names[model_key]}")

            return True
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def check_data_recency(self, point_id: str) -> bool:
        """检查指定点位的最新数据是否在5分钟以内"""
        try:
            if self.mysql_engine is None:
                logger.warning("MySQL数据库未连接")
                return False

            # 检查表是否存在
            check_query = f"SHOW TABLES LIKE '{point_id}'"
            with self.mysql_engine.connect() as conn:
                table_exists = conn.execute(text(check_query)).fetchone()
            if not table_exists:
                logger.warning(f"表 {point_id} 不存在")
                return False

            query = f"SELECT MAX(UpdateDateTime) FROM `{point_id}`"
            with self.mysql_engine.connect() as conn:
                result = conn.execute(text(query)).fetchone()

            if result and result[0]:
                latest_time = result[0]
                current_time = datetime.now()
                time_diff = current_time - latest_time
                time_diff_minutes = time_diff.total_seconds() / 60
                if time_diff_minutes <= self.data_recency_minutes:
                    return True
                else:
                    logger.warning(
                        f"表 {point_id} 最新数据已超过{self.data_recency_minutes}分钟: {time_diff_minutes:.1f}分钟")
                    return False
            else:
                logger.warning(f"表 {point_id} 无数据")
                return False
        except Exception as e:
            logger.error(f"检查数据时效性失败 ({point_id}): {e}")
            return False

    def check_all_data_recency(self) -> bool:
        """检查所有特征点的最新数据是否都在5分钟以内（只检查部分关键点位）"""
        logger.info("检查数据时效性...")
        # 检查关键点位：冷却水供回水温度、湿球温度、总功率等
        key_points = [
            settings.total_cooling_inlet_temp,
            settings.total_cooling_return_temp,
            settings.wet_bulb_temperature,
            settings.composite_total_host_meter,
            settings.composite_total_cooling_tower_meter,
            settings.composite_total_cooling_pump_meter
        ]
        all_tables_valid = True
        for point_id in key_points:
            if not self.check_data_recency(point_id):
                all_tables_valid = False
        if all_tables_valid:
            logger.info(f"所有关键点位数据均在{self.data_recency_minutes}分钟内")
        else:
            logger.warning("部分关键点位数据超时")
        return all_tables_valid

    def get_latest_data(self):
        """获取所有点位的最新数据，返回字典 {point_id: value} 和数据时间"""
        try:
            if self.mysql_engine is None:
                logger.warning("MySQL数据库未连接，使用默认值")
                return self.default_feature_values.copy(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            feature_values = {}
            data_time = None

            for point_id in self.point_ids:
                try:
                    # 检查表是否存在
                    check_query = f"SHOW TABLES LIKE '{point_id}'"
                    with self.mysql_engine.connect() as conn:
                        table_exists = conn.execute(text(check_query)).fetchone()
                    if not table_exists:
                        logger.warning(f"表 {point_id} 不存在，使用默认值")
                        if point_id in self.default_feature_values:
                            feature_values[point_id] = self.default_feature_values[point_id]
                        continue

                    query = f"SELECT PointValue, UpdateDateTime FROM `{point_id}` ORDER BY UpdateDateTime DESC LIMIT 1"
                    with self.mysql_engine.connect() as conn:
                        result = conn.execute(text(query)).fetchone()

                    if result and result[0] is not None:
                        try:
                            # 判断是否为状态点（通过ID中的 "di" 或 "status" 粗略判断）
                                                        # 判断是否为状态点（使用白名单）
                            if point_id in self.status_point_ids:
                                # 尝试多种解析方式
                                parsed_value = None
                                raw_value = result[0] 
                                if isinstance(raw_value, (int, float)):
                                    if raw_value in (0, 1):
                                        parsed_value = float(raw_value)
                                    else:
                                        logger.warning(f"状态点 {point_id} 读到数值 {raw_value}，视为运行（非0）")
                                        parsed_value = 1.0 if raw_value != 0 else 0.0
                                else:
                                    s = str(raw_value).strip().lower()
                                    if s in ['true', 'on', '运行', '1', 'open', 'opened']:
                                        parsed_value = 1.0
                                    elif s in ['false', 'off', '停止', '0', 'close', 'closed']:
                                        parsed_value = 0.0
                                    else:
                                        try:
                                            num = float(s)
                                            parsed_value = 1.0 if num != 0 else 0.0
                                        except:
                                            logger.warning(f"无法解析状态点 {point_id} 的值 '{raw_value}'，使用默认值 0")
                                            parsed_value = 0.0
                                feature_values[point_id] = parsed_value
                                logger.info(f"状态点 {point_id} 原始值: {raw_value}, 解析后: {parsed_value}")
                            else:
                                feature_values[point_id] = float(result[0])

                            # 记录第一个非空数据的时间作为整体数据时间（简单处理）
                            if data_time is None:
                                data_time = result[1]
                        except (ValueError, TypeError) as e:
                            logger.warning(f"点位 {point_id} 值无法转换为浮点数: {result[0]}, 错误: {e}")
                            if point_id in self.default_feature_values:
                                feature_values[point_id] = self.default_feature_values[point_id]
                    else:
                        logger.warning(f"无法获取 {point_id} 的最新值，使用默认值")
                        if point_id in self.default_feature_values:
                            feature_values[point_id] = self.default_feature_values[point_id]
                except Exception as e:
                    logger.warning(f"获取 {point_id} 失败: {e}")
                    if point_id in self.default_feature_values:
                        feature_values[point_id] = self.default_feature_values[point_id]

            # 补充默认值中但未获取到的点位
            for point_id, default_val in self.default_feature_values.items():
                if point_id not in feature_values:
                    feature_values[point_id] = default_val

            if data_time is None:
                data_time = datetime.now()

            logger.info(f"成功获取 {len(feature_values)} 个点位的最新数据（时间: {data_time}）")
            # 简要记录设备状态
            host1_status = feature_values.get(settings.host_1_running_status, 0)
            host2_status = feature_values.get(settings.host_2_running_status, 0)
            host_running = host1_status == 1.0 or host2_status == 1.0
            logger.info(f"主机运行状态: {'运行' if host_running else '停止'} (1#:{host1_status}, 2#:{host2_status})")

            pump_statuses = [
                feature_values.get(settings.cooling_pump_1_running_status, 0),
                feature_values.get(settings.cooling_pump_2_running_status, 0),
                feature_values.get(settings.cooling_pump_3_running_status, 0),
                feature_values.get(settings.cooling_pump_4_running_status, 0)
            ]
            pump_running = any(s == 1.0 for s in pump_statuses)
            logger.info(f"冷却泵运行状态: {'运行' if pump_running else '停止'} (1#:{pump_statuses[0]}, 2#:{pump_statuses[1]}, 3#:{pump_statuses[2]}, 4#:{pump_statuses[3]})")

            tower_statuses = [
                feature_values.get(settings.cooling_tower_1_running_status, 0),
                feature_values.get(settings.cooling_tower_2_running_status, 0),
                feature_values.get(settings.cooling_tower_3_running_status, 0),
                feature_values.get(settings.cooling_tower_4_running_status, 0)
            ]
            tower_running = any(s == 1.0 for s in tower_statuses)
            logger.info(f"冷却塔运行状态: {'运行' if tower_running else '停止'} (1#:{tower_statuses[0]}, 2#:{tower_statuses[1]}, 3#:{tower_statuses[2]}, 4#:{tower_statuses[3]})")

            return feature_values, data_time
        except Exception as e:
            logger.error(f"获取最新数据失败: {e}")
            logger.info("使用默认特征值继续...")
            return self.default_feature_values.copy(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def prepare_features(self, feature_values: Dict, cooling_inlet_temp: float, cooling_return_temp: float,
                        model_key: str):
        """准备特征数据，更新冷却水供水温度和回水温度，并处理属性名到点位ID的映射"""
        try:
            # 更新特征字典中的冷却水温度（使用点位ID作为键）
            feature_values[settings.total_cooling_inlet_temp] = cooling_inlet_temp
            feature_values[settings.total_cooling_return_temp] = cooling_return_temp

            feature_names = self.model_feature_names[model_key]
            if not feature_names:
                logger.warning(f"{model_key} 特征列表为空，无法准备特征")
                return None

            features = []
            for feature_name in feature_names:
                # 1. 直接作为点位ID尝试（兼容旧数据）
                if feature_name in feature_values:
                    features.append(feature_values[feature_name])
                    continue

                # 2. 尝试将 feature_name 解释为 settings 中的属性名，获取对应的点位ID
                point_id = None
                try:
                    point_id = getattr(settings, feature_name, None)
                    if point_id is not None and isinstance(point_id, str) and point_id in feature_values:
                        features.append(feature_values[point_id])
                        continue
                except Exception:
                    pass

                # 3. 处理派生特征：运行状态
                if feature_name == 'host_running_status':
                    s1 = feature_values.get(settings.host_1_running_status, 0)
                    s2 = feature_values.get(settings.host_2_running_status, 0)
                    features.append(1.0 if s1 == 1.0 or s2 == 1.0 else 0.0)
                    continue
                elif feature_name == 'cooling_pump_running_status':
                    pumps = [
                        feature_values.get(settings.cooling_pump_1_running_status, 0),
                        feature_values.get(settings.cooling_pump_2_running_status, 0),
                        feature_values.get(settings.cooling_pump_3_running_status, 0),
                        feature_values.get(settings.cooling_pump_4_running_status, 0)
                    ]
                    features.append(1.0 if any(p == 1.0 for p in pumps) else 0.0)
                    continue
                elif feature_name == 'cooling_tower_running_status':
                    towers = [
                        feature_values.get(settings.cooling_tower_1_running_status, 0),
                        feature_values.get(settings.cooling_tower_2_running_status, 0),
                        feature_values.get(settings.cooling_tower_3_running_status, 0),
                        feature_values.get(settings.cooling_tower_4_running_status, 0)
                    ]
                    features.append(1.0 if any(t == 1.0 for t in towers) else 0.0)
                    continue

                # 4. 未知特征，使用默认值（按类型推断）
                default_val = 0.0
                if 'temp' in feature_name.lower():
                    default_val = 25.0
                elif 'pressure' in feature_name.lower():
                    default_val = 1.0
                elif 'power' in feature_name.lower():
                    default_val = 100.0
                elif 'cop' in feature_name.lower():
                    default_val = 5.0
                elif 'capacity' in feature_name.lower():
                    default_val = 1000.0
                elif 'flow' in feature_name.lower():
                    default_val = 100.0
                elif 'humidity' in feature_name.lower():
                    default_val = 60.0
                features.append(default_val)
                logger.debug(f"特征 {feature_name} 未找到，使用默认值 {default_val}")

            features_array = np.array(features).reshape(1, -1)
            return features_array
        except Exception as e:
            logger.error(f"准备{model_key}特征数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def predict_power_with_status(self, model_key: str, features_array: np.ndarray, feature_values: Dict,
                                cooling_inlet_temp: float, cooling_return_temp: float,
                                historical_residuals: Optional[List[float]] = None) -> float:
        """预测总功率，考虑对应设备组的运行状态，并使用历史残差进行滞后特征构造"""
        try:
            POWER_THRESHOLD = 10.0  # 功率阈值（kW），可根据现场设备待机功率调整

            # 确定该模型对应的设备组是否有设备运行，并获取当前功率
            device_group_running = True
            if model_key == 'host_total':
                host1 = feature_values.get(settings.host_1_running_status, 1.0)
                host2 = feature_values.get(settings.host_2_running_status, 1.0)
                device_group_running = (host1 == 1.0 or host2 == 1.0)
                current_power = feature_values.get(settings.composite_total_host_meter, 300.0)
            elif model_key == 'cooling_pump_total':
                pumps = [
                    feature_values.get(settings.cooling_pump_1_running_status, 1.0),
                    feature_values.get(settings.cooling_pump_2_running_status, 1.0),
                    feature_values.get(settings.cooling_pump_3_running_status, 1.0),
                    feature_values.get(settings.cooling_pump_4_running_status, 1.0)
                ]
                device_group_running = any(p == 1.0 for p in pumps)
                current_power = feature_values.get(settings.composite_total_cooling_pump_meter, 100.0)
            elif model_key == 'cooling_tower_total':
                towers = [
                    feature_values.get(settings.cooling_tower_1_running_status, 1.0),
                    feature_values.get(settings.cooling_tower_2_running_status, 1.0),
                    feature_values.get(settings.cooling_tower_3_running_status, 1.0),
                    feature_values.get(settings.cooling_tower_4_running_status, 1.0)
                ]
                device_group_running = any(t == 1.0 for t in towers)
                current_power = feature_values.get(settings.composite_total_cooling_tower_meter, 60.0)
            else:
                return 0.0

            # 容错：状态全停但功率大于阈值，视为状态错误继续预测
            if not device_group_running:
                if current_power > POWER_THRESHOLD:
                    logger.debug(
                        f"{model_key} 状态全停但功率 {current_power:.2f} > {POWER_THRESHOLD}kW，视为状态错误，继续预测")
                else:
                    return 0.0

            if self.models[model_key] is None:
                logger.warning(f"{model_key}模型未加载，使用默认总功率")
                return current_power

            # 基础预测
            feature_names = self.model_feature_names[model_key]
            if len(feature_names) != features_array.shape[1]:
                temp_names = [f'feature_{i}' for i in range(features_array.shape[1])]
                dmatrix = xgb.DMatrix(features_array, feature_names=temp_names)
            else:
                dmatrix = xgb.DMatrix(features_array, feature_names=feature_names)

            base_pred = self.models[model_key].predict(dmatrix)[0]
            # 静态偏差修正（训练集平均偏差）
            base_pred += self.avg_bias.get(model_key, 0.0)
            final_pred = base_pred

            # 残差模型处理
            residual_model = self.residual_models.get(model_key)
            residual_params = self.residual_model_params.get(model_key, {})
            residual_lags = residual_params.get('residual_lags', 0)
            use_standardize = residual_params.get('use_standardize', False)
            residual_mean = residual_params.get('residual_mean', 0.0)
            residual_std = residual_params.get('residual_std', 1.0)

            if residual_model is not None:
                # 构造残差模型输入特征
                if residual_lags > 0:
                    # 需要滞后特征
                    if historical_residuals is None:
                        # 无历史残差，用0填充
                        lag_features = np.zeros((features_array.shape[0], residual_lags))
                        logger.debug(f"{model_key} 无历史残差，使用0填充滞后特征")
                    else:
                        # 确保队列长度足够，不足时前面补0
                        if len(historical_residuals) < residual_lags:
                            pad = [0.0] * (residual_lags - len(historical_residuals))
                            full_residuals = pad + historical_residuals
                        else:
                            full_residuals = historical_residuals[-residual_lags:]  # 取最近 lag 个（时间顺序）
                        lag_features = np.tile(full_residuals, (features_array.shape[0], 1))
                        logger.debug(f"{model_key} 使用历史残差 {full_residuals} 构造滞后特征")

                    X_res = np.hstack([features_array, lag_features])
                else:
                    X_res = features_array

                try:
                    residual_pred_scaled = residual_model.predict(X_res)
                    # 处理预测结果形状
                    if isinstance(residual_pred_scaled, np.ndarray):
                        if residual_pred_scaled.ndim == 2 and residual_pred_scaled.shape[1] == 1:
                            residual_pred_scaled = residual_pred_scaled[0, 0]
                        elif residual_pred_scaled.ndim == 1:
                            residual_pred_scaled = residual_pred_scaled[0]
                        else:
                            residual_pred_scaled = residual_pred_scaled.item()
                    else:
                        residual_pred_scaled = float(residual_pred_scaled)

                    if use_standardize:
                        residual_pred = residual_pred_scaled * residual_std + residual_mean
                    else:
                        residual_pred = residual_pred_scaled

                    logger.debug(f"{model_key} 残差预测值: {residual_pred}")
                    final_pred = base_pred + residual_pred
                except Exception as e:
                    logger.warning(f"{model_key} 残差模型预测失败: {e}，使用基础预测")
                    final_pred = base_pred

            logger.debug(f"{model_key} 最终预测功率: {final_pred}")
            return float(final_pred)
        except Exception as e:
            logger.error(f"{model_key}预测失败: {e}")
            import traceback
            traceback.print_exc()
            return 0.0

    def calculate_system_heat_dissipation(self, host_power: float, instant_cooling_capacity: float) -> float:
        return host_power + instant_cooling_capacity

    def calculate_total_power(self, host_power: float, cooling_tower_power: float, cooling_pump_power: float) -> float:
        return host_power + cooling_tower_power + cooling_pump_power

    def get_optimization_constraints(self, base_feature_values: Dict) -> Dict:
        if self.optimization_config is None:
            logger.error("优化配置未加载")
            return None

        wet_bulb_temp = base_feature_values.get(settings.wet_bulb_temperature, 20.0)
        return_temp_lower_limit = self.optimization_config['return_temp_lower_limit']
        supply_temp_lower_limit = self.optimization_config['supply_temp_lower_limit']
        Tmin_return = wet_bulb_temp + return_temp_lower_limit
        Tmin_supply = wet_bulb_temp + supply_temp_lower_limit
        inlet_max = self.optimization_config['supply_temp_upper_limit']
        return_max = self.optimization_config['return_temp_upper_limit']
        delta_temp_min = self.optimization_config['temp_diff_lower_limit']
        delta_temp_max = self.optimization_config['temp_diff_upper_limit']

        return {
            'wet_bulb_temp': round(wet_bulb_temp, 1),
            'Tmin_return': round(Tmin_return, 1),
            'Tmin_supply': round(Tmin_supply, 1),
            'inlet_min': round(max(Tmin_supply, wet_bulb_temp + 1), 1),
            'inlet_max': round(inlet_max, 1),
            'return_min': round(max(Tmin_return, wet_bulb_temp + 1), 1),
            'return_max': round(return_max, 1),
            'delta_temp_min': delta_temp_min,
            'delta_temp_max': delta_temp_max,
            'step_size': self.STEP_SIZE,
            'heat_dissipation_lower_limit': self.optimization_config['heat_dissipation_lower_limit'],
            'heat_dissipation_upper_limit': self.optimization_config['heat_dissipation_upper_limit']
        }

    def generate_temperature_pairs(self, constraints: Dict):
        if constraints is None:
            return []
        inlet_temps = np.arange(constraints['inlet_min'], constraints['inlet_max'] + self.STEP_SIZE, self.STEP_SIZE)
        inlet_temps = [round(temp, 1) for temp in inlet_temps]
        return_temps = np.arange(constraints['return_min'], constraints['return_max'] + self.STEP_SIZE, self.STEP_SIZE)
        return_temps = [round(temp, 1) for temp in return_temps]
        pairs = []
        for inlet_temp in inlet_temps:
            for return_temp in return_temps:
                if inlet_temp > return_temp:
                    pairs.append((inlet_temp, return_temp))
        logger.info(f"生成了 {len(pairs)} 个温度组合")
        return pairs

    def find_optimal_temperature_pair(self, base_feature_values: Dict,
                                  historical_residuals: Optional[Dict] = None):
        try:
            # 检查模型是否已加载
            if any(model is None for model in self.models.values()):
                logger.error("存在未加载的模型，无法执行优化搜索")
                return None

            constraints = self.get_optimization_constraints(base_feature_values)
            if constraints is None:
                logger.error("获取优化约束失败")
                return None

            # 获取当前运行参数
            current_system_heat_dissipation = base_feature_values.get(settings.system_heat_dissipation, 2000.0)
            current_instant_cooling_capacity = base_feature_values.get(settings.instant_cooling_capacity, 1000.0)
            current_cooling_inlet_temp = base_feature_values.get(settings.total_cooling_inlet_temp, 32.0)
            current_cooling_return_temp = base_feature_values.get(settings.total_cooling_return_temp, 28.0)
            current_host_power = base_feature_values.get(settings.composite_total_host_meter, 300.0)
            current_cooling_pump_power = base_feature_values.get(settings.composite_total_cooling_pump_meter, 100.0)
            current_cooling_tower_power = base_feature_values.get(settings.composite_total_cooling_tower_meter, 60.0)

            # 设备状态
            host1_status = base_feature_values.get(settings.host_1_running_status, 1.0)
            host2_status = base_feature_values.get(settings.host_2_running_status, 1.0)
            pump_statuses = [
                base_feature_values.get(settings.cooling_pump_1_running_status, 1.0),
                base_feature_values.get(settings.cooling_pump_2_running_status, 1.0),
                base_feature_values.get(settings.cooling_pump_3_running_status, 1.0),
                base_feature_values.get(settings.cooling_pump_4_running_status, 1.0)
            ]
            tower_statuses = [
                base_feature_values.get(settings.cooling_tower_1_running_status, 1.0),
                base_feature_values.get(settings.cooling_tower_2_running_status, 1.0),
                base_feature_values.get(settings.cooling_tower_3_running_status, 1.0),
                base_feature_values.get(settings.cooling_tower_4_running_status, 1.0)
            ]
            host_running = host1_status == 1.0 or host2_status == 1.0
            pump_running = any(p == 1.0 for p in pump_statuses)
            tower_running = any(t == 1.0 for t in tower_statuses)

            current_total_power = self.calculate_total_power(
                current_host_power, current_cooling_tower_power, current_cooling_pump_power
            )

            logger.info("=" * 60)
            logger.info("优化约束条件详细报告:")
            logger.info(f"  湿球温度: {constraints['wet_bulb_temp']}℃")
            logger.info(f"  当前供水温度: {current_cooling_inlet_temp}℃, 回水温度: {current_cooling_return_temp}℃")
            logger.info(f"  供水温度范围: {constraints['inlet_min']}℃ ~ {constraints['inlet_max']}℃")
            logger.info(f"  回水温度范围: {constraints['return_min']}℃ ~ {constraints['return_max']}℃")
            logger.info(f"  温差范围: {constraints['delta_temp_min']}℃ ~ {constraints['delta_temp_max']}℃")
            logger.info(f"  散热量范围: {constraints['heat_dissipation_lower_limit']*100:.0f}% ~ {constraints['heat_dissipation_upper_limit']*100:.0f}%")
            logger.info(f"  当前总功率: {current_total_power:.2f} kW")
            logger.info("=" * 60)

            temperature_pairs = self.generate_temperature_pairs(constraints)
            logger.info(f"生成的温度组合总数: {len(temperature_pairs)}")
            if not temperature_pairs:
                logger.error("未生成有效的温度组合，请检查约束条件（尤其是供回水温度范围及步长）")
                return None

            results = []
            # 细化计数器
            filtered_by_delta_low = 0   # 温差低于下限
            filtered_by_delta_high = 0  # 温差高于上限
            filtered_by_inlet_low = 0   # 供水温度低于下限
            filtered_by_inlet_high = 0  # 供水温度高于上限
            filtered_by_return_low = 0  # 回水温度低于下限
            filtered_by_return_high = 0 # 回水温度高于上限
            filtered_by_heat_low = 0    # 散热量低于下限
            filtered_by_heat_high = 0   # 散热量高于上限
            feature_failed = 0
            other_error = 0

            for idx, (inlet_temp, return_temp) in enumerate(temperature_pairs):
                delta_temp = inlet_temp - return_temp
                log_filter = idx < 10   # 仅前10个打印详细原因

                # 温差过滤（区分高低）
                if delta_temp < constraints['delta_temp_min']:
                    filtered_by_delta_low += 1
                    if log_filter:
                        logger.debug(f"组合{idx}: 温差{delta_temp:.1f}℃ 低于下限 {constraints['delta_temp_min']}℃")
                    continue
                if delta_temp > constraints['delta_temp_max']:
                    filtered_by_delta_high += 1
                    if log_filter:
                        logger.debug(f"组合{idx}: 温差{delta_temp:.1f}℃ 高于上限 {constraints['delta_temp_max']}℃")
                    continue

                # 供水温度过滤（区分高低）
                if inlet_temp < constraints['inlet_min']:
                    filtered_by_inlet_low += 1
                    if log_filter:
                        logger.debug(f"组合{idx}: 供水温度{inlet_temp}℃ 低于下限 {constraints['inlet_min']}℃")
                    continue
                if inlet_temp > constraints['inlet_max']:
                    filtered_by_inlet_high += 1
                    if log_filter:
                        logger.debug(f"组合{idx}: 供水温度{inlet_temp}℃ 高于上限 {constraints['inlet_max']}℃")
                    continue

                # 回水温度过滤（区分高低）
                if return_temp < constraints['return_min']:
                    filtered_by_return_low += 1
                    if log_filter:
                        logger.debug(f"组合{idx}: 回水温度{return_temp}℃ 低于下限 {constraints['return_min']}℃")
                    continue
                if return_temp > constraints['return_max']:
                    filtered_by_return_high += 1
                    if log_filter:
                        logger.debug(f"组合{idx}: 回水温度{return_temp}℃ 高于上限 {constraints['return_max']}℃")
                    continue

                try:
                    # 准备三个模型的特征
                    host_features = self.prepare_features(base_feature_values.copy(), inlet_temp, return_temp, 'host_total')
                    pump_features = self.prepare_features(base_feature_values.copy(), inlet_temp, return_temp, 'cooling_pump_total')
                    tower_features = self.prepare_features(base_feature_values.copy(), inlet_temp, return_temp, 'cooling_tower_total')
                    if any(f is None for f in [host_features, pump_features, tower_features]):
                        feature_failed += 1
                        if log_filter:
                            logger.debug(f"组合{idx}: 特征准备失败 (host_features={host_features is not None}, pump={pump_features is not None}, tower={tower_features is not None})")
                        continue

                    # 预测三个总功率
                    host_power = self.predict_power_with_status(
                        'host_total', host_features, base_feature_values,
                        inlet_temp, return_temp,
                        historical_residuals=historical_residuals.get('host_total') if historical_residuals else None
                    )
                    pump_power = self.predict_power_with_status(
                        'cooling_pump_total', pump_features, base_feature_values,
                        inlet_temp, return_temp,
                        historical_residuals=historical_residuals.get('cooling_pump_total') if historical_residuals else None
                    )
                    tower_power = self.predict_power_with_status(
                        'cooling_tower_total', tower_features, base_feature_values,
                        inlet_temp, return_temp,
                        historical_residuals=historical_residuals.get('cooling_tower_total') if historical_residuals else None
                    )

                    # 打印第一个有效组合的预测功率
                    if not results and idx < 20:
                        logger.info(f"首个有效组合(供水{inlet_temp}℃,回水{return_temp}℃): 主机={host_power:.2f}kW, 冷却泵={pump_power:.2f}kW, 冷却塔={tower_power:.2f}kW, 总={host_power+pump_power+tower_power:.2f}kW")

                    # 散热量检查（区分高低）
                    system_heat_dissipation = self.calculate_system_heat_dissipation(host_power, current_instant_cooling_capacity)
                    min_heat = constraints['heat_dissipation_lower_limit'] * current_system_heat_dissipation
                    max_heat = constraints['heat_dissipation_upper_limit'] * current_system_heat_dissipation
                    if system_heat_dissipation < min_heat:
                        filtered_by_heat_low += 1
                        if log_filter:
                            logger.debug(f"组合{idx}: 散热量{system_heat_dissipation:.1f}kW 低于下限 {min_heat:.1f}kW (当前散热量{current_system_heat_dissipation:.1f}kW)")
                        continue
                    if system_heat_dissipation > max_heat:
                        filtered_by_heat_high += 1
                        if log_filter:
                            logger.debug(f"组合{idx}: 散热量{system_heat_dissipation:.1f}kW 高于上限 {max_heat:.1f}kW (当前散热量{current_system_heat_dissipation:.1f}kW)")
                        continue

                    # 通过所有检查，计算总功率并添加到结果列表
                    total_power = self.calculate_total_power(host_power, tower_power, pump_power)
                    power_diff = total_power - current_total_power
                    inlet_temp_diff = abs(inlet_temp - current_cooling_inlet_temp)
                    return_temp_diff = abs(return_temp - current_cooling_return_temp)

                    results.append({
                        'cooling_inlet_temp': inlet_temp,
                        'cooling_return_temp': return_temp,
                        'actual_inlet_temp': round(inlet_temp, 1),
                        'actual_return_temp': round(return_temp, 1),
                        'delta_temp': round(delta_temp, 1),
                        'host_power': round(host_power, 2),
                        'cooling_pump_power': round(pump_power, 2),
                        'cooling_tower_power': round(tower_power, 2),
                        'total_power': round(total_power, 2),
                        'system_heat_dissipation': round(system_heat_dissipation, 2),
                        'heat_dissipation_percent': round(system_heat_dissipation / current_system_heat_dissipation * 100, 1),
                        'power_diff': round(power_diff, 2),
                        'power_diff_percent': round(power_diff / current_total_power * 100, 2) if current_total_power != 0 else 0,
                        'inlet_temp_diff': round(inlet_temp_diff, 1),
                        'return_temp_diff': round(return_temp_diff, 1),
                        'host_running': host_running,
                        'pump_running': pump_running,
                        'tower_running': tower_running,
                        'is_valid': True
                    })
                except Exception as e:
                    other_error += 1
                    if idx < 10:
                        logger.debug(f"组合{idx}: 预测过程异常 - {e}")
                    continue

            # 输出详细过滤统计
            filter_stats = {
                'total_pairs': len(temperature_pairs),
                'delta_low': filtered_by_delta_low,
                'delta_high': filtered_by_delta_high,
                'inlet_low': filtered_by_inlet_low,
                'inlet_high': filtered_by_inlet_high,
                'return_low': filtered_by_return_low,
                'return_high': filtered_by_return_high,
                'heat_low': filtered_by_heat_low,
                'heat_high': filtered_by_heat_high,
                'feature_failed': feature_failed,
                'other_error': other_error
            }
            logger.info(
                f"过滤统计: 温差低于下限={filtered_by_delta_low}, 温差高于上限={filtered_by_delta_high}, "
                f"供水低于下限={filtered_by_inlet_low}, 供水高于上限={filtered_by_inlet_high}, "
                f"回水低于下限={filtered_by_return_low}, 回水高于上限={filtered_by_return_high}, "
                f"散热量低于下限={filtered_by_heat_low}, 散热量高于上限={filtered_by_heat_high}, "
                f"特征失败={feature_failed}, 其他错误={other_error}"
            )
            logger.info(f"满足所有约束的有效组合数: {len(results)}")

            if not results:
                logger.warning("未找到满足所有约束条件的温度组合")
                return {
                    'success': False,
                    'reason': 'no_valid_combinations',
                    'filter_stats': filter_stats,
                    'constraints': constraints
                }

            results.sort(key=lambda x: x['total_power'])
            optimal_result = results[0]
            logger.info(f"最优组合总功率: {optimal_result['total_power']:.2f} kW, 供水{optimal_result['cooling_inlet_temp']}℃, 回水{optimal_result['cooling_return_temp']}℃")

            # 节能率阈值检查
            energy_saving_threshold = self.optimization_config.get('energy_saving_threshold', 0.0)
            optimal_total_power = optimal_result['total_power']
            energy_saving_percent = (current_total_power - optimal_total_power) / current_total_power * 100.0
            logger.info(f"节能率: {energy_saving_percent:.2f}% (阈值: {energy_saving_threshold}%)")

            if energy_saving_percent < energy_saving_threshold:
                logger.info(f"最优组合节能率 {energy_saving_percent:.2f}% 低于阈值 {energy_saving_threshold}%，无有效优化")
                return {
                    'success': False,
                    'reason': 'energy_saving_too_low',
                    'energy_saving_percent': energy_saving_percent,
                    'threshold': energy_saving_threshold,
                    'optimal_power': optimal_total_power,
                    'current_power': current_total_power,
                    'filter_stats': filter_stats,
                    'constraints': constraints
                }

            if optimal_result['total_power'] >= current_total_power:
                logger.info(f"最优组合预测功率 {optimal_result['total_power']:.2f} kW 不低于当前 {current_total_power:.2f} kW，无有效优化")
                return {
                    'success': False,
                    'reason': 'power_not_lower',
                    'optimal_power': optimal_result['total_power'],
                    'current_power': current_total_power,
                    'filter_stats': filter_stats,
                    'constraints': constraints
                }

            # 最优温度组合预测对比
            inlet = optimal_result['cooling_inlet_temp']
            ret = optimal_result['cooling_return_temp']
            host_feat_opt = self.prepare_features(base_feature_values.copy(), inlet, ret, 'host_total')
            pump_feat_opt = self.prepare_features(base_feature_values.copy(), inlet, ret, 'cooling_pump_total')
            tower_feat_opt = self.prepare_features(base_feature_values.copy(), inlet, ret, 'cooling_tower_total')
            if all(f is not None for f in [host_feat_opt, pump_feat_opt, tower_feat_opt]):
                def base_only(model_key, feat):
                    fnames = self.model_feature_names[model_key]
                    if len(fnames) != feat.shape[1]:
                        dmat = xgb.DMatrix(feat, feature_names=[f'f{i}' for i in range(feat.shape[1])])
                    else:
                        dmat = xgb.DMatrix(feat, feature_names=fnames)
                    return self.models[model_key].predict(dmat)[0]

                base_host_only = base_only('host_total', host_feat_opt)
                base_pump_only = base_only('cooling_pump_total', pump_feat_opt)
                base_tower_only = base_only('cooling_tower_total', tower_feat_opt)
                base_total_only = base_host_only + base_pump_only + base_tower_only

                base_host_bias = base_host_only + self.avg_bias.get('host_total', 0.0)
                base_pump_bias = base_pump_only + self.avg_bias.get('cooling_pump_total', 0.0)
                base_tower_bias = base_tower_only + self.avg_bias.get('cooling_tower_total', 0.0)
                base_total_bias = base_host_bias + base_pump_bias + base_tower_bias

                host_no_hist = self.predict_power_with_status('host_total', host_feat_opt, base_feature_values,
                                                            inlet, ret, historical_residuals=None)
                pump_no_hist = self.predict_power_with_status('cooling_pump_total', pump_feat_opt, base_feature_values,
                                                            inlet, ret, historical_residuals=None)
                tower_no_hist = self.predict_power_with_status('cooling_tower_total', tower_feat_opt,
                                                            base_feature_values, inlet, ret, historical_residuals=None)
                total_no_hist = host_no_hist + pump_no_hist + tower_no_hist

                host_with_hist = optimal_result['host_power']
                pump_with_hist = optimal_result['cooling_pump_power']
                tower_with_hist = optimal_result['cooling_tower_power']
                total_with_hist = host_with_hist + pump_with_hist + tower_with_hist

                logger.info("===== 最优温度组合预测对比 =====")
                logger.info(f"温度: 供水={inlet}℃, 回水={ret}℃")
                logger.info(f"基础预测(无偏差): {base_total_only:.2f} kW")
                logger.info(f"基础预测(加偏差): {base_total_bias:.2f} kW")
                logger.info(f"残差预测(无历史): {total_no_hist:.2f} kW")
                logger.info(f"残差预测(有历史): {total_with_hist:.2f} kW")
                logger.info(f"当前实际总功率: {current_total_power:.2f} kW")
                logger.info("==============================")
            else:
                logger.warning("无法准备最优温度组合特征，跳过对比")

            logger.info(f"所有有效结果总功率范围: min={min(r['total_power'] for r in results):.2f} kW, max={max(r['total_power'] for r in results):.2f} kW")

            return {
                'success': True,
                'optimal_result': optimal_result,
                'all_valid_results': results[:10],
                'all_results': results,
                'constraints': constraints,
                'current_values': {
                    'cooling_inlet_temp': round(current_cooling_inlet_temp, 1),
                    'cooling_return_temp': round(current_cooling_return_temp, 1),
                    'system_heat_dissipation': round(current_system_heat_dissipation, 2),
                    'instant_cooling_capacity': round(current_instant_cooling_capacity, 2),
                    'host_power': round(current_host_power, 2),
                    'cooling_pump_power': round(current_cooling_pump_power, 2),
                    'cooling_tower_power': round(current_cooling_tower_power, 2),
                    'total_power': round(current_total_power, 2),
                    'host_running': host_running,
                    'pump_running': pump_running,
                    'tower_running': tower_running
                },
                'total_candidates': len(temperature_pairs),
                'optimization_config': self.optimization_config
            }
        except Exception as e:
            logger.error(f"寻找最优温度组合失败: {e}")
            import traceback
            traceback.print_exc()
            return None 
    
    def create_current_as_optimal_result(self, base_feature_values: Dict):
        """创建当前值作为优化结果（优化失败时使用）"""
        try:
            current_system_heat_dissipation = base_feature_values.get(settings.system_heat_dissipation, 2000.0)
            current_instant_cooling_capacity = base_feature_values.get(settings.instant_cooling_capacity, 1000.0)
            current_cooling_inlet_temp = base_feature_values.get(settings.total_cooling_inlet_temp, 32.0)
            current_cooling_return_temp = base_feature_values.get(settings.total_cooling_return_temp, 28.0)
            current_host_power = base_feature_values.get(settings.composite_total_host_meter, 300.0)
            current_cooling_pump_power = base_feature_values.get(settings.composite_total_cooling_pump_meter, 100.0)
            current_cooling_tower_power = base_feature_values.get(settings.composite_total_cooling_tower_meter, 60.0)
            host1_status = base_feature_values.get(settings.host_1_running_status, 1.0)
            host2_status = base_feature_values.get(settings.host_2_running_status, 1.0)
            pump_statuses = [
                base_feature_values.get(settings.cooling_pump_1_running_status, 1.0),
                base_feature_values.get(settings.cooling_pump_2_running_status, 1.0),
                base_feature_values.get(settings.cooling_pump_3_running_status, 1.0),
                base_feature_values.get(settings.cooling_pump_4_running_status, 1.0)
            ]
            tower_statuses = [
                base_feature_values.get(settings.cooling_tower_1_running_status, 1.0),
                base_feature_values.get(settings.cooling_tower_2_running_status, 1.0),
                base_feature_values.get(settings.cooling_tower_3_running_status, 1.0),
                base_feature_values.get(settings.cooling_tower_4_running_status, 1.0)
            ]
            host_running = host1_status == 1.0 or host2_status == 1.0
            pump_running = any(p == 1.0 for p in pump_statuses)
            tower_running = any(t == 1.0 for t in tower_statuses)
            current_total_power = self.calculate_total_power(
                current_host_power, current_cooling_tower_power, current_cooling_pump_power
            )

            optimal_result = {
                'cooling_inlet_temp': current_cooling_inlet_temp,
                'cooling_return_temp': current_cooling_return_temp,
                'actual_inlet_temp': round(current_cooling_inlet_temp, 1),
                'actual_return_temp': round(current_cooling_return_temp, 1),
                'delta_temp': round(current_cooling_inlet_temp - current_cooling_return_temp, 1),
                'host_power': round(current_host_power, 2),
                'cooling_pump_power': round(current_cooling_pump_power, 2),
                'cooling_tower_power': round(current_cooling_tower_power, 2),
                'total_power': round(current_total_power, 2),
                'system_heat_dissipation': round(current_system_heat_dissipation, 2),
                'heat_dissipation_percent': 100.0,
                'power_diff': 0.0,
                'power_diff_percent': 0.0,
                'inlet_temp_diff': 0.0,
                'return_temp_diff': 0.0,
                'host_running': host_running,
                'pump_running': pump_running,
                'tower_running': tower_running,
                'is_valid': False
            }

            current_values = {
                'cooling_inlet_temp': round(current_cooling_inlet_temp, 1),
                'cooling_return_temp': round(current_cooling_return_temp, 1),
                'system_heat_dissipation': round(current_system_heat_dissipation, 2),
                'instant_cooling_capacity': round(current_instant_cooling_capacity, 2),
                'host_power': round(current_host_power, 2),
                'cooling_pump_power': round(current_cooling_pump_power, 2),
                'cooling_tower_power': round(current_cooling_tower_power, 2),
                'total_power': round(current_total_power, 2),
                'host_running': host_running,
                'pump_running': pump_running,
                'tower_running': tower_running
            }

            return {
                'optimal_result': optimal_result,
                'all_valid_results': [],
                'constraints': None,
                'current_values': current_values,
                'total_candidates': 0,
                'optimization_config': self.optimization_config
            }
        except Exception as e:
            logger.error(f"创建当前值作为优化结果失败: {e}")
            return None

    def save_optimization_results(self, optimization_result: Dict, data_time, extra_remark: str = ""):
        """保存优化结果到cooling_opt_parameters_total表（已扩展支持标记位和失败原因）"""
        try:
            if optimization_result is None or self.postgres_engine is None:
                logger.error("优化结果为空或PostgreSQL未连接")
                return False

            optimal = optimization_result['optimal_result']
            current = optimization_result['current_values']
            config = optimization_result.get('optimization_config', self.optimization_config)

            # ---------- 新增：提取标记位和失败原因 ----------
            return_applied = optimization_result.get('optimized_return_temp_applied', False)
            diff_applied = optimization_result.get('optimized_temp_diff_applied', False)
            failure_reasons_list = optimization_result.get('failure_reasons', [])
            if failure_reasons_list:
                # 生成带序号的字符串：1. 错误A; 2. 错误B
                numbered_list = [f"{i+1}. {reason}" for i, reason in enumerate(failure_reasons_list)]
                failure_reasons_str = '; '.join(numbered_list)
            else:
                failure_reasons_str = None

            diff_total_power = optimal['total_power'] - current['total_power']
            diff_host_power = optimal['host_power'] - current['host_power']
            diff_cooling_tower_power = optimal['cooling_tower_power'] - current['cooling_tower_power']
            diff_cooling_pump_power = optimal['cooling_pump_power'] - current['cooling_pump_power']
            diff_supply_temp = optimal['actual_inlet_temp'] - current['cooling_inlet_temp']
            diff_return_temp = optimal['actual_return_temp'] - current['cooling_return_temp']
            diff_temp_diff = optimal['delta_temp'] - (current['cooling_inlet_temp'] - current['cooling_return_temp'])

            current_heat_dissipation_pct = 100.0
            diff_heat_dissipation = optimal['heat_dissipation_percent'] - current_heat_dissipation_pct

            percent_total_power = -diff_total_power / current['total_power'] * 100 if current['total_power'] != 0 else 0
            percent_host_power = -diff_host_power / current['host_power'] * 100 if current['host_power'] != 0 else 0
            percent_cooling_tower_power = -diff_cooling_tower_power / current['cooling_tower_power'] * 100 if current['cooling_tower_power'] != 0 else 0
            percent_cooling_pump_power = -diff_cooling_pump_power / current['cooling_pump_power'] * 100 if current['cooling_pump_power'] != 0 else 0

            total_energy_saving = -diff_total_power
            energy_saving_percent = percent_total_power

            current_time = datetime.now()
            data_time_obj = data_time if isinstance(data_time, datetime) else datetime.strptime(data_time, '%Y-%m-%d %H:%M:%S')
            time_diff = current_time - data_time_obj
            time_diff_minutes = time_diff.total_seconds() / 60

            base_remarks = f"数据时间: {data_time}, 设备状态: 主机组({'运行' if current['host_running'] else '停止'}), 冷却泵组({'运行' if current['pump_running'] else '停止'}), 冷却塔组({'运行' if current['tower_running'] else '停止'})"
            if extra_remark:
                base_remarks += f", {extra_remark}"
            if time_diff_minutes > self.data_recency_minutes:
                base_remarks += f", 数据超时(超过{time_diff_minutes:.1f}分钟)"
            if not optimal.get('is_valid', True):
                base_remarks += ", 优化失败(使用当前值)"

            # 插入到 cooling_opt_parameters_total 表（增加三个新字段）
            query = """
            INSERT INTO cooling_opt_parameters_total (
                return_temp_lower_limit, return_temp_upper_limit,
                supply_temp_lower_limit, supply_temp_upper_limit,
                temp_diff_lower_limit, temp_diff_upper_limit,
                heat_dissipation_lower_limit, heat_dissipation_upper_limit,
                current_total_power, current_host_total_power,
                current_cooling_tower_total_power, current_cooling_pump_total_power,
                current_supply_temp, current_return_temp, current_temp_diff, current_heat_dissipation,
                optimized_total_power, optimized_host_total_power,
                optimized_cooling_tower_total_power, optimized_cooling_pump_total_power,
                optimized_supply_temp, optimized_return_temp, optimized_temp_diff, optimized_heat_dissipation,
                diff_total_power, diff_host_total_power,
                diff_cooling_tower_total_power, diff_cooling_pump_total_power,
                diff_supply_temp, diff_return_temp, diff_temp_diff, diff_heat_dissipation,
                percent_total_power, percent_host_total_power,
                percent_cooling_tower_total_power, percent_cooling_pump_total_power,
                total_energy_saving, energy_saving_percent,
                optimized_return_temp_applied, optimized_temp_diff_applied, failure_reasons,
                remarks
            ) VALUES (
                :return_temp_lower_limit, :return_temp_upper_limit,
                :supply_temp_lower_limit, :supply_temp_upper_limit,
                :temp_diff_lower_limit, :temp_diff_upper_limit,
                :heat_dissipation_lower_limit, :heat_dissipation_upper_limit,
                :current_total_power, :current_host_total_power,
                :current_cooling_tower_total_power, :current_cooling_pump_total_power,
                :current_supply_temp, :current_return_temp, :current_temp_diff, :current_heat_dissipation,
                :optimized_total_power, :optimized_host_total_power,
                :optimized_cooling_tower_total_power, :optimized_cooling_pump_total_power,
                :optimized_supply_temp, :optimized_return_temp, :optimized_temp_diff, :optimized_heat_dissipation,
                :diff_total_power, :diff_host_total_power,
                :diff_cooling_tower_total_power, :diff_cooling_pump_total_power,
                :diff_supply_temp, :diff_return_temp, :diff_temp_diff, :diff_heat_dissipation,
                :percent_total_power, :percent_host_total_power,
                :percent_cooling_tower_total_power, :percent_cooling_pump_total_power,
                :total_energy_saving, :energy_saving_percent,
                :optimized_return_temp_applied, :optimized_temp_diff_applied, :failure_reasons,
                :remarks
            )
            """

            params = {
                'return_temp_lower_limit': float(config['return_temp_lower_limit']),
                'return_temp_upper_limit': float(config['return_temp_upper_limit']),
                'supply_temp_lower_limit': float(config['supply_temp_lower_limit']),
                'supply_temp_upper_limit': float(config['supply_temp_upper_limit']),
                'temp_diff_lower_limit': float(config['temp_diff_lower_limit']),
                'temp_diff_upper_limit': float(config['temp_diff_upper_limit']),
                'heat_dissipation_lower_limit': float(config['heat_dissipation_lower_limit'] * 100),
                'heat_dissipation_upper_limit': float(config['heat_dissipation_upper_limit'] * 100),

                'current_total_power': float(current['total_power']),
                'current_host_total_power': float(current['host_power']),
                'current_cooling_tower_total_power': float(current['cooling_tower_power']),
                'current_cooling_pump_total_power': float(current['cooling_pump_power']),
                'current_supply_temp': float(current['cooling_inlet_temp']),
                'current_return_temp': float(current['cooling_return_temp']),
                'current_temp_diff': float(current['cooling_inlet_temp'] - current['cooling_return_temp']),
                'current_heat_dissipation': 100.0,

                'optimized_total_power': float(optimal['total_power']),
                'optimized_host_total_power': float(optimal['host_power']),
                'optimized_cooling_tower_total_power': float(optimal['cooling_tower_power']),
                'optimized_cooling_pump_total_power': float(optimal['cooling_pump_power']),
                'optimized_supply_temp': float(optimal['actual_inlet_temp']),
                'optimized_return_temp': float(optimal['actual_return_temp']),
                'optimized_temp_diff': float(optimal['delta_temp']),
                'optimized_heat_dissipation': float(optimal['heat_dissipation_percent']),

                'diff_total_power': float(diff_total_power),
                'diff_host_total_power': float(diff_host_power),
                'diff_cooling_tower_total_power': float(diff_cooling_tower_power),
                'diff_cooling_pump_total_power': float(diff_cooling_pump_power),
                'diff_supply_temp': float(diff_supply_temp),
                'diff_return_temp': float(diff_return_temp),
                'diff_temp_diff': float(diff_temp_diff),
                'diff_heat_dissipation': float(diff_heat_dissipation),

                'percent_total_power': float(percent_total_power),
                'percent_host_total_power': float(percent_host_power),
                'percent_cooling_tower_total_power': float(percent_cooling_tower_power),
                'percent_cooling_pump_total_power': float(percent_cooling_pump_power),

                'total_energy_saving': float(total_energy_saving),
                'energy_saving_percent': float(energy_saving_percent),

                # 新增参数
                'optimized_return_temp_applied': return_applied,
                'optimized_temp_diff_applied': diff_applied,
                'failure_reasons': failure_reasons_str,
                'remarks': base_remarks
            }

            with self.postgres_engine.connect() as conn:
                conn.execute(text(query), params)
                conn.commit()

            logger.info(f"优化结果已保存到 cooling_opt_parameters_total 表，标记: 回水温度={return_applied}, 温差={diff_applied}")
            if failure_reasons_str:
                logger.info(f"失败原因: {failure_reasons_str}")
            return True
        except Exception as e:
            logger.error(f"保存优化结果失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    def run_optimization_cycle(self):
        """运行一次完整的优化周期（包含前置过滤、稳态检查、R²检查）"""
        logger.info("=" * 80)
        logger.info(f"开始优化周期 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        failure_reasons = []           # 收集所有失败原因
        optimization_result = None
        data_time = None
        feature_values = None
        all_checks_passed = False

        try:
            # 1. 加载优化配置
            if not self.load_optimization_config():
                failure_reasons.append("加载优化配置失败")
                logger.error("加载优化配置失败")
            else:
                logger.info("优化配置加载成功")

            # 2. 数据时效性检查
            data_recency_ok = self.check_all_data_recency()
            if not data_recency_ok:
                failure_reasons.append(f"数据时效性检查失败(超过{self.data_recency_minutes}分钟)")

            # 3. 模型加载检查
            if all(model is None for model in self.models.values()):
                if not self.load_models():
                    failure_reasons.append("模型加载失败")
                else:
                    logger.info("模型加载成功")

            # 4. 获取最新数据
            feature_values, data_time = self.get_latest_data()

            # 检查数据时间是否超时
            current_time = datetime.now()
            data_time_obj = data_time if isinstance(data_time, datetime) else datetime.strptime(data_time, '%Y-%m-%d %H:%M:%S')
            time_diff_minutes = (current_time - data_time_obj).total_seconds() / 60
            if time_diff_minutes > self.data_recency_minutes:
                failure_reasons.append(f"数据时间超时({time_diff_minutes:.1f}分钟)")

            # 检查是否有任何冷却侧设备在运行
            host_running = (feature_values.get(settings.host_1_running_status, 0) == 1.0 or
                            feature_values.get(settings.host_2_running_status, 0) == 1.0)
            pump_running = any(feature_values.get(getattr(settings, f'cooling_pump_{i}_running_status'), 0) == 1.0 for i in range(1,5))
            tower_running = any(feature_values.get(getattr(settings, f'cooling_tower_{i}_running_status'), 0) == 1.0 for i in range(1,5))
            if not (host_running or pump_running or tower_running):
                failure_reasons.append("所有冷却侧设备均未运行")

            # 5. 更新历史残差队列
            def predict_base(model_key, inlet_temp, return_temp):
                feat = self.prepare_features(feature_values.copy(), inlet_temp, return_temp, model_key)
                if feat is None:
                    return None
                fnames = self.model_feature_names[model_key]
                if len(fnames) != feat.shape[1]:
                    dmat = xgb.DMatrix(feat, feature_names=[f'f{i}' for i in range(feat.shape[1])])
                else:
                    dmat = xgb.DMatrix(feat, feature_names=fnames)
                base = self.models[model_key].predict(dmat)[0]
                base += self.avg_bias.get(model_key, 0.0)
                return base

            current_inlet = feature_values.get(settings.total_cooling_inlet_temp, 32.0)
            current_return = feature_values.get(settings.total_cooling_return_temp, 28.0)

            base_host = predict_base('host_total', current_inlet, current_return)
            base_pump = predict_base('cooling_pump_total', current_inlet, current_return)
            base_tower = predict_base('cooling_tower_total', current_inlet, current_return)

            if None not in [base_host, base_pump, base_tower]:
                actual_host = feature_values.get(settings.composite_total_host_meter, 300.0)
                actual_pump = feature_values.get(settings.composite_total_cooling_pump_meter, 100.0)
                actual_tower = feature_values.get(settings.composite_total_cooling_tower_meter, 60.0)

                residual_host = actual_host - base_host
                residual_pump = actual_pump - base_pump
                residual_tower = actual_tower - base_tower

                self.historical_residuals['host_total'].append(residual_host)
                self.historical_residuals['cooling_pump_total'].append(residual_pump)
                self.historical_residuals['cooling_tower_total'].append(residual_tower)

                max_lags = max(
                    self.residual_model_params.get('host_total', {}).get('residual_lags', 0),
                    self.residual_model_params.get('cooling_pump_total', {}).get('residual_lags', 0),
                    self.residual_model_params.get('cooling_tower_total', {}).get('residual_lags', 0)
                )
                for key in self.historical_residuals:
                    if len(self.historical_residuals[key]) > max_lags:
                        self.historical_residuals[key] = self.historical_residuals[key][-max_lags:]

                logger.info(f"更新历史残差: host={residual_host:.2f}, pump={residual_pump:.2f}, tower={residual_tower:.2f}")
            else:
                logger.warning("无法计算基础预测，历史残差未更新")

            # 6. 稳态检查和 R² 检查（仅在前置条件通过时执行，因为这些检查依赖数据质量）
            precheck_passed = (len(failure_reasons) == 0)
            if precheck_passed:
                # 稳态检查
                stable, stable_reasons = self.check_all_running_devices_stable(feature_values)
                if not stable:
                    failure_reasons.extend(stable_reasons)
                    logger.warning("设备功率不稳定，但将继续尝试优化（仅影响标记位）")
                else:
                    logger.info("所有运行设备功率处于稳态")

                # R² 检查
                r2_ok, r2_reasons = self.check_model_r2()
                if not r2_ok:
                    failure_reasons.extend(r2_reasons)
                    logger.warning("模型R²不满足阈值，但将继续尝试优化（仅影响标记位）")

            # 7. 执行优化搜索（无论前置条件是否通过，只要模型已加载就执行）
            # 注意：如果模型未加载，则跳过优化搜索
            if any(model is None for model in self.models.values()):
                logger.warning("模型未加载，无法执行优化搜索")
            else:
                search_result = self.find_optimal_temperature_pair(
                    feature_values,
                    historical_residuals=self.historical_residuals
                )

                if search_result is None:
                    # 异常情况
                    failure_reasons.append("优化搜索异常（未返回有效结果）")
                    logger.warning("优化搜索返回 None")
                elif not search_result.get('success', False):
                    # 详细失败原因解析
                    reason = search_result.get('reason')
                    stats = search_result.get('filter_stats', {})
                    constraints = search_result.get('constraints', {})

                    if reason == 'no_valid_combinations':
                        if stats.get('delta_high', 0) > 0:
                            failure_reasons.append(f"温差高于上限的组合有 {stats['delta_high']} 个（上限={constraints.get('delta_temp_max')}℃），请尝试增大 `temp_diff_upper_limit`")
                        if stats.get('delta_low', 0) > 0:
                            failure_reasons.append(f"温差低于下限的组合有 {stats['delta_low']} 个（下限={constraints.get('delta_temp_min')}℃），请尝试减小 `temp_diff_lower_limit`")
                        if stats.get('inlet_high', 0) > 0:
                            failure_reasons.append(f"供水温度高于上限的组合有 {stats['inlet_high']} 个（上限={constraints.get('inlet_max')}℃），请尝试增大 `supply_temp_upper_limit`")
                        if stats.get('inlet_low', 0) > 0:
                            failure_reasons.append(f"供水温度低于下限的组合有 {stats['inlet_low']} 个（下限={constraints.get('inlet_min')}℃），请尝试减小 `supply_temp_lower_limit`")
                        if stats.get('return_high', 0) > 0:
                            failure_reasons.append(f"回水温度高于上限的组合有 {stats['return_high']} 个（上限={constraints.get('return_max')}℃），请尝试增大 `return_temp_upper_limit`")
                        if stats.get('return_low', 0) > 0:
                            failure_reasons.append(f"回水温度低于下限的组合有 {stats['return_low']} 个（下限={constraints.get('return_min')}℃），请尝试减小 `return_temp_lower_limit`")
                        if stats.get('heat_high', 0) > 0:
                            failure_reasons.append(f"散热量高于上限的组合有 {stats['heat_high']} 个（上限={constraints.get('heat_dissipation_upper_limit')*100:.0f}%），请尝试增大 `heat_dissipation_upper_limit`")
                        if stats.get('heat_low', 0) > 0:
                            failure_reasons.append(f"散热量低于下限的组合有 {stats['heat_low']} 个（下限={constraints.get('heat_dissipation_lower_limit')*100:.0f}%），请尝试减小 `heat_dissipation_lower_limit`")
                        if stats.get('feature_failed', 0) > 0:
                            failure_reasons.append(f"特征准备失败的组合有 {stats['feature_failed']} 个，请检查模型特征映射或数据完整性")
                        if stats.get('other_error', 0) > 0:
                            failure_reasons.append(f"其他预测异常的组合有 {stats['other_error']} 个，请查看详细日志")
                        if not any([stats.get(k,0) for k in ['delta_high','delta_low','inlet_high','inlet_low','return_high','return_low','heat_high','heat_low','feature_failed','other_error']]):
                            failure_reasons.append("未找到任何有效组合，但所有过滤计数均为0，可能存在逻辑错误")
                    elif reason == 'energy_saving_too_low':
                        failure_reasons.append(
                            f"最优组合节能率 {search_result.get('energy_saving_percent', 0):.2f}% 低于阈值 {search_result.get('threshold', 0)}%，"
                            f"请尝试降低 `energy_saving_threshold` 或检查模型预测是否偏大"
                        )
                    elif reason == 'power_not_lower':
                        failure_reasons.append(
                            f"最优组合预测功率 {search_result.get('optimal_power', 0):.2f} kW 不低于当前功率 {search_result.get('current_power', 0):.2f} kW，"
                            f"可能是模型预测偏大或约束条件过严"
                        )
                    else:
                        failure_reasons.append(f"优化搜索失败，未知原因: {reason}")

                    logger.warning("优化搜索无有效结果")
                else:
                    # 成功找到优化结果
                    optimization_result = search_result
                    logger.info("优化搜索完成，找到最优温度组合")

            # 8. 构造最终结果并设置标记位
            if optimization_result is None:
                # 无优化结果，使用当前值
                current_result = self.create_current_as_optimal_result(feature_values)
                if current_result:
                    current_result['failure_reasons'] = failure_reasons
                    current_result['optimized_return_temp_applied'] = False
                    current_result['optimized_temp_diff_applied'] = False
                    self.save_optimization_results(current_result, data_time)
                return True

            # 有优化结果，判断是否所有检查均通过
            all_checks_passed = (len(failure_reasons) == 0)
            optimization_result['failure_reasons'] = failure_reasons
            optimization_result['optimized_return_temp_applied'] = all_checks_passed
            optimization_result['optimized_temp_diff_applied'] = all_checks_passed

            # 保存结果
            self.save_optimization_results(optimization_result, data_time)

            # 日志输出
            if all_checks_passed:
                logger.info("所有检查通过，优化结果可下发")
            else:
                logger.warning(f"存在失败原因，优化结果不可下发: {'; '.join(failure_reasons)}")

            # 9. Redis 缓存（略，同原代码）
            if self.redis_client is not None and 'all_results' in optimization_result:
                try:
                    all_results = optimization_result['all_results']
                    total_count = len(all_results)
                    if total_count == 0:
                        return True

                    best = optimization_result['optimal_result']
                    desc_results = sorted(all_results, key=lambda x: x['total_power'], reverse=True)
                    others = [r for r in desc_results if not (
                            r['total_power'] == best['total_power'] and
                            r['cooling_inlet_temp'] == best['cooling_inlet_temp'] and
                            r['cooling_return_temp'] == best['cooling_return_temp']
                    )]

                    if total_count <= 20:
                        selected_raw = desc_results
                    else:
                        sample_size = min(19, len(others))
                        selected_others = random.sample(others, sample_size) if sample_size > 0 else []
                        selected_raw = selected_others + [best]
                        selected_raw.sort(key=lambda x: x['total_power'], reverse=True)

                    combinations = []
                    for idx, res in enumerate(selected_raw):
                        original_rank = None
                        for i, cand in enumerate(desc_results):
                            if (cand['total_power'] == res['total_power'] and
                                    cand['cooling_inlet_temp'] == res['cooling_inlet_temp'] and
                                    cand['cooling_return_temp'] == res['cooling_return_temp']):
                                original_rank = i + 1
                                break
                        if original_rank is None:
                            original_rank = idx + 1

                        combinations.append({
                            "index": original_rank,
                            "cooling_inlet_temp": res['cooling_inlet_temp'],
                            "cooling_return_temp": res['cooling_return_temp'],
                            "actual_inlet_temp": res['actual_inlet_temp'],
                            "actual_return_temp": res['actual_return_temp'],
                            "delta_temp": res['delta_temp'],
                            "host_power": res['host_power'],
                            "cooling_pump_power": res['cooling_pump_power'],
                            "cooling_tower_power": res['cooling_tower_power'],
                            "total_power": res['total_power'],
                            "system_heat_dissipation": res['system_heat_dissipation'],
                            "heat_dissipation_percent": res['heat_dissipation_percent'],
                            "power_diff": res['power_diff'],
                            "power_diff_percent": res['power_diff_percent']
                        })

                    cache_data = {
                        "timestamp": datetime.now().isoformat(),
                        "combinations": combinations
                    }
                    redis_key = f"{settings.PROGRAM_NAME}:cooling_opt:latest_iteration"
                    self.redis_client.setex(
                        redis_key,
                        300,
                        json.dumps(cache_data, ensure_ascii=False)
                    )
                    logger.info(f"迭代数据已缓存，共 {len(combinations)} 个组合（最后一个为最优）")
                except Exception as e:
                    logger.error(f"缓存迭代数据到 Redis 失败: {e}")
            return True

        except Exception as e:
            logger.error(f"优化周期执行失败: {e}")
            import traceback
            traceback.print_exc()
            try:
                if feature_values is None:
                    feature_values, data_time = self.get_latest_data()
                current_result = self.create_current_as_optimal_result(feature_values)
                if current_result:
                    failure_reasons.append(f"优化过程异常: {str(e)[:50]}")
                    current_result['failure_reasons'] = failure_reasons
                    current_result['optimized_return_temp_applied'] = False
                    current_result['optimized_temp_diff_applied'] = False
                    self.save_optimization_results(current_result, data_time)
            except Exception as save_error:
                logger.error(f"保存异常记录失败: {save_error}")
            return False  
    def start_scheduler(self):
        """启动定时调度器（每5分钟运行一次）"""
        try:
            logger.info("启动冷却水优化调度器（总功率模型版本）...")

            if not self.connect_databases():
                logger.error("数据库连接失败，无法启动调度器")
                return False

            if not self.load_optimization_config():
                logger.error("首次加载优化配置失败")
                return False

            if not self.load_models():
                logger.warning("首次加载模型失败，将继续使用当前值作为优化结果")

            self.scheduler = BlockingScheduler()
            # 使用从数据库读取的优化周期
            cycle_minutes = self.optimization_config.get('optimization_cycle_minutes', 5)
            # 生成 cron 表达式，例如每 5 分钟执行一次：'0,5,10,15,20,25,30,35,40,45,50,55'
            cron_minutes = ','.join([str(i) for i in range(0, 60, cycle_minutes)])
            self.scheduler.add_job(
                self.run_optimization_cycle,
                trigger=CronTrigger(minute=cron_minutes),
                id='cooling_optimization_total',
                name='冷却水系统优化（总功率）',
                replace_existing=True
            )
            # 新增心跳任务（每30秒）
            self.scheduler.add_job(
                self.update_heartbeat,
                trigger='interval',
                seconds=30,
                id='heartbeat_job',
                name='心跳检测更新',
                replace_existing=True
            )

            jobs = self.scheduler.get_jobs()
            for job in jobs:
                logger.info(f"已调度任务: {job.name}")
                next_run = getattr(job, 'next_run_time', None)
                if next_run:
                    logger.info(f"  下次运行时间: {next_run}")
                else:
                    logger.info("  下次运行时间: 尚未计划（调度器启动后计算）")

            cycle_minutes = self.optimization_config.get('optimization_cycle_minutes', 5)
            logger.info(f"调度器已启动，每{cycle_minutes}分钟运行一次优化，心跳每30秒一次")
            logger.info("按 Ctrl+C 停止调度器")

            logger.info("立即执行首次优化...")
            self.run_optimization_cycle()

            self.is_running = True
            logger.info("开始运行调度器...")
            self.scheduler.start()
            return True
        except KeyboardInterrupt:
            logger.info("用户中断调度器")
            self.stop_scheduler()
            return True
        except Exception as e:
            logger.error(f"启动调度器失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def stop_scheduler(self):
        """停止调度器"""
        if self.scheduler:
            try:
                self.scheduler.shutdown()
                self.scheduler = None
                self.is_running = False
                logger.info("调度器已停止")
            except Exception as e:
                logger.error(f"停止调度器失败: {e}")

    def run_once(self):
        """单次运行优化（用于测试）"""
        try:
            logger.info("开始单次优化测试（总功率模型）...")
            if not self.connect_databases():
                logger.error("数据库连接失败")
                return False
            if not self.load_optimization_config():
                logger.error("加载优化配置失败")
                return False
            if not self.load_models():
                logger.warning("加载模型失败，将继续使用当前值作为优化结果")
            success = self.run_optimization_cycle()
            if success:
                logger.info("单次优化测试完成")
            else:
                logger.error("单次优化测试失败")
            return success
        except Exception as e:
            logger.error(f"单次优化测试失败: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """主函数 - 启动总功率模型版本的定时调度器"""
    scheduler = CoolingTempSchedulerTotal()
    scheduler.start_scheduler()


if __name__ == "__main__":
    main()