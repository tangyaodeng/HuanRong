-- =====================================================
-- 冷却侧优化配置表（可动态修改的约束）
-- =====================================================
CREATE TABLE cooling_opt_config (
    id SERIAL PRIMARY KEY,

    -- 冷却水回水温度范围
    return_temp_lower_limit DECIMAL(5,2) DEFAULT 1.00,
    return_temp_upper_limit DECIMAL(5,2) DEFAULT 32.00,

    -- 冷却水供水温度范围
    supply_temp_lower_limit DECIMAL(5,2) DEFAULT 1.00,
    supply_temp_upper_limit DECIMAL(5,2) DEFAULT 40.00,

    -- 冷却水温差范围
    temp_diff_lower_limit DECIMAL(5,2) DEFAULT 2.00,
    temp_diff_upper_limit DECIMAL(5,2) DEFAULT 8.00,

    -- 散热量范围
    heat_dissipation_lower_limit DECIMAL(5,2) DEFAULT 95.00,
    heat_dissipation_upper_limit DECIMAL(5,2) DEFAULT 105.00,

    -- 阈值参数
    return_temp_threshold DECIMAL(5,2) DEFAULT 0.50,
    temp_diff_threshold DECIMAL(5,2) DEFAULT 0.80,
    energy_saving_threshold DECIMAL(5,2) DEFAULT 2.00,

    -- 寻优周期（分钟）
    optimization_cycle_minutes INTEGER DEFAULT 5,

    -- R² 阈值
    r2_threshold DECIMAL(3,2) DEFAULT 0.60,

    -- 约束
    CONSTRAINT ck_cooling_return_temp_range CHECK (return_temp_upper_limit >= return_temp_lower_limit),
    CONSTRAINT ck_cooling_supply_temp_range CHECK (supply_temp_upper_limit >= supply_temp_lower_limit),
    CONSTRAINT ck_cooling_temp_diff_range CHECK (temp_diff_upper_limit >= temp_diff_lower_limit),
    CONSTRAINT ck_cooling_heat_dissipation_range CHECK (heat_dissipation_upper_limit >= heat_dissipation_lower_limit),
    CONSTRAINT ck_cooling_return_temp_threshold_nonnegative CHECK (return_temp_threshold >= 0),
    CONSTRAINT ck_cooling_temp_diff_threshold_nonnegative CHECK (temp_diff_threshold >= 0),
    CONSTRAINT ck_cooling_energy_saving_threshold_nonnegative CHECK (energy_saving_threshold >= 0),
    CONSTRAINT ck_cooling_opt_cycle_positive CHECK (optimization_cycle_minutes > 0),
    CONSTRAINT ck_cooling_r2_threshold_range CHECK (r2_threshold >= 0 AND r2_threshold <= 1)
);

-- 字段注释
COMMENT ON COLUMN cooling_opt_config.return_temp_lower_limit IS '冷却水回水温度下限(℃) = 湿球温度+ n';
COMMENT ON COLUMN cooling_opt_config.return_temp_upper_limit IS '冷却水回水温度上限(℃)';
COMMENT ON COLUMN cooling_opt_config.supply_temp_lower_limit IS '冷却水供水温度下限(℃)= 湿球温度+ n';
COMMENT ON COLUMN cooling_opt_config.supply_temp_upper_limit IS '冷却水供水温度上限(℃)';
COMMENT ON COLUMN cooling_opt_config.temp_diff_lower_limit IS '冷却水温差下限(℃)';
COMMENT ON COLUMN cooling_opt_config.temp_diff_upper_limit IS '冷却水温差上限(℃)';
COMMENT ON COLUMN cooling_opt_config.heat_dissipation_lower_limit IS '散热量下限(%)';
COMMENT ON COLUMN cooling_opt_config.heat_dissipation_upper_limit IS '散热量上限(%)';
COMMENT ON COLUMN cooling_opt_config.return_temp_threshold IS '冷却水回水温度阈值(℃) ≥ ±0.5';
COMMENT ON COLUMN cooling_opt_config.temp_diff_threshold IS '冷却水温差阈值(℃) ≥ ±0.8';
COMMENT ON COLUMN cooling_opt_config.energy_saving_threshold IS '节能率阈值(%) ≥2';
COMMENT ON COLUMN cooling_opt_config.optimization_cycle_minutes IS '寻优周期（分钟）';
COMMENT ON COLUMN cooling_opt_config.r2_threshold IS '模型R²阈值，低于此值时预测值标记为不可信';

-- 初始化默认配置（id=1）
INSERT INTO cooling_opt_config (
    id,
    return_temp_lower_limit, return_temp_upper_limit,
    supply_temp_lower_limit, supply_temp_upper_limit,
    temp_diff_lower_limit, temp_diff_upper_limit,
    heat_dissipation_lower_limit, heat_dissipation_upper_limit,
    return_temp_threshold, temp_diff_threshold, energy_saving_threshold,
    optimization_cycle_minutes, r2_threshold
) VALUES (
    1,
    1.00, 32.00,    -- 回水
    1.00, 40.00,    -- 供水
    2.00, 8.00,     -- 温差
    95.00, 105.00,  -- 散热量
    0.50, 0.80, 2.00,  -- 阈值
    5, 0.60         -- 寻优周期, R²阈值
);

-- =====================================================
-- 冷冻侧优化配置表（可动态修改的约束）
-- =====================================================
CREATE TABLE chilled_opt_config (
    id SERIAL PRIMARY KEY,

    -- 冷冻水回水温度范围
    return_temp_lower_limit DECIMAL(5,2) DEFAULT 9.00,
    return_temp_upper_limit DECIMAL(5,2) DEFAULT 15.00,

    -- 冷冻水供水温度范围
    supply_temp_lower_limit DECIMAL(5,2) DEFAULT 7.00,
    supply_temp_upper_limit DECIMAL(5,2) DEFAULT 10.00,

    -- 冷冻水温差范围
    temp_diff_lower_limit DECIMAL(5,2) DEFAULT 4.00,
    temp_diff_upper_limit DECIMAL(5,2) DEFAULT 6.00,

    -- 阈值参数
    supply_temp_threshold DECIMAL(5,2) DEFAULT 0.50,
    temp_diff_threshold DECIMAL(5,2) DEFAULT 0.80,
    energy_saving_threshold DECIMAL(5,2) DEFAULT 2.00,

    -- 寻优周期（分钟）
    optimization_cycle_minutes INTEGER DEFAULT 5,

    -- R² 阈值
    r2_threshold DECIMAL(3,2) DEFAULT 0.60,

    -- 约束
    CONSTRAINT ck_chilled_return_temp_range CHECK (return_temp_upper_limit >= return_temp_lower_limit),
    CONSTRAINT ck_chilled_supply_temp_range CHECK (supply_temp_upper_limit >= supply_temp_lower_limit),
    CONSTRAINT ck_chilled_temp_diff_range CHECK (temp_diff_upper_limit >= temp_diff_lower_limit),
    CONSTRAINT ck_chilled_supply_threshold_nonnegative CHECK (supply_temp_threshold >= 0),
    CONSTRAINT ck_chilled_temp_diff_threshold_nonnegative CHECK (temp_diff_threshold >= 0),
    CONSTRAINT ck_chilled_energy_threshold_nonnegative CHECK (energy_saving_threshold >= 0),
    CONSTRAINT ck_chilled_opt_cycle_positive CHECK (optimization_cycle_minutes > 0),
    CONSTRAINT ck_chilled_r2_threshold_range CHECK (r2_threshold >= 0 AND r2_threshold <= 1)
);

-- 字段注释
COMMENT ON COLUMN chilled_opt_config.return_temp_lower_limit IS '冷冻水回水温度下限(℃)';
COMMENT ON COLUMN chilled_opt_config.return_temp_upper_limit IS '冷冻水回水温度上限(℃)';
COMMENT ON COLUMN chilled_opt_config.supply_temp_lower_limit IS '冷冻水供水温度下限(℃)';
COMMENT ON COLUMN chilled_opt_config.supply_temp_upper_limit IS '冷冻水供水温度上限(℃)';
COMMENT ON COLUMN chilled_opt_config.temp_diff_lower_limit IS '冷冻水温差下限(℃)';
COMMENT ON COLUMN chilled_opt_config.temp_diff_upper_limit IS '冷冻水温差上限(℃)';
COMMENT ON COLUMN chilled_opt_config.supply_temp_threshold IS '冷冻水供水温度阈值(℃) ≥ ±0.5';
COMMENT ON COLUMN chilled_opt_config.temp_diff_threshold IS '冷冻水温差阈值(℃) ≥ ±0.8';
COMMENT ON COLUMN chilled_opt_config.energy_saving_threshold IS '节能率阈值(%) ≥2';
COMMENT ON COLUMN chilled_opt_config.optimization_cycle_minutes IS '寻优周期（分钟）';
COMMENT ON COLUMN chilled_opt_config.r2_threshold IS '模型R²阈值，低于此值时预测值标记为不可信';

-- 初始化默认配置（id=1）
INSERT INTO chilled_opt_config (
    id,
    return_temp_lower_limit, return_temp_upper_limit,
    supply_temp_lower_limit, supply_temp_upper_limit,
    temp_diff_lower_limit, temp_diff_upper_limit,
    supply_temp_threshold, temp_diff_threshold, energy_saving_threshold,
    optimization_cycle_minutes, r2_threshold
) VALUES (
    1,
    9.00, 15.00,    -- 回水
    7.00, 10.00,    -- 供水
    4.00, 6.00,     -- 温差
    0.50, 0.80, 2.00,  -- 阈值
    5, 0.60         -- 寻优周期, R²阈值
);

-- =====================================================
-- 冷却侧优化参数记录表（总功率模型版本）
-- =====================================================
CREATE TABLE cooling_opt_parameters_total (
    id SERIAL PRIMARY KEY,
    optimization_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    applied BOOLEAN DEFAULT FALSE,

    -- 心跳检测字段
    heartbeat_timestamp TIMESTAMP,
    heartbeat_state SMALLINT DEFAULT 0,

    -- 使用参数（优化时使用的配置）
    return_temp_lower_limit DECIMAL(5,2),
    return_temp_upper_limit DECIMAL(5,2),
    supply_temp_lower_limit DECIMAL(5,2),
    supply_temp_upper_limit DECIMAL(5,2),
    temp_diff_lower_limit DECIMAL(5,2),
    temp_diff_upper_limit DECIMAL(5,2),
    heat_dissipation_lower_limit DECIMAL(5,2),
    heat_dissipation_upper_limit DECIMAL(5,2),

    -- 优化前当前值
    current_total_power DECIMAL(8,2),
    current_host_total_power DECIMAL(8,2),
    current_cooling_tower_total_power DECIMAL(8,2),
    current_cooling_pump_total_power DECIMAL(8,2),
    current_supply_temp DECIMAL(5,2),
    current_return_temp DECIMAL(5,2),
    current_temp_diff DECIMAL(5,2),
    current_heat_dissipation DECIMAL(5,2),

    -- 优化后结果
    optimized_total_power DECIMAL(8,2),
    optimized_host_total_power DECIMAL(8,2),
    optimized_cooling_tower_total_power DECIMAL(8,2),
    optimized_cooling_pump_total_power DECIMAL(8,2),
    optimized_supply_temp DECIMAL(5,2),
    optimized_return_temp DECIMAL(5,2),
    optimized_temp_diff DECIMAL(5,2),
    optimized_heat_dissipation DECIMAL(5,2),

    -- 优化后是否可以下发的标记位
    optimized_return_temp_applied BOOLEAN DEFAULT FALSE,
    optimized_temp_diff_applied BOOLEAN DEFAULT FALSE,

    -- 下发失败原因
    failure_reasons TEXT,

    -- 差值
    diff_total_power DECIMAL(8,2),
    diff_host_total_power DECIMAL(8,2),
    diff_cooling_tower_total_power DECIMAL(8,2),
    diff_cooling_pump_total_power DECIMAL(8,2),
    diff_supply_temp DECIMAL(5,2),
    diff_return_temp DECIMAL(5,2),
    diff_temp_diff DECIMAL(5,2),
    diff_heat_dissipation DECIMAL(5,2),

    -- 百分比差值
    percent_total_power DECIMAL(5,2),
    percent_host_total_power DECIMAL(5,2),
    percent_cooling_tower_total_power DECIMAL(5,2),
    percent_cooling_pump_total_power DECIMAL(5,2),

    -- 统计信息
    total_energy_saving DECIMAL(8,2),
    energy_saving_percent DECIMAL(5,2),

    remarks TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_cooling_opt_total_timestamp ON cooling_opt_parameters_total(optimization_timestamp DESC);
CREATE INDEX idx_cooling_opt_total_applied ON cooling_opt_parameters_total(applied);
CREATE INDEX idx_cooling_opt_total_energy_saving ON cooling_opt_parameters_total(total_energy_saving DESC);
CREATE INDEX idx_cooling_opt_total_heartbeat ON cooling_opt_parameters_total(heartbeat_timestamp DESC);

-- 字段注释
COMMENT ON COLUMN cooling_opt_parameters_total.optimization_timestamp IS '优化时间戳';
COMMENT ON COLUMN cooling_opt_parameters_total.applied IS '是否已应用该优化';
COMMENT ON COLUMN cooling_opt_parameters_total.heartbeat_timestamp IS '最后一次心跳时间';
COMMENT ON COLUMN cooling_opt_parameters_total.heartbeat_state IS '心跳状态（0/1翻转）';
COMMENT ON COLUMN cooling_opt_parameters_total.optimized_return_temp_applied IS '优化冷却水回水温度是否可以下发';
COMMENT ON COLUMN cooling_opt_parameters_total.optimized_temp_diff_applied IS '优化冷却水温差是否可以下发';
COMMENT ON COLUMN cooling_opt_parameters_total.failure_reasons IS '下发失败原因（多条用分号分隔）';
-- （其他字段注释可根据需要添加）

-- =====================================================
-- 冷冻侧优化参数记录表（总功率模型版本）
-- =====================================================
CREATE TABLE chilled_opt_parameters_total (
    id SERIAL PRIMARY KEY,
    optimization_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    applied BOOLEAN DEFAULT FALSE,

    -- 心跳检测字段
    heartbeat_timestamp TIMESTAMP,
    heartbeat_state SMALLINT DEFAULT 0,

    -- 使用参数（优化时使用的配置）
    return_temp_lower_limit DECIMAL(5,2),
    return_temp_upper_limit DECIMAL(5,2),
    supply_temp_lower_limit DECIMAL(5,2),
    supply_temp_upper_limit DECIMAL(5,2),
    temp_diff_lower_limit DECIMAL(5,2),
    temp_diff_upper_limit DECIMAL(5,2),

    -- 优化前当前值
    current_total_power DECIMAL(8,2),
    current_host_total_power DECIMAL(8,2),
    current_chilled_pump_total_power DECIMAL(8,2),
    current_supply_temp DECIMAL(5,2),
    current_return_temp DECIMAL(5,2),
    current_temp_diff DECIMAL(5,2),

    -- 优化后结果
    optimized_total_power DECIMAL(8,2),
    optimized_host_total_power DECIMAL(8,2),
    optimized_chilled_pump_total_power DECIMAL(8,2),
    optimized_supply_temp DECIMAL(5,2),
    optimized_return_temp DECIMAL(5,2),
    optimized_temp_diff DECIMAL(5,2),

    -- 优化后是否可以下发的标记位
    optimized_supply_temp_applied BOOLEAN DEFAULT FALSE,
    optimized_temp_diff_applied BOOLEAN DEFAULT FALSE,

    -- 下发失败原因
    failure_reasons TEXT,

    -- 差值
    diff_total_power DECIMAL(8,2),
    diff_host_total_power DECIMAL(8,2),
    diff_chilled_pump_total_power DECIMAL(8,2),
    diff_supply_temp DECIMAL(5,2),
    diff_return_temp DECIMAL(5,2),
    diff_temp_diff DECIMAL(5,2),

    -- 百分比差值
    percent_total_power DECIMAL(5,2),
    percent_host_total_power DECIMAL(5,2),
    percent_chilled_pump_total_power DECIMAL(5,2),

    -- 统计信息
    total_energy_saving DECIMAL(8,2),
    energy_saving_percent DECIMAL(5,2),

    remarks TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引
CREATE INDEX idx_chilled_opt_total_timestamp ON chilled_opt_parameters_total(optimization_timestamp DESC);
CREATE INDEX idx_chilled_opt_total_applied ON chilled_opt_parameters_total(applied);
CREATE INDEX idx_chilled_opt_total_energy_saving ON chilled_opt_parameters_total(total_energy_saving DESC);
CREATE INDEX idx_chilled_opt_total_heartbeat ON chilled_opt_parameters_total(heartbeat_timestamp DESC);

-- 字段注释
COMMENT ON COLUMN chilled_opt_parameters_total.optimization_timestamp IS '优化时间戳';
COMMENT ON COLUMN chilled_opt_parameters_total.applied IS '是否已应用该优化';
COMMENT ON COLUMN chilled_opt_parameters_total.heartbeat_timestamp IS '最后一次心跳时间';
COMMENT ON COLUMN chilled_opt_parameters_total.heartbeat_state IS '心跳状态（0/1翻转）';
COMMENT ON COLUMN chilled_opt_parameters_total.optimized_supply_temp_applied IS '优化冷冻水供水温度是否可以下发';
COMMENT ON COLUMN chilled_opt_parameters_total.optimized_temp_diff_applied IS '优化冷冻水温差是否可以下发';
COMMENT ON COLUMN chilled_opt_parameters_total.failure_reasons IS '下发失败原因（多条用分号分隔）';