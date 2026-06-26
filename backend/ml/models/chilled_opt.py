"""
冷冻水温度优化模型 - 总功率模型版本（直接修正模式）
适配新项目 config.py 和 chilled_opt_parameters_total 表结构
backend/ml/models/chilled_opt.py
"""
import pickle
import numpy as np
import os
import sys
from typing import Dict, List, Optional, Any,Tuple
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import xgboost as xgb
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import signal
import redis
import json
import random
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))
from app.config import settings
from ml.utils.heartbeat_utils import update_heartbeat

# 设置日志（修复Windows控制台编码）
class UnicodeSafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            self.stream.write(msg + self.terminator)
            self.flush()
        except UnicodeEncodeError:
            try:
                msg = self.format(record).encode('gbk', errors='replace').decode('gbk')
                self.stream.write(msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)
        except Exception:
            self.handleError(record)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chilled_optimization_total.log', encoding='utf-8'),
        UnicodeSafeStreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)   # <--- 在这里添加



class ChilledTempSchedulerTotal:
    """冷冻水系统优化调度器（总功率模型版本，增强残差修正）"""

    def __init__(self):
        # ========== 数据库配置 ==========
        self.mysql_config = {
            'host': settings.MYSQL_HOST,
            'port': settings.MYSQL_PORT,
            'user': settings.MYSQL_USER,
            'password': settings.MYSQL_PASSWORD,
            'database': settings.MYSQL_DATABASE,
            'charset': settings.MYSQL_CHARSET
        }
        self.postgres_config = {'url': settings.DATABASE_URL}
        # ========== 数据时效性阈值（分钟） ==========
        self.data_recency_minutes = 10
        # ========== 新增：历史残差队列（每个模型独立）==========
        self.historical_residuals = {
            'host_total': [],
            'chilled_pump_total': []
        }
        # 新增：静态偏差（从模型加载）
        self.avg_bias = {
            'host_total': 0.0,
            'chilled_pump_total': 0.0
        }
        self.model_info = {
            'host_total': {},
            'chilled_pump_total': {}
        }
        # ========== 点位ID列表 ==========
        self.point_ids = []
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
            settings.chilled_pump_1_running_status,
            settings.chilled_pump_2_running_status,
            settings.chilled_pump_3_running_status,
            settings.chilled_pump_4_running_status,
        }
        # 总功率
        self.point_ids.append(settings.composite_total_host_meter)
        self.point_ids.append(settings.composite_total_chilled_pump_meter)
        # ===== 补充：冷却塔总功率（冷冻泵模型需要）=====
        self.point_ids.append(settings.composite_total_cooling_tower_meter)
        # ===== 补充：系统散热量（可能用于派生特征）=====
        self.point_ids.append(settings.system_heat_dissipation)

        # 主机状态
        self.point_ids.append(settings.host_1_running_status)
        self.point_ids.append(settings.host_2_running_status)
        # 冷冻泵状态
        self.point_ids.append(settings.chilled_pump_1_running_status)
        self.point_ids.append(settings.chilled_pump_2_running_status)
        self.point_ids.append(settings.chilled_pump_3_running_status)
        self.point_ids.append(settings.chilled_pump_4_running_status)
        # 温度
        self.point_ids.append(settings.total_chilled_inlet_temp)
        self.point_ids.append(settings.total_chilled_return_temp)
        self.point_ids.append(settings.total_cooling_inlet_temp)
        self.point_ids.append(settings.total_cooling_return_temp)
        self.point_ids.append(settings.outdoor_temperature)
        self.point_ids.append(settings.wet_bulb_temperature)
        self.point_ids.append(settings.outdoor_humidity)
        # 冷量等
        self.point_ids.append(settings.instant_cooling_capacity)
        self.point_ids.append(settings.total_1_instantaneous_flow)
        self.point_ids.append(settings.chilled_pump_4_running_status)
        # ===== 补充：冷冻泵频率反馈 =====
        self.point_ids.append(settings.chilled_pump_1_frequency_feedback)
        self.point_ids.append(settings.chilled_pump_2_frequency_feedback)
        self.point_ids.append(settings.chilled_pump_3_frequency_feedback)
        # ===== 补充：冷却泵总功率（用于 total_real_time_power_of_cooling_pump_meter 映射）=====
        self.point_ids.append(settings.composite_total_cooling_pump_meter)
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

        # ========== 模型相关 ==========
        self.model_dir = os.path.join(os.path.dirname(__file__), "saved_models")
        self.models = {
            'host_total': None,
            'chilled_pump_total': None
        }
        self.residual_models = {
            'host_total': None,
            'chilled_pump_total': None
        }
        self.residual_model_params = {}  # 存储每个模型的残差参数
        self.model_feature_names = {
            'host_total': [],
            'chilled_pump_total': []
        }
        self.model_prefixes = {
            'host_total': settings.MODEL_PREFIX_HOST_TOTAL,
            'chilled_pump_total': settings.MODEL_PREFIX_CHILLED_PUMP_TOTAL
        }

        # ========== 默认特征值（使用新点位ID作为键） ==========
        self.default_feature_values = {
            settings.total_chilled_return_temp: 12.0,
            settings.total_chilled_inlet_temp: 7.0,
            settings.total_cooling_inlet_temp: 32.0,
            settings.total_cooling_return_temp: 28.0,
            settings.instant_cooling_capacity: 1000.0,
            settings.host_1_running_status: 1.0,
            settings.host_2_running_status: 1.0,
            settings.chilled_pump_1_running_status: 1.0,
            settings.chilled_pump_2_running_status: 1.0,
            settings.chilled_pump_3_running_status: 1.0,
            settings.chilled_pump_4_running_status: 1.0,
            settings.outdoor_humidity: 60.0,
            settings.outdoor_temperature: 25.0,
            settings.wet_bulb_temperature: 20.0,
            settings.total_1_instantaneous_flow: 100.0,
            settings.composite_total_host_meter: 300.0,
            settings.composite_total_chilled_pump_meter: 60.0,
            # ===== 补充默认值 =====
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
            settings.chilled_pump_1_frequency_feedback: 0.0,
            settings.chilled_pump_2_frequency_feedback: 0.0,
            settings.chilled_pump_3_frequency_feedback: 0.0,
            # ===== 补充冷却泵总功率默认值 =====
            settings.composite_total_cooling_pump_meter: 100.0,
        }

        self.STEP_SIZE = 0.1
        self.scheduler = None
        self.is_running = False
        self.mysql_engine = None
        self.postgres_engine = None
        self.optimization_config = None

        # Redis
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
            logger.warning(f"Redis 连接失败: {e}")

        signal.signal(signal.SIGINT, self.signal_handler)

    def update_heartbeat(self):
        """更新冷冻水优化表的心跳"""
        update_heartbeat(self.postgres_engine, 'chilled_opt_parameters_total', logger)
    def signal_handler(self, signum, frame):
        logger.info("接收到Ctrl+C信号，正在停止调度器...")
        self.stop_scheduler()
        sys.exit(0)

    def connect_databases(self):
        try:
            encoded_password = quote_plus(self.mysql_config['password'])
            mysql_url = (f"mysql+pymysql://{self.mysql_config['user']}:{encoded_password}"
                         f"@{self.mysql_config['host']}:{self.mysql_config['port']}/{self.mysql_config['database']}"
                         f"?charset={self.mysql_config['charset']}")
            self.mysql_engine = create_engine(mysql_url, pool_recycle=300, pool_pre_ping=True)
            with self.mysql_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("MySQL 连接成功")

            self.postgres_engine = create_engine(self.postgres_config['url'], pool_recycle=300, pool_pre_ping=True)
            with self.postgres_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("PostgreSQL 连接成功")
            return True
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return False

    def load_optimization_config(self):
        try:
            if not self.postgres_engine:
                return False
            query = """
            SELECT return_temp_lower_limit, return_temp_upper_limit,
                   supply_temp_lower_limit, supply_temp_upper_limit,
                   temp_diff_lower_limit, temp_diff_upper_limit,
                   optimization_cycle_minutes, r2_threshold, energy_saving_threshold
            FROM chilled_opt_config WHERE id = 1
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
                    'optimization_cycle_minutes': int(result[6]) if result[6] is not None else 5,
                    'r2_threshold': float(result[7]) if result[7] is not None else 0.6,
                    'energy_saving_threshold': float(result[8]) if result[8] is not None else 0.5
                }
                logger.info(f"成功加载冷冻优化配置，优化周期: {self.optimization_config['optimization_cycle_minutes']}分钟, R²阈值: {self.optimization_config['r2_threshold']}")
                return True
            else:
                logger.error("未找到 id=1 的冷冻优化配置")
                return False
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return False

    def load_models(self):
        """加载模型，并读取 avg_bias 和残差参数，打印特征名称列表"""
        try:
            if not os.path.exists(self.model_dir):
                logger.error(f"模型目录不存在: {self.model_dir}")
                return False
            for key, prefix in self.model_prefixes.items():
                model_file = None
                for f in os.listdir(self.model_dir):
                    if f.startswith(prefix):
                        model_file = os.path.join(self.model_dir, f)
                        break
                if not model_file:
                    logger.error(f"未找到模型文件: {prefix}")
                    return False
                with open(model_file, 'rb') as f:
                    data = pickle.load(f)
                self.models[key] = data['model']
                self.residual_models[key] = data.get('residual_model')
                self.model_feature_names[key] = data.get('feature_names', [])
                self.residual_model_params[key] = {
                    'residual_lags': data.get('residual_lags', 0),
                    'use_standardize': data.get('use_standardize', False),
                    'residual_mean': data.get('residual_mean', 0.0),
                    'residual_std': data.get('residual_std', 1.0)
                }
                # 新增：加载 avg_bias
                self.avg_bias[key] = data.get('avg_bias', 0.0)
                has_residual = self.residual_models[key] is not None
                logger.info(f"{key} 模型加载成功，特征数: {len(self.model_feature_names[key])}, 含残差模型: {has_residual}")
                logger.info(f"{key} 残差滞后步数: {self.residual_model_params[key]['residual_lags']}")
                # 新增：打印特征名称列表，便于调试
                logger.info(f"{key} 特征名称列表: {self.model_feature_names[key]}")
            return True
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False

    def check_data_recency(self, point_id):
        try:
            if not self.mysql_engine:
                return False
            with self.mysql_engine.connect() as conn:
                exists = conn.execute(text(f"SHOW TABLES LIKE '{point_id}'")).fetchone()
                if not exists:
                    return False
                result = conn.execute(text(f"SELECT MAX(UpdateDateTime) FROM `{point_id}`")).fetchone()
                if result and result[0]:
                    diff = (datetime.now() - result[0]).total_seconds() / 60
                    return diff <= self.data_recency_minutes
            return False
        except Exception as e:
            logger.error(f"时效性检查失败 {point_id}: {e}")
            return False

    def check_all_data_recency(self):
        key_points = [
            settings.total_chilled_inlet_temp,
            settings.total_chilled_return_temp,
            settings.composite_total_host_meter,
            settings.composite_total_chilled_pump_meter
        ]
        all_ok = all(self.check_data_recency(p) for p in key_points)
        if all_ok:
            logger.info(f"所有关键点位数据均在{self.data_recency_minutes}分钟内")
        else:
            logger.warning("部分关键点位数据超时")
        return all_ok

    def get_recent_power_series(self, point_id: str, window_minutes: int = 5) -> List[float]:
        """从MySQL获取最近N分钟内的功率时间序列"""
        try:
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
        if len(powers) < 3:
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
        """
        检查所有运行中的主机、冷冻泵的功率是否稳定（使用单个设备功率表）
        返回 (全部稳定标志, 失败原因列表)
        """
        failure_reasons = []
        all_stable = True

        # ---------- 主机：分别检查 1# 和 2# ----------
        host1_running = feature_values.get(settings.host_1_running_status, 0) == 1.0
        host2_running = feature_values.get(settings.host_2_running_status, 0) == 1.0

        if host1_running:
            stable, reason = self.is_power_stable(
                settings.real_time_power_of_host_meter_1,   # 1#主机功率表
                window_minutes=5,
                std_threshold=30.0      # 主机功率波动阈值（kW）
            )
            if not stable:
                all_stable = False
                failure_reasons.append(f"1#主机: {reason}")
        if host2_running:
            stable, reason = self.is_power_stable(
                settings.real_time_power_of_host_meter_2,   # 2#主机功率表
                window_minutes=5,
                std_threshold=30.0
            )
            if not stable:
                all_stable = False
                failure_reasons.append(f"2#主机: {reason}")

        if not (host1_running or host2_running):
            logger.info("所有主机均未运行，跳过主机稳态检查")

        # ---------- 冷冻泵：分别检查 1#、2#、3#、4# ----------
        pump_statuses = [
            (settings.chilled_pump_1_running_status, settings.chilled_pump_1_power_meter_real_time_power, "1#冷冻泵"),
            (settings.chilled_pump_2_running_status, settings.chilled_pump_2_power_meter_real_time_power, "2#冷冻泵"),
            (settings.chilled_pump_3_running_status, settings.chilled_pump_3_power_meter_real_time_power, "3#冷冻泵"),
            (settings.chilled_pump_4_running_status, settings.chilled_pump_4_power_meter_real_time_power, "4#冷冻泵")
        ]

        for status_point, power_point, pump_name in pump_statuses:
            running = feature_values.get(status_point, 0) == 1.0
            if running:
                stable, reason = self.is_power_stable(
                    power_point,
                    window_minutes=5,
                    std_threshold=3.0      # 冷冻泵功率波动阈值（kW）
                )
                if not stable:
                    all_stable = False
                    failure_reasons.append(f"{pump_name}: {reason}")

        if not any(feature_values.get(p[0], 0) == 1.0 for p in pump_statuses):
            logger.info("所有冷冻泵均未运行，跳过冷冻泵稳态检查")

        return all_stable, failure_reasons

    def check_model_r2(self) -> Tuple[bool, List[str]]:
        """检查主机和冷冻泵总模型的R²是否均大于等于阈值（从 model_evaluations 表获取）"""
        if self.optimization_config is None:
            return False, ["优化配置未加载"]
        threshold = self.optimization_config['r2_threshold']
        failure_reasons = []
        all_pass = True

        # 模型关键字到设备ID的映射（与 model_evaluations 表中的 model_id 对应）
        # 假设：1-主机总功率，4-冷冻泵总功率（请根据实际数据库中的定义调整）
        model_device_id_map = {
            'host_total': 1,
            'chilled_pump_total': 4
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
    
    def get_latest_data(self):
        try:
            if not self.mysql_engine:
                return self.default_feature_values.copy(), datetime.now()
            values = {}
            data_time = None
            for pid in self.point_ids:
                try:
                    with self.mysql_engine.connect() as conn:
                        exists = conn.execute(text(f"SHOW TABLES LIKE '{pid}'")).fetchone()
                        if not exists:
                            logger.warning(f"表 {pid} 不存在，使用默认值")
                            values[pid] = self.default_feature_values.get(pid, 0.0)
                            continue
                        row = conn.execute(text(
                            f"SELECT PointValue, UpdateDateTime FROM `{pid}` ORDER BY UpdateDateTime DESC LIMIT 1")).fetchone()
                        if row and row[0] is not None:
                            raw_value = row[0]
                            # 判断是否为状态点
                            if pid in self.status_point_ids:
                                # 尝试多种解析方式
                                parsed_value = None
                                if isinstance(raw_value, (int, float)):
                                    if raw_value in (0, 1):
                                        parsed_value = float(raw_value)
                                    else:
                                        logger.warning(f"状态点 {pid} 读到数值 {raw_value}，视为运行（非0）")
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
                                            logger.warning(f"无法解析状态点 {pid} 的值 '{raw_value}'，使用默认值 0")
                                            parsed_value = 0.0
                                values[pid] = parsed_value
                                logger.info(f"状态点 {pid} 原始值: {raw_value}, 解析后: {parsed_value}")
                            else:
                                values[pid] = float(raw_value)
                            if data_time is None:
                                data_time = row[1]
                        else:
                            logger.warning(f"表 {pid} 无数据，使用默认值")
                            values[pid] = self.default_feature_values.get(pid, 0.0)
                except Exception as e:
                    logger.error(f"获取点位 {pid} 数据时发生异常: {e}，使用默认值")
                    values[pid] = self.default_feature_values.get(pid, 0.0)

            for k, v in self.default_feature_values.items():
                if k not in values:
                    values[k] = v
            if data_time is None:
                data_time = datetime.now()

            logger.info(f"获取到 {len(values)} 个点位数据，时间戳: {data_time}")
            # 详细状态打印
            host1_status = values.get(settings.host_1_running_status, 0)
            host2_status = values.get(settings.host_2_running_status, 0)
            host_running = host1_status == 1.0 or host2_status == 1.0
            logger.info(f"主机运行状态: {'运行' if host_running else '停止'} (1#:{host1_status}, 2#:{host2_status})")
            pump_statuses = [
                values.get(settings.chilled_pump_1_running_status, 0),
                values.get(settings.chilled_pump_2_running_status, 0),
                values.get(settings.chilled_pump_3_running_status, 0),
                values.get(settings.chilled_pump_4_running_status, 0)
            ]
            pump_running = any(s == 1.0 for s in pump_statuses)
            logger.info(
                f"冷冻泵运行状态: {'运行' if pump_running else '停止'} (1#:{pump_statuses[0]}, 2#:{pump_statuses[1]}, 3#:{pump_statuses[2]}, 4#:{pump_statuses[3]})")
            return values, data_time
        except Exception as e:
            logger.error(f"获取数据失败: {e}")
            return self.default_feature_values.copy(), datetime.now()

    def prepare_features(self, feature_values, inlet_temp, return_temp, model_key):
        """准备特征数据，处理特征名到点位ID的映射"""
        try:
            # 更新特征字典中的冷冻水温度（使用点位ID作为键）
            feature_values[settings.total_chilled_inlet_temp] = inlet_temp
            feature_values[settings.total_chilled_return_temp] = return_temp

            fnames = self.model_feature_names[model_key]
            if not fnames:
                logger.warning(f"{model_key} 特征列表为空")
                return None

            feats = []
            for fn in fnames:
                # 1. 直接作为点位ID尝试
                if fn in feature_values:
                    feats.append(feature_values[fn])
                    logger.debug(f"特征 {fn} 直接匹配点位ID，值={feature_values[fn]}")
                    continue

                # 2. 尝试将 fn 解释为 settings 中的属性名，获取对应的点位ID
                point_id = None
                try:
                    point_id = getattr(settings, fn, None)
                    if point_id is not None and isinstance(point_id, str) and point_id in feature_values:
                        feats.append(feature_values[point_id])
                        logger.debug(f"特征 {fn} 通过属性映射到点位 {point_id}，值={feature_values[point_id]}")
                        continue
                except Exception:
                    pass

                # 3. 处理派生特征：运行状态
                if fn == 'host_running_status':
                    s1 = feature_values.get(settings.host_1_running_status, 0)
                    s2 = feature_values.get(settings.host_2_running_status, 0)
                    feats.append(1.0 if s1 == 1.0 or s2 == 1.0 else 0.0)
                    continue
                elif fn == 'chilled_pump_running_status':
                    pumps = [
                        feature_values.get(settings.chilled_pump_1_running_status, 0),
                        feature_values.get(settings.chilled_pump_2_running_status, 0),
                        feature_values.get(settings.chilled_pump_3_running_status, 0),
                        feature_values.get(settings.chilled_pump_4_running_status, 0)
                    ]
                    feats.append(1.0 if any(p == 1.0 for p in pumps) else 0.0)
                    continue
                # 特殊处理：总功率相关的特征名可能直接是属性名
                elif fn == 'total_real_time_power_of_host_meter':
                    # 映射到主机总功率
                    point = settings.composite_total_host_meter
                    feats.append(feature_values.get(point, 300.0))
                    continue
                elif fn == 'total_real_time_power_of_cooling_tower_meter':
                    point = settings.composite_total_cooling_tower_meter
                    feats.append(feature_values.get(point, 60.0))
                    continue
                # ===== 新增：冷却泵总功率映射 =====
                elif fn == 'total_real_time_power_of_cooling_pump_meter':
                    point = settings.composite_total_cooling_pump_meter
                    feats.append(feature_values.get(point, 100.0))
                    continue
                # 4. 未知特征，使用默认值（按类型推断）
                default_val = 0.0
                if 'temp' in fn.lower():
                    default_val = 25.0
                elif 'pressure' in fn.lower():
                    default_val = 1.0
                elif 'power' in fn.lower():
                    default_val = 100.0
                elif 'cop' in fn.lower():
                    default_val = 5.0
                elif 'capacity' in fn.lower():
                    default_val = 1000.0
                elif 'flow' in fn.lower():
                    default_val = 100.0
                elif 'humidity' in fn.lower():
                    default_val = 60.0
                feats.append(default_val)
                logger.debug(f"特征 {fn} 未找到映射，使用默认值 {default_val}")

            return np.array(feats).reshape(1, -1)
        except Exception as e:
            logger.error(f"准备特征失败 {model_key}: {e}")
            return None

    def predict_power_with_status(self, model_key: str, features_array: np.ndarray, feature_values: Dict,
                                   inlet_temp: float, return_temp: float,
                                   historical_residuals: Optional[List[float]] = None) -> float:
        """预测总功率，考虑设备状态，并使用历史残差进行滞后特征构造"""
        try:
            POWER_THRESHOLD = 10.0  # 功率阈值

            # 确定该模型对应的设备组是否有设备运行，并获取当前功率
            if model_key == 'host_total':
                s1 = feature_values.get(settings.host_1_running_status, 1.0)
                s2 = feature_values.get(settings.host_2_running_status, 1.0)
                device_group_running = (s1 == 1.0 or s2 == 1.0)
                current_power = feature_values.get(settings.composite_total_host_meter, 300.0)
            else:  # chilled_pump_total
                pumps = [
                    feature_values.get(settings.chilled_pump_1_running_status, 1.0),
                    feature_values.get(settings.chilled_pump_2_running_status, 1.0),
                    feature_values.get(settings.chilled_pump_3_running_status, 1.0),
                    feature_values.get(settings.chilled_pump_4_running_status, 1.0)
                ]
                device_group_running = any(p == 1.0 for p in pumps)
                current_power = feature_values.get(settings.composite_total_chilled_pump_meter, 60.0)

            # 容错：状态全停但功率 > 阈值，视为状态错误继续预测
            if not device_group_running:
                if current_power > POWER_THRESHOLD:
                    logger.debug(f"{model_key} 状态全停但功率 {current_power:.2f} > {POWER_THRESHOLD}kW，视为状态错误，继续预测")
                else:
                    return 0.0

            if self.models[model_key] is None:
                logger.warning(f"{model_key}模型未加载，使用默认总功率")
                return current_power

            # 基础预测
            fnames = self.model_feature_names[model_key]
            if len(fnames) != features_array.shape[1]:
                dmat = xgb.DMatrix(features_array, feature_names=[f'f{i}' for i in range(features_array.shape[1])])
            else:
                dmat = xgb.DMatrix(features_array, feature_names=fnames)
            base_pred = self.models[model_key].predict(dmat)[0]
            # 静态偏差修正
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
                    if historical_residuals is None:
                        lag_features = np.zeros((features_array.shape[0], residual_lags))
                        logger.debug(f"{model_key} 无历史残差，使用0填充滞后特征")
                    else:
                        if len(historical_residuals) < residual_lags:
                            pad = [0.0] * (residual_lags - len(historical_residuals))
                            full_residuals = pad + historical_residuals
                        else:
                            full_residuals = historical_residuals[-residual_lags:]
                        lag_features = np.tile(full_residuals, (features_array.shape[0], 1))
                        logger.debug(f"{model_key} 使用历史残差 {full_residuals} 构造滞后特征")
                    X_res = np.hstack([features_array, lag_features])
                else:
                    X_res = features_array

                try:
                    residual_pred_scaled = residual_model.predict(X_res)
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

            return float(final_pred)
        except Exception as e:
            logger.error(f"预测失败 {model_key}: {e}")
            return 0.0

    def calculate_total_power(self, host_power, pump_power):
        return host_power + pump_power

    def generate_temperature_pairs(self, constraints):
        inlet_min, inlet_max = constraints['supply_temp_lower_limit'], constraints['supply_temp_upper_limit']
        return_min, return_max = constraints['return_temp_lower_limit'], constraints['return_temp_upper_limit']
        delta_min, delta_max = constraints['temp_diff_lower_limit'], constraints['temp_diff_upper_limit']

        inlets = np.arange(inlet_min, inlet_max + self.STEP_SIZE, self.STEP_SIZE).round(1).tolist()
        returns = np.arange(return_min, return_max + self.STEP_SIZE, self.STEP_SIZE).round(1).tolist()
        pairs = []
        for i in inlets:
            for r in returns:
                if r > i and delta_min <= (r - i) <= delta_max:
                    pairs.append((i, r))
        logger.info(f"生成 {len(pairs)} 个温度组合")
        return pairs

    def find_optimal_pair(self, base_values: Dict, historical_residuals: Optional[Dict] = None):
        """寻找最优温度组合，返回详细统计信息（与冷却侧一致）"""
        constraints = self.optimization_config
        if not constraints:
            logger.error("优化配置未加载")
            return None

        current_inlet = base_values.get(settings.total_chilled_inlet_temp, 7.0)
        current_return = base_values.get(settings.total_chilled_return_temp, 12.0)
        current_host = base_values.get(settings.composite_total_host_meter, 300.0)
        current_pump = base_values.get(settings.composite_total_chilled_pump_meter, 60.0)
        current_total = current_host + current_pump

        host1 = base_values.get(settings.host_1_running_status, 1.0)
        host2 = base_values.get(settings.host_2_running_status, 1.0)
        host_run = (host1 == 1.0 or host2 == 1.0)
        pumps = [
            base_values.get(settings.chilled_pump_1_running_status, 1.0),
            base_values.get(settings.chilled_pump_2_running_status, 1.0),
            base_values.get(settings.chilled_pump_3_running_status, 1.0),
            base_values.get(settings.chilled_pump_4_running_status, 1.0)
        ]
        pump_run = any(p == 1.0 for p in pumps)

        logger.info("=" * 60)
        logger.info(f"当前供水温度: {current_inlet}℃, 回水温度: {current_return}℃")
        logger.info(f"主机总功率: {current_host:.2f} kW ({'运行' if host_run else '停止'})")
        logger.info(f"冷冻泵总功率: {current_pump:.2f} kW ({'运行' if pump_run else '停止'})")
        logger.info(f"当前总功率: {current_total:.2f} kW")
        logger.info(f"供水温度范围: {constraints['supply_temp_lower_limit']}℃ ~ {constraints['supply_temp_upper_limit']}℃")
        logger.info(f"回水温度范围: {constraints['return_temp_lower_limit']}℃ ~ {constraints['return_temp_upper_limit']}℃")
        logger.info(f"温差范围: {constraints['temp_diff_lower_limit']}℃ ~ {constraints['temp_diff_upper_limit']}℃")
        logger.info("=" * 60)

        pairs = self.generate_temperature_pairs(constraints)
        if not pairs:
            logger.warning("未生成任何温度组合")
            return None

        results = []
        # 细化计数器
        filtered_by_delta_low = 0   # 温差低于下限
        filtered_by_delta_high = 0  # 温差高于上限
        filtered_by_inlet_low = 0   # 供水温度低于下限
        filtered_by_inlet_high = 0  # 供水温度高于上限
        filtered_by_return_low = 0  # 回水温度低于下限
        filtered_by_return_high = 0 # 回水温度高于上限
        feature_failed = 0
        other_error = 0

        pairs_list = list(pairs)
        for idx, (inlet, ret) in enumerate(pairs_list):
            delta_temp = ret - inlet  # 回水 - 供水 = 温差
            log_filter = idx < 10

            # 温差过滤（区分高低）
            if delta_temp < constraints['temp_diff_lower_limit']:
                filtered_by_delta_low += 1
                if log_filter:
                    logger.debug(f"组合{idx}: 温差{delta_temp:.1f}℃ 低于下限 {constraints['temp_diff_lower_limit']}℃")
                continue
            if delta_temp > constraints['temp_diff_upper_limit']:
                filtered_by_delta_high += 1
                if log_filter:
                    logger.debug(f"组合{idx}: 温差{delta_temp:.1f}℃ 高于上限 {constraints['temp_diff_upper_limit']}℃")
                continue

            # 供水温度过滤（区分高低）
            if inlet < constraints['supply_temp_lower_limit']:
                filtered_by_inlet_low += 1
                if log_filter:
                    logger.debug(f"组合{idx}: 供水温度{inlet}℃ 低于下限 {constraints['supply_temp_lower_limit']}℃")
                continue
            if inlet > constraints['supply_temp_upper_limit']:
                filtered_by_inlet_high += 1
                if log_filter:
                    logger.debug(f"组合{idx}: 供水温度{inlet}℃ 高于上限 {constraints['supply_temp_upper_limit']}℃")
                continue

            # 回水温度过滤（区分高低）
            if ret < constraints['return_temp_lower_limit']:
                filtered_by_return_low += 1
                if log_filter:
                    logger.debug(f"组合{idx}: 回水温度{ret}℃ 低于下限 {constraints['return_temp_lower_limit']}℃")
                continue
            if ret > constraints['return_temp_upper_limit']:
                filtered_by_return_high += 1
                if log_filter:
                    logger.debug(f"组合{idx}: 回水温度{ret}℃ 高于上限 {constraints['return_temp_upper_limit']}℃")
                continue

            try:
                host_feat = self.prepare_features(base_values.copy(), inlet, ret, 'host_total')
                pump_feat = self.prepare_features(base_values.copy(), inlet, ret, 'chilled_pump_total')
                if host_feat is None or pump_feat is None:
                    feature_failed += 1
                    if log_filter:
                        logger.debug(f"组合{idx}: 特征准备失败 (host_feat={host_feat is not None}, pump_feat={pump_feat is not None})")
                    continue

                host_power = self.predict_power_with_status(
                    'host_total', host_feat, base_values, inlet, ret,
                    historical_residuals=historical_residuals.get('host_total') if historical_residuals else None
                )
                pump_power = self.predict_power_with_status(
                    'chilled_pump_total', pump_feat, base_values, inlet, ret,
                    historical_residuals=historical_residuals.get('chilled_pump_total') if historical_residuals else None
                )
                total = host_power + pump_power
                power_diff = total - current_total
                results.append({
                    'inlet': inlet,
                    'return': ret,
                    'host_power': round(host_power, 2),
                    'pump_power': round(pump_power, 2),
                    'total_power': round(total, 2),
                    'power_diff': round(power_diff, 2),
                    'power_diff_percent': round(power_diff / current_total * 100, 2) if current_total else 0,
                    'host_run': host_run,
                    'pump_run': pump_run
                })
            except Exception as e:
                other_error += 1
                if idx < 10:
                    logger.debug(f"组合{idx}: 预测过程异常 - {e}")
                continue

        # 统计信息
        filter_stats = {
            'total_pairs': len(pairs_list),
            'delta_low': filtered_by_delta_low,
            'delta_high': filtered_by_delta_high,
            'inlet_low': filtered_by_inlet_low,
            'inlet_high': filtered_by_inlet_high,
            'return_low': filtered_by_return_low,
            'return_high': filtered_by_return_high,
            'feature_failed': feature_failed,
            'other_error': other_error
        }
        logger.info(
            f"过滤统计: 温差低于下限={filtered_by_delta_low}, 温差高于上限={filtered_by_delta_high}, "
            f"供水低于下限={filtered_by_inlet_low}, 供水高于上限={filtered_by_inlet_high}, "
            f"回水低于下限={filtered_by_return_low}, 回水高于上限={filtered_by_return_high}, "
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
        best = results[0]
        logger.info(f"最优总功率: {best['total_power']:.2f} kW (供水{best['inlet']}℃, 回水{best['return']}℃)")

        # 节能率阈值检查
        energy_saving_threshold = self.optimization_config.get('energy_saving_threshold', 0.0)
        optimal_total_power = best['total_power']
        energy_saving_percent = (current_total - optimal_total_power) / current_total * 100.0
        logger.info(f"节能率: {energy_saving_percent:.2f}% (阈值: {energy_saving_threshold}%)")

        if energy_saving_percent < energy_saving_threshold:
            logger.info(f"最优组合节能率 {energy_saving_percent:.2f}% 低于阈值 {energy_saving_threshold}%，无有效优化")
            return {
                'success': False,
                'reason': 'energy_saving_too_low',
                'energy_saving_percent': energy_saving_percent,
                'threshold': energy_saving_threshold,
                'optimal_power': optimal_total_power,
                'current_power': current_total,
                'filter_stats': filter_stats,
                'constraints': constraints
            }

        if best['total_power'] >= current_total:
            logger.info(f"最优组合预测功率 {best['total_power']:.2f} kW 不低于当前 {current_total:.2f} kW，无有效优化")
            return {
                'success': False,
                'reason': 'power_not_lower',
                'optimal_power': best['total_power'],
                'current_power': current_total,
                'filter_stats': filter_stats,
                'constraints': constraints
            }

        # 预测对比（可选）
        inlet = best['inlet']
        ret = best['return']
        host_feat_opt = self.prepare_features(base_values.copy(), inlet, ret, 'host_total')
        pump_feat_opt = self.prepare_features(base_values.copy(), inlet, ret, 'chilled_pump_total')
        if host_feat_opt is not None and pump_feat_opt is not None:
            def base_only(model_key, feat):
                fnames = self.model_feature_names[model_key]
                if len(fnames) != feat.shape[1]:
                    dmat = xgb.DMatrix(feat, feature_names=[f'f{i}' for i in range(feat.shape[1])])
                else:
                    dmat = xgb.DMatrix(feat, feature_names=fnames)
                return self.models[model_key].predict(dmat)[0]

            base_host_only = base_only('host_total', host_feat_opt)
            base_pump_only = base_only('chilled_pump_total', pump_feat_opt)
            base_total_only = base_host_only + base_pump_only

            base_host_bias = base_host_only + self.avg_bias.get('host_total', 0.0)
            base_pump_bias = base_pump_only + self.avg_bias.get('chilled_pump_total', 0.0)
            base_total_bias = base_host_bias + base_pump_bias

            host_no_hist = self.predict_power_with_status('host_total', host_feat_opt, base_values, inlet, ret, historical_residuals=None)
            pump_no_hist = self.predict_power_with_status('chilled_pump_total', pump_feat_opt, base_values, inlet, ret, historical_residuals=None)
            total_no_hist = host_no_hist + pump_no_hist

            host_with_hist = best['host_power']
            pump_with_hist = best['pump_power']
            total_with_hist = best['total_power']

            logger.info("===== 最优温度组合预测对比 =====")
            logger.info(f"温度: 供水={inlet}℃, 回水={ret}℃")
            logger.info(f"基础预测(无偏差): {base_total_only:.2f} kW")
            logger.info(f"基础预测(加偏差): {base_total_bias:.2f} kW")
            logger.info(f"残差预测(无历史): {total_no_hist:.2f} kW")
            logger.info(f"残差预测(有历史): {total_with_hist:.2f} kW")
            logger.info(f"当前实际总功率: {current_total:.2f} kW")
            logger.info("==============================")
        else:
            logger.warning("无法准备最优温度组合特征，跳过对比")

        logger.info(f"所有有效结果总功率范围: min={min(r['total_power'] for r in results):.2f} kW, max={max(r['total_power'] for r in results):.2f} kW")

        return {
            'success': True,
            'optimal': best,
            'all_results': results,
            'constraints': constraints,
            'current': {
                'inlet': round(current_inlet, 1),
                'return': round(current_return, 1),
                'host_power': round(current_host, 2),
                'pump_power': round(current_pump, 2),
                'total_power': round(current_total, 2),
                'host_run': host_run,
                'pump_run': pump_run
            }
        }
    def save_results(self, opt_result, data_time, remark=""):
        try:
            if not self.postgres_engine:
                return False
            opt = opt_result['optimal']
            cur = opt_result['current']
            cfg = opt_result.get('constraints', self.optimization_config or {})

            # ---------- 提取标记位和失败原因 ----------
            supply_applied = opt_result.get('optimized_supply_temp_applied', False)
            diff_applied = opt_result.get('optimized_temp_diff_applied', False)
            failure_reasons_list = opt_result.get('failure_reasons', [])
            if failure_reasons_list:
                numbered_list = [f"{i+1}. {reason}" for i, reason in enumerate(failure_reasons_list)]
                failure_reasons_str = '; '.join(numbered_list)
            else:
                failure_reasons_str = None

            diff_total = opt['total_power'] - cur['total_power']
            diff_host = opt['host_power'] - cur['host_power']
            diff_pump = opt['pump_power'] - cur['pump_power']
            diff_supply = opt['inlet'] - cur['inlet']
            diff_return = opt['return'] - cur['return']
            diff_delta = (opt['return'] - opt['inlet']) - (cur['return'] - cur['inlet'])

            percent_total = -diff_total / cur['total_power'] * 100 if cur['total_power'] else 0
            percent_host = -diff_host / cur['host_power'] * 100 if cur['host_power'] else 0
            percent_pump = -diff_pump / cur['pump_power'] * 100 if cur['pump_power'] else 0

            # 处理 data_time
            if isinstance(data_time, datetime):
                data_time_obj = data_time
                data_time_str = data_time.strftime('%Y-%m-%d %H:%M:%S')
            else:
                try:
                    data_time_obj = datetime.strptime(str(data_time), '%Y-%m-%d %H:%M:%S')
                    data_time_str = str(data_time)
                except:
                    data_time_obj = datetime.now()
                    data_time_str = data_time_obj.strftime('%Y-%m-%d %H:%M:%S')
            time_diff = (datetime.now() - data_time_obj).total_seconds() / 60

            remarks_lines = []
            remarks_lines.append(f"数据时间: {data_time_str}")
            remarks_lines.append("设备状态:")
            remarks_lines.append(f"主机组 {'运行' if cur.get('host_run', False) else '停止'}")
            remarks_lines.append(f"冷冻泵组 {'运行' if cur.get('pump_run', False) else '停止'}")

            if remark:
                remarks_lines.append(remark)

            if time_diff > self.data_recency_minutes:
                remarks_lines.append(f"数据超时 {time_diff:.1f}分钟")

            if not opt_result.get('is_valid', True):
                remarks_lines.append("优化失败(使用当前值)")

            base_rem = ", ".join(remarks_lines)

            # 插入SQL（增加三个新字段）
            query = """
            INSERT INTO chilled_opt_parameters_total (
                return_temp_lower_limit, return_temp_upper_limit,
                supply_temp_lower_limit, supply_temp_upper_limit,
                temp_diff_lower_limit, temp_diff_upper_limit,
                current_total_power, current_host_total_power, current_chilled_pump_total_power,
                current_supply_temp, current_return_temp, current_temp_diff,
                optimized_total_power, optimized_host_total_power, optimized_chilled_pump_total_power,
                optimized_supply_temp, optimized_return_temp, optimized_temp_diff,
                diff_total_power, diff_host_total_power, diff_chilled_pump_total_power,
                diff_supply_temp, diff_return_temp, diff_temp_diff,
                percent_total_power, percent_host_total_power, percent_chilled_pump_total_power,
                total_energy_saving, energy_saving_percent,
                optimized_supply_temp_applied, optimized_temp_diff_applied, failure_reasons,
                remarks
            ) VALUES (
                :r_low, :r_up, :s_low, :s_up, :d_low, :d_up,
                :cur_total, :cur_host, :cur_pump,
                :cur_supply, :cur_return, :cur_delta,
                :opt_total, :opt_host, :opt_pump,
                :opt_supply, :opt_return, :opt_delta,
                :diff_total, :diff_host, :diff_pump,
                :diff_supply, :diff_return, :diff_delta,
                :per_total, :per_host, :per_pump,
                :save_total, :save_per,
                :supply_applied, :diff_applied, :failure_reasons,
                :remarks
            )
            """
            params = {
                'r_low': float(cfg.get('return_temp_lower_limit', 0)),
                'r_up': float(cfg.get('return_temp_upper_limit', 0)),
                's_low': float(cfg.get('supply_temp_lower_limit', 0)),
                's_up': float(cfg.get('supply_temp_upper_limit', 0)),
                'd_low': float(cfg.get('temp_diff_lower_limit', 0)),
                'd_up': float(cfg.get('temp_diff_upper_limit', 0)),
                'cur_total': float(cur['total_power']),
                'cur_host': float(cur['host_power']),
                'cur_pump': float(cur['pump_power']),
                'cur_supply': float(cur['inlet']),
                'cur_return': float(cur['return']),
                'cur_delta': float(cur['return'] - cur['inlet']),
                'opt_total': float(opt['total_power']),
                'opt_host': float(opt['host_power']),
                'opt_pump': float(opt['pump_power']),
                'opt_supply': float(opt['inlet']),
                'opt_return': float(opt['return']),
                'opt_delta': float(opt['return'] - opt['inlet']),
                'diff_total': float(diff_total),
                'diff_host': float(diff_host),
                'diff_pump': float(diff_pump),
                'diff_supply': float(diff_supply),
                'diff_return': float(diff_return),
                'diff_delta': float(diff_delta),
                'per_total': float(percent_total),
                'per_host': float(percent_host),
                'per_pump': float(percent_pump),
                'save_total': float(-diff_total),
                'save_per': float(percent_total),
                'supply_applied': supply_applied,
                'diff_applied': diff_applied,
                'failure_reasons': failure_reasons_str,
                'remarks': base_rem
            }
            with self.postgres_engine.connect() as conn:
                conn.execute(text(query), params)
                conn.commit()
            logger.info(f"优化结果已保存，可下发标记: 供水温度={supply_applied}, 温差={diff_applied}")
            if failure_reasons_str:
                logger.info(f"失败原因: {failure_reasons_str}")
            return True
        except Exception as e:
            logger.error(f"保存失败: {e}")
            import traceback
            traceback.print_exc()
            return False
    def run_cycle(self):
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
            # ---------- 1. 加载优化配置 ----------
            if not self.load_optimization_config():
                failure_reasons.append("加载优化配置失败")
                logger.error("加载优化配置失败")
            else:
                logger.info("优化配置加载成功")

            # ---------- 2. 数据时效性检查 ----------
            data_recency_ok = self.check_all_data_recency()
            if not data_recency_ok:
                failure_reasons.append(f"数据时效性检查失败(超过{self.data_recency_minutes}分钟)")

            # ---------- 3. 模型加载检查 ----------
            if all(model is None for model in self.models.values()):
                if not self.load_models():
                    failure_reasons.append("模型加载失败")
                else:
                    logger.info("模型加载成功")

            # ---------- 4. 获取最新数据 ----------
            feature_values, data_time = self.get_latest_data()

            # 检查数据时间是否超时
            current_time = datetime.now()
            if isinstance(data_time, datetime):
                data_time_obj = data_time
            elif isinstance(data_time, str):
                try:
                    data_time_obj = datetime.strptime(data_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    data_time_obj = datetime.now()
                    failure_reasons.append("数据时间字符串格式异常")
            else:
                data_time_obj = datetime.now()
                failure_reasons.append("数据时间类型未知")

            time_diff_minutes = (current_time - data_time_obj).total_seconds() / 60
            if time_diff_minutes > self.data_recency_minutes:
                failure_reasons.append(f"数据时间超时({time_diff_minutes:.1f}分钟)")

            # 检查是否有任何冷冻侧设备在运行
            host_running = (feature_values.get(settings.host_1_running_status, 0) == 1.0 or
                            feature_values.get(settings.host_2_running_status, 0) == 1.0)
            pump_running = any(feature_values.get(getattr(settings, f'chilled_pump_{i}_running_status'), 0) == 1.0 for i in range(1,5))
            if not (host_running or pump_running):
                failure_reasons.append("所有冷冻侧设备均未运行")

            # ---------- 5. 更新历史残差队列（保留原逻辑）----------
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

            current_inlet = feature_values.get(settings.total_chilled_inlet_temp, 7.0)
            current_return = feature_values.get(settings.total_chilled_return_temp, 12.0)

            base_host = predict_base('host_total', current_inlet, current_return)
            base_pump = predict_base('chilled_pump_total', current_inlet, current_return)

            actual_host = None
            actual_pump = None
            if None not in [base_host, base_pump]:
                actual_host = feature_values.get(settings.composite_total_host_meter, 300.0)
                actual_pump = feature_values.get(settings.composite_total_chilled_pump_meter, 60.0)

                residual_host = actual_host - base_host
                residual_pump = actual_pump - base_pump

                self.historical_residuals['host_total'].append(residual_host)
                self.historical_residuals['chilled_pump_total'].append(residual_pump)

                max_lags = max(
                    self.residual_model_params.get('host_total', {}).get('residual_lags', 0),
                    self.residual_model_params.get('chilled_pump_total', {}).get('residual_lags', 0)
                )
                for key in self.historical_residuals:
                    if len(self.historical_residuals[key]) > max_lags:
                        self.historical_residuals[key] = self.historical_residuals[key][-max_lags:]

                logger.info(f"更新历史残差: host={residual_host:.2f}, pump={residual_pump:.2f}")
            else:
                logger.warning("无法计算基础预测，历史残差未更新")

            # ---------- 6. 前置条件判断（用于后续的稳态/R²检查） ----------
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

            # ---------- 7. 执行优化搜索（无论前置条件是否通过，只要模型已加载就执行） ----------
            if any(model is None for model in self.models.values()):
                logger.warning("模型未加载，无法执行优化搜索")
            else:
                search_result = self.find_optimal_pair(
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
                            failure_reasons.append(f"温差高于上限的组合有 {stats['delta_high']} 个（上限={constraints.get('temp_diff_upper_limit')}℃），请尝试增大 `temp_diff_upper_limit`")
                        if stats.get('delta_low', 0) > 0:
                            failure_reasons.append(f"温差低于下限的组合有 {stats['delta_low']} 个（下限={constraints.get('temp_diff_lower_limit')}℃），请尝试减小 `temp_diff_lower_limit`")
                        if stats.get('inlet_high', 0) > 0:
                            failure_reasons.append(f"供水温度高于上限的组合有 {stats['inlet_high']} 个（上限={constraints.get('supply_temp_upper_limit')}℃），请尝试增大 `supply_temp_upper_limit`")
                        if stats.get('inlet_low', 0) > 0:
                            failure_reasons.append(f"供水温度低于下限的组合有 {stats['inlet_low']} 个（下限={constraints.get('supply_temp_lower_limit')}℃），请尝试减小 `supply_temp_lower_limit`")
                        if stats.get('return_high', 0) > 0:
                            failure_reasons.append(f"回水温度高于上限的组合有 {stats['return_high']} 个（上限={constraints.get('return_temp_upper_limit')}℃），请尝试增大 `return_temp_upper_limit`")
                        if stats.get('return_low', 0) > 0:
                            failure_reasons.append(f"回水温度低于下限的组合有 {stats['return_low']} 个（下限={constraints.get('return_temp_lower_limit')}℃），请尝试减小 `return_temp_lower_limit`")
                        if stats.get('feature_failed', 0) > 0:
                            failure_reasons.append(f"特征准备失败的组合有 {stats['feature_failed']} 个，请检查模型特征映射或数据完整性")
                        if stats.get('other_error', 0) > 0:
                            failure_reasons.append(f"其他预测异常的组合有 {stats['other_error']} 个，请查看详细日志")
                        if not any([stats.get(k,0) for k in ['delta_high','delta_low','inlet_high','inlet_low','return_high','return_low','feature_failed','other_error']]):
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

            # ---------- 8. 构造最终结果并设置标记位 ----------
            if optimization_result is None:
                # 无优化结果，使用当前值
                current_result = self.create_fallback(feature_values)
                if current_result:
                    current_result['failure_reasons'] = failure_reasons
                    current_result['optimized_supply_temp_applied'] = False
                    current_result['optimized_temp_diff_applied'] = False
                    self.save_results(current_result, data_time)
                return True

            # 有优化结果，判断是否所有检查均通过
            all_checks_passed = (len(failure_reasons) == 0)
            optimization_result['failure_reasons'] = failure_reasons
            optimization_result['optimized_supply_temp_applied'] = all_checks_passed
            optimization_result['optimized_temp_diff_applied'] = all_checks_passed

            # 保存结果
            self.save_results(optimization_result, data_time)

            # 日志输出
            if all_checks_passed:
                logger.info("所有检查通过，优化结果可下发")
            else:
                logger.warning(f"存在失败原因，优化结果不可下发: {'; '.join(failure_reasons)}")

            # ---------- Redis 缓存（保留原逻辑）----------
            if self.redis_client:
                try:
                    all_res = optimization_result['all_results']
                    best = optimization_result['optimal']
                    desc = sorted(all_res, key=lambda x: x['total_power'], reverse=True)
                    others = [r for r in desc if not (r['total_power'] == best['total_power'] and r['inlet'] == best['inlet'] and r['return'] == best['return'])]
                    if len(desc) <= 20:
                        selected = desc
                    else:
                        sample_size = min(19, len(others))
                        selected_others = random.sample(others, sample_size) if sample_size > 0 else []
                        selected = selected_others + [best]
                        selected.sort(key=lambda x: x['total_power'], reverse=True)
                    logger.info("Selected total_power values: " + ", ".join([f"{r['total_power']:.2f}" for r in selected]))
                    combinations = []
                    for idx, r in enumerate(selected):
                        orig_rank = next((i+1 for i, c in enumerate(desc) if c['total_power'] == r['total_power'] and c['inlet'] == r['inlet'] and c['return'] == r['return']), idx+1)
                        combinations.append({
                            "index": orig_rank,
                            "chilled_inlet_temp": r['inlet'],
                            "chilled_return_temp": r['return'],
                            "actual_inlet_temp": r['inlet'],
                            "actual_return_temp": r['return'],
                            "delta_temp": round(r['return'] - r['inlet'], 1),
                            "host_power": r['host_power'],
                            "pump_power": r['pump_power'],
                            "total_power": r['total_power'],
                            "power_diff": r['power_diff'],
                            "power_diff_percent": r['power_diff_percent']
                        })
                    cache = {"timestamp": datetime.now().isoformat(), "combinations": combinations}
                    redis_key = f"{settings.PROGRAM_NAME}:chilled_opt:latest_iteration"
                    self.redis_client.setex(redis_key, 300, json.dumps(cache))
                    logger.info(f"迭代数据已缓存，共 {len(combinations)} 个组合（最后一个为最优）")
                except Exception as e:
                    logger.error(f"Redis缓存失败: {e}")

            best = optimization_result['optimal']
            cur = optimization_result['current']
            logger.info(f"当前总功率: {cur['total_power']:.2f} kW, 优化后: {best['total_power']:.2f} kW, 节能: {-best['power_diff']:.2f} kW")
            return True

        except Exception as e:
            logger.error(f"优化周期执行失败: {e}")
            import traceback
            traceback.print_exc()
            try:
                if feature_values is None:
                    feature_values, data_time = self.get_latest_data()
                current_result = self.create_fallback(feature_values)
                if current_result:
                    failure_reasons.append(f"优化过程异常: {str(e)[:50]}")
                    current_result['failure_reasons'] = failure_reasons
                    current_result['optimized_supply_temp_applied'] = False
                    current_result['optimized_temp_diff_applied'] = False
                    self.save_results(current_result, data_time)
            except Exception as save_error:
                logger.error(f"保存异常记录失败: {save_error}")
            return False
    def create_fallback(self, vals):
        inlet = vals.get(settings.total_chilled_inlet_temp, 7.0)
        ret = vals.get(settings.total_chilled_return_temp, 12.0)
        host = vals.get(settings.composite_total_host_meter, 300.0)
        pump = vals.get(settings.composite_total_chilled_pump_meter, 60.0)
        host1 = vals.get(settings.host_1_running_status, 1.0)
        host2 = vals.get(settings.host_2_running_status, 1.0)
        host_run = host1 == 1.0 or host2 == 1.0
        p1 = vals.get(settings.chilled_pump_1_running_status, 1.0)
        p2 = vals.get(settings.chilled_pump_2_running_status, 1.0)
        p3 = vals.get(settings.chilled_pump_3_running_status, 1.0)
        p4 = vals.get(settings.chilled_pump_4_running_status, 1.0)
        pump_run = any(p == 1.0 for p in [p1, p2, p3, p4])
        current = {
            'inlet': round(inlet, 1),
            'return': round(ret, 1),
            'host_power': round(host, 2),
            'pump_power': round(pump, 2),
            'total_power': round(host + pump, 2),
            'host_run': host_run,
            'pump_run': pump_run
        }
        best = {
            'inlet': current['inlet'],
            'return': current['return'],
            'host_power': current['host_power'],
            'pump_power': current['pump_power'],
            'total_power': current['total_power'],
            'power_diff': 0,
            'power_diff_percent': 0
        }
        return {
            'optimal': best,
            'all_results': [],
            'constraints': self.optimization_config or {},
            'current': current,
            'is_valid': False  # 标记为无效优化结果
        }

    def start(self):
        try:
            logger.info("启动冷冻水优化调度器（总功率版本，增强残差修正）...")
            if not self.connect_databases():
                return False
            if not self.load_optimization_config():
                return False
            self.load_models()
            self.scheduler = BlockingScheduler()
            # 使用从数据库读取的优化周期
            cycle_minutes = self.optimization_config.get('optimization_cycle_minutes', 5)
            # 生成 cron 表达式，例如每 5 分钟执行一次：'0,5,10,15,20,25,30,35,40,45,50,55'
            cron_minutes = ','.join([str(i) for i in range(0, 60, cycle_minutes)])
            self.scheduler.add_job(self.run_cycle, trigger=CronTrigger(minute=cron_minutes),
                                    id='chilled_opt_total', replace_existing=True)
            # 新增心跳任务（每30秒）
            self.scheduler.add_job(
                self.update_heartbeat,
                trigger='interval',
                seconds=30,
                id='heartbeat_job',
                name='心跳检测更新',
                replace_existing=True
            )
            cycle_minutes = self.optimization_config.get('optimization_cycle_minutes', 5)
            logger.info(f"调度器已启动，每{cycle_minutes}分钟运行一次，心跳每30秒一次")
            self.run_cycle()
            self.is_running = True
            self.scheduler.start()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        if self.scheduler:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("调度器已停止")

    def run_once(self):
        try:
            logger.info("单次运行测试")
            self.connect_databases()
            self.load_optimization_config()
            self.load_models()
            return self.run_cycle()
        except Exception as e:
            logger.error(f"单次运行失败: {e}")
            return False


def main():
    scheduler = ChilledTempSchedulerTotal()
    scheduler.start()


if __name__ == "__main__":
    main()