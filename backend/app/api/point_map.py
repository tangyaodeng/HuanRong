# backend/app/api/point_map.py
from ..config import settings

# ---------- 指标中文名映射 ----------
METRIC_CN = {
    "power": "功率",
    "frequency_feedback": "频率反馈",
    "running_status": "运行状态",
    "chilled_inlet_temp": "冷冻水出水温度",
    "chilled_return_temp": "冷冻水回水温度",
    "cooling_inlet_temp": "冷却水进水温度",
    "cooling_return_temp": "冷却水出水温度",
    "condenser_temp": "冷凝器温度",
    "evaporator_temp": "蒸发器温度",
    "evaporator_pressure": "蒸发器压力",
    "condenser_pressure": "冷凝器压力",
    "outlet_temp": "出水温度",
    "primary_inlet_temp": "一次进水温度",
    "primary_outlet_temp": "一次出水温度",
    "secondary_outlet_temp": "二次出水温度",
}

# ---------- 设备类别中文名 ----------
DEVICE_CN = {
    "HOST": "主机",
    "CHILLED_PUMP": "冷冻泵",
    "COOLING_PUMP": "冷却泵",
    "COOLING_TOWER": "冷却塔",
    "ETHYLENE_GLYCOL_PUMP": "乙二醇泵",
    "PLATE_EXCHANGER": "板换",
}

def build_point_map() -> dict:
    point_map = {}

    # ========== 1. 处理结构化设备字典，生成聚合和单设备映射 ==========
    device_configs = {
        "HOST": settings.HOST,
        "CHILLED_PUMP": settings.CHILLED_PUMP,
        "COOLING_PUMP": settings.COOLING_PUMP,
        "COOLING_TOWER": settings.COOLING_TOWER,
        "ETHYLENE_GLYCOL_PUMP": settings.ETHYLENE_GLYCOL_PUMP,
        "PLATE_EXCHANGER": settings.PLATE_EXCHANGER,
    }

    for device_key, config in device_configs.items():
        device_type_cn = DEVICE_CN.get(device_key, device_key)
        devices = config.get("devices", {})

        # 遍历每台设备中的指标
        for metric_field in METRIC_CN:
            tags_list = []
            for dev_id, dev in devices.items():
                if metric_field in dev:
                    tag = dev[metric_field]
                    if tag:
                        tags_list.append(tag)

                    # 单设备映射：如 "1号主机冷冻水出水温度"
                    single_name = f"{dev_id}号{device_type_cn}{METRIC_CN[metric_field]}"
                    if tag:
                        point_map[single_name] = [tag]

            # 聚合映射：如 "主机冷冻水出水温度"
            if tags_list:
                aggregate_name = f"{device_type_cn}{METRIC_CN[metric_field]}"
                # 去重（有些设备可能共用同一个tag，如冷却塔功率）
                unique_tags = list(dict.fromkeys(tags_list))
                point_map[aggregate_name] = unique_tags

        # 特殊处理：设备运行状态也生成映射
        # 已经在循环中包含了

    # ========== 2. 扁平变量（天气、总管等） ==========
    flat_mappings = {
        "室外温度": settings.outdoor_temperature,
        "室外湿度": settings.outdoor_humidity,
        "湿球温度": settings.wet_bulb_temperature,
        "冷冻水总管供水温度": settings.total_chilled_inlet_temp,
        "冷冻水总管回水温度": settings.total_chilled_return_temp,
        "冷冻水总管供水压力": settings.supply_pressure_of_chilled_water_main,
        "冷冻水总管回水压力": settings.return_pressure_of_chilled_water_main_pipe,
        "冷却水总管供水温度": settings.cooling_water_main_supply_temperature,
        "冷却水总管回水温度": settings.return_water_temperature_of_cooling_water_main_pipe,
        "冷冻水供回水温差": settings.temperature_difference_between_supply_and_return_of_chilled_water,
        "冷冻水供回水压差": settings.cold_water_supply_and_return_pressure_difference,
        "板换冷冻水供回水温差": settings.temperature_difference_between_supply_and_return_water_of_plate_replacement_chilled_water,
        "板换冷冻水供回水压差": settings.pressure_difference_between_the_supply_and_return_of_chilled_water_for_plate_replacement,
        "冷却水供回水温差": settings.temperature_difference_between_supply_and_return_of_cooling_water,
        "乙二醇泵回水压力": settings.return_water_pressure_of_ethylene_glycol_pump,
        "板换二次总管供水温度": settings.plate_replacement_secondary_main_water_supply_temperature,
        "板换二次总管供水压力": settings.plate_replacement_secondary_main_water_supply_pressure,
        "板换二次总管回水温度": settings.return_water_temperature_of_board_replacement_secondary_main_pipe,
        "板换二次总管回水压力": settings.plate_replacement_secondary_main_return_water_pressure,
        # ========== 用电量（小时） ==========
        "主机用电量（小时）": f"{settings.ELEC_BASE_HOST}_hours",
        "冷冻泵用电量（小时）": f"{settings.ELEC_BASE_CHILLED_PUMP}_hours",
        "乙二醇泵用电量（小时）": f"{settings.ELEC_BASE_GLYCOL_PUMP}_hours",
        "冷却泵用电量（小时）": f"{settings.ELEC_BASE_COOLING_PUMP}_hours",
        "冷却塔用电量（小时）": f"{settings.ELEC_BASE_COOLING_TOWER}_hours",

        # 全部设备总用电量（小时）—— 聚合多张表求和
        "全部设备总用电量（小时）": [
            f"{settings.ELEC_BASE_HOST}_hours",
            f"{settings.ELEC_BASE_CHILLED_PUMP}_hours",
            f"{settings.ELEC_BASE_GLYCOL_PUMP}_hours",
            f"{settings.ELEC_BASE_COOLING_PUMP}_hours",
            f"{settings.ELEC_BASE_COOLING_TOWER}_hours",
        ],

        # ========== 用电量（天） ==========
        "主机用电量（天）": f"{settings.ELEC_BASE_HOST}_day",
        "冷冻泵用电量（天）": f"{settings.ELEC_BASE_CHILLED_PUMP}_day",
        "乙二醇泵用电量（天）": f"{settings.ELEC_BASE_GLYCOL_PUMP}_day",
        "冷却泵用电量（天）": f"{settings.ELEC_BASE_COOLING_PUMP}_day",
        "冷却塔用电量（天）": f"{settings.ELEC_BASE_COOLING_TOWER}_day",
        "全部设备总用电量（天）": [
            f"{settings.ELEC_BASE_HOST}_day",
            f"{settings.ELEC_BASE_CHILLED_PUMP}_day",
            f"{settings.ELEC_BASE_GLYCOL_PUMP}_day",
            f"{settings.ELEC_BASE_COOLING_PUMP}_day",
            f"{settings.ELEC_BASE_COOLING_TOWER}_day",
        ],

        # ========== 用电量（月） ==========
        "主机用电量（月）": f"{settings.ELEC_BASE_HOST}_month",
        "冷冻泵用电量（月）": f"{settings.ELEC_BASE_CHILLED_PUMP}_month",
        "乙二醇泵用电量（月）": f"{settings.ELEC_BASE_GLYCOL_PUMP}_month",
        "冷却泵用电量（月）": f"{settings.ELEC_BASE_COOLING_PUMP}_month",
        "冷却塔用电量（月）": f"{settings.ELEC_BASE_COOLING_TOWER}_month",
        "全部设备总用电量（月）": [
            f"{settings.ELEC_BASE_HOST}_month",
            f"{settings.ELEC_BASE_CHILLED_PUMP}_month",
            f"{settings.ELEC_BASE_GLYCOL_PUMP}_month",
            f"{settings.ELEC_BASE_COOLING_PUMP}_month",
            f"{settings.ELEC_BASE_COOLING_TOWER}_month",
        ],

        # ========== 用电量（年） ==========
        "主机用电量（年）": f"{settings.ELEC_BASE_HOST}_year",
        "冷冻泵用电量（年）": f"{settings.ELEC_BASE_CHILLED_PUMP}_year",
        "乙二醇泵用电量（年）": f"{settings.ELEC_BASE_GLYCOL_PUMP}_year",
        "冷却泵用电量（年）": f"{settings.ELEC_BASE_COOLING_PUMP}_year",
        "冷却塔用电量（年）": f"{settings.ELEC_BASE_COOLING_TOWER}_year",
        "全部设备总用电量（年）": [
            f"{settings.ELEC_BASE_HOST}_year",
            f"{settings.ELEC_BASE_CHILLED_PUMP}_year",
            f"{settings.ELEC_BASE_GLYCOL_PUMP}_year",
            f"{settings.ELEC_BASE_COOLING_PUMP}_year",
            f"{settings.ELEC_BASE_COOLING_TOWER}_year",
        ],
    }

    for name, tag in flat_mappings.items():
        if tag:
            point_map[name] = [tag]

    # ========== 3. 补充冷却塔出水温度（单独处理） ==========
    # 冷却塔出水温度在 config 中是扁平变量，但没有在设备字典中
    cooling_tower_outlet_temps = {
        "CT11": settings.cooling_tower_outlet_temperature_ct11,
        "CT12": settings.cooling_tower_outlet_temperature_ct12,
        "CT13": settings.cooling_tower_outlet_temperature_ct13,
        "CT14": settings.cooling_tower_outlet_temperature_ct14,
        "CT21": settings.cooling_tower_outlet_temperature_ct21,
        "CT22": settings.cooling_tower_outlet_temperature_ct22,
        "CT23": settings.cooling_tower_outlet_temperature_ct23,
        "CT24": settings.cooling_tower_outlet_temperature_ct24,
        "CT31": settings.cooling_tower_outlet_temperature_ct31,
        "CT32": settings.cooling_tower_outlet_temperature_ct32,
        "CT33": settings.cooling_tower_outlet_temperature_ct33,
        "CT34": settings.cooling_tower_outlet_temperature_ct34,
    }
    # 单塔映射
    for ct_name, tag in cooling_tower_outlet_temps.items():
        if tag:
            point_map[f"冷却塔{ct_name}出水温度"] = [tag]

    # 聚合所有冷却塔出水温度
    all_ct_tags = [tag for tag in cooling_tower_outlet_temps.values() if tag]
    if all_ct_tags:
        point_map["冷却塔出水温度"] = list(dict.fromkeys(all_ct_tags))

    # ========== 4. 补充主机详细传感器（已在结构化中处理，但保证不会遗漏） ==========
    # 前面循环已自动生成

    return point_map