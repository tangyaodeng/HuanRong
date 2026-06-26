"""
base_optimizer.py — 优化调度器公共基类
======================================
将 cooling_opt / chilled_opt 中 ~60% 的重复代码提取到此基类。
子类只需实现少量钩子方法即可得到一个完整的定时优化调度器。

架构：
  BaseOptimizationScheduler  (本文件)
  ├── CoolingTempSchedulerTotal (new_cooling_opt.py)  — 冷却水优化
  └── ChilledTempSchedulerTotal (new_chilled_opt.py)  — 冷冻水优化

约定：
  - 所有 "settings 属性名" 通过 getattr(settings, attr) 解析为实际点位 ID 字符串
  - 配置从 app.new_config 的 OPTIMIZATION_CONFIGS / GROUP_COMPOSITE_METERS 读取
"""
import pickle
import numpy as np
import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
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
from app.new_config import OPTIMIZATION_CONFIGS, GROUP_COMPOSITE_METERS
from ml.utils.heartbeat_utils import update_heartbeat as _update_heartbeat


# ======================== 日志工具 ========================
class _UnicodeSafeStreamHandler(logging.StreamHandler):
    """修复 Windows 控制台编码问题"""
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


# ======================== 基类 ========================
class BaseOptimizationScheduler:
    """优化调度器公共基类"""

    # 子类需覆盖的属性
    OPT_TYPE: str = ""  # "cooling" | "chilled"

    def __init__(self):
        if not self.OPT_TYPE:
            raise ValueError("子类必须设置 OPT_TYPE")

        self.opt_cfg = OPTIMIZATION_CONFIGS[self.OPT_TYPE]

        # ---- 日志 ----
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.opt_cfg["log_filename"], encoding='utf-8'),
                _UnicodeSafeStreamHandler()
            ]
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)

        # ---- 数据库配置 ----
        self.mysql_config = {
            'host': settings.MYSQL_HOST,
            'port': settings.MYSQL_PORT,
            'user': settings.MYSQL_USER,
            'password': settings.MYSQL_PASSWORD,
            'database': settings.MYSQL_DATABASE,
            'charset': settings.MYSQL_CHARSET,
        }
        self.postgres_config = {'url': settings.DATABASE_URL}
        self.data_recency_minutes = self.opt_cfg.get("data_recency_minutes", 10)
        self.STEP_SIZE = 0.1

        # ---- 设备组 & 模型 ----
        self._device_groups = self.opt_cfg["device_groups"]
        self._temp_inlet_attr = self.opt_cfg["temp_inlet_attr"]
        self._temp_return_attr = self.opt_cfg["temp_return_attr"]

        # 从 MODEL_GROUPS 中过滤出参与本优化器的组
        _all_groups = settings.MODEL_GROUPS
        self.model_groups = {g: _all_groups[g] for g in self._device_groups if g in _all_groups}

        # 组 → 复合总功率电表（settings 属性名列表）
        self._group_comp_attrs = {
            g: GROUP_COMPOSITE_METERS[g]
            for g in self._device_groups if g in GROUP_COMPOSITE_METERS
        }
        # 组 → 实际点位 ID 列表
        self.group_total_power_map = {}
        for g, attrs in self._group_comp_attrs.items():
            pts = []
            for a in attrs:
                try:
                    pts.append(getattr(settings, a))
                except AttributeError:
                    self.logger.warning(f"settings 缺少属性 {a}，使用属性名作为点位")
                    pts.append(a)
            self.group_total_power_map[g] = pts

        # 组 → 设备运行状态点位列表（从结构化字典提取）
        _struct_map = {
            "host": settings.HOST,
            "cooling_tower": settings.COOLING_TOWER,
            "cooling_pump": settings.COOLING_PUMP,
            "chilled_pump": settings.CHILLED_PUMP,
        }
        self.group_status_points = {}
        self.group_device_power_points = {}  # 组 → [(power_point_id, device_label), ...]
        for g in self._device_groups:
            if g in _struct_map:
                devs = _struct_map[g].get("devices", {})
                self.group_status_points[g] = [d["running_status"] for d in devs.values()]
                # 提取每个设备的独立功率点位（用于稳态检查）
                pp = []
                for dev_num, d in devs.items():
                    if "power" in d and d["power"]:
                        pp.append((d["power"], f"{g}#{dev_num}"))
                self.group_device_power_points[g] = pp
            else:
                self.group_status_points[g] = []
                self.group_device_power_points[g] = []

        # 生成 model_keys
        self.model_keys = []
        self.group_for_key = {}
        self.total_power_point_for_key = {}

        for g, prefixes in self.model_groups.items():
            total_pts = self.group_total_power_map.get(g, [])
            if len(prefixes) != len(total_pts):
                self.logger.warning(f"组 {g} 前缀数({len(prefixes)}) != 总功率点数({len(total_pts)})")
                total_pts = total_pts[:len(prefixes)]
                self.group_total_power_map[g] = total_pts
            for idx, prefix in enumerate(prefixes):
                key = f"{g}_{idx}"
                self.model_keys.append(key)
                self.group_for_key[key] = g
                self.total_power_point_for_key[key] = total_pts[idx] if idx < len(total_pts) else total_pts[-1]

        # ---- 模型属性字典 ----
        self.models = {k: None for k in self.model_keys}
        self.residual_models = {k: None for k in self.model_keys}
        self.residual_model_params = {}
        self.model_feature_names = {k: [] for k in self.model_keys}
        self.model_info = {k: {} for k in self.model_keys}
        self.avg_bias = {k: 0.0 for k in self.model_keys}
        self.historical_residuals = {k: [] for k in self.model_keys}

        # ---- 构建 point_ids（从结构化设备字典 + 全局传感器）----
        self.point_ids = []
        self._collect_point_ids_from_structs()
        self.point_ids = list(set(self.point_ids))

        # 状态点白名单（从 group_status_points 汇总）
        self.status_point_ids = set()
        for pts in self.group_status_points.values():
            self.status_point_ids.update(pts)
        # 同时纳入未参与优化但存在的组的状态点（避免误判）
        for g, dev_dict in _struct_map.items():
            if g not in self._device_groups:
                for d in dev_dict.get("devices", {}).values():
                    self.status_point_ids.add(d.get("running_status", ""))

        # ---- 默认特征值 ----
        from app.new_config import DEFAULT_FEATURE_VALUES_BY_ATTR
        self.default_feature_values = {}
        for attr_name, val in DEFAULT_FEATURE_VALUES_BY_ATTR.items():
            try:
                pt_id = getattr(settings, attr_name)
                self.default_feature_values[pt_id] = val
            except AttributeError:
                pass

        # 确保涉及的温度变量和复合电表也有默认值
        for g in self._device_groups:
            for attr in self._group_comp_attrs.get(g, []):
                try:
                    pt = getattr(settings, attr)
                    if pt not in self.default_feature_values:
                        self.default_feature_values[pt] = 50.0
                except AttributeError:
                    pass

        # ---- 模型文件路径 ----
        self.model_dir = os.path.join(os.path.dirname(__file__), "saved_models")

        # ---- 调度器 ----
        self.scheduler = None
        self.is_running = False
        self.mysql_engine = None
        self.postgres_engine = None
        self.optimization_config = None

        # ---- Redis ----
        self.redis_client = None
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=2,
            )
            self.redis_client.ping()
            self.logger.info("Redis 连接成功")
        except Exception as e:
            self.logger.warning(f"Redis 连接失败: {e}")

        signal.signal(signal.SIGINT, self._signal_handler)

    # ======================== 内部辅助 ========================
    def _collect_point_ids_from_structs(self):
        """从 HOST / COOLING_TOWER / COOLING_PUMP / CHILLED_PUMP 字典中提取所有点位"""
        _struct_map = {
            "host": settings.HOST,
            "cooling_tower": settings.COOLING_TOWER,
            "cooling_pump": settings.COOLING_PUMP,
            "chilled_pump": settings.CHILLED_PUMP,
        }
        for g in self._device_groups:
            if g not in _struct_map:
                continue
            struct = _struct_map[g]
            # 设备子字段
            for dev in struct.get("devices", {}).values():
                for v in dev.values():
                    if v:
                        self.point_ids.append(v)
            # total 子字段
            for v in struct.get("total", {}).values():
                if v:
                    self.point_ids.append(v)
        # 天气
        for v in settings.WEATHER.values():
            if v:
                self.point_ids.append(v)
        # 复合电表
        for attrs in self._group_comp_attrs.values():
            for a in attrs:
                try:
                    self.point_ids.append(getattr(settings, a))
                except AttributeError:
                    pass

    def _resolve_attr(self, attr_name: str, default=None):
        """settings 属性名 → 实际点位 ID"""
        try:
            return getattr(settings, attr_name)
        except AttributeError:
            return default

    # ======================== 基础设施 ========================
    def update_heartbeat(self):
        _update_heartbeat(self.postgres_engine, self.opt_cfg["heartbeat_table"], self.logger)

    def _signal_handler(self, signum, frame):
        self.logger.info("接收到 Ctrl+C 信号，正在停止...")
        self.stop_scheduler()
        sys.exit(0)

    def connect_databases(self):
        try:
            ep = quote_plus(self.mysql_config['password'])
            mysql_url = (
                f"mysql+pymysql://{self.mysql_config['user']}:{ep}"
                f"@{self.mysql_config['host']}:{self.mysql_config['port']}"
                f"/{self.mysql_config['database']}?charset={self.mysql_config['charset']}"
            )
            self.mysql_engine = create_engine(mysql_url, pool_recycle=300, pool_pre_ping=True)
            with self.mysql_engine.connect() as c:
                c.execute(text("SELECT 1"))
            self.logger.info("MySQL 连接成功")
            self.postgres_engine = create_engine(self.postgres_config['url'], pool_recycle=300, pool_pre_ping=True)
            with self.postgres_engine.connect() as c:
                c.execute(text("SELECT 1"))
            self.logger.info("PostgreSQL 连接成功")
            return True
        except Exception as e:
            self.logger.error(f"数据库连接失败: {e}")
            return False

    def load_optimization_config(self):
        cfg = self.opt_cfg
        try:
            if not self.postgres_engine:
                return False
            cols = ", ".join(cfg["config_columns"])
            query = f"SELECT {cols} FROM {cfg['config_table']} WHERE id = 1"
            with self.postgres_engine.connect() as c:
                row = c.execute(text(query)).fetchone()
            if not row:
                self.logger.error(f"未找到 id=1 的 {cfg['config_table']} 配置")
                return False
            self.optimization_config = {}
            for i, key in enumerate(cfg["config_keys"]):
                val = row[i]
                if val is None and key in cfg["config_defaults"]:
                    val = cfg["config_defaults"][key]
                if key in cfg["config_transforms"]:
                    val = cfg["config_transforms"][key](val)
                elif val is not None:
                    try:
                        val = float(val)
                    except (ValueError, TypeError):
                        pass
                self.optimization_config[key] = val
            self.logger.info(
                f"加载 {cfg['config_table']} 成功，周期={self.optimization_config.get('optimization_cycle_minutes')}min, "
                f"R²阈值={self.optimization_config.get('r2_threshold')}"
            )
            return True
        except Exception as e:
            self.logger.error(f"加载优化配置失败: {e}")
            return False

    def load_models(self):
        try:
            if not os.path.exists(self.model_dir):
                self.logger.error(f"模型目录不存在: {self.model_dir}")
                return False
            for key in self.model_keys:
                g = self.group_for_key[key]
                idx = int(key.split('_')[-1])
                prefix = self.model_groups[g][idx]
                matched = sorted(
                    [f for f in os.listdir(self.model_dir) if f.startswith(prefix)],
                    reverse=True,
                )
                if not matched:
                    self.logger.error(f"未找到模型 {key} (prefix={prefix})")
                    return False
                path = os.path.join(self.model_dir, matched[0])
                self.logger.info(f"加载 {key}: {path}")
                try:
                    with open(path, 'rb') as f:
                        data = pickle.load(f)
                except EOFError as e:
                    self.logger.error(f"文件 {path} 损坏或不完整: {e}")
                    return False
                self.models[key] = data['model']
                self.residual_models[key] = data.get('residual_model')
                self.model_feature_names[key] = data.get('feature_names', [])
                self.model_info[key] = {
                    'model_params': data.get('model_params', {}),
                    'training_stats': data.get('training_stats', {}),
                    'feature_importance': data.get('feature_importance', {}),
                }
                self.residual_model_params[key] = {
                    'residual_lags': data.get('residual_lags', 0),
                    'use_standardize': data.get('use_standardize', False),
                    'residual_mean': data.get('residual_mean', 0.0),
                    'residual_std': data.get('residual_std', 1.0),
                }
                self.avg_bias[key] = data.get('avg_bias', 0.0)
                self.logger.info(f"  特征数={len(self.model_feature_names[key])}")
            self.logger.info(f"所有模型加载完成，共 {len(self.model_keys)} 个")
            return True
        except Exception as e:
            self.logger.error(f"加载模型失败: {e}")
            import traceback; traceback.print_exc()
            return False

    def check_data_recency(self, point_id: str) -> bool:
        try:
            if not self.mysql_engine:
                return False
            with self.mysql_engine.connect() as c:
                exists = c.execute(text(f"SHOW TABLES LIKE '{point_id}'")).fetchone()
                if not exists:
                    return False
                row = c.execute(text(f"SELECT MAX(UpdateDateTime) FROM `{point_id}`")).fetchone()
                if row and row[0]:
                    diff = (datetime.now() - row[0]).total_seconds() / 60
                    return diff <= self.data_recency_minutes
            return False
        except Exception as e:
            self.logger.error(f"时效检查失败 {point_id}: {e}")
            return False

    def check_all_data_recency(self) -> bool:
        self.logger.info("检查数据时效性...")
        key_pt_ids = []
        for attr in self.opt_cfg.get("recency_key_attrs", []):
            pt = self._resolve_attr(attr)
            if pt:
                key_pt_ids.append(pt)
        all_ok = True
        for pt in key_pt_ids:
            if not self.check_data_recency(pt):
                all_ok = False
        if all_ok:
            self.logger.info(f"所有关键点位数据在 {self.data_recency_minutes} 分钟内")
        else:
            self.logger.warning("部分关键点位数据超时")
        return all_ok

    def get_recent_power_series(self, point_id: str, window_minutes: int = 5) -> List[float]:
        try:
            if not self.mysql_engine:
                return []
            with self.mysql_engine.connect() as c:
                exists = c.execute(text(f"SHOW TABLES LIKE '{point_id}'")).fetchone()
            if not exists:
                return []
            query = f"""
            SELECT PointValue FROM `{point_id}`
            WHERE UpdateDateTime >= NOW() - INTERVAL {window_minutes} MINUTE
            ORDER BY UpdateDateTime ASC
            """
            with self.mysql_engine.connect() as c:
                rows = c.execute(text(query)).fetchall()
            return [float(r[0]) for r in rows if r[0] is not None]
        except Exception as e:
            self.logger.error(f"获取 {point_id} 功率序列失败: {e}")
            return []

    def is_power_stable(self, point_id: str, window_minutes: int = 5,
                        std_threshold: float = None, cv_threshold: float = 0.05) -> Tuple[bool, str]:
        powers = self.get_recent_power_series(point_id, window_minutes)
        if len(powers) < 3:
            return False, f"点位{point_id}数据不足({len(powers)}点)"
        mean_v = np.mean(powers)
        std_v = np.std(powers)
        if std_threshold is not None:
            if std_v > std_threshold:
                return False, f"点位{point_id}不稳定(σ={std_v:.2f}>{std_threshold}kW)"
        else:
            cv = std_v / mean_v if mean_v > 0 else 0
            if cv > cv_threshold:
                return False, f"点位{point_id}不稳定(CV={cv:.3f}>{cv_threshold})"
        return True, ""

    def check_all_running_devices_stable(self, feature_values):
        failures = []
        thresholds = self.opt_cfg.get("stability_thresholds", {})
        for g in self._device_groups:
            if g not in self.model_groups:
                continue
            status_pts = self.group_status_points.get(g, [])
            if not any(feature_values.get(pt, 0) == 1.0 for pt in status_pts):
                continue
            thr = thresholds.get(g)
            if thr is None:
                continue
            # 优先用单个设备功率点检查; fallback 到复合总表
            dev_pps = self.group_device_power_points.get(g, [])
            if dev_pps:
                for pp, label in dev_pps:
                    stable, reason = self.is_power_stable(pp, window_minutes=5, std_threshold=thr)
                    if not stable:
                        failures.append(f"{label}: {reason}")
            else:
                for idx, total_pt in enumerate(self.group_total_power_map.get(g, [])):
                    stable, reason = self.is_power_stable(total_pt, window_minutes=5, std_threshold=thr)
                    if not stable:
                        failures.append(f"{g}[{idx}]: {reason}")
        return (len(failures) == 0), failures

    def check_model_r2(self):
        threshold = self.optimization_config.get('r2_threshold', 0.6) if self.optimization_config else 0.6
        failures = []
        r2map = self.opt_cfg.get("r2_device_id_map", {})
        skip = set(self.opt_cfg.get("r2_skip_groups", []))
        for key in self.model_keys:
            if self.group_for_key[key] in skip:
                continue
            did = r2map.get(key)
            if did is None:
                failures.append(f"模型 {key} 无 R² device_id 映射")
                continue
            r2 = self._get_latest_r2_for_device_id(did)
            if r2 is None or r2 < threshold:
                failures.append(f"模型 {key} R²({r2}) < 阈值({threshold})")
        return (len(failures) == 0), failures

    def _get_latest_r2_for_device_id(self, device_id: int) -> Optional[float]:
        try:
            q = "SELECT r_squared FROM model_evaluations WHERE model_id = :mid ORDER BY created_at DESC LIMIT 1"
            with self.postgres_engine.connect() as c:
                row = c.execute(text(q), {"mid": device_id}).fetchone()
                if row:
                    return float(row[0])
        except Exception as e:
            self.logger.error(f"获取 device_id={device_id} R² 失败: {e}")
        return None

    def get_latest_data(self):
        try:
            if not self.mysql_engine:
                return self.default_feature_values.copy(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            vals = {}
            data_time = None
            for pid in self.point_ids:
                try:
                    with self.mysql_engine.connect() as c:
                        exists = c.execute(text(f"SHOW TABLES LIKE '{pid}'")).fetchone()
                    if not exists:
                        vals[pid] = self.default_feature_values.get(pid, 0.0)
                        continue
                    with self.mysql_engine.connect() as c:
                        row = c.execute(text(
                            f"SELECT PointValue, UpdateDateTime FROM `{pid}` ORDER BY UpdateDateTime DESC LIMIT 1"
                        )).fetchone()
                    if row and row[0] is not None:
                        if pid in self.status_point_ids:
                            raw = row[0]
                            if isinstance(raw, (int, float)):
                                vals[pid] = float(raw) if raw in (0, 1) else (1.0 if raw != 0 else 0.0)
                            else:
                                s = str(raw).strip().lower()
                                vals[pid] = 1.0 if s in ('true','on','运行','1','open','opened') else 0.0
                        else:
                            vals[pid] = float(row[0])
                        if data_time is None:
                            data_time = row[1]
                    else:
                        vals[pid] = self.default_feature_values.get(pid, 0.0)
                except Exception:
                    vals[pid] = self.default_feature_values.get(pid, 0.0)
            for pid, dv in self.default_feature_values.items():
                if pid not in vals:
                    vals[pid] = dv
            if data_time is None:
                data_time = datetime.now()
            self.logger.info(f"获取 {len(vals)} 个点位数据 (时间: {data_time})")
            return vals, data_time
        except Exception as e:
            self.logger.error(f"获取数据失败: {e}")
            return self.default_feature_values.copy(), datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # ======================== 特征准备 / 预测（参数化）========================
    def prepare_features(self, feature_values: Dict, inlet_temp: float, return_temp: float,
                         model_key: str):
        """准备特征 — 更新温差点位，处理派生特征。子类可覆盖。"""
        try:
            inlet_pt = self._resolve_attr(self._temp_inlet_attr)
            return_pt = self._resolve_attr(self._temp_return_attr)
            if inlet_pt and inlet_pt in feature_values:
                feature_values[inlet_pt] = inlet_temp
            if return_pt and return_pt in feature_values:
                feature_values[return_pt] = return_temp

            fnames = self.model_feature_names[model_key]
            if not fnames:
                return None
            feats = []
            for fn in fnames:
                if fn in feature_values:
                    feats.append(feature_values[fn])
                    continue
                # 试试 settings 属性映射
                pt = self._resolve_attr(fn)
                if pt and isinstance(pt, str) and pt in feature_values:
                    feats.append(feature_values[pt])
                    continue
                # 派生特征
                from app.new_config import DERIVED_FEATURE_GROUPS
                if fn in DERIVED_FEATURE_GROUPS:
                    g = DERIVED_FEATURE_GROUPS[fn]
                    status_pts = self.group_status_points.get(g, [])
                    feats.append(1.0 if any(feature_values.get(sp, 0) == 1.0 for sp in status_pts) else 0.0)
                    continue
                # 旧属性名映射
                from app.new_config import LEGACY_POWER_ATTR_MAP
                if fn in LEGACY_POWER_ATTR_MAP:
                    pt2 = self._resolve_attr(LEGACY_POWER_ATTR_MAP[fn])
                    if pt2 and pt2 in feature_values:
                        feats.append(feature_values[pt2])
                        continue
                # 默认值
                dv = 0.0
                if 'temp' in fn.lower(): dv = 25.0
                elif 'pressure' in fn.lower(): dv = 1.0
                elif 'power' in fn.lower(): dv = 100.0
                elif 'cop' in fn.lower(): dv = 5.0
                elif 'capacity' in fn.lower(): dv = 1000.0
                elif 'flow' in fn.lower(): dv = 100.0
                elif 'humidity' in fn.lower(): dv = 60.0
                feats.append(dv)
            return np.array(feats).reshape(1, -1)
        except Exception as e:
            self.logger.error(f"prepare_features {model_key}: {e}")
            return None

    def predict_power_with_status(self, model_key: str, features_array, feature_values: Dict,
                                   inlet_temp: float, return_temp: float,
                                   historical_residuals: Optional[List[float]] = None) -> float:
        POWER_THRESHOLD = 10.0
        g = self.group_for_key[model_key]
        total_pt = self.total_power_point_for_key.get(model_key)
        status_pts = self.group_status_points.get(g, [])
        running = any(feature_values.get(sp, 0) == 1.0 for sp in status_pts)
        cur_pwr = feature_values.get(total_pt, 0.0) if total_pt else 0.0
        if not running and cur_pwr <= POWER_THRESHOLD:
            return 0.0
        if self.models.get(model_key) is None:
            return cur_pwr
        fnames = self.model_feature_names[model_key]
        if len(fnames) != features_array.shape[1]:
            dmat = xgb.DMatrix(features_array, feature_names=[f'f{i}' for i in range(features_array.shape[1])])
        else:
            dmat = xgb.DMatrix(features_array, feature_names=fnames)
        base = self.models[model_key].predict(dmat)[0]
        base += self.avg_bias.get(model_key, 0.0)
        final = base
        rmodel = self.residual_models.get(model_key)
        rp = self.residual_model_params.get(model_key, {})
        rlags = rp.get('residual_lags', 0)
        if rmodel is not None:
            if rlags > 0:
                if historical_residuals is None:
                    lf = np.zeros((features_array.shape[0], rlags))
                else:
                    if len(historical_residuals) < rlags:
                        pad = [0.0] * (rlags - len(historical_residuals))
                        full_r = pad + historical_residuals
                    else:
                        full_r = historical_residuals[-rlags:]
                    lf = np.tile(full_r, (features_array.shape[0], 1))
                Xr = np.hstack([features_array, lf])
            else:
                Xr = features_array
            try:
                rp_val = rmodel.predict(Xr)
                if isinstance(rp_val, np.ndarray):
                    rp_val = rp_val.ravel()[0]
                if rp.get('use_standardize', False):
                    rp_val = rp_val * rp.get('residual_std', 1.0) + rp.get('residual_mean', 0.0)
                final = base + rp_val
            except Exception as e:
                self.logger.warning(f"{model_key} 残差预测失败: {e}")
        return float(final)

    def _get_group_total_power(self, feature_values, group_name):
        """从 feature_values 中汇总某组的总功率"""
        total = 0.0
        for pt in self.group_total_power_map.get(group_name, []):
            total += feature_values.get(pt, 0.0)
        return total

    def _calc_total_power(self, sub_powers: Dict[str, float]) -> float:
        """计算优化总功率：只累加参与优化的设备组"""
        total = 0.0
        for k, v in sub_powers.items():
            if self.group_for_key.get(k) in self._device_groups:
                total += v
        return total

    # ======================== 温度对生成（参数化）= 子类可覆盖 ========================
    def _get_optimization_constraints(self, base_feature_values: Dict) -> Optional[Dict]:
        """获取优化约束。冷却侧基于湿球温度；冷冻侧直接使用 DB 配置。子类可覆盖。"""
        raise NotImplementedError

    def _generate_temperature_pairs(self, constraints: Dict) -> List[Tuple[float, float]]:
        """生成温度组合。子类可覆盖。"""
        raise NotImplementedError

    # ======================== 搜索 & 结果构建 = 子类必须覆盖 ========================


    def _create_fallback_result(self, feature_values: Dict) -> Optional[Dict]:
        """创建回退结果（优化失败时使用当前值）。子类必须实现。"""
        raise NotImplementedError

    def _save_results(self, optimization_result: Dict, data_time) -> bool:
        """保存结果到 PostgreSQL。子类必须实现。"""
        raise NotImplementedError

    def _cache_to_redis(self, optimization_result: Dict):
        """缓存迭代数据到 Redis。子类可覆盖。"""
        pass

    # ======================== 优化周期主循环 ========================
    def run_optimization_cycle(self):
        """运行一次完整的优化周期"""
        self.logger.info("=" * 80)
        self.logger.info(f"开始优化周期 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 80)

        failure_reasons = []
        optimization_result = None
        data_time = None
        feature_values = None

        try:
            # 1. 加载配置
            if not self.load_optimization_config():
                failure_reasons.append("加载优化配置失败")

            # 2. 时效性检查
            if not self.check_all_data_recency():
                failure_reasons.append(f"数据时效性检查失败(>{self.data_recency_minutes}分钟)")

            # 3. 模型加载
            if all(m is None for m in self.models.values()):
                if not self.load_models():
                    failure_reasons.append("模型加载失败")

            # 4. 获取数据
            feature_values, data_time = self.get_latest_data()

            # 检查数据时间
            now = datetime.now()
            if isinstance(data_time, datetime):
                dt_obj = data_time
            elif isinstance(data_time, str):
                try:
                    dt_obj = datetime.strptime(data_time, '%Y-%m-%d %H:%M:%S')
                except ValueError:
                    dt_obj = now
                    failure_reasons.append("数据时间格式异常")
            else:
                dt_obj = now
            if (now - dt_obj).total_seconds() / 60 > self.data_recency_minutes:
                failure_reasons.append(f"数据超时({(now-dt_obj).total_seconds()/60:.1f}分钟)")

            # 检查是否有设备在运行
            any_running = False
            for g in self._device_groups:
                status_pts = self.group_status_points.get(g, [])
                if any(feature_values.get(sp, 0) == 1.0 for sp in status_pts):
                    any_running = True
                    break
            if not any_running:
                failure_reasons.append("所有设备均未运行")

            # 5. 更新历史残差
            cur_inlet_pt = self._resolve_attr(self._temp_inlet_attr)
            cur_return_pt = self._resolve_attr(self._temp_return_attr)
            cur_inlet = feature_values.get(cur_inlet_pt, 0) if cur_inlet_pt else 0
            cur_return = feature_values.get(cur_return_pt, 0) if cur_return_pt else 0

            def predict_base(mk):
                f = self.prepare_features(feature_values.copy(), cur_inlet, cur_return, mk)
                if f is None:
                    return None
                fn2 = self.model_feature_names[mk]
                if len(fn2) != f.shape[1]:
                    dm = xgb.DMatrix(f, feature_names=[f'f{i}' for i in range(f.shape[1])])
                else:
                    dm = xgb.DMatrix(f, feature_names=fn2)
                return self.models[mk].predict(dm)[0]

            for mk in self.model_keys:
                bp = predict_base(mk)
                if bp is not None:
                    actual = feature_values.get(self.total_power_point_for_key.get(mk, ""), bp)
                    residual = actual - bp
                    self.historical_residuals[mk].append(residual)
                    if len(self.historical_residuals[mk]) > 20:
                        self.historical_residuals[mk] = self.historical_residuals[mk][-20:]

            # 6. 前置判断
            precheck_ok = (len(failure_reasons) == 0)
            if precheck_ok:
                stable, s_reasons = self.check_all_running_devices_stable(feature_values)
                if not stable:
                    failure_reasons.extend(s_reasons)
                r2_ok, r2_reasons = self.check_model_r2()
                if not r2_ok:
                    failure_reasons.extend(r2_reasons)

            # 7. 优化搜索
            if any(m is None for m in self.models.values()):
                missing = [k for k, m in self.models.items() if m is None]
                failure_reasons.append(f"部分模型未加载({len(missing)}/{len(self.model_keys)}: {', '.join(missing)})，跳过优化搜索")
                self.logger.warning(f"跳过优化搜索：缺失模型 {missing}")
            else:
                search_result = self._find_optimal(feature_values, self.historical_residuals)
                if search_result is None:
                    failure_reasons.append("优化搜索异常（返回None）")
                elif not search_result.get('success', False):
                    reason = search_result.get('reason', '')
                    stats = search_result.get('filter_stats', {})
                    constraints = search_result.get('constraints', {})
                    self._add_failure_details(failure_reasons, reason, stats, constraints, search_result)
                else:
                    optimization_result = search_result

            # 8. 保存
            if optimization_result is None:
                fb = self._create_fallback_result(feature_values)
                if fb:
                    fb['failure_reasons'] = failure_reasons
                    for flag in self.opt_cfg.get("applied_flags", []):
                        fb[flag] = False
                    self._save_results(fb, data_time)
                return True

            all_ok = (len(failure_reasons) == 0)
            optimization_result['failure_reasons'] = failure_reasons
            for flag in self.opt_cfg.get("applied_flags", []):
                optimization_result[flag] = all_ok
            self._save_results(optimization_result, data_time)
            if all_ok:
                self.logger.info("所有检查通过，优化结果可下发")
            else:
                self.logger.warning(f"存在失败原因: {'; '.join(failure_reasons)}")
            self._cache_to_redis(optimization_result)
            return True
        except Exception as e:
            self.logger.error(f"优化周期执行失败: {e}")
            import traceback; traceback.print_exc()
            try:
                if feature_values is None:
                    feature_values, data_time = self.get_latest_data()
                fb = self._create_fallback_result(feature_values)
                if fb:
                    failure_reasons.append(f"优化异常: {str(e)[:50]}")
                    fb['failure_reasons'] = failure_reasons
                    for flag in self.opt_cfg.get("applied_flags", []):
                        fb[flag] = False
                    self._save_results(fb, data_time)
            except Exception as se:
                self.logger.error(f"保存异常记录失败: {se}")
            return False

    def _find_optimal(self, base_values, historical_residuals):
        """网格搜索最优温度组合。
        子类需实现: _get_optimization_constraints, _generate_temperature_pairs,
        _predict_for_temp_pair, _create_fallback_result, _save_results.
        """
        try:
            constraints = self._get_optimization_constraints(base_values)
            if constraints is None:
                return None
            pairs = self._generate_temperature_pairs(constraints)
            if not pairs:
                self.logger.warning("未生成任何温度组合")
                return None
            results = []
            # 过滤器计数器
            fc = {}
            for idx, (inlet, ret) in enumerate(pairs):
                try:
                    entry = self._predict_for_temp_pair(inlet, ret, base_values, historical_residuals)
                except Exception as e:
                    fc['other_error'] = fc.get('other_error', 0) + 1
                    if idx < 10:
                        self.logger.debug(f"组合{idx}: 预测异常 - {e}")
                    continue
                if entry is None:
                    fc['feature_failed'] = fc.get('feature_failed', 0) + 1
                    continue
                # 基类统一过滤
                passed, reason_key = self._filter_temp_pair(entry, constraints, base_values)
                if not passed:
                    fc[reason_key] = fc.get(reason_key, 0) + 1
                    continue
                results.append(entry)
            filter_stats = {'total_pairs': len(pairs), **fc}
            self.logger.info(f"过滤统计: {filter_stats}, 有效组合: {len(results)}")
            if not results:
                return {'success': False, 'reason': 'no_valid_combinations',
                        'filter_stats': filter_stats, 'constraints': constraints}
            results.sort(key=lambda x: x.get('total_power', 1e9))
            best = results[0]
            cur_total = self._get_current_total_power(base_values)
            es_thr = self.optimization_config.get('energy_saving_threshold', 0.0)
            es_pct = (cur_total - best['total_power']) / cur_total * 100.0 if cur_total else 0
            self.logger.info(f"最优功率={best['total_power']:.2f}kW, 当前={cur_total:.2f}kW, 节能率={es_pct:.2f}%")
            if es_pct < es_thr:
                return {'success': False, 'reason': 'energy_saving_too_low',
                        'energy_saving_percent': es_pct, 'threshold': es_thr,
                        'optimal_power': best['total_power'], 'current_power': cur_total,
                        'filter_stats': filter_stats, 'constraints': constraints}
            if best['total_power'] >= cur_total:
                return {'success': False, 'reason': 'power_not_lower',
                        'optimal_power': best['total_power'], 'current_power': cur_total,
                        'filter_stats': filter_stats, 'constraints': constraints}
            return self._build_final_result(best, results, constraints, base_values, cur_total)
        except Exception as e:
            self.logger.error(f"搜索失败: {e}")
            import traceback; traceback.print_exc()
            return None

    def _predict_for_temp_pair(self, inlet_temp, return_temp, base_values, historical_residuals):
        """对单个温度组合预测功率。子类必须实现。返回 dict 或 None。"""
        raise NotImplementedError

    def _filter_temp_pair(self, entry, constraints, base_values):
        """基类统一过滤 — 子类可在 entry 中设 '__skip_reason' 来跳过。返回 (passed, reason_key)"""
        reason = entry.pop('__skip_reason', None)
        if reason:
            return False, reason
        return True, None

    def _get_current_total_power(self, base_values):
        total = 0.0
        for g in self._device_groups:
            total += self._get_group_total_power(base_values, g)
        return total

    def _build_final_result(self, best, all_results, constraints, base_values, cur_total):
        """构建最终结果 — 子类可覆盖"""
        return {
            'success': True,
            'optimal_result': best,
            'all_results': all_results,
            'constraints': constraints,
        }

    def _add_failure_details(self, failure_reasons, reason, stats, constraints, search_result):
        """添加详细的失败原因。子类可覆盖。"""
        if reason == 'no_valid_combinations':
            for k, label in [('delta_high','温差高于上限'),('delta_low','温差低于下限'),
                             ('inlet_high','供水高于上限'),('inlet_low','供水低于下限'),
                             ('return_high','回水高于上限'),('return_low','回水低于下限'),
                             ('heat_high','散热量高于上限'),('heat_low','散热量低于下限'),
                             ('feature_failed','特征准备失败'),('other_error','预测异常')]:
                if stats.get(k, 0) > 0:
                    failure_reasons.append(f"{label}的组合 {stats[k]} 个")
        elif reason == 'energy_saving_too_low':
            failure_reasons.append(
                f"节能率 {search_result.get('energy_saving_percent',0):.2f}% < 阈值 {search_result.get('threshold',0)}%")
        elif reason == 'power_not_lower':
            failure_reasons.append(
                f"最优功率 {search_result.get('optimal_power',0):.2f} >= 当前 {search_result.get('current_power',0):.2f}")
        else:
            failure_reasons.append(f"未知失败原因: {reason}")

    # ======================== 调度器生命周期 ========================
    def start_scheduler(self):
        try:
            self.logger.info(f"启动 {self.OPT_TYPE} 优化调度器...")
            if not self.connect_databases():
                return False
            if not self.load_optimization_config():
                return False
            if not self.load_models():
                self.logger.warning("模型加载失败，将使用当前值")
            self.scheduler = BlockingScheduler()
            cycle = self.optimization_config.get('optimization_cycle_minutes', 5)
            cron_m = ','.join(str(i) for i in range(0, 60, int(cycle)))
            self.scheduler.add_job(
                self.run_optimization_cycle, trigger=CronTrigger(minute=cron_m),
                id=f'{self.OPT_TYPE}_opt', replace_existing=True,
            )
            self.scheduler.add_job(
                self.update_heartbeat, trigger='interval', seconds=30,
                id='heartbeat_job', replace_existing=True,
            )
            self.logger.info(f"调度器已启动，每 {cycle} 分钟一次，心跳 30 秒")
            self.logger.info("立即执行首次优化...")
            self.run_optimization_cycle()
            self.is_running = True
            self.scheduler.start()
            return True
        except KeyboardInterrupt:
            self.stop_scheduler()
            return True
        except Exception as e:
            self.logger.error(f"启动失败: {e}")
            import traceback; traceback.print_exc()
            return False

    def stop_scheduler(self):
        if self.scheduler:
            try:
                self.scheduler.shutdown()
                self.scheduler = None
                self.is_running = False
                self.logger.info("调度器已停止")
            except Exception as e:
                self.logger.error(f"停止失败: {e}")

    def run_once(self):
        try:
            self.logger.info("单次运行测试...")
            self.connect_databases()
            self.load_optimization_config()
            self.load_models()
            return self.run_optimization_cycle()
        except Exception as e:
            self.logger.error(f"单次运行失败: {e}")
            return False
