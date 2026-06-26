-- 1. 先启用扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- 1. 项目表
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    name VARCHAR(100) NOT NULL,                    -- 项目名称
    code VARCHAR(50) UNIQUE NOT NULL,              -- 项目代码，全局唯一
    description TEXT,                              -- 项目描述
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive')), -- 状态：使用中、未使用
    tags TEXT[],                                   -- 标签数组
    device_count INTEGER DEFAULT 0,                -- 设备数量（统计用）
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 约束：项目代码格式（字母、数字、下划线）
    CONSTRAINT chk_project_code_format CHECK (code ~* '^[A-Za-z0-9_]+$'),
    -- 约束：项目名称不能为空
    CONSTRAINT chk_project_name_length CHECK (LENGTH(name) >= 1)
);
-- 2. 设备模型表（存储设备模型定义）
CREATE TABLE IF NOT EXISTS device_models (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_predefined BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    config_schema JSONB,

    CONSTRAINT chk_model_code_format CHECK (code ~* '^[A-Za-z0-9_]+$')
);

COMMENT ON TABLE device_models IS '设备模型表：存储系统预定义和用户自定义的设备模型定义';
-- 3. 设备模型版本表
CREATE TABLE IF NOT EXISTS device_model_versions (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    model_id INTEGER NOT NULL REFERENCES device_models(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    config_schema JSONB,

    UNIQUE(model_id, version)
);

COMMENT ON TABLE device_model_versions IS '设备模型版本表：存储每个设备模型的不同版本信息';
-- 4. 设备表（用于统计设备数量）
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,                    -- 设备名称
    identifier VARCHAR(50) NOT NULL,               -- 设备标识符（项目内唯一）
    description TEXT,                              -- 设备描述
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive')), -- 设备状态
    location VARCHAR(200),                         -- 设备位置
    device_metadata JSONB,                         -- 元数据

    -- 新增字段：关联的模型版本ID
    model_version_id INTEGER REFERENCES device_model_versions(id) ON DELETE SET NULL,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 同一项目内设备标识符必须唯一
    CONSTRAINT uq_project_identifier UNIQUE(project_id, identifier),

    -- 约束：设备标识符格式
    CONSTRAINT chk_device_identifier_format CHECK (identifier ~* '^[A-Za-z0-9_-]+$'),

    -- 外键约束：关联设备模型版本
    CONSTRAINT fk_devices_model_version_id
        FOREIGN KEY (model_version_id)
        REFERENCES device_model_versions(id)
        ON DELETE SET NULL
);

-- 表注释
COMMENT ON TABLE devices IS '设备表：存储项目中的物理设备信息';
COMMENT ON COLUMN devices.id IS '设备ID';
COMMENT ON COLUMN devices.uuid IS '设备全局唯一标识';
COMMENT ON COLUMN devices.project_id IS '所属项目ID';
COMMENT ON COLUMN devices.name IS '设备名称';
COMMENT ON COLUMN devices.identifier IS '设备标识符（项目内唯一）';
COMMENT ON COLUMN devices.description IS '设备描述';
COMMENT ON COLUMN devices.status IS '设备状态（active/inactive）';
COMMENT ON COLUMN devices.location IS '设备位置';
COMMENT ON COLUMN devices.device_metadata IS '设备元数据（JSON格式）';
COMMENT ON COLUMN devices.model_version_id IS '关联的设备模型版本ID';
COMMENT ON COLUMN devices.created_at IS '创建时间';
COMMENT ON COLUMN devices.updated_at IS '更新时间';

-- 索引优化
CREATE INDEX IF NOT EXISTS idx_devices_project_id ON devices(project_id);
CREATE INDEX IF NOT EXISTS idx_devices_model_version_id ON devices(model_version_id);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,  -- 连接名称（如"生产数据库"）
    host VARCHAR(100) NOT NULL,  -- 主机地址（默认localhost）
    port INTEGER DEFAULT 3306,    -- 端口
    database_name VARCHAR(100) NOT NULL,  -- 数据库名
    username VARCHAR(100) NOT NULL,
    password VARCHAR(255),       -- 密码（实际应用中需加密存储，此处简化）
    charset VARCHAR(50) DEFAULT 'utf8mb4',
    timeout INTEGER DEFAULT 10,   -- 连接超时(秒)
    is_active BOOLEAN DEFAULT true,  -- 是否启用
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE data_sources IS '存储MySQL数据源配置，用于特征映射';
-- 5. 特征表（存储特征定义）
CREATE TABLE IF NOT EXISTS features (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(50) UNIQUE NOT NULL,
    data_type VARCHAR(20) NOT NULL,
    unit VARCHAR(20),
    description TEXT,
    is_required BOOLEAN DEFAULT false,
    default_value TEXT,
    validation_rules JSONB,
    -- 新增映射字段（可为空）
    data_source_id INTEGER REFERENCES data_sources(id) ON DELETE SET NULL,
    database_name VARCHAR(100),
    table_name VARCHAR(200),
    column_name VARCHAR(100) DEFAULT 'PointValue',
    timestamp_column VARCHAR(100) DEFAULT 'UpdateDateTime',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_feature_code_format CHECK (code ~* '^[A-Za-z0-9_]+$'),
    CONSTRAINT chk_data_type CHECK (data_type IN ('string', 'number', 'boolean', 'array'))
);

-- 6. 模型版本特征关联表（关联模型版本和需要的特征）
CREATE TABLE IF NOT EXISTS model_version_features (
    id SERIAL PRIMARY KEY,
    version_id INTEGER NOT NULL REFERENCES device_model_versions(id) ON DELETE CASCADE,
    feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 缺失的字段
    is_output BOOLEAN DEFAULT false NOT NULL,
    is_primary_output BOOLEAN DEFAULT false NOT NULL,
    is_status BOOLEAN DEFAULT false NOT NULL,

    -- 约束
    CONSTRAINT uq_version_feature UNIQUE(version_id, feature_id),
    CONSTRAINT ck_primary_must_be_output CHECK (
        (is_primary_output = true AND is_output = true) OR (is_primary_output = false)
    )
);

-- 字段注释
COMMENT ON TABLE model_version_features IS '模型版本特征关联表：定义每个设备模型版本需要哪些特征';
COMMENT ON COLUMN model_version_features.version_id IS '设备模型版本ID';
COMMENT ON COLUMN model_version_features.feature_id IS '特征ID';
COMMENT ON COLUMN model_version_features.display_order IS '显示顺序';
COMMENT ON COLUMN model_version_features.is_output IS '标记是否为输出特征（可以多个）';
COMMENT ON COLUMN model_version_features.is_primary_output IS '标记是否为主输出特征（每个版本只能有一个）';
COMMENT ON COLUMN model_version_features.is_status IS '标记是否为开关机状态特征';

-- 索引
CREATE INDEX IF NOT EXISTS idx_model_version_features_version_id ON model_version_features(version_id);
CREATE INDEX IF NOT EXISTS idx_model_version_features_feature_id ON model_version_features(feature_id);
CREATE INDEX IF NOT EXISTS idx_model_version_features_is_output ON model_version_features(is_output) WHERE is_output = true;
CREATE INDEX IF NOT EXISTS idx_model_version_features_is_primary_output ON model_version_features(is_primary_output) WHERE is_primary_output = true;

-- 7. 设备特征值表（存储每个设备的具体特征值）
-- 1. 启用TimescaleDB扩展
-- CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 2. 创建设备特征值核心表（最小化设计）
CREATE TABLE IF NOT EXISTS device_feature_values (
    -- 核心关联字段
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,

    -- 核心时序字段
    timestamp TIMESTAMPTZ NOT NULL,

    -- 【修改点】核心数据字段：改为 DOUBLE PRECISION 以优化数值计算和存储
    -- 注意：如果业务需要同时存储状态文本（如 "OPEN"/"CLOSED"），此设计将不再适用，需保留 TEXT 或拆分表
    value DOUBLE PRECISION NOT NULL,

    -- 审计字段：【新增】记录行创建时间
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,

    -- 复合主键
    PRIMARY KEY (device_id, feature_id, timestamp)
);


CREATE TABLE IF NOT EXISTS feature_column_mappings (
    id SERIAL PRIMARY KEY,
    data_source_id INTEGER NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,  -- 关联数据源
    table_name VARCHAR(100) NOT NULL,  -- MySQL表名（如"forecast_host1_power"）
    column_name VARCHAR(100) NOT NULL,  -- MySQL列名（如"PointValue"）
    feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,  -- 关联系统特征
    is_active BOOLEAN DEFAULT true,  -- 是否启用此映射
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (data_source_id, table_name, column_name)  -- 确保同一列不会重复映射
);

COMMENT ON TABLE feature_column_mappings IS '存储MySQL列到系统特征的映射关系，用于数据同步';

-- 特征值表
CREATE TABLE IF NOT EXISTS device_feature_values (
    timestamp TIMESTAMPTZ NOT NULL,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    value DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 主键：确保同一设备同一特征在同一时间只有一个值
    PRIMARY KEY (device_id, feature_id, timestamp)
);

-- 步骤3: 创建索引以支持不同查询模式
CREATE INDEX IF NOT EXISTS idx_dfv_timestamp_device ON device_feature_values(timestamp, device_id);
CREATE INDEX IF NOT EXISTS idx_dfv_feature_timestamp ON device_feature_values(feature_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_dfv_device_feature ON device_feature_values(device_id, feature_id);

-- 映射配置表
CREATE TABLE IF NOT EXISTS feature_table_mappings (
    id SERIAL PRIMARY KEY,
    data_source_id INTEGER NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    database_name VARCHAR(100) NOT NULL,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    table_name VARCHAR(200) NOT NULL,
    column_name VARCHAR(100) DEFAULT 'PointValue',  -- 特征值列名
    timestamp_column VARCHAR(100) DEFAULT 'UpdateDateTime',  -- 时间戳列名
    is_active BOOLEAN DEFAULT true,
    sync_frequency INTEGER DEFAULT 15,  -- 同步频率（分钟）
    last_sync_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 确保同一设备、同一特征不会重复映射
    UNIQUE(device_id, feature_id),
    -- 确保同一设备、数据源、数据库、表不会重复映射（同一设备不能将同一个表映射给不同特征，按需求可保留或调整）
    UNIQUE(device_id, data_source_id, database_name, table_name)
);

COMMENT ON TABLE feature_table_mappings IS '存储MySQL表列到设备特征的映射关系';

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_feature_table_mappings_data_source ON feature_table_mappings(data_source_id);
CREATE INDEX IF NOT EXISTS idx_feature_table_mappings_device ON feature_table_mappings(device_id);
CREATE INDEX IF NOT EXISTS idx_feature_table_mappings_feature ON feature_table_mappings(feature_id);
CREATE INDEX IF NOT EXISTS idx_feature_table_mappings_active ON feature_table_mappings(is_active);

-- 同步历史表
CREATE TABLE IF NOT EXISTS sync_history (
    id SERIAL PRIMARY KEY,
    mapping_id INTEGER NOT NULL REFERENCES feature_table_mappings(id) ON DELETE CASCADE,
    sync_type VARCHAR(20) NOT NULL,  -- 'manual' 或 'auto'
    records_count INTEGER,
    sync_duration INTERVAL,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,

    CONSTRAINT chk_sync_type CHECK (sync_type IN ('manual', 'auto')),
    CONSTRAINT chk_status CHECK (status IN ('success', 'failed', 'partial'))
);

COMMENT ON TABLE sync_history IS '存储数据同步历史记录';
-- 模型评估表（存储模型训练后的评估指标）
CREATE TABLE IF NOT EXISTS model_evaluations (
    id SERIAL PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE, -- 关联到模型表
    r_squared DECIMAL(10, 4) NOT NULL,        -- R²分数
    rmse DECIMAL(10, 4) NOT NULL,             -- RMSE
    mae DECIMAL(10, 4) NOT NULL,              -- MAE
    -- 新增的残差相关指标列
    r_squared_residual DECIMAL(10, 4),
    rmse_residual DECIMAL(10, 4),
    mae_residual DECIMAL(10, 4),
    training_time INTERVAL NOT NULL,          -- 训练时间
    training_data_size INTEGER NOT NULL,      -- 训练数据量
    test_data_size INTEGER NOT NULL,          -- 测试数据量
    feature_count INTEGER NOT NULL,           -- 特征数量
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS data_sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,  -- 连接名称（如"生产数据库"）
    host VARCHAR(100) NOT NULL,  -- 主机地址（默认localhost）
    port INTEGER DEFAULT 3306,    -- 端口
    database_name VARCHAR(100) NOT NULL,  -- 数据库名
    username VARCHAR(100) NOT NULL,
    password VARCHAR(255),       -- 密码（实际应用中需加密存储，此处简化）
    charset VARCHAR(50) DEFAULT 'utf8mb4',
    timeout INTEGER DEFAULT 10,   -- 连接超时(秒)
    is_active BOOLEAN DEFAULT true,  -- 是否启用
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE data_sources IS '存储MySQL数据源配置，用于特征映射';

CREATE TABLE IF NOT EXISTS feature_column_mappings (
    id SERIAL PRIMARY KEY,
    data_source_id INTEGER NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,  -- 关联数据源
    table_name VARCHAR(100) NOT NULL,  -- MySQL表名（如"forecast_host1_power"）
    column_name VARCHAR(100) NOT NULL,  -- MySQL列名（如"PointValue"）
    feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,  -- 关联系统特征
    is_active BOOLEAN DEFAULT true,  -- 是否启用此映射
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (data_source_id, table_name, column_name)  -- 确保同一列不会重复映射
);

COMMENT ON TABLE feature_column_mappings IS '存储MySQL列到系统特征的映射关系，用于数据同步';

-- 特征值表
CREATE TABLE IF NOT EXISTS device_feature_values (
    timestamp TIMESTAMPTZ NOT NULL,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    value DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 主键：确保同一设备同一特征在同一时间只有一个值
    PRIMARY KEY (device_id, feature_id, timestamp)
);

-- 步骤3: 创建索引以支持不同查询模式
CREATE INDEX IF NOT EXISTS idx_dfv_timestamp_device ON device_feature_values(timestamp, device_id);
CREATE INDEX IF NOT EXISTS idx_dfv_feature_timestamp ON device_feature_values(feature_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_dfv_device_feature ON device_feature_values(device_id, feature_id);

-- 映射配置表
CREATE TABLE IF NOT EXISTS feature_table_mappings (
    id SERIAL PRIMARY KEY,
    data_source_id INTEGER NOT NULL REFERENCES data_sources(id) ON DELETE CASCADE,
    database_name VARCHAR(100) NOT NULL,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    table_name VARCHAR(200) NOT NULL,
    column_name VARCHAR(100) DEFAULT 'PointValue',  -- 特征值列名
    timestamp_column VARCHAR(100) DEFAULT 'UpdateDateTime',  -- 时间戳列名
    is_active BOOLEAN DEFAULT true,
    sync_frequency INTEGER DEFAULT 15,  -- 同步频率（分钟）
    last_sync_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 确保同一设备、同一特征不会重复映射
    UNIQUE(device_id, feature_id),
    -- 确保同一数据源、数据库、表的同一列不会重复映射


    UNIQUE(data_source_id, database_name, table_name, column_name)
);

COMMENT ON TABLE feature_table_mappings IS '存储MySQL表列到设备特征的映射关系';

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_feature_table_mappings_data_source ON feature_table_mappings(data_source_id);
CREATE INDEX IF NOT EXISTS idx_feature_table_mappings_device ON feature_table_mappings(device_id);
CREATE INDEX IF NOT EXISTS idx_feature_table_mappings_feature ON feature_table_mappings(feature_id);
CREATE INDEX IF NOT EXISTS idx_feature_table_mappings_active ON feature_table_mappings(is_active);

-- 同步历史表
CREATE TABLE IF NOT EXISTS sync_history (
    id SERIAL PRIMARY KEY,
    mapping_id INTEGER NOT NULL REFERENCES feature_table_mappings(id) ON DELETE CASCADE,
    sync_type VARCHAR(20) NOT NULL,  -- 'manual' 或 'auto'
    records_count INTEGER,
    sync_duration INTERVAL,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,

    CONSTRAINT chk_sync_type CHECK (sync_type IN ('manual', 'auto')),
    CONSTRAINT chk_status CHECK (status IN ('success', 'failed', 'partial'))
);

COMMENT ON TABLE sync_history IS '存储数据同步历史记录';
-- ==================== 训练计划表 (training_schedules) ====================
CREATE TABLE IF NOT EXISTS training_schedules (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,

    -- 关联设备
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,

    -- 计划类型
    schedule_type VARCHAR(20) NOT NULL CHECK (schedule_type IN ('train', 'predict')),

    -- 时间设置
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ CHECK (end_time IS NULL OR end_time > start_time),

    -- 间隔设置
    interval_value INTEGER NOT NULL CHECK (interval_value > 0),
    interval_unit VARCHAR(10) NOT NULL CHECK (interval_unit IN ('minutes', 'hours', 'days')),

    -- 输出模式（新增）
    output_mode VARCHAR(20) CHECK (output_mode IN ('single', 'multi')),
    output_count INTEGER CHECK (output_count >= 1),

    -- 状态
    is_active BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,

    -- 执行统计
    total_runs INTEGER DEFAULT 0,
    success_runs INTEGER DEFAULT 0,
    failed_runs INTEGER DEFAULT 0,

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);


-- 设备模型训练信息表（最小实现）
CREATE TABLE IF NOT EXISTS device_model_training (
    id SERIAL PRIMARY KEY,
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,

    -- 关联信息
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    model_version_id INTEGER REFERENCES device_model_versions(id) ON DELETE SET NULL,

    -- 训练配置
    model_type VARCHAR(50) DEFAULT 'xgboost',
    last_trained_at TIMESTAMPTZ,  -- 最后训练时间
    training_interval_minutes INTEGER DEFAULT 720,  -- 训练间隔（分钟），默认12小时
    prediction_interval_minutes INTEGER DEFAULT 5,  -- 预测间隔（分钟），默认5分钟


    -- 状态信息
    training_status VARCHAR(20) DEFAULT 'not_started' CHECK (
        training_status IN ('not_started', 'training', 'trained', 'failed')
    ),

    -- 时间戳
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 约束和索引
    UNIQUE(device_id),  -- 一个设备对应一条训练记录
    CONSTRAINT chk_positive_intervals CHECK (
        training_interval_minutes > 0 AND prediction_interval_minutes > 0
    )
);

CREATE TABLE IF NOT EXISTS device_data_configs (
    id SERIAL PRIMARY KEY,                      -- 自动创建序列
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    device_id INTEGER NOT NULL UNIQUE REFERENCES devices(id) ON DELETE CASCADE,
    data_start_time TIMESTAMPTZ,
    data_end_time TIMESTAMPTZ,
    max_rows_limit INTEGER DEFAULT 300000 CHECK (max_rows_limit > 0),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_valid_time_range CHECK (data_end_time IS NULL OR data_start_time IS NULL OR data_end_time > data_start_time)
);

ALTER TABLE "public"."device_data_configs"
  OWNER TO "postgres";

CREATE INDEX "idx_device_data_configs_device" ON "public"."device_data_configs" USING btree (
  "device_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

COMMENT ON TABLE "public"."device_data_configs" IS '设备数据加载配置表，允许为每个设备单独配置数据加载参数';


CREATE TABLE IF NOT EXISTS trainer_configs (
    id SERIAL PRIMARY KEY,                          -- 自动创建序列
    uuid UUID DEFAULT uuid_generate_v4() UNIQUE,
    device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    trainer_path VARCHAR(500) NOT NULL,
    trainer_type VARCHAR(50) DEFAULT 'xgboost',
    is_primary BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    -- 同一设备下路径唯一
    CONSTRAINT trainer_configs_device_id_trainer_path_key UNIQUE (device_id, trainer_path),

    -- 路径格式校验（字母数字下划线加可选类名）
    CONSTRAINT chk_trainer_path_format CHECK (
        trainer_path ~ '^([a-zA-Z0-9_]+\.)*[a-zA-Z0-9_]+(\.[A-Z][a-zA-Z0-9_]*)?$'
    ),

    -- 确保每个设备最多只有一个主配置（is_primary = true）
    CONSTRAINT unique_primary_per_device EXCLUDE USING btree (device_id WITH =) WHERE (is_primary)
);

-- 索引（btree 索引可简化，但已有的 EXCLUDE 已为 device_id 创建索引）
CREATE INDEX IF NOT EXISTS idx_trainer_configs_active ON trainer_configs(is_active);
CREATE INDEX IF NOT EXISTS idx_trainer_configs_path ON trainer_configs(trainer_path);
