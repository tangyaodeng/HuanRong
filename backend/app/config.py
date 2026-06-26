# backend/app/config.py
from pydantic_settings import BaseSettings
from typing import Optional

# CREATE TABLE `hrdz_zlz_ai38` (
#   `UpdateDateTime` datetime DEFAULT NULL,
#   `PointValue` float DEFAULT NULL
# ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ROW_FORMAT=DYNAMIC
class Settings(BaseSettings):
    CELERY_BROKER_URL: str = "redis://:123456@192.168.5.240:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://:123456@192.168.5.240:6379/1"
    DEEPSEEK_APIKEY: str = "sk-ca2dd1ebf47c4c1991c0f7ef677e5ab0"
    #项目名
    PROGRAM_NAME: str = "HuanRong"
    # 数据库配置
    DATABASE_URL: str = "postgresql://postgres:123456@192.168.5.240:5432/HuanRong"
    # MySQL数据库配置（用于实时监控）
    MYSQL_HOST: str = "192.168.5.43"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "admin1"  # 请替换为实际的用户名
    MYSQL_PASSWORD: str = "123456"  # 请替换为实际的密码
    MYSQL_DATABASE: str = "xm_hisdata"
    MYSQL_CHARSET: str = "utf8mb4"
    # Redis 配置（用于冷冻水优化缓存）
    REDIS_HOST: str = "192.168.5.240"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = "123456"

    # ==================== 新增配置：优化模型类型 ====================
    # 1 = 单设备模型（每个设备单独模型），2 = 类型设备模型（总功率模型）
    OPTIMIZATION_MODEL_TYPE: int = 2



    # ==================== 新项目变量定义（扁平）====================

    # --- 主机运行状态 ---
    operating_status_of_host_1: str = "hrdz_zlz_di90"  # 1号主机运行状态
    operating_status_of_host_2: str = "hrdz_zlz_di97"  # 2号主机运行状态
    operating_status_of_host_3: str = "hrdz_zlz_di104"  # 3号主机运行状态
    operating_status_of_host_4: str = "hrdz_zlz_di111"  # 4号主机运行状态
    operating_status_of_host_5: str = "hrdz_zlz_di118"  # 5号主机运行状态

    # --- 冷冻泵运行状态 ---
    operation_status_of_no_1_refrigeration_pump: str = "hrdz_zlz_di125"  # 1号冷冻泵运行状态
    operation_status_of_the_no_2_refrigeration_pump: str = "hrdz_zlz_di129"  # 2号冷冻泵运行状态
    operation_status_of_no_3_refrigeration_pump: str = "hrdz_zlz_di133"  # 3号冷冻泵运行状态
    operation_status_of_no_4_refrigeration_pump: str = "hrdz_zlz_di137"  # 4号冷冻泵运行状态
    operation_status_of_the_5th_refrigeration_pump: str = "hrdz_zlz_di141"  # 5号冷冻泵运行状态
    operation_status_of_the_6th_refrigeration_pump: str = "hrdz_zlz_di145"  # 6号冷冻泵运行状态
    operating_status_of_the_7th_refrigeration_pump: str = "hrdz_zlz_di149"  # 7号冷冻泵运行状态

    # --- 乙二醇泵运行状态 ---
    operation_status_of_no_1_ethylene_glycol_pump: str = "hrdz_zlz_di153"  # 1号乙二醇泵运行状态
    operation_status_of_no_2_ethylene_glycol_pump: str = "hrdz_zlz_di157"  # 2号乙二醇泵运行状态
    operation_status_of_no_3_ethylene_glycol_pump: str = "hrdz_zlz_di161"  # 3号乙二醇泵运行状态

    # --- 冷却泵运行状态 ---
    operation_status_of_cooling_pump_no_1: str = "hrdz_zlz_di165"  # 1号冷却泵运行状态
    operation_status_of_cooling_pump_no_2: str = "hrdz_zlz_di169"  # 2号冷却泵运行状态
    operation_status_of_cooling_pump_no_3: str = "hrdz_zlz_di173"  # 3号冷却泵运行状态
    operation_status_of_cooling_pump_no_4: str = "hrdz_zlz_di177"  # 4号冷却泵运行状态
    operation_status_of_cooling_pump_no_5: str = "hrdz_zlz_di181"  # 5号冷却泵运行状态
    operation_status_of_cooling_pump_no_6: str = "hrdz_zlz_di185"  # 6号冷却泵运行状态
    operation_status_of_cooling_pump_no_7: str = "hrdz_zlz_di189"  # 7号冷却泵运行状态

    # --- 冷却塔运行状态 ---
    operation_status_of_cooling_tower_no_1: str = "hrdz_zlz_di194"  # 1号冷却塔运行状态
    operation_status_of_cooling_tower_no_2: str = "hrdz_zlz_di198"  # 2号冷却塔运行状态
    operation_status_of_cooling_tower_no_3: str = "hrdz_zlz_di202"  # 3号冷却塔运行状态
    operation_status_of_cooling_tower_no_4: str = "hrdz_zlz_di206"  # 4号冷却塔运行状态
    operation_status_of_cooling_tower_no_5: str = "hrdz_zlz_di210"  # 5号冷却塔运行状态
    operation_status_of_cooling_tower_no_6: str = "hrdz_zlz_di214"  # 6号冷却塔运行状态
    operation_status_of_cooling_tower_no_7: str = "hrdz_zlz_di218"  # 7号冷却塔运行状态
    operation_status_of_cooling_tower_no_8: str = "hrdz_zlz_di222"  # 8号冷却塔运行状态
    operation_status_of_cooling_tower_no_9: str = "hrdz_zlz_di226"  # 9号冷却塔运行状态
    operation_status_of_cooling_tower_10: str = "hrdz_zlz_di230"  # 10号冷却塔运行状态
    operation_status_of_cooling_tower_11: str = "hrdz_zlz_di234"  # 11号冷却塔运行状态
    operation_status_of_cooling_tower_no_12: str = "hrdz_zlz_di238"  # 12号冷却塔运行状态

    # --- 天气与总管传感器 ---
    outdoor_temperature: str = "hrdz_zlz_ai38"  # 室外温度
    outdoor_humidity: str = "hrdz_zlz_ai39"  # 室外湿度
    wet_bulb_temperature: str = "hrdz_zlz_ai40"  # 湿球温度
    total_chilled_inlet_temp: str = "hrdz_zlz_ai41"  # 冷冻水总管供水温度
    total_chilled_return_temp: str = "hrdz_zlz_ai42"  # 冷冻水总管回水温度
    supply_pressure_of_chilled_water_main: str = "hrdz_zlz_ai43"  # 冷冻水总管供水压力
    return_pressure_of_chilled_water_main_pipe: str = "hrdz_zlz_ai44"  # 冷冻水总管回水压力
    cooling_water_main_supply_temperature: str = "hrdz_zlz_ai45"  # 冷却水总管供水温度
    return_water_temperature_of_cooling_water_main_pipe: str = "hrdz_zlz_ai46"  # 冷却水总管回水温度

    # --- 板换总管传感器 ---
    plate_replacement_secondary_main_water_supply_temperature: str = "hrdz_zlz_ai48"  # 板换二次总管供水温度
    plate_replacement_secondary_main_water_supply_pressure: str = "hrdz_zlz_ai49"  # 板换二次总管供水压力
    return_water_temperature_of_board_replacement_secondary_main_pipe: str = "hrdz_zlz_ai50"  # 板换二次总管回水温度
    plate_replacement_secondary_main_return_water_pressure: str = "hrdz_zlz_ai51"  # 板换二次总管回水压力

    # --- 温差与压差 ---
    temperature_difference_between_supply_and_return_of_chilled_water: str = "hrdz_zlz_ai147"  # 冷冻水供回水温差
    cold_water_supply_and_return_pressure_difference: str = "hrdz_zlz_ai148"  # 冷冻水供回水压差
    temperature_difference_between_supply_and_return_water_of_plate_replacement_chilled_water: str = "hrdz_zlz_ai149"  # 板换冷冻水供回水温差
    pressure_difference_between_the_supply_and_return_of_chilled_water_for_plate_replacement: str = "hrdz_zlz_ai150"  # 板换冷冻水供回水压差
    temperature_difference_between_supply_and_return_of_cooling_water: str = "hrdz_zlz_ai151"  # 冷却水供回水温差

    # --- 主机详细传感器（1号）---
    temperature_of_chilled_water_outlet_from_host_1: str = "hrdz_zlz_ai223"  # 1号主机冷冻水出水温度
    temperature_of_chilled_water_return_for_unit_1: str = "hrdz_zlz_ai224"  # 1号主机冷冻水回水温度
    cooling_water_outlet_temperature_of_host_1: str = "hrdz_zlz_ai225"  # 1号主机冷却水出水温度
    cooling_water_return_temperature_of_host_1: str = "hrdz_zlz_ai226"  # 1号主机冷却水回水温度
    temperature_of_the_condenser_of_host_1: str = "hrdz_zlz_ai227"  # 1号主机冷凝器温度
    temperature_of_evaporator_of_no_1_host: str = "hrdz_zlz_ai228"  # 1号主机蒸发器温度
    pressure_of_the_condenser_of_the_no_1_host: str = "hrdz_zlz_ai229"  # 1号主机冷凝器压力
    evaporator_pressure_of_no_1_main_engine: str = "hrdz_zlz_ai230"  # 1号主机蒸发器压力

    # --- 主机详细传感器（2号）---
    temperature_of_chilled_water_outlet_from_host_2: str = "hrdz_zlz_ai248"  # 2号主机冷冻水出水温度
    temperature_of_chilled_water_return_for_unit_2: str = "hrdz_zlz_ai249"  # 2号主机冷冻水回水温度
    cooling_water_outlet_temperature_of_host_2: str = "hrdz_zlz_ai250"  # 2号主机冷却水出水温度
    cooling_water_return_temperature_of_host_2: str = "hrdz_zlz_ai251"  # 2号主机冷却水回水温度
    temperature_of_the_condenser_of_the_2nd_host: str = "hrdz_zlz_ai252"  # 2号主机冷凝器温度
    temperature_of_evaporator_of_host_2: str = "hrdz_zlz_ai253"  # 2号主机蒸发器温度
    pressure_of_the_condenser_of_the_2nd_host: str = "hrdz_zlz_ai254"  # 2号主机冷凝器压力
    evaporator_pressure_of_unit_2: str = "hrdz_zlz_ai255"  # 2号主机蒸发器压力

    # --- 主机详细传感器（3号）---
    temperature_of_chilled_water_outlet_from_host_3: str = "hrdz_zlz_ai273"  # 3号主机冷冻水出水温度
    temperature_of_chilled_water_return_for_unit_3: str = "hrdz_zlz_ai274"  # 3号主机冷冻水回水温度
    cooling_water_outlet_temperature_of_host_3: str = "hrdz_zlz_ai275"  # 3号主机冷却水出水温度
    cooling_water_return_temperature_of_host_3: str = "hrdz_zlz_ai276"  # 3号主机冷却水回水温度
    temperature_of_the_condenser_of_the_3rd_host: str = "hrdz_zlz_ai277"  # 3号主机冷凝器温度
    temperature_of_evaporator_of_host_3: str = "hrdz_zlz_ai278"  # 3号主机蒸发器温度
    pressure_of_the_condenser_of_the_3rd_host: str = "hrdz_zlz_ai279"  # 3号主机冷凝器压力
    evaporator_pressure_of_unit_3: str = "hrdz_zlz_ai280"  # 3号主机蒸发器压力

    # --- 主机详细传感器（4号）---
    temperature_of_chilled_water_outlet_from_host_4: str = "hrdz_zlz_ai298"  # 4号主机冷冻水出水温度
    temperature_of_chilled_water_return_for_unit_4: str = "hrdz_zlz_ai299"  # 4号主机冷冻水回水温度
    cooling_water_outlet_temperature_of_host_4: str = "hrdz_zlz_ai300"  # 4号主机冷却水出水温度
    cooling_water_return_temperature_of_host_4: str = "hrdz_zlz_ai301"  # 4号主机冷却水回水温度
    temperature_of_the_condenser_of_the_4th_host: str = "hrdz_zlz_ai302"  # 4号主机冷凝器温度
    temperature_of_evaporator_on_host_4: str = "hrdz_zlz_ai303"  # 4号主机蒸发器温度
    pressure_of_the_condenser_of_the_4th_host: str = "hrdz_zlz_ai304"  # 4号主机冷凝器压力
    evaporator_pressure_of_host_4: str = "hrdz_zlz_ai305"  # 4号主机蒸发器压力

    # --- 主机详细传感器（5号）---
    temperature_of_chilled_water_outlet_from_host_5: str = "hrdz_zlz_ai323"  # 5号主机冷冻水出水温度
    temperature_of_chilled_water_return_for_unit_5: str = "hrdz_zlz_ai324"  # 5号主机冷冻水回水温度
    cooling_water_outlet_temperature_of_host_5: str = "hrdz_zlz_ai325"  # 5号主机冷却水出水温度
    cooling_water_return_temperature_of_host_5: str = "hrdz_zlz_ai326"  # 5号主机冷却水回水温度
    temperature_of_the_condenser_of_the_5th_host: str = "hrdz_zlz_ai327"  # 5号主机冷凝器温度
    evaporator_temperature_of_host_5: str = "hrdz_zlz_ai328"  # 5号主机蒸发器温度
    pressure_of_the_condenser_of_the_5th_host: str = "hrdz_zlz_ai329"  # 5号主机冷凝器压力
    evaporator_pressure_of_unit_5: str = "hrdz_zlz_ai330"  # 5号主机蒸发器压力

    # --- 主机电表实时功率 ---
    real_time_power_of_host_1_s_electricity_meter: str = "hrdz_zlz_ai354"  # 1号主机电表实时功率
    real_time_power_of_the_second_host_s_electricity_meter: str = "hrdz_zlz_ai362"  # 2号主机电表实时功率
    real_time_power_of_the_meter_on_the_3rd_host: str = "hrdz_zlz_ai370"  # 3号主机电表实时功率
    real_time_power_of_the_4th_host_electricity_meter: str = "hrdz_zlz_ai378"  # 4号主机电表实时功率
    real_time_power_of_the_5th_host_s_electricity_meter: str = "hrdz_zlz_ai386"  # 5号主机电表实时功率

    # --- 冷冻泵电表实时功率 ---
    real_time_power_of_the_electric_meter_for_the_no_1_refrigeration_pump: str = "hrdz_zlz_ai394"  # 1号冷冻泵电表实时功率
    real_time_power_of_the_electric_meter_for_the_2nd_refrigeration_pump: str = "hrdz_zlz_ai402"  # 2号冷冻泵电表实时功率
    real_time_power_of_the_electric_meter_for_the_3rd_refrigeration_pump: str = "hrdz_zlz_ai410"  # 3号冷冻泵电表实时功率
    real_time_power_of_the_electric_meter_for_the_4th_refrigeration_pump: str = "hrdz_zlz_ai418"  # 4号冷冻泵电表实时功率
    real_time_power_of_the_electric_meter_for_the_5th_refrigeration_pump: str = "hrdz_zlz_ai426"  # 5号冷冻泵电表实时功率
    real_time_power_of_the_electric_meter_for_the_6th_refrigeration_pump: str = "hrdz_zlz_ai434"  # 6号冷冻泵电表实时功率
    real_time_power_of_the_electric_meter_for_the_7th_refrigeration_pump: str = "hrdz_zlz_ai442"  # 7号冷冻泵电表实时功率

    # --- 乙二醇泵电表实时功率 ---
    real_time_power_of_meter_for_no_1_ethylene_glycol_pump: str = "hrdz_zlz_ai450"  # 1号乙二醇泵电表实时功率
    real_time_power_of_electric_meter_for_no_2_ethylene_glycol_pump: str = "hrdz_zlz_ai458"  # 2号乙二醇泵电表实时功率
    real_time_power_of_the_electric_meter_for_the_3rd_ethylene_glycol_pump: str = "hrdz_zlz_ai466"  # 3号乙二醇泵电表实时功率

    # --- 冷却泵电表实时功率 ---
    real_time_power_of_cooling_pump_no_1_electric_meter: str = "hrdz_zlz_ai474"  # 1号冷却泵电表实时功率
    real_time_power_of_the_electric_meter_for_cooling_pump_no_2: str = "hrdz_zlz_ai482"  # 2号冷却泵电表实时功率
    real_time_power_of_the_electric_meter_for_cooling_pump_no_3: str = "hrdz_zlz_ai490"  # 3号冷却泵电表实时功率
    real_time_power_of_the_electric_meter_for_cooling_pump_no_4: str = "hrdz_zlz_ai498"  # 4号冷却泵电表实时功率
    real_time_power_of_the_electric_meter_for_cooling_pump_no_5: str = "hrdz_zlz_ai506"  # 5号冷却泵电表实时功率
    real_time_power_of_meter_for_cooling_pump_no_6: str = "hrdz_zlz_ai514"  # 6号冷却泵电表实时功率
    real_time_power_of_the_electric_meter_for_cooling_pump_no_7: str = "hrdz_zlz_ai522"  # 7号冷却泵电表实时功率

    # --- 冷却塔配电柜电表实时功率 ---
    real_time_power_of_electric_meter_in_cooling_tower_no_1_distribution_cabinet: str = "hrdz_zlz_ai704"  # 冷却塔1号配电柜电表实时功率
    real_time_power_of_electric_meter_in_cooling_tower_no_2_distribution_cabinet: str = "hrdz_zlz_ai712"  # 冷却塔2号配电柜电表实时功率
    real_time_power_of_electric_meter_in_cooling_tower_no_3_distribution_cabinet: str = "hrdz_zlz_ai720"  # 冷却塔3号配电柜电表实时功率
    real_time_power_of_electric_meter_in_cooling_tower_no_4_distribution_cabinet: str = "hrdz_zlz_ai728"  # 冷却塔4号配电柜电表实时功率

    # --- 冷却塔出水温度 ---
    cooling_tower_outlet_temperature_ct11: str = "hrdz_zlz_ai52"  # 冷却塔出水温度CT11
    cooling_tower_outlet_temperature_ct12: str = "hrdz_zlz_ai53"  # 冷却塔出水温度CT12
    cooling_tower_outlet_temperature_ct13: str = "hrdz_zlz_ai54"  # 冷却塔出水温度CT13
    cooling_tower_outlet_temperature_ct14: str = "hrdz_zlz_ai55"  # 冷却塔出水温度CT14
    cooling_tower_outlet_temperature_ct21: str = "hrdz_zlz_ai56"  # 冷却塔出水温度CT21
    cooling_tower_outlet_temperature_ct22: str = "hrdz_zlz_ai57"  # 冷却塔出水温度CT22
    cooling_tower_outlet_temperature_ct23: str = "hrdz_zlz_ai58"  # 冷却塔出水温度CT23
    cooling_tower_outlet_temperature_ct24: str = "hrdz_zlz_ai59"  # 冷却塔出水温度CT24
    cooling_tower_outlet_temperature_ct31: str = "hrdz_zlz_ai60"  # 冷却塔出水温度CT31
    cooling_tower_outlet_temperature_ct32: str = "hrdz_zlz_ai61"  # 冷却塔出水温度CT32
    cooling_tower_outlet_temperature_ct33: str = "hrdz_zlz_ai62"  # 冷却塔出水温度CT33
    cooling_tower_outlet_temperature_ct34: str = "hrdz_zlz_ai63"  # 冷却塔出水温度CT34

    # --- 频率反馈（冷冻泵）---
    frequency_feedback_of_no_1_refrigeration_pump: str = "hrdz_zlz_ai169"  # 1号冷冻泵频率反馈
    frequency_feedback_of_no_2_refrigeration_pump: str = "hrdz_zlz_ai170"  # 2号冷冻泵频率反馈
    frequency_feedback_of_no_3_refrigeration_pump: str = "hrdz_zlz_ai171"  # 3号冷冻泵频率反馈
    frequency_feedback_of_the_4th_refrigeration_pump: str = "hrdz_zlz_ai172"  # 4号冷冻泵频率反馈
    frequency_feedback_of_the_5th_refrigeration_pump: str = "hrdz_zlz_ai173"  # 5号冷冻泵频率反馈
    frequency_feedback_of_the_6th_refrigeration_pump: str = "hrdz_zlz_ai174"  # 6号冷冻泵频率反馈
    frequency_feedback_of_the_7th_refrigeration_pump: str = "hrdz_zlz_ai175"  # 7号冷冻泵频率反馈

    # --- 频率反馈（乙二醇泵）---
    frequency_feedback_of_no_1_ethylene_glycol_pump: str = "hrdz_zlz_ai176"  # 1号乙二醇泵频率反馈
    frequency_feedback_of_no_2_ethylene_glycol_pump: str = "hrdz_zlz_ai177"  # 2号乙二醇泵频率反馈
    frequency_feedback_of_the_3rd_ethylene_glycol_pump: str = "hrdz_zlz_ai178"  # 3号乙二醇泵频率反馈

    # --- 频率反馈（冷却泵）---
    frequency_feedback_of_cooling_pump_no_1: str = "hrdz_zlz_ai179"  # 1号冷却泵频率反馈
    frequency_feedback_of_cooling_pump_no_2: str = "hrdz_zlz_ai180"  # 2号冷却泵频率反馈
    frequency_feedback_of_cooling_pump_no_3: str = "hrdz_zlz_ai181"  # 3号冷却泵频率反馈
    frequency_feedback_of_cooling_pump_no_4: str = "hrdz_zlz_ai182"  # 4号冷却泵频率反馈
    frequency_feedback_of_cooling_pump_no_5: str = "hrdz_zlz_ai183"  # 5号冷却泵频率反馈
    frequency_feedback_of_cooling_pump_no_6: str = "hrdz_zlz_ai184"  # 6号冷却泵频率反馈
    frequency_feedback_of_cooling_pump_no_7: str = "hrdz_zlz_ai185"  # 7号冷却泵频率反馈

    # --- 板换相关传感器 ---
    replace_the_inlet_water_temperature_of_board_1_once: str = "hrdz_zlz_ai75"  # 1号板换一次进水温度
    replace_the_outlet_temperature_of_board_1_once: str = "hrdz_zlz_ai76"  # 1号板换一次出水温度
    replace_the_inlet_water_temperature_of_board_2_once: str = "hrdz_zlz_ai77"  # 2号板换一次进水温度
    replace_the_outlet_temperature_of_board_2_once: str = "hrdz_zlz_ai78"  # 2号板换一次出水温度
    the_temperature_of_the_water_outlet_after_the_second_replacement_of_board_1: str = "hrdz_zlz_ai79"  # 1号板换二次出水温度
    temperature_of_secondary_water_outlet_for_board_2_replacement: str = "hrdz_zlz_ai80"  # 2号板换二次出水温度

    # --- 冷量相关 ---
    cooling_capacity_of_the_cooling_side_of_host_1: str = "hrdz_zlz_ai754"  # 1号主机冷却侧冷量
    cooling_capacity_of_the_cooling_side_of_host_2: str = "hrdz_zlz_ai755"  # 2号主机冷却侧冷量
    cooling_capacity_of_the_cooling_side_of_host_3: str = "hrdz_zlz_ai756"  # 3号主机冷却侧冷量
    cooling_capacity_of_the_cooling_side_of_host_4: str = "hrdz_zlz_ai757"  # 4号主机冷却侧冷量
    cooling_capacity_of_the_cooling_side_of_host_5: str = "hrdz_zlz_ai758"  # 5号主机冷却侧冷量
    cooling_capacity_of_plate_heat_exchanger_no_1: str = "hrdz_zlz_ai759"  # 1号板换冷量
    cooling_capacity_of_plate_heat_exchanger_no_2: str = "hrdz_zlz_ai760"  # 2号板换冷量
    base_load_cooling_side_main_pipe_cooling_capacity: str = "hrdz_zlz_ai761"  # 基载冷冻侧总管冷量

    # --- 其他 ---
    return_water_pressure_of_ethylene_glycol_pump: str = "hrdz_zlz_ai74"  # 乙二醇泵回水压力

    # ==================== 复合特征点位（由 composite_feature 计算生成）====================
    # --- 主机总功率（分组）---
    composite_total_host_meter_1: str = "composite_total_host_meter_1"  # 1~3号主机总功率
    composite_total_host_meter_2: str = "composite_total_host_meter_2"  # 4~5号主机总功率

    # --- 系统散热量（分组）---
    composite_system_heat_dissipation_1: str = "composite_system_heat_dissipation_1"  # 1~3号主机冷却侧冷量之和
    composite_system_heat_dissipation_2: str = "composite_system_heat_dissipation_2"  # 4~5号主机冷却侧冷量之和

    # --- 冷却塔总功率 ---
    composite_total_cooling_tower_meter: str = "composite_total_cooling_tower_meter"  # 1~4号配电柜功率之和（12个塔）

    # --- 冷却泵总功率（分组）---
    composite_total_cooling_pump_meter_1: str = "composite_total_cooling_pump_meter_1"  # 1~4号冷却泵总功率
    composite_total_cooling_pump_meter_2: str = "composite_total_cooling_pump_meter_2"  # 5~7号冷却泵总功率

    # --- 冷冻泵总功率（分组）---
    composite_total_chilled_pump_meter_1: str = "composite_total_chilled_pump_meter_1"  # 1~4号冷冻泵总功率
    composite_total_chilled_pump_meter_2: str = "composite_total_chilled_pump_meter_2"  # 5~7号冷冻泵总功率

    # --- 乙二醇泵总功率 ---
    composite_total_glycol_pump_meter: str = "composite_total_glycol_pump_meter"  # 1~3号乙二醇泵总功率

    # --- 小时冷量相关（如需使用累计差分量）---
    composite_hourly_cooling_energy_base: str = "composite_hourly_cooling_energy_base"  # 基载冷冻侧每小时冷量
    composite_hourly_cooling_energy_plate_1: str = "composite_hourly_cooling_energy_plate_1"  # 1号板换每小时冷量
    composite_hourly_cooling_energy_plate_2: str = "composite_hourly_cooling_energy_plate_2"  # 2号板换每小时冷量
    composite_hourly_cooling_energy_total: str = "composite_hourly_cooling_energy_total"  # 总每小时用冷量

    # ==================== 预测点位（由 模型预测 计算生成）==================== pre-
    pre_composite_total_host_meter_1: str = "pre-composite_total_host_meter_1"  # 1~3号主机总功率
    pre_composite_total_host_meter_2: str = "pre-composite_total_host_meter_2"  # 4~5号主机总功率
    pre_composite_total_cooling_tower_meter: str = "pre-composite_total_cooling_tower_meter"  # 1~4号配电柜功率之和（12个塔）
    pre_composite_total_cooling_pump_meter_1: str = "pre-composite_total_cooling_pump_meter_1"  # 1~4号冷却泵总功率
    pre_composite_total_cooling_pump_meter_2: str = "pre-composite_total_cooling_pump_meter_2"  # 5~7号冷却泵总功率
    pre_composite_total_chilled_pump_meter_1: str = "pre-composite_total_chilled_pump_meter_1"  # 1~4号冷冻泵总功率
    pre_composite_total_chilled_pump_meter_2: str = "pre-composite_total_chilled_pump_meter_2"  # 5~7号冷冻泵总功率
    pre_composite_total_glycol_pump_meter: str = "pre-composite_total_glycol_pump_meter"  # 1~3号乙二醇泵总功率
    pre_multistep_composite_hourly_cooling_energy_total: str = "pre-multistep_composite_hourly_cooling_energy_total"  # 负荷预测24

    # ==================== 监控页面类别配置 ====================
    MONITORING_CATEGORIES: dict = {
        "host": {
            "title": "主机总功率预测",
            "y_axis_name": "kW",
            "pred_tables": [
                # 待填入预测表名，例如：
                "pre-composite_total_host_meter_1",
                "pre-composite_total_host_meter_2",
            ],
            "actual_tables": [
                # 待填入真实表名，例如：
                "composite_total_host_meter_1",
                "composite_total_host_meter_2",
            ]
        },
        "cooling_tower": {
            "title": "冷却塔总功率预测",
            "y_axis_name": "kW",
            "pred_tables": [
                "pre-composite_total_cooling_tower_meter",
            ],
            "actual_tables": [
                "composite_total_cooling_tower_meter",
            ]
        },
        "cooling_pump": {
            "title": "冷却泵总功率预测",
            "y_axis_name": "kW",
            "pred_tables": [
                "pre-composite_total_cooling_pump_meter_1",
                "pre-composite_total_cooling_pump_meter_2",
            ],
            "actual_tables": [
                "composite_total_cooling_pump_meter_1",
                "composite_total_cooling_pump_meter_2",
            ]
        },
        "chilled_pump": {
            "title": "冷冻泵总功率预测",
            "y_axis_name": "kW",
            "pred_tables": [
                "pre-composite_total_chilled_pump_meter_1",
                "pre-composite_total_chilled_pump_meter_2",
                "pre-composite_total_glycol_pump_meter",
            ],
            "actual_tables": [
                "composite_total_chilled_pump_meter_1",
                "composite_total_chilled_pump_meter_2",
                "composite_total_glycol_pump_meter",
            ]
        },
    }
    # ==================== 监控配置结束 ====================
    # ==================== 结构化配置（供优化器使用）====================

    # 主机相关
    HOST: dict = {
        "devices": {
            1: {
                "running_status": operating_status_of_host_1,  # 1号主机运行状态
                "evaporator_pressure": evaporator_pressure_of_no_1_main_engine,  # 1号主机蒸发器压力
                "condenser_pressure": pressure_of_the_condenser_of_the_no_1_host,  # 1号主机冷凝器压力
                "chilled_inlet_temp": temperature_of_chilled_water_outlet_from_host_1,  # 1号主机冷冻水供水温度（出主机）
                "chilled_return_temp": temperature_of_chilled_water_return_for_unit_1,  # 1号主机冷冻水回水温度（进主机）
                "cooling_inlet_temp": cooling_water_return_temperature_of_host_1,  # 1号主机冷却水供水温度（进主机）
                "cooling_return_temp": cooling_water_outlet_temperature_of_host_1,  # 1号主机冷却水回水温度（出主机）
                "power": real_time_power_of_host_1_s_electricity_meter,  # 1号主机电表实时功率
                "condenser_temp": temperature_of_the_condenser_of_host_1,  # 1号主机冷凝器温度
                "evaporator_temp": temperature_of_evaporator_of_no_1_host,  # 1号主机蒸发器温度
            },
            2: {
                "running_status": operating_status_of_host_2,  # 2号主机运行状态
                "evaporator_pressure": evaporator_pressure_of_unit_2,  # 2号主机蒸发器压力
                "condenser_pressure": pressure_of_the_condenser_of_the_2nd_host,  # 2号主机冷凝器压力
                "chilled_inlet_temp": temperature_of_chilled_water_outlet_from_host_2,  # 2号主机冷冻水供水温度
                "chilled_return_temp": temperature_of_chilled_water_return_for_unit_2,  # 2号主机冷冻水回水温度
                "cooling_inlet_temp": cooling_water_return_temperature_of_host_2,  # 2号主机冷却水供水温度
                "cooling_return_temp": cooling_water_outlet_temperature_of_host_2,  # 2号主机冷却水回水温度
                "power": real_time_power_of_the_second_host_s_electricity_meter,  # 2号主机电表实时功率
                "condenser_temp": temperature_of_the_condenser_of_the_2nd_host,  # 2号主机冷凝器温度
                "evaporator_temp": temperature_of_evaporator_of_host_2,  # 2号主机蒸发器温度
            },
            3: {
                "running_status": operating_status_of_host_3,  # 3号主机运行状态
                "evaporator_pressure": evaporator_pressure_of_unit_3,  # 3号主机蒸发器压力
                "condenser_pressure": pressure_of_the_condenser_of_the_3rd_host,  # 3号主机冷凝器压力
                "chilled_inlet_temp": temperature_of_chilled_water_outlet_from_host_3,  # 3号主机冷冻水供水温度
                "chilled_return_temp": temperature_of_chilled_water_return_for_unit_3,  # 3号主机冷冻水回水温度
                "cooling_inlet_temp": cooling_water_return_temperature_of_host_3,  # 3号主机冷却水供水温度
                "cooling_return_temp": cooling_water_outlet_temperature_of_host_3,  # 3号主机冷却水回水温度
                "power": real_time_power_of_the_meter_on_the_3rd_host,  # 3号主机电表实时功率
                "condenser_temp": temperature_of_the_condenser_of_the_3rd_host,  # 3号主机冷凝器温度
                "evaporator_temp": temperature_of_evaporator_of_host_3,  # 3号主机蒸发器温度
            },
            4: {
                "running_status": operating_status_of_host_4,  # 4号主机运行状态
                "evaporator_pressure": evaporator_pressure_of_host_4,  # 4号主机蒸发器压力
                "condenser_pressure": pressure_of_the_condenser_of_the_4th_host,  # 4号主机冷凝器压力
                "chilled_inlet_temp": temperature_of_chilled_water_outlet_from_host_4,  # 4号主机冷冻水供水温度
                "chilled_return_temp": temperature_of_chilled_water_return_for_unit_4,  # 4号主机冷冻水回水温度
                "cooling_inlet_temp": cooling_water_return_temperature_of_host_4,  # 4号主机冷却水供水温度
                "cooling_return_temp": cooling_water_outlet_temperature_of_host_4,  # 4号主机冷却水回水温度
                "power": real_time_power_of_the_4th_host_electricity_meter,  # 4号主机电表实时功率
                "condenser_temp": temperature_of_the_condenser_of_the_4th_host,  # 4号主机冷凝器温度
                "evaporator_temp": temperature_of_evaporator_on_host_4,  # 4号主机蒸发器温度
            },
            5: {
                "running_status": operating_status_of_host_5,  # 5号主机运行状态
                "evaporator_pressure": evaporator_pressure_of_unit_5,  # 5号主机蒸发器压力
                "condenser_pressure": pressure_of_the_condenser_of_the_5th_host,  # 5号主机冷凝器压力
                "chilled_inlet_temp": temperature_of_chilled_water_outlet_from_host_5,  # 5号主机冷冻水供水温度
                "chilled_return_temp": temperature_of_chilled_water_return_for_unit_5,  # 5号主机冷冻水回水温度
                "cooling_inlet_temp": cooling_water_return_temperature_of_host_5,  # 5号主机冷却水供水温度
                "cooling_return_temp": cooling_water_outlet_temperature_of_host_5,  # 5号主机冷却水回水温度
                "power": real_time_power_of_the_5th_host_s_electricity_meter,  # 5号主机电表实时功率
                "condenser_temp": temperature_of_the_condenser_of_the_5th_host,  # 5号主机冷凝器温度
                "evaporator_temp": evaporator_temperature_of_host_5,  # 5号主机蒸发器温度
            },
        },
        "total": {
            "chilled_supply_temp": total_chilled_inlet_temp,  # 冷冻水总管供水温度
            "chilled_return_temp": total_chilled_return_temp,  # 冷冻水总管回水温度
            "chilled_supply_pressure": supply_pressure_of_chilled_water_main,  # 冷冻水总管供水压力
            "chilled_return_pressure": return_pressure_of_chilled_water_main_pipe,  # 冷冻水总管回水压力
            "cooling_supply_temp": cooling_water_main_supply_temperature,  # 冷却水总管供水温度
            "cooling_return_temp": return_water_temperature_of_cooling_water_main_pipe,  # 冷却水总管回水温度
            "chilled_temp_diff": temperature_difference_between_supply_and_return_of_chilled_water,  # 冷冻水供回水温差
            "chilled_pressure_diff": cold_water_supply_and_return_pressure_difference,  # 冷冻水供回水压差
            "cooling_temp_diff": temperature_difference_between_supply_and_return_of_cooling_water,  # 冷却水供回水温差
        }
    }

    # 冷却塔相关
    COOLING_TOWER: dict = {
        "devices": {
            1: {
                "running_status": operation_status_of_cooling_tower_no_1,  # 1号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_1_distribution_cabinet,  # 冷却塔1号配电柜电表实时功率
                "outlet_temp": cooling_tower_outlet_temperature_ct11,  # 冷却塔出水温度CT11
            },
            2: {
                "running_status": operation_status_of_cooling_tower_no_2,  # 2号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_1_distribution_cabinet,  # 使用1号配电柜功率
                "outlet_temp": cooling_tower_outlet_temperature_ct12,  # 冷却塔出水温度CT12
            },
            3: {
                "running_status": operation_status_of_cooling_tower_no_3,  # 3号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_1_distribution_cabinet,  # 使用1号配电柜功率
                "outlet_temp": cooling_tower_outlet_temperature_ct13,  # 冷却塔出水温度CT13
            },
            4: {
                "running_status": operation_status_of_cooling_tower_no_4,  # 4号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_2_distribution_cabinet,  # 冷却塔2号配电柜电表实时功率
                "outlet_temp": cooling_tower_outlet_temperature_ct14,  # 冷却塔出水温度CT14
            },
            5: {
                "running_status": operation_status_of_cooling_tower_no_5,  # 5号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_2_distribution_cabinet,  # 使用2号配电柜功率
                "outlet_temp": cooling_tower_outlet_temperature_ct21,  # 冷却塔出水温度CT21
            },
            6: {
                "running_status": operation_status_of_cooling_tower_no_6,  # 6号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_2_distribution_cabinet,  # 使用2号配电柜功率
                "outlet_temp": cooling_tower_outlet_temperature_ct22,  # 冷却塔出水温度CT22
            },
            7: {
                "running_status": operation_status_of_cooling_tower_no_7,  # 7号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_3_distribution_cabinet,  # 冷却塔3号配电柜电表实时功率
                "outlet_temp": cooling_tower_outlet_temperature_ct23,  # 冷却塔出水温度CT23
            },
            8: {
                "running_status": operation_status_of_cooling_tower_no_8,  # 8号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_3_distribution_cabinet,  # 使用3号配电柜功率
                "outlet_temp": cooling_tower_outlet_temperature_ct24,  # 冷却塔出水温度CT24
            },
            9: {
                "running_status": operation_status_of_cooling_tower_no_9,  # 9号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_3_distribution_cabinet,  # 使用3号配电柜功率
                "outlet_temp": cooling_tower_outlet_temperature_ct31,  # 冷却塔出水温度CT31
            },
            10: {
                "running_status": operation_status_of_cooling_tower_10,  # 10号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_4_distribution_cabinet,  # 冷却塔4号配电柜电表实时功率
                "outlet_temp": cooling_tower_outlet_temperature_ct32,  # 冷却塔出水温度CT32
            },
            11: {
                "running_status": operation_status_of_cooling_tower_11,  # 11号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_4_distribution_cabinet,  # 使用4号配电柜功率
                "outlet_temp": cooling_tower_outlet_temperature_ct33,  # 冷却塔出水温度CT33
            },
            12: {
                "running_status": operation_status_of_cooling_tower_no_12,  # 12号冷却塔运行状态
                "power": real_time_power_of_electric_meter_in_cooling_tower_no_4_distribution_cabinet,  # 使用4号配电柜功率
                "outlet_temp": cooling_tower_outlet_temperature_ct34,  # 冷却塔出水温度CT34
            },
        },
        "total": {
            # 暂无冷却塔总功率复合点，可置空或后续补充
        }
    }

    # 冷却泵相关
    COOLING_PUMP: dict = {
        "devices": {
            1: {
                "running_status": operation_status_of_cooling_pump_no_1,  # 1号冷却泵运行状态
                "power": real_time_power_of_cooling_pump_no_1_electric_meter,  # 1号冷却泵电表实时功率
                "frequency_feedback": frequency_feedback_of_cooling_pump_no_1,  # 1号冷却泵频率反馈
            },
            2: {
                "running_status": operation_status_of_cooling_pump_no_2,  # 2号冷却泵运行状态
                "power": real_time_power_of_the_electric_meter_for_cooling_pump_no_2,  # 2号冷却泵电表实时功率
                "frequency_feedback": frequency_feedback_of_cooling_pump_no_2,  # 2号冷却泵频率反馈
            },
            3: {
                "running_status": operation_status_of_cooling_pump_no_3,  # 3号冷却泵运行状态
                "power": real_time_power_of_the_electric_meter_for_cooling_pump_no_3,  # 3号冷却泵电表实时功率
                "frequency_feedback": frequency_feedback_of_cooling_pump_no_3,  # 3号冷却泵频率反馈
            },
            4: {
                "running_status": operation_status_of_cooling_pump_no_4,  # 4号冷却泵运行状态
                "power": real_time_power_of_the_electric_meter_for_cooling_pump_no_4,  # 4号冷却泵电表实时功率
                "frequency_feedback": frequency_feedback_of_cooling_pump_no_4,  # 4号冷却泵频率反馈
            },
            5: {
                "running_status": operation_status_of_cooling_pump_no_5,  # 5号冷却泵运行状态
                "power": real_time_power_of_the_electric_meter_for_cooling_pump_no_5,  # 5号冷却泵电表实时功率
                "frequency_feedback": frequency_feedback_of_cooling_pump_no_5,  # 5号冷却泵频率反馈
            },
            6: {
                "running_status": operation_status_of_cooling_pump_no_6,  # 6号冷却泵运行状态
                "power": real_time_power_of_meter_for_cooling_pump_no_6,  # 6号冷却泵电表实时功率
                "frequency_feedback": frequency_feedback_of_cooling_pump_no_6,  # 6号冷却泵频率反馈
            },
            7: {
                "running_status": operation_status_of_cooling_pump_no_7,  # 7号冷却泵运行状态
                "power": real_time_power_of_the_electric_meter_for_cooling_pump_no_7,  # 7号冷却泵电表实时功率
                "frequency_feedback": frequency_feedback_of_cooling_pump_no_7,  # 7号冷却泵频率反馈
            },
        },
        "total": {
            # 暂无冷却泵总功率复合点
        }
    }

    # 冷冻泵相关
    CHILLED_PUMP: dict = {
        "devices": {
            1: {
                "running_status": operation_status_of_no_1_refrigeration_pump,  # 1号冷冻泵运行状态
                "power": real_time_power_of_the_electric_meter_for_the_no_1_refrigeration_pump,  # 1号冷冻泵电表实时功率
                "frequency_feedback": frequency_feedback_of_no_1_refrigeration_pump,  # 1号冷冻泵频率反馈
            },
            2: {
                "running_status": operation_status_of_the_no_2_refrigeration_pump,  # 2号冷冻泵运行状态
                "power": real_time_power_of_the_electric_meter_for_the_2nd_refrigeration_pump,  # 2号冷冻泵电表实时功率
                "frequency_feedback": frequency_feedback_of_no_2_refrigeration_pump,  # 2号冷冻泵频率反馈
            },
            3: {
                "running_status": operation_status_of_no_3_refrigeration_pump,  # 3号冷冻泵运行状态
                "power": real_time_power_of_the_electric_meter_for_the_3rd_refrigeration_pump,  # 3号冷冻泵电表实时功率
                "frequency_feedback": frequency_feedback_of_no_3_refrigeration_pump,  # 3号冷冻泵频率反馈
            },
            4: {
                "running_status": operation_status_of_no_4_refrigeration_pump,  # 4号冷冻泵运行状态
                "power": real_time_power_of_the_electric_meter_for_the_4th_refrigeration_pump,  # 4号冷冻泵电表实时功率
                "frequency_feedback": frequency_feedback_of_the_4th_refrigeration_pump,  # 4号冷冻泵频率反馈
            },
            5: {
                "running_status": operation_status_of_the_5th_refrigeration_pump,  # 5号冷冻泵运行状态
                "power": real_time_power_of_the_electric_meter_for_the_5th_refrigeration_pump,  # 5号冷冻泵电表实时功率
                "frequency_feedback": frequency_feedback_of_the_5th_refrigeration_pump,  # 5号冷冻泵频率反馈
            },
            6: {
                "running_status": operation_status_of_the_6th_refrigeration_pump,  # 6号冷冻泵运行状态
                "power": real_time_power_of_the_electric_meter_for_the_6th_refrigeration_pump,  # 6号冷冻泵电表实时功率
                "frequency_feedback": frequency_feedback_of_the_6th_refrigeration_pump,  # 6号冷冻泵频率反馈
            },
            7: {
                "running_status": operating_status_of_the_7th_refrigeration_pump,  # 7号冷冻泵运行状态
                "power": real_time_power_of_the_electric_meter_for_the_7th_refrigeration_pump,  # 7号冷冻泵电表实时功率
                "frequency_feedback": frequency_feedback_of_the_7th_refrigeration_pump,  # 7号冷冻泵频率反馈
            },
        },
        "total": {
            # 暂无冷冻泵总功率复合点
        }
    }

    # 乙二醇泵相关
    ETHYLENE_GLYCOL_PUMP: dict = {
        "devices": {
            1: {
                "running_status": operation_status_of_no_1_ethylene_glycol_pump,  # 1号乙二醇泵运行状态
                "power": real_time_power_of_meter_for_no_1_ethylene_glycol_pump,  # 1号乙二醇泵电表实时功率
                "frequency_feedback": frequency_feedback_of_no_1_ethylene_glycol_pump,  # 1号乙二醇泵频率反馈
            },
            2: {
                "running_status": operation_status_of_no_2_ethylene_glycol_pump,  # 2号乙二醇泵运行状态
                "power": real_time_power_of_electric_meter_for_no_2_ethylene_glycol_pump,  # 2号乙二醇泵电表实时功率
                "frequency_feedback": frequency_feedback_of_no_2_ethylene_glycol_pump,  # 2号乙二醇泵频率反馈
            },
            3: {
                "running_status": operation_status_of_no_3_ethylene_glycol_pump,  # 3号乙二醇泵运行状态
                "power": real_time_power_of_the_electric_meter_for_the_3rd_ethylene_glycol_pump,  # 3号乙二醇泵电表实时功率
                "frequency_feedback": frequency_feedback_of_the_3rd_ethylene_glycol_pump,  # 3号乙二醇泵频率反馈
            },
        },
        "total": {
            "return_pressure": return_water_pressure_of_ethylene_glycol_pump,  # 乙二醇泵回水压力
        }
    }

    # 板换相关
    PLATE_EXCHANGER: dict = {
        "devices": {
            1: {
                "primary_inlet_temp": replace_the_inlet_water_temperature_of_board_1_once,  # 1号板换一次进水温度
                "primary_outlet_temp": replace_the_outlet_temperature_of_board_1_once,  # 1号板换一次出水温度
                "secondary_outlet_temp": the_temperature_of_the_water_outlet_after_the_second_replacement_of_board_1,
                # 1号板换二次出水温度
            },
            2: {
                "primary_inlet_temp": replace_the_inlet_water_temperature_of_board_2_once,  # 2号板换一次进水温度
                "primary_outlet_temp": replace_the_outlet_temperature_of_board_2_once,  # 2号板换一次出水温度
                "secondary_outlet_temp": temperature_of_secondary_water_outlet_for_board_2_replacement,  # 2号板换二次出水温度
            },
        },
        "total": {
            "secondary_supply_temp": plate_replacement_secondary_main_water_supply_temperature,  # 板换二次总管供水温度
            "secondary_supply_pressure": plate_replacement_secondary_main_water_supply_pressure,  # 板换二次总管供水压力
            "secondary_return_temp": return_water_temperature_of_board_replacement_secondary_main_pipe,  # 板换二次总管回水温度
            "secondary_return_pressure": plate_replacement_secondary_main_return_water_pressure,  # 板换二次总管回水压力
            "temp_diff": temperature_difference_between_supply_and_return_water_of_plate_replacement_chilled_water,
            # 板换冷冻水供回水温差
            "pressure_diff": pressure_difference_between_the_supply_and_return_of_chilled_water_for_plate_replacement,
            # 板换冷冻水供回水压差
        }
    }

    # 天气相关
    WEATHER: dict = {
        "outdoor_temperature": outdoor_temperature,  # 室外温度
        "outdoor_humidity": outdoor_humidity,  # 室外湿度
        "wet_bulb_temperature": wet_bulb_temperature,  # 湿球温度
    }
    # ==================== 用电量基础表名 ====================
    # 基础前缀：改后缀 _add_hours / _add_day / _add_month / _add_year 即可查询不同粒度
    ELEC_BASE_HOST: str = "xm_ele_zlz1_ch_add"  # 主机
    ELEC_BASE_CHILLED_PUMP: str = "xm_ele_zlz1_chwp_add"  # 冷冻泵
    ELEC_BASE_GLYCOL_PUMP: str = "xm_ele_zlz1_yecb_add"  # 乙二醇泵
    ELEC_BASE_COOLING_PUMP: str = "xm_ele_zlz1_cdwp_add"  # 冷却泵
    ELEC_BASE_COOLING_TOWER: str = "xm_ele_zlz1_ct_add"  # 冷却塔

    # ==================== 模型文件前缀（用于类型设备模型） ====================
    # 总功率模型（设备类型模型）前缀
    MODEL_PREFIX_HOST_TOTAL: str = ""
    MODEL_PREFIX_COOLING_TOWER_TOTAL: str = "xgboost_device_4_total_cooling_tower_power_"
    MODEL_PREFIX_COOLING_PUMP_TOTAL: str = ""
    MODEL_PREFIX_CHILLED_PUMP_TOTAL: str = ""
    MODEL_PREFIX_HOURLY_COOLING_ENERGY_TOTAL: str = "xgboost_device_10_hourly_cooling_energy_total_"

    # 单设备模型前缀（可根据需要保留或删除）
    MODEL_PREFIX_HOST_SINGLE: str = ""
    MODEL_PREFIX_COOLING_PUMP1_SINGLE: str = "xgboost_device_5_total_cooling_pump_power_1_"
    MODEL_PREFIX_COOLING_PUMP2_SINGLE: str = "xgboost_device_6_total_cooling_pump_power_2_"
    MODEL_PREFIX_CHILLED_PUMP1_SINGLE: str = "xgboost_device_7_total_chilled_pump_power_1_"
    MODEL_PREFIX_CHILLED_PUMP2_SINGLE: str = "xgboost_device_8_total_chilled_pump_power_2_"
    MODEL_PREFIX_CHILLED_PUMP3_SINGLE: str = "xgboost_device_9_total_glycol_pump_power_"
    # ==================== 模型分组配置（四组） ====================
    # 每组包含一个或多个模型前缀，实际部署时任选一种（总模型/分模型）
    MODEL_GROUPS: dict = {
        "host": [
            # 如果使用总模型，填写总模型前缀；如果分模型，填写多个前缀
            "xgboost_device_2_total_host_power_",
            "xgboost_device_3_total_host_power_",
        ],
        "cooling_tower": [
            "xgboost_device_4_total_cooling_tower_power_",  # 冷却塔总功率（只有一个配电柜，可以继续用这个前缀）
        ],
        "cooling_pump": [
            "xgboost_device_5_total_cooling_pump_power_1_",  # 冷却泵分组1
            "xgboost_device_6_total_cooling_pump_power_2_",  # 冷却泵分组2
            # 如果改成总模型，只保留一个前缀即可
        ],
        "chilled_pump": [
            "xgboost_device_7_total_chilled_pump_power_1_",  # 冷冻泵分组1
            "xgboost_device_8_total_chilled_pump_power_2_",  # 冷冻泵分组2
            "xgboost_device_9_total_glycol_pump_power_",  # 乙二醇泵（原有，如果属于冷冻泵组）
            # 实际字段请替换为真实文件名前缀
        ],
    }


    # API配置
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "工业负荷预测系统"
    VERSION: str = "1.0.0"

    # CORS配置
    BACKEND_CORS_ORIGINS: list = ["http://localhost:8000", "http://127.0.0.1:8000","*"]

    class Config:
        env_file = ".env"
        extra = "ignore"  # 忽略 .env 中未定义的字段（如 deepseek_api_key vs DEEPSEEK_APIKEY）


settings = Settings()
