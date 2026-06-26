-- 启用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 插入当前项目所有特征数据
INSERT INTO features (
    name, code, data_type, unit, description, is_required, validation_rules,
    data_source_id, database_name, table_name, column_name, timestamp_column
) VALUES

-- ========== 主机运行状态 ==========
('1号主机运行状态', 'host_1_running_status', 'boolean', '', '1号主机开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di90', 'PointValue', 'UpdateDateTime'),
('2号主机运行状态', 'host_2_running_status', 'boolean', '', '2号主机开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di97', 'PointValue', 'UpdateDateTime'),
('3号主机运行状态', 'host_3_running_status', 'boolean', '', '3号主机开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di104', 'PointValue', 'UpdateDateTime'),
('4号主机运行状态', 'host_4_running_status', 'boolean', '', '4号主机开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di111', 'PointValue', 'UpdateDateTime'),
('5号主机运行状态', 'host_5_running_status', 'boolean', '', '5号主机开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di118', 'PointValue', 'UpdateDateTime'),

-- ========== 冷冻泵运行状态 ==========
('1号冷冻泵运行状态', 'chilled_pump_1_running_status', 'boolean', '', '1号冷冻泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di125', 'PointValue', 'UpdateDateTime'),
('2号冷冻泵运行状态', 'chilled_pump_2_running_status', 'boolean', '', '2号冷冻泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di129', 'PointValue', 'UpdateDateTime'),
('3号冷冻泵运行状态', 'chilled_pump_3_running_status', 'boolean', '', '3号冷冻泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di133', 'PointValue', 'UpdateDateTime'),
('4号冷冻泵运行状态', 'chilled_pump_4_running_status', 'boolean', '', '4号冷冻泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di137', 'PointValue', 'UpdateDateTime'),
('5号冷冻泵运行状态', 'chilled_pump_5_running_status', 'boolean', '', '5号冷冻泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di141', 'PointValue', 'UpdateDateTime'),
('6号冷冻泵运行状态', 'chilled_pump_6_running_status', 'boolean', '', '6号冷冻泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di145', 'PointValue', 'UpdateDateTime'),
('7号冷冻泵运行状态', 'chilled_pump_7_running_status', 'boolean', '', '7号冷冻泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di149', 'PointValue', 'UpdateDateTime'),

-- ========== 乙二醇泵运行状态 ==========
('1号乙二醇泵运行状态', 'ethylene_glycol_pump_1_running_status', 'boolean', '', '1号乙二醇泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di153', 'PointValue', 'UpdateDateTime'),
('2号乙二醇泵运行状态', 'ethylene_glycol_pump_2_running_status', 'boolean', '', '2号乙二醇泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di157', 'PointValue', 'UpdateDateTime'),
('3号乙二醇泵运行状态', 'ethylene_glycol_pump_3_running_status', 'boolean', '', '3号乙二醇泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di161', 'PointValue', 'UpdateDateTime'),

-- ========== 冷却泵运行状态 ==========
('1号冷却泵运行状态', 'cooling_pump_1_running_status', 'boolean', '', '1号冷却泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di165', 'PointValue', 'UpdateDateTime'),
('2号冷却泵运行状态', 'cooling_pump_2_running_status', 'boolean', '', '2号冷却泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di169', 'PointValue', 'UpdateDateTime'),
('3号冷却泵运行状态', 'cooling_pump_3_running_status', 'boolean', '', '3号冷却泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di173', 'PointValue', 'UpdateDateTime'),
('4号冷却泵运行状态', 'cooling_pump_4_running_status', 'boolean', '', '4号冷却泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di177', 'PointValue', 'UpdateDateTime'),
('5号冷却泵运行状态', 'cooling_pump_5_running_status', 'boolean', '', '5号冷却泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di181', 'PointValue', 'UpdateDateTime'),
('6号冷却泵运行状态', 'cooling_pump_6_running_status', 'boolean', '', '6号冷却泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di185', 'PointValue', 'UpdateDateTime'),
('7号冷却泵运行状态', 'cooling_pump_7_running_status', 'boolean', '', '7号冷却泵开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di189', 'PointValue', 'UpdateDateTime'),

-- ========== 冷却塔运行状态 ==========
('1号冷却塔运行状态', 'cooling_tower_1_running_status', 'boolean', '', '1号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di194', 'PointValue', 'UpdateDateTime'),
('2号冷却塔运行状态', 'cooling_tower_2_running_status', 'boolean', '', '2号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di198', 'PointValue', 'UpdateDateTime'),
('3号冷却塔运行状态', 'cooling_tower_3_running_status', 'boolean', '', '3号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di202', 'PointValue', 'UpdateDateTime'),
('4号冷却塔运行状态', 'cooling_tower_4_running_status', 'boolean', '', '4号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di206', 'PointValue', 'UpdateDateTime'),
('5号冷却塔运行状态', 'cooling_tower_5_running_status', 'boolean', '', '5号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di210', 'PointValue', 'UpdateDateTime'),
('6号冷却塔运行状态', 'cooling_tower_6_running_status', 'boolean', '', '6号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di214', 'PointValue', 'UpdateDateTime'),
('7号冷却塔运行状态', 'cooling_tower_7_running_status', 'boolean', '', '7号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di218', 'PointValue', 'UpdateDateTime'),
('8号冷却塔运行状态', 'cooling_tower_8_running_status', 'boolean', '', '8号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di222', 'PointValue', 'UpdateDateTime'),
('9号冷却塔运行状态', 'cooling_tower_9_running_status', 'boolean', '', '9号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di226', 'PointValue', 'UpdateDateTime'),
('10号冷却塔运行状态', 'cooling_tower_10_running_status', 'boolean', '', '10号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di230', 'PointValue', 'UpdateDateTime'),
('11号冷却塔运行状态', 'cooling_tower_11_running_status', 'boolean', '', '11号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di234', 'PointValue', 'UpdateDateTime'),
('12号冷却塔运行状态', 'cooling_tower_12_running_status', 'boolean', '', '12号冷却塔开关机状态', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_di238', 'PointValue', 'UpdateDateTime'),

-- ========== 温度类 (传感器) ==========
('室外温度', 'outdoor_temperature', 'number', '°C', '室外环境温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai38', 'PointValue', 'UpdateDateTime'),
('室外湿度', 'outdoor_humidity', 'number', '%', '室外环境相对湿度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai39', 'PointValue', 'UpdateDateTime'),
('湿球温度', 'wet_bulb_temperature', 'number', '°C', '室外湿球温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai40', 'PointValue', 'UpdateDateTime'),
('冷冻水总管供水温度', 'total_chilled_inlet_temp', 'number', '°C', '冷冻水系统总管供水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai41', 'PointValue', 'UpdateDateTime'),
('冷冻水总管回水温度', 'total_chilled_return_temp', 'number', '°C', '冷冻水系统总管回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai42', 'PointValue', 'UpdateDateTime'),
('冷冻水总管供水压力', 'total_chilled_supply_pressure', 'number', 'MPa', '冷冻水系统总管供水压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai43', 'PointValue', 'UpdateDateTime'),
('冷冻水总管回水压力', 'total_chilled_return_pressure', 'number', 'MPa', '冷冻水系统总管回水压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai44', 'PointValue', 'UpdateDateTime'),
('冷却水总管供水温度', 'total_cooling_inlet_temp', 'number', '°C', '冷却水系统总管供水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai45', 'PointValue', 'UpdateDateTime'),
('冷却水总管回水温度', 'total_cooling_return_temp', 'number', '°C', '冷却水系统总管回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai46', 'PointValue', 'UpdateDateTime'),
('板换二次总管供水温度', 'phe_secondary_main_supply_temp', 'number', '°C', '板换二次总管供水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai48', 'PointValue', 'UpdateDateTime'),
('板换二次总管供水压力', 'phe_secondary_main_supply_pressure', 'number', 'MPa', '板换二次总管供水压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai49', 'PointValue', 'UpdateDateTime'),
('板换二次总管回水温度', 'phe_secondary_main_return_temp', 'number', '°C', '板换二次总管回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai50', 'PointValue', 'UpdateDateTime'),
('板换二次总管回水压力', 'phe_secondary_main_return_pressure', 'number', 'MPa', '板换二次总管回水压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai51', 'PointValue', 'UpdateDateTime'),

-- ========== 冷却塔出水温度 (CT11~CT34) ==========
('冷却塔出水温度CT11', 'cooling_tower_ct11_outlet_temp', 'number', '°C', '冷却塔CT11出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai52', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT12', 'cooling_tower_ct12_outlet_temp', 'number', '°C', '冷却塔CT12出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai53', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT13', 'cooling_tower_ct13_outlet_temp', 'number', '°C', '冷却塔CT13出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai54', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT14', 'cooling_tower_ct14_outlet_temp', 'number', '°C', '冷却塔CT14出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai55', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT21', 'cooling_tower_ct21_outlet_temp', 'number', '°C', '冷却塔CT21出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai56', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT22', 'cooling_tower_ct22_outlet_temp', 'number', '°C', '冷却塔CT22出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai57', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT23', 'cooling_tower_ct23_outlet_temp', 'number', '°C', '冷却塔CT23出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai58', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT24', 'cooling_tower_ct24_outlet_temp', 'number', '°C', '冷却塔CT24出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai59', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT31', 'cooling_tower_ct31_outlet_temp', 'number', '°C', '冷却塔CT31出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai60', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT32', 'cooling_tower_ct32_outlet_temp', 'number', '°C', '冷却塔CT32出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai61', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT33', 'cooling_tower_ct33_outlet_temp', 'number', '°C', '冷却塔CT33出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai62', 'PointValue', 'UpdateDateTime'),
('冷却塔出水温度CT34', 'cooling_tower_ct34_outlet_temp', 'number', '°C', '冷却塔CT34出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai63', 'PointValue', 'UpdateDateTime'),

-- ========== 主机冷冻/冷却侧出水温度 ==========
('1号主机冷冻侧出水温度', 'host_1_chilled_outlet_temp', 'number', '°C', '1号主机冷冻水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai64', 'PointValue', 'UpdateDateTime'),
('1号主机冷却侧出水温度', 'host_1_cooling_outlet_temp', 'number', '°C', '1号主机冷却水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai65', 'PointValue', 'UpdateDateTime'),
('2号主机冷冻侧出水温度', 'host_2_chilled_outlet_temp', 'number', '°C', '2号主机冷冻水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai66', 'PointValue', 'UpdateDateTime'),
('2号主机冷却侧出水温度', 'host_2_cooling_outlet_temp', 'number', '°C', '2号主机冷却水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai67', 'PointValue', 'UpdateDateTime'),
('3号主机冷冻侧出水温度', 'host_3_chilled_outlet_temp', 'number', '°C', '3号主机冷冻水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai68', 'PointValue', 'UpdateDateTime'),
('3号主机冷却侧出水温度', 'host_3_cooling_outlet_temp', 'number', '°C', '3号主机冷却水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai69', 'PointValue', 'UpdateDateTime'),
('4号主机冷冻侧出水温度', 'host_4_chilled_outlet_temp', 'number', '°C', '4号主机冷冻水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai70', 'PointValue', 'UpdateDateTime'),
('4号主机冷却侧出水温度', 'host_4_cooling_outlet_temp', 'number', '°C', '4号主机冷却水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai71', 'PointValue', 'UpdateDateTime'),
('5号主机冷冻侧出水温度', 'host_5_chilled_outlet_temp', 'number', '°C', '5号主机冷冻水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai72', 'PointValue', 'UpdateDateTime'),
('5号主机冷却侧出水温度', 'host_5_cooling_outlet_temp', 'number', '°C', '5号主机冷却水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai73', 'PointValue', 'UpdateDateTime'),

-- ========== 乙二醇泵回水压力 ==========
('乙二醇泵回水压力', 'ethylene_glycol_return_pressure', 'number', 'MPa', '乙二醇泵回水压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai74', 'PointValue', 'UpdateDateTime'),

-- ========== 板换一次/二次温度 ==========
('1号板换一次进水温度', 'phe1_primary_inlet_temp', 'number', '°C', '1号板换一次进水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai75', 'PointValue', 'UpdateDateTime'),
('1号板换一次出水温度', 'phe1_primary_outlet_temp', 'number', '°C', '1号板换一次出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai76', 'PointValue', 'UpdateDateTime'),
('2号板换一次进水温度', 'phe2_primary_inlet_temp', 'number', '°C', '2号板换一次进水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai77', 'PointValue', 'UpdateDateTime'),
('2号板换一次出水温度', 'phe2_primary_outlet_temp', 'number', '°C', '2号板换一次出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai78', 'PointValue', 'UpdateDateTime'),
('1号板换二次出水温度', 'phe1_secondary_outlet_temp', 'number', '°C', '1号板换二次出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai79', 'PointValue', 'UpdateDateTime'),
('2号板换二次出水温度', 'phe2_secondary_outlet_temp', 'number', '°C', '2号板换二次出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai80', 'PointValue', 'UpdateDateTime'),

-- ========== 温差与压差 ==========
('冷冻水供回水温差', 'chilled_water_temp_diff', 'number', '°C', '冷冻水供回水温差', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai147', 'PointValue', 'UpdateDateTime'),
('冷冻水供回水压差', 'chilled_water_pressure_diff', 'number', 'MPa', '冷冻水供回水压差', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai148', 'PointValue', 'UpdateDateTime'),
('板换冷冻水供回水温差', 'phe_chilled_water_temp_diff', 'number', '°C', '板换冷冻水供回水温差', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai149', 'PointValue', 'UpdateDateTime'),
('板换冷冻水供回水压差', 'phe_chilled_water_pressure_diff', 'number', 'MPa', '板换冷冻水供回水压差', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai150', 'PointValue', 'UpdateDateTime'),
('冷却水供回水温差', 'cooling_water_temp_diff', 'number', '°C', '冷却水供回水温差', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai151', 'PointValue', 'UpdateDateTime'),

-- ========== 频率反馈 ==========
('1号冷冻泵频率反馈', 'chilled_pump_1_freq', 'number', 'Hz', '1号冷冻泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai169', 'PointValue', 'UpdateDateTime'),
('2号冷冻泵频率反馈', 'chilled_pump_2_freq', 'number', 'Hz', '2号冷冻泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai170', 'PointValue', 'UpdateDateTime'),
('3号冷冻泵频率反馈', 'chilled_pump_3_freq', 'number', 'Hz', '3号冷冻泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai171', 'PointValue', 'UpdateDateTime'),
('4号冷冻泵频率反馈', 'chilled_pump_4_freq', 'number', 'Hz', '4号冷冻泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai172', 'PointValue', 'UpdateDateTime'),
('5号冷冻泵频率反馈', 'chilled_pump_5_freq', 'number', 'Hz', '5号冷冻泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai173', 'PointValue', 'UpdateDateTime'),
('6号冷冻泵频率反馈', 'chilled_pump_6_freq', 'number', 'Hz', '6号冷冻泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai174', 'PointValue', 'UpdateDateTime'),
('7号冷冻泵频率反馈', 'chilled_pump_7_freq', 'number', 'Hz', '7号冷冻泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai175', 'PointValue', 'UpdateDateTime'),
('1号乙二醇泵频率反馈', 'ethylene_glycol_pump_1_freq', 'number', 'Hz', '1号乙二醇泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai176', 'PointValue', 'UpdateDateTime'),
('2号乙二醇泵频率反馈', 'ethylene_glycol_pump_2_freq', 'number', 'Hz', '2号乙二醇泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai177', 'PointValue', 'UpdateDateTime'),
('3号乙二醇泵频率反馈', 'ethylene_glycol_pump_3_freq', 'number', 'Hz', '3号乙二醇泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai178', 'PointValue', 'UpdateDateTime'),
('1号冷却泵频率反馈', 'cooling_pump_1_freq', 'number', 'Hz', '1号冷却泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai179', 'PointValue', 'UpdateDateTime'),
('2号冷却泵频率反馈', 'cooling_pump_2_freq', 'number', 'Hz', '2号冷却泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai180', 'PointValue', 'UpdateDateTime'),
('3号冷却泵频率反馈', 'cooling_pump_3_freq', 'number', 'Hz', '3号冷却泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai181', 'PointValue', 'UpdateDateTime'),
('4号冷却泵频率反馈', 'cooling_pump_4_freq', 'number', 'Hz', '4号冷却泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai182', 'PointValue', 'UpdateDateTime'),
('5号冷却泵频率反馈', 'cooling_pump_5_freq', 'number', 'Hz', '5号冷却泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai183', 'PointValue', 'UpdateDateTime'),
('6号冷却泵频率反馈', 'cooling_pump_6_freq', 'number', 'Hz', '6号冷却泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai184', 'PointValue', 'UpdateDateTime'),
('7号冷却泵频率反馈', 'cooling_pump_7_freq', 'number', 'Hz', '7号冷却泵变频器频率反馈', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai185', 'PointValue', 'UpdateDateTime'),

-- ========== 主机详细传感器（1~5号主机） ==========
-- 1号主机
('1号主机冷冻水出水温度', 'host_1_chilled_supply_temp', 'number', '°C', '1号主机冷冻水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai223', 'PointValue', 'UpdateDateTime'),
('1号主机冷冻水回水温度', 'host_1_chilled_return_temp', 'number', '°C', '1号主机冷冻水回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai224', 'PointValue', 'UpdateDateTime'),
('1号主机冷却水出水温度', 'host_1_cooling_supply_temp', 'number', '°C', '1号主机冷却水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai225', 'PointValue', 'UpdateDateTime'),
('1号主机冷却水回水温度', 'host_1_cooling_return_temp', 'number', '°C', '1号主机冷却水回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai226', 'PointValue', 'UpdateDateTime'),
('1号主机冷凝器温度', 'host_1_condenser_temp', 'number', '°C', '1号主机冷凝器温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai227', 'PointValue', 'UpdateDateTime'),
('1号主机蒸发器温度', 'host_1_evaporator_temp', 'number', '°C', '1号主机蒸发器温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai228', 'PointValue', 'UpdateDateTime'),
('1号主机冷凝器压力', 'host_1_condenser_pressure', 'number', 'MPa', '1号主机冷凝器压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai229', 'PointValue', 'UpdateDateTime'),
('1号主机蒸发器压力', 'host_1_evaporator_pressure', 'number', 'MPa', '1号主机蒸发器压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai230', 'PointValue', 'UpdateDateTime'),

-- 2号主机
('2号主机冷冻水出水温度', 'host_2_chilled_supply_temp', 'number', '°C', '2号主机冷冻水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai248', 'PointValue', 'UpdateDateTime'),
('2号主机冷冻水回水温度', 'host_2_chilled_return_temp', 'number', '°C', '2号主机冷冻水回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai249', 'PointValue', 'UpdateDateTime'),
('2号主机冷却水出水温度', 'host_2_cooling_supply_temp', 'number', '°C', '2号主机冷却水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai250', 'PointValue', 'UpdateDateTime'),
('2号主机冷却水回水温度', 'host_2_cooling_return_temp', 'number', '°C', '2号主机冷却水回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai251', 'PointValue', 'UpdateDateTime'),
('2号主机冷凝器温度', 'host_2_condenser_temp', 'number', '°C', '2号主机冷凝器温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai252', 'PointValue', 'UpdateDateTime'),
('2号主机蒸发器温度', 'host_2_evaporator_temp', 'number', '°C', '2号主机蒸发器温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai253', 'PointValue', 'UpdateDateTime'),
('2号主机冷凝器压力', 'host_2_condenser_pressure', 'number', 'MPa', '2号主机冷凝器压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai254', 'PointValue', 'UpdateDateTime'),
('2号主机蒸发器压力', 'host_2_evaporator_pressure', 'number', 'MPa', '2号主机蒸发器压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai255', 'PointValue', 'UpdateDateTime'),

-- 3号主机
('3号主机冷冻水出水温度', 'host_3_chilled_supply_temp', 'number', '°C', '3号主机冷冻水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai273', 'PointValue', 'UpdateDateTime'),
('3号主机冷冻水回水温度', 'host_3_chilled_return_temp', 'number', '°C', '3号主机冷冻水回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai274', 'PointValue', 'UpdateDateTime'),
('3号主机冷却水出水温度', 'host_3_cooling_supply_temp', 'number', '°C', '3号主机冷却水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai275', 'PointValue', 'UpdateDateTime'),
('3号主机冷却水回水温度', 'host_3_cooling_return_temp', 'number', '°C', '3号主机冷却水回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai276', 'PointValue', 'UpdateDateTime'),
('3号主机冷凝器温度', 'host_3_condenser_temp', 'number', '°C', '3号主机冷凝器温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai277', 'PointValue', 'UpdateDateTime'),
('3号主机蒸发器温度', 'host_3_evaporator_temp', 'number', '°C', '3号主机蒸发器温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai278', 'PointValue', 'UpdateDateTime'),
('3号主机冷凝器压力', 'host_3_condenser_pressure', 'number', 'MPa', '3号主机冷凝器压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai279', 'PointValue', 'UpdateDateTime'),
('3号主机蒸发器压力', 'host_3_evaporator_pressure', 'number', 'MPa', '3号主机蒸发器压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai280', 'PointValue', 'UpdateDateTime'),

-- 4号主机
('4号主机冷冻水出水温度', 'host_4_chilled_supply_temp', 'number', '°C', '4号主机冷冻水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai298', 'PointValue', 'UpdateDateTime'),
('4号主机冷冻水回水温度', 'host_4_chilled_return_temp', 'number', '°C', '4号主机冷冻水回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai299', 'PointValue', 'UpdateDateTime'),
('4号主机冷却水出水温度', 'host_4_cooling_supply_temp', 'number', '°C', '4号主机冷却水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai300', 'PointValue', 'UpdateDateTime'),
('4号主机冷却水回水温度', 'host_4_cooling_return_temp', 'number', '°C', '4号主机冷却水回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai301', 'PointValue', 'UpdateDateTime'),
('4号主机冷凝器温度', 'host_4_condenser_temp', 'number', '°C', '4号主机冷凝器温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai302', 'PointValue', 'UpdateDateTime'),
('4号主机蒸发器温度', 'host_4_evaporator_temp', 'number', '°C', '4号主机蒸发器温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai303', 'PointValue', 'UpdateDateTime'),
('4号主机冷凝器压力', 'host_4_condenser_pressure', 'number', 'MPa', '4号主机冷凝器压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai304', 'PointValue', 'UpdateDateTime'),
('4号主机蒸发器压力', 'host_4_evaporator_pressure', 'number', 'MPa', '4号主机蒸发器压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai305', 'PointValue', 'UpdateDateTime'),

-- 5号主机
('5号主机冷冻水出水温度', 'host_5_chilled_supply_temp', 'number', '°C', '5号主机冷冻水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai323', 'PointValue', 'UpdateDateTime'),
('5号主机冷冻水回水温度', 'host_5_chilled_return_temp', 'number', '°C', '5号主机冷冻水回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai324', 'PointValue', 'UpdateDateTime'),
('5号主机冷却水出水温度', 'host_5_cooling_supply_temp', 'number', '°C', '5号主机冷却水出水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai325', 'PointValue', 'UpdateDateTime'),
('5号主机冷却水回水温度', 'host_5_cooling_return_temp', 'number', '°C', '5号主机冷却水回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai326', 'PointValue', 'UpdateDateTime'),
('5号主机冷凝器温度', 'host_5_condenser_temp', 'number', '°C', '5号主机冷凝器温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai327', 'PointValue', 'UpdateDateTime'),
('5号主机蒸发器温度', 'host_5_evaporator_temp', 'number', '°C', '5号主机蒸发器温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai328', 'PointValue', 'UpdateDateTime'),
('5号主机冷凝器压力', 'host_5_condenser_pressure', 'number', 'MPa', '5号主机冷凝器压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai329', 'PointValue', 'UpdateDateTime'),
('5号主机蒸发器压力', 'host_5_evaporator_pressure', 'number', 'MPa', '5号主机蒸发器压力', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai330', 'PointValue', 'UpdateDateTime'),

-- ========== 电表实时功率 ==========
('1号主机电表实时功率', 'host_1_power', 'number', 'kW', '1号主机电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai354', 'PointValue', 'UpdateDateTime'),
('2号主机电表实时功率', 'host_2_power', 'number', 'kW', '2号主机电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai362', 'PointValue', 'UpdateDateTime'),
('3号主机电表实时功率', 'host_3_power', 'number', 'kW', '3号主机电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai370', 'PointValue', 'UpdateDateTime'),
('4号主机电表实时功率', 'host_4_power', 'number', 'kW', '4号主机电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai378', 'PointValue', 'UpdateDateTime'),
('5号主机电表实时功率', 'host_5_power', 'number', 'kW', '5号主机电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai386', 'PointValue', 'UpdateDateTime'),
('1号冷冻泵电表实时功率', 'chilled_pump_1_power', 'number', 'kW', '1号冷冻泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai394', 'PointValue', 'UpdateDateTime'),
('2号冷冻泵电表实时功率', 'chilled_pump_2_power', 'number', 'kW', '2号冷冻泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai402', 'PointValue', 'UpdateDateTime'),
('3号冷冻泵电表实时功率', 'chilled_pump_3_power', 'number', 'kW', '3号冷冻泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai410', 'PointValue', 'UpdateDateTime'),
('4号冷冻泵电表实时功率', 'chilled_pump_4_power', 'number', 'kW', '4号冷冻泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai418', 'PointValue', 'UpdateDateTime'),
('5号冷冻泵电表实时功率', 'chilled_pump_5_power', 'number', 'kW', '5号冷冻泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai426', 'PointValue', 'UpdateDateTime'),
('6号冷冻泵电表实时功率', 'chilled_pump_6_power', 'number', 'kW', '6号冷冻泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai434', 'PointValue', 'UpdateDateTime'),
('7号冷冻泵电表实时功率', 'chilled_pump_7_power', 'number', 'kW', '7号冷冻泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai442', 'PointValue', 'UpdateDateTime'),
('1号乙二醇泵电表实时功率', 'ethylene_glycol_pump_1_power', 'number', 'kW', '1号乙二醇泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai450', 'PointValue', 'UpdateDateTime'),
('2号乙二醇泵电表实时功率', 'ethylene_glycol_pump_2_power', 'number', 'kW', '2号乙二醇泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai458', 'PointValue', 'UpdateDateTime'),
('3号乙二醇泵电表实时功率', 'ethylene_glycol_pump_3_power', 'number', 'kW', '3号乙二醇泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai466', 'PointValue', 'UpdateDateTime'),
('1号冷却泵电表实时功率', 'cooling_pump_1_power', 'number', 'kW', '1号冷却泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai474', 'PointValue', 'UpdateDateTime'),
('2号冷却泵电表实时功率', 'cooling_pump_2_power', 'number', 'kW', '2号冷却泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai482', 'PointValue', 'UpdateDateTime'),
('3号冷却泵电表实时功率', 'cooling_pump_3_power', 'number', 'kW', '3号冷却泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai490', 'PointValue', 'UpdateDateTime'),
('4号冷却泵电表实时功率', 'cooling_pump_4_power', 'number', 'kW', '4号冷却泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai498', 'PointValue', 'UpdateDateTime'),
('5号冷却泵电表实时功率', 'cooling_pump_5_power', 'number', 'kW', '5号冷却泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai506', 'PointValue', 'UpdateDateTime'),
('6号冷却泵电表实时功率', 'cooling_pump_6_power', 'number', 'kW', '6号冷却泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai514', 'PointValue', 'UpdateDateTime'),
('7号冷却泵电表实时功率', 'cooling_pump_7_power', 'number', 'kW', '7号冷却泵电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai522', 'PointValue', 'UpdateDateTime'),
('1号冷却塔电表实时功率', 'cooling_tower_1_power', 'number', 'kW', '1号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai530', 'PointValue', 'UpdateDateTime'),
('2号冷却塔电表实时功率', 'cooling_tower_2_power', 'number', 'kW', '2号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai538', 'PointValue', 'UpdateDateTime'),
('3号冷却塔电表实时功率', 'cooling_tower_3_power', 'number', 'kW', '3号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai546', 'PointValue', 'UpdateDateTime'),
('4号冷却塔电表实时功率', 'cooling_tower_4_power', 'number', 'kW', '4号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai554', 'PointValue', 'UpdateDateTime'),
('5号冷却塔电表实时功率', 'cooling_tower_5_power', 'number', 'kW', '5号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai562', 'PointValue', 'UpdateDateTime'),
('6号冷却塔电表实时功率', 'cooling_tower_6_power', 'number', 'kW', '6号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai570', 'PointValue', 'UpdateDateTime'),
('7号冷却塔电表实时功率', 'cooling_tower_7_power', 'number', 'kW', '7号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai578', 'PointValue', 'UpdateDateTime'),
('8号冷却塔电表实时功率', 'cooling_tower_8_power', 'number', 'kW', '8号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai586', 'PointValue', 'UpdateDateTime'),
('9号冷却塔电表实时功率', 'cooling_tower_9_power', 'number', 'kW', '9号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai594', 'PointValue', 'UpdateDateTime'),
('10号冷却塔电表实时功率', 'cooling_tower_10_power', 'number', 'kW', '10号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai602', 'PointValue', 'UpdateDateTime'),
('11号冷却塔电表实时功率', 'cooling_tower_11_power', 'number', 'kW', '11号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai610', 'PointValue', 'UpdateDateTime'),
('12号冷却塔电表实时功率', 'cooling_tower_12_power', 'number', 'kW', '12号冷却塔电表实时功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai618', 'PointValue', 'UpdateDateTime'),

-- ========== 主机能量计 ==========
-- 1号主机
('1号主机能量计瞬时流速', 'host_1_energy_meter_instant_velocity', 'number', 'm/s', '1号主机能量计瞬时流速', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai620', 'PointValue', 'UpdateDateTime'),
('1号主机能量计瞬时流量', 'host_1_energy_meter_instant_flow', 'number', 'm³/h', '1号主机能量计瞬时流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai621', 'PointValue', 'UpdateDateTime'),
('1号主机能量计瞬时冷量', 'host_1_energy_meter_instant_cooling', 'number', 'kW', '1号主机能量计瞬时冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai622', 'PointValue', 'UpdateDateTime'),
('1号主机能量计供水温度', 'host_1_energy_meter_supply_temp', 'number', '°C', '1号主机能量计供水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai623', 'PointValue', 'UpdateDateTime'),
('1号主机能量计回水温度', 'host_1_energy_meter_return_temp', 'number', '°C', '1号主机能量计回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai624', 'PointValue', 'UpdateDateTime'),
('1号主机能量计累积流量', 'host_1_energy_meter_cumulative_flow', 'number', 'm³', '1号主机能量计累积流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai625', 'PointValue', 'UpdateDateTime'),
('1号主机能量计累积冷量', 'host_1_energy_meter_cumulative_cooling', 'number', 'kWh', '1号主机能量计累积冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai626', 'PointValue', 'UpdateDateTime'),

-- 2号主机
('2号主机能量计瞬时流速', 'host_2_energy_meter_instant_velocity', 'number', 'm/s', '2号主机能量计瞬时流速', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai627', 'PointValue', 'UpdateDateTime'),
('2号主机能量计瞬时流量', 'host_2_energy_meter_instant_flow', 'number', 'm³/h', '2号主机能量计瞬时流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai628', 'PointValue', 'UpdateDateTime'),
('2号主机能量计瞬时冷量', 'host_2_energy_meter_instant_cooling', 'number', 'kW', '2号主机能量计瞬时冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai629', 'PointValue', 'UpdateDateTime'),
('2号主机能量计供水温度', 'host_2_energy_meter_supply_temp', 'number', '°C', '2号主机能量计供水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai630', 'PointValue', 'UpdateDateTime'),
('2号主机能量计回水温度', 'host_2_energy_meter_return_temp', 'number', '°C', '2号主机能量计回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai631', 'PointValue', 'UpdateDateTime'),
('2号主机能量计累积流量', 'host_2_energy_meter_cumulative_flow', 'number', 'm³', '2号主机能量计累积流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai632', 'PointValue', 'UpdateDateTime'),
('2号主机能量计累积冷量', 'host_2_energy_meter_cumulative_cooling', 'number', 'kWh', '2号主机能量计累积冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai633', 'PointValue', 'UpdateDateTime'),

-- 3号主机
('3号主机能量计瞬时流速', 'host_3_energy_meter_instant_velocity', 'number', 'm/s', '3号主机能量计瞬时流速', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai634', 'PointValue', 'UpdateDateTime'),
('3号主机能量计瞬时流量', 'host_3_energy_meter_instant_flow', 'number', 'm³/h', '3号主机能量计瞬时流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai635', 'PointValue', 'UpdateDateTime'),
('3号主机能量计瞬时冷量', 'host_3_energy_meter_instant_cooling', 'number', 'kW', '3号主机能量计瞬时冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai636', 'PointValue', 'UpdateDateTime'),
('3号主机能量计供水温度', 'host_3_energy_meter_supply_temp', 'number', '°C', '3号主机能量计供水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai637', 'PointValue', 'UpdateDateTime'),
('3号主机能量计回水温度', 'host_3_energy_meter_return_temp', 'number', '°C', '3号主机能量计回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai638', 'PointValue', 'UpdateDateTime'),
('3号主机能量计累积流量', 'host_3_energy_meter_cumulative_flow', 'number', 'm³', '3号主机能量计累积流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai639', 'PointValue', 'UpdateDateTime'),
('3号主机能量计累积冷量', 'host_3_energy_meter_cumulative_cooling', 'number', 'kWh', '3号主机能量计累积冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai640', 'PointValue', 'UpdateDateTime'),

-- 4号主机
('4号主机能量计瞬时流速', 'host_4_energy_meter_instant_velocity', 'number', 'm/s', '4号主机能量计瞬时流速', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai641', 'PointValue', 'UpdateDateTime'),
('4号主机能量计瞬时流量', 'host_4_energy_meter_instant_flow', 'number', 'm³/h', '4号主机能量计瞬时流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai642', 'PointValue', 'UpdateDateTime'),
('4号主机能量计瞬时冷量', 'host_4_energy_meter_instant_cooling', 'number', 'kW', '4号主机能量计瞬时冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai643', 'PointValue', 'UpdateDateTime'),
('4号主机能量计供水温度', 'host_4_energy_meter_supply_temp', 'number', '°C', '4号主机能量计供水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai644', 'PointValue', 'UpdateDateTime'),
('4号主机能量计回水温度', 'host_4_energy_meter_return_temp', 'number', '°C', '4号主机能量计回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai645', 'PointValue', 'UpdateDateTime'),
('4号主机能量计累积流量', 'host_4_energy_meter_cumulative_flow', 'number', 'm³', '4号主机能量计累积流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai646', 'PointValue', 'UpdateDateTime'),
('4号主机能量计累积冷量', 'host_4_energy_meter_cumulative_cooling', 'number', 'kWh', '4号主机能量计累积冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai647', 'PointValue', 'UpdateDateTime'),

-- 5号主机
('5号主机能量计瞬时流速', 'host_5_energy_meter_instant_velocity', 'number', 'm/s', '5号主机能量计瞬时流速', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai648', 'PointValue', 'UpdateDateTime'),
('5号主机能量计瞬时流量', 'host_5_energy_meter_instant_flow', 'number', 'm³/h', '5号主机能量计瞬时流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai649', 'PointValue', 'UpdateDateTime'),
('5号主机能量计瞬时冷量', 'host_5_energy_meter_instant_cooling', 'number', 'kW', '5号主机能量计瞬时冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai650', 'PointValue', 'UpdateDateTime'),
('5号主机能量计供水温度', 'host_5_energy_meter_supply_temp', 'number', '°C', '5号主机能量计供水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai651', 'PointValue', 'UpdateDateTime'),
('5号主机能量计回水温度', 'host_5_energy_meter_return_temp', 'number', '°C', '5号主机能量计回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai652', 'PointValue', 'UpdateDateTime'),
('5号主机能量计累积流量', 'host_5_energy_meter_cumulative_flow', 'number', 'm³', '5号主机能量计累积流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai653', 'PointValue', 'UpdateDateTime'),
('5号主机能量计累积冷量', 'host_5_energy_meter_cumulative_cooling', 'number', 'kWh', '5号主机能量计累积冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai654', 'PointValue', 'UpdateDateTime'),

-- ========== 基载总管能量计 ==========
('基载总管能量计瞬时流速', 'base_load_main_energy_meter_instant_velocity', 'number', 'm/s', '基载总管能量计瞬时流速', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai655', 'PointValue', 'UpdateDateTime'),
('基载总管能量计瞬时流量', 'base_load_main_energy_meter_instant_flow', 'number', 'm³/h', '基载总管能量计瞬时流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai656', 'PointValue', 'UpdateDateTime'),
('基载总管能量计瞬时冷量', 'base_load_main_energy_meter_instant_cooling', 'number', 'kW', '基载总管能量计瞬时冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai657', 'PointValue', 'UpdateDateTime'),
('基载总管能量计供水温度', 'base_load_main_energy_meter_supply_temp', 'number', '°C', '基载总管能量计供水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai658', 'PointValue', 'UpdateDateTime'),
('基载总管能量计回水温度', 'base_load_main_energy_meter_return_temp', 'number', '°C', '基载总管能量计回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai659', 'PointValue', 'UpdateDateTime'),
('基载总管能量计累积流量', 'base_load_main_energy_meter_cumulative_flow', 'number', 'm³', '基载总管能量计累积流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai660', 'PointValue', 'UpdateDateTime'),
('基载总管能量计累积冷量', 'base_load_main_energy_meter_cumulative_cooling', 'number', 'kWh', '基载总管能量计累积冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai661', 'PointValue', 'UpdateDateTime'),

-- ========== 板换二次总管能量计 ==========
('板换二次总管能量计瞬时流速', 'phe_secondary_main_energy_meter_instant_velocity', 'number', 'm/s', '板换二次总管能量计瞬时流速', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai662', 'PointValue', 'UpdateDateTime'),
('板换二次总管能量计瞬时流量', 'phe_secondary_main_energy_meter_instant_flow', 'number', 'm³/h', '板换二次总管能量计瞬时流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai663', 'PointValue', 'UpdateDateTime'),
('板换二次总管能量计瞬时冷量', 'phe_secondary_main_energy_meter_instant_cooling', 'number', 'kW', '板换二次总管能量计瞬时冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai664', 'PointValue', 'UpdateDateTime'),
('板换二次总管能量计供水温度', 'phe_secondary_main_energy_meter_supply_temp', 'number', '°C', '板换二次总管能量计供水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai665', 'PointValue', 'UpdateDateTime'),
('板换二次总管能量计回水温度', 'phe_secondary_main_energy_meter_return_temp', 'number', '°C', '板换二次总管能量计回水温度', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai666', 'PointValue', 'UpdateDateTime'),
('板换二次总管能量计累积流量', 'phe_secondary_main_energy_meter_cumulative_flow', 'number', 'm³', '板换二次总管能量计累积流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai667', 'PointValue', 'UpdateDateTime'),
('板换二次总管能量计累积冷量', 'phe_secondary_main_energy_meter_cumulative_cooling', 'number', 'kWh', '板换二次总管能量计累积冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai668', 'PointValue', 'UpdateDateTime'),

-- ========== 其他流量 ==========
('冰槽回水流量', 'ice_tank_return_flow', 'number', 'm³/h', '冰槽回水流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai678', 'PointValue', 'UpdateDateTime'),
('基载总管供水流量', 'base_load_main_supply_flow', 'number', 'm³/h', '基载总管供水流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai679', 'PointValue', 'UpdateDateTime'),
('板换二次总管供水流量', 'phe_secondary_main_supply_flow', 'number', 'm³/h', '板换二次总管供水流量', true, '{}'::jsonb, 1, 'xm_hisdata', 'hrdz_zlz_ai680', 'PointValue', 'UpdateDateTime')

ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    data_type = EXCLUDED.data_type,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    is_required = EXCLUDED.is_required,
    validation_rules = EXCLUDED.validation_rules,
    data_source_id = EXCLUDED.data_source_id,
    database_name = EXCLUDED.database_name,
    table_name = EXCLUDED.table_name,
    column_name = EXCLUDED.column_name,
    timestamp_column = EXCLUDED.timestamp_column,
    updated_at = CURRENT_TIMESTAMP;

-- 插入复合特征到 features 表（幂等，冲突时更新）
INSERT INTO features (
    name, code, data_type, unit, description, is_required, validation_rules,
    data_source_id, database_name, table_name, column_name, timestamp_column
)
VALUES
-- 主机总功率1
('主机总功率1', 'total_host_power_1', 'number', 'kW', '主机总功率1 = 1#主机功率+2#主机功率+3#主机功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_total_host_meter_1', 'PointValue', 'UpdateDateTime'),
-- 主机总功率2
('主机总功率2', 'total_host_power_2', 'number', 'kW', '主机总功率2 = 4#主机功率+5#主机功率', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_total_host_meter_2', 'PointValue', 'UpdateDateTime'),
-- 主机总瞬时冷量1
('主机总瞬时冷量1', 'total_host_instant_cooling_1', 'number', 'kW', '主机总瞬时冷量1 = 1号主机能量计瞬时冷量+2号主机能量计瞬时冷量+3号主机能量计瞬时冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_instantaneous_cooling_1', 'PointValue', 'UpdateDateTime'),
-- 主机总瞬时冷量2
('主机总瞬时冷量2', 'total_host_instant_cooling_2', 'number', 'kW', '主机总瞬时冷量2 = 4号主机能量计瞬时冷量+5号主机能量计瞬时冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_instantaneous_cooling_2', 'PointValue', 'UpdateDateTime'),
-- 系统散热量1
('系统散热量1', 'system_heat_dissipation_1', 'number', 'kW', '系统散热量1 = 主机总功率1+主机总瞬时冷量1', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_system_heat_dissipation_1', 'PointValue', 'UpdateDateTime'),
-- 系统散热量2
('系统散热量2', 'system_heat_dissipation_2', 'number', 'kW', '系统散热量2 = 主机总功率2+主机总瞬时冷量2', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_system_heat_dissipation_2', 'PointValue', 'UpdateDateTime'),
-- 冷却塔总功率
('冷却塔总功率', 'total_cooling_tower_power', 'number', 'kW', '冷却塔总功率 = 1~12号冷却塔电表实时功率之和', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_total_cooling_tower_meter', 'PointValue', 'UpdateDateTime'),
-- 冷却泵总功率1
('冷却泵总功率1', 'total_cooling_pump_power_1', 'number', 'kW', '冷却泵总功率1 = 1#冷却泵+2#冷却泵+3#冷却泵+4#冷却泵', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_total_cooling_pump_meter_1', 'PointValue', 'UpdateDateTime'),
-- 冷却泵总功率2
('冷却泵总功率2', 'total_cooling_pump_power_2', 'number', 'kW', '冷却泵总功率2 = 5#冷却泵+6#冷却泵+7#冷却泵', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_total_cooling_pump_meter_2', 'PointValue', 'UpdateDateTime'),
-- 冷冻泵总功率1
('冷冻泵总功率1', 'total_chilled_pump_power_1', 'number', 'kW', '冷冻泵总功率1 = 1#冷冻泵+2#冷冻泵+3#冷冻泵+4#冷冻泵', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_total_chilled_pump_meter_1', 'PointValue', 'UpdateDateTime'),
-- 冷冻泵总功率2
('冷冻泵总功率2', 'total_chilled_pump_power_2', 'number', 'kW', '冷冻泵总功率2 = 5#冷冻泵+6#冷冻泵+7#冷冻泵', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_total_chilled_pump_meter_2', 'PointValue', 'UpdateDateTime'),
-- 乙二醇泵总功率
('乙二醇泵总功率', 'total_glycol_pump_power', 'number', 'kW', '乙二醇泵总功率 = 1#乙二醇泵+2#乙二醇泵+3#乙二醇泵', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_total_glycol_pump_meter', 'PointValue', 'UpdateDateTime'),
-- 基载总管每小时冷量
('基载总管每小时冷量', 'hourly_cooling_energy_base', 'number', 'kWh', '通过基载总管累计冷量整点差值计算每小时的冷量消耗', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_hourly_cooling_energy_base', 'PointValue', 'UpdateDateTime'),
-- 板换二次总管每小时冷量
('板换二次总管每小时冷量', 'hourly_cooling_energy_sec', 'number', 'kWh', '通过板换二次总管累计冷量整点差值计算每小时的冷量消耗', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_hourly_cooling_energy_sec', 'PointValue', 'UpdateDateTime'),
-- 总每小时用冷量
('总每小时用冷量', 'total_hourly_cooling_energy', 'number', 'kWh', '总每小时用冷量 = 基载总管每小时冷量 + 板换二次总管每小时冷量', true, '{}'::jsonb, 1, 'xm_hisdata', 'composite_hourly_cooling_energy_total', 'PointValue', 'UpdateDateTime')
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    data_type = EXCLUDED.data_type,
    unit = EXCLUDED.unit,
    description = EXCLUDED.description,
    is_required = EXCLUDED.is_required,
    validation_rules = EXCLUDED.validation_rules,
    data_source_id = EXCLUDED.data_source_id,
    database_name = EXCLUDED.database_name,
    table_name = EXCLUDED.table_name,
    column_name = EXCLUDED.column_name,
    timestamp_column = EXCLUDED.timestamp_column,
    updated_at = CURRENT_TIMESTAMP;