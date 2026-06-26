"""
new_config.py — 优化器集中配置
===============================
引入原因：cooling_opt / chilled_opt 各自在 __init__ 中硬编码了大量项目相关的
点位映射、复合电表、表名等。新项目上线时不得不同时修改两个大文件。

本模块提供两份东西：
1. OPTIMIZATION_CONFIGS  — 冷却侧 / 冷冻侧各自的优化参数（表名、Redis key、设备组等）
2. GROUP_COMPOSITE_METERS — 每个设备组的复合总功率电表列表（顺序与 MODEL_GROUPS 前缀一一对应）

使用方式：
    from app.new_config import OPTIMIZATION_CONFIGS, GROUP_COMPOSITE_METERS
    cfg = OPTIMIZATION_CONFIGS["cooling"]

约定：
- 所有 "settings 属性名" 都是 config.Settings 上的字段名，运行时通过
  getattr(settings, attr_name) 解析为实际点位 ID 字符串。
- 新增项目时只需在此文件追加/修改配置，cooling_opt / chilled_opt 不动。
"""
from typing import Dict, List, Any

# ============================================================================
# 1. 冷却 / 冷冻 优化配置
# ============================================================================
OPTIMIZATION_CONFIGS: Dict[str, Dict[str, Any]] = {
    "cooling": {
        # ---- 数据库表名 ----
        "config_table": "cooling_opt_config",
        "result_table": "cooling_opt_parameters_total",
        "heartbeat_table": "cooling_opt_parameters_total",

        # ---- Redis 缓存 key 模板（{program_name} 会被 settings.PROGRAM_NAME 替换）----
        "redis_key_pattern": "{program_name}:cooling_opt:latest_iteration",

        # ---- 日志文件名 ----
        "log_filename": "cooling_optimization_total.log",

        # ---- 参与优化的设备组（与 MODEL_GROUPS 的 key 对应）----
        "device_groups": ["host", "cooling_tower", "cooling_pump"],

        # ---- 被优化的温度变量（settings 属性名）----
        "temp_inlet_attr": "cooling_water_main_supply_temperature",
        "temp_return_attr": "return_water_temperature_of_cooling_water_main_pipe",

        # ---- 温度大小关系：冷却侧 供水 > 回水；冷冻侧 回水 > 供水 ----
        "temp_direction": "inlet_gt_return",

        # ---- 数据时效性阈值（分钟）----
        "data_recency_minutes": 30,

        # ---- 是否使用散热量约束（仅冷却侧有）----
        "use_heat_dissipation": True,

        # ---- 从 config_table SELECT 的列名列表（按顺序）----
        "config_columns": [
            "return_temp_lower_limit", "return_temp_upper_limit",
            "supply_temp_lower_limit", "supply_temp_upper_limit",
            "temp_diff_lower_limit", "temp_diff_upper_limit",
            "heat_dissipation_lower_limit", "heat_dissipation_upper_limit",
            "optimization_cycle_minutes", "r2_threshold", "energy_saving_threshold",
        ],
        "config_keys": [
            "return_temp_lower_limit", "return_temp_upper_limit",
            "supply_temp_lower_limit", "supply_temp_upper_limit",
            "temp_diff_lower_limit", "temp_diff_upper_limit",
            "heat_dissipation_lower_limit", "heat_dissipation_upper_limit",
            "optimization_cycle_minutes", "r2_threshold", "energy_saving_threshold",
        ],
        "config_transforms": {
            "heat_dissipation_lower_limit": lambda v: float(v) / 100.0,
            "heat_dissipation_upper_limit": lambda v: float(v) / 100.0,
        },
        "config_defaults": {
            "optimization_cycle_minutes": 5,
            "r2_threshold": 0.6,
            "energy_saving_threshold": 0.0,
        },

        # ---- R² 检查：model_key → model_evaluations.model_id ----
        "r2_device_id_map": {
            "host_0": 2, "host_1": 3,
            "cooling_tower_0": 4,
            "cooling_pump_0": 5, "cooling_pump_1": 6,
        },
        "r2_skip_groups": ["chilled_pump"],

        # ---- 稳态检查：各组总功率点的标准差阈值 (kW) ----
        "stability_thresholds": {
            "host": 30.0,
            "cooling_tower": 3.0,
            "cooling_pump": 2.0,
        },

        # ---- 结果表中"优化是否可下发"的标记字段名 ----
        "applied_flags": ["optimized_return_temp_applied", "optimized_temp_diff_applied"],

        # ---- 数据时效性检查的关键点位（settings 属性名列表）----
        "recency_key_attrs": [
            "cooling_water_main_supply_temperature",
            "return_water_temperature_of_cooling_water_main_pipe",
            "wet_bulb_temperature",
            "composite_total_host_meter_1",
            "composite_total_host_meter_2",
            "composite_total_cooling_tower_meter",
            "composite_total_cooling_pump_meter_1",
            "composite_total_cooling_pump_meter_2",
        ],
    },

    "chilled": {
        # ---- 数据库表名 ----
        "config_table": "chilled_opt_config",
        "result_table": "chilled_opt_parameters_total",
        "heartbeat_table": "chilled_opt_parameters_total",

        # ---- Redis 缓存 key 模板 ----
        "redis_key_pattern": "{program_name}:chilled_opt:latest_iteration",

        # ---- 日志文件名 ----
        "log_filename": "chilled_optimization_total.log",

        # ---- 参与优化的设备组 ----
        "device_groups": ["host", "chilled_pump"],

        # ---- 被优化的温度变量 ----
        "temp_inlet_attr": "total_chilled_inlet_temp",
        "temp_return_attr": "total_chilled_return_temp",

        # ---- 温度大小关系 ----
        "temp_direction": "return_gt_inlet",

        # ---- 数据时效性阈值（分钟）----
        "data_recency_minutes": 30,

        # ---- 不使用散热量约束 ----
        "use_heat_dissipation": False,

        # ---- 配置列 ----
        "config_columns": [
            "return_temp_lower_limit", "return_temp_upper_limit",
            "supply_temp_lower_limit", "supply_temp_upper_limit",
            "temp_diff_lower_limit", "temp_diff_upper_limit",
            "optimization_cycle_minutes", "r2_threshold", "energy_saving_threshold",
        ],
        "config_keys": [
            "return_temp_lower_limit", "return_temp_upper_limit",
            "supply_temp_lower_limit", "supply_temp_upper_limit",
            "temp_diff_lower_limit", "temp_diff_upper_limit",
            "optimization_cycle_minutes", "r2_threshold", "energy_saving_threshold",
        ],
        "config_transforms": {},
        "config_defaults": {
            "optimization_cycle_minutes": 5,
            "r2_threshold": 0.6,
            "energy_saving_threshold": 0.5,
        },

        # ---- R² 检查 ----
        "r2_device_id_map": {
            "host_0": 2, "host_1": 3,
            "chilled_pump_0": 7, "chilled_pump_1": 8, "chilled_pump_2": 9,
        },
        "r2_skip_groups": ["cooling_tower", "cooling_pump"],

        # ---- 稳态检查阈值 ----
        "stability_thresholds": {
            "host": 30.0,
            "chilled_pump": 3.0,
        },

        # ---- 结果标记字段 ----
        "applied_flags": ["optimized_supply_temp_applied", "optimized_temp_diff_applied"],

        # ---- 数据时效性检查的关键点位 ----
        "recency_key_attrs": [
            "total_chilled_inlet_temp",
            "total_chilled_return_temp",
            "composite_total_host_meter_1",
            "composite_total_host_meter_2",
            "composite_total_chilled_pump_meter_1",
            "composite_total_chilled_pump_meter_2",
            "composite_total_glycol_pump_meter",
        ],
    },
}

# ============================================================================
# 2. 设备组 → 总功率复合电表列表（settings 属性名）
#    顺序与 config.MODEL_GROUPS[group_name] 一一对应
# ============================================================================
GROUP_COMPOSITE_METERS: Dict[str, List[str]] = {
    "host": [
        "composite_total_host_meter_1",
        "composite_total_host_meter_2",
    ],
    "cooling_tower": [
        "composite_total_cooling_tower_meter",
    ],
    "cooling_pump": [
        "composite_total_cooling_pump_meter_1",
        "composite_total_cooling_pump_meter_2",
    ],
    "chilled_pump": [
        "composite_total_chilled_pump_meter_1",
        "composite_total_chilled_pump_meter_2",
        "composite_total_glycol_pump_meter",
    ],
}

# ============================================================================
# 3. 默认特征值（settings 属性名 → 物理默认值）
# ============================================================================
DEFAULT_FEATURE_VALUES_BY_ATTR: Dict[str, float] = {
    # ---- 总管温度 ----
    "total_chilled_inlet_temp": 7.0,
    "total_chilled_return_temp": 12.0,
    "cooling_water_main_supply_temperature": 32.0,
    "return_water_temperature_of_cooling_water_main_pipe": 28.0,
    "outdoor_temperature": 25.0,
    "wet_bulb_temperature": 20.0,
    # ---- 湿度 ----
    "outdoor_humidity": 60.0,
    # ---- 主机运行状态 ----
    "operating_status_of_host_1": 1.0,
    "operating_status_of_host_2": 1.0,
    "operating_status_of_host_3": 1.0,
    "operating_status_of_host_4": 1.0,
    "operating_status_of_host_5": 1.0,
    # ---- 冷冻泵运行状态 ----
    "operation_status_of_no_1_refrigeration_pump": 1.0,
    "operation_status_of_the_no_2_refrigeration_pump": 1.0,
    "operation_status_of_no_3_refrigeration_pump": 1.0,
    "operation_status_of_no_4_refrigeration_pump": 1.0,
    "operation_status_of_the_5th_refrigeration_pump": 1.0,
    "operation_status_of_the_6th_refrigeration_pump": 1.0,
    "operating_status_of_the_7th_refrigeration_pump": 1.0,
    # ---- 乙二醇泵运行状态 ----
    "operation_status_of_no_1_ethylene_glycol_pump": 1.0,
    "operation_status_of_no_2_ethylene_glycol_pump": 1.0,
    "operation_status_of_no_3_ethylene_glycol_pump": 1.0,
    # ---- 冷却泵运行状态 ----
    "operation_status_of_cooling_pump_no_1": 1.0,
    "operation_status_of_cooling_pump_no_2": 1.0,
    "operation_status_of_cooling_pump_no_3": 1.0,
    "operation_status_of_cooling_pump_no_4": 1.0,
    "operation_status_of_cooling_pump_no_5": 1.0,
    "operation_status_of_cooling_pump_no_6": 1.0,
    "operation_status_of_cooling_pump_no_7": 1.0,
    # ---- 冷却塔运行状态 ----
    "operation_status_of_cooling_tower_no_1": 1.0,
    "operation_status_of_cooling_tower_no_2": 1.0,
    "operation_status_of_cooling_tower_no_3": 1.0,
    "operation_status_of_cooling_tower_no_4": 1.0,
    "operation_status_of_cooling_tower_no_5": 1.0,
    "operation_status_of_cooling_tower_no_6": 1.0,
    "operation_status_of_cooling_tower_no_7": 1.0,
    "operation_status_of_cooling_tower_no_8": 1.0,
    "operation_status_of_cooling_tower_no_9": 1.0,
    "operation_status_of_cooling_tower_10": 1.0,
    "operation_status_of_cooling_tower_11": 1.0,
    "operation_status_of_cooling_tower_no_12": 1.0,
    # ---- 复合总功率 ----
    "composite_total_host_meter_1": 150.0,
    "composite_total_host_meter_2": 150.0,
    "composite_total_cooling_tower_meter": 60.0,
    "composite_total_cooling_pump_meter_1": 50.0,
    "composite_total_cooling_pump_meter_2": 50.0,
    "composite_total_chilled_pump_meter_1": 30.0,
    "composite_total_chilled_pump_meter_2": 30.0,
    "composite_total_glycol_pump_meter": 20.0,
    # ---- 频率反馈 ----
    "frequency_feedback_of_no_1_refrigeration_pump": 0.0,
    "frequency_feedback_of_no_2_refrigeration_pump": 0.0,
    "frequency_feedback_of_no_3_refrigeration_pump": 0.0,
    "frequency_feedback_of_the_4th_refrigeration_pump": 0.0,
    "frequency_feedback_of_the_5th_refrigeration_pump": 0.0,
    "frequency_feedback_of_the_6th_refrigeration_pump": 0.0,
    "frequency_feedback_of_the_7th_refrigeration_pump": 0.0,
    "frequency_feedback_of_no_1_ethylene_glycol_pump": 0.0,
    "frequency_feedback_of_no_2_ethylene_glycol_pump": 0.0,
    "frequency_feedback_of_the_3rd_ethylene_glycol_pump": 0.0,
    "frequency_feedback_of_cooling_pump_no_1": 0.0,
    "frequency_feedback_of_cooling_pump_no_2": 0.0,
    "frequency_feedback_of_cooling_pump_no_3": 0.0,
    "frequency_feedback_of_cooling_pump_no_4": 0.0,
    "frequency_feedback_of_cooling_pump_no_5": 0.0,
    "frequency_feedback_of_cooling_pump_no_6": 0.0,
    "frequency_feedback_of_cooling_pump_no_7": 0.0,
}

# ============================================================================
# 4. 派牛特征映射：模型特征列中的"虚拟特征名" → 对应设备组
# ============================================================================
DERIVED_FEATURE_GROUPS: Dict[str, str] = {
    "host_running_status": "host",
    "cooling_pump_running_status": "cooling_pump",
    "cooling_tower_running_status": "cooling_tower",
    "chilled_pump_running_status": "chilled_pump",
}

# ============================================================================
# 5. 旧属性名 → 新属性名映射（兼容旧模型中的特征名）
# ============================================================================
LEGACY_POWER_ATTR_MAP: Dict[str, str] = {
    "total_real_time_power_of_host_meter": "composite_total_host_meter",
    "total_real_time_power_of_cooling_tower_meter": "composite_total_cooling_tower_meter",
    "total_real_time_power_of_cooling_pump_meter": "composite_total_cooling_pump_meter",
}
