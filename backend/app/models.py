# app/models.py - 简化版本
from sqlalchemy import (Column, Integer, String, Text, DateTime, ForeignKey, Boolean,
                        UniqueConstraint, Float, Interval, CheckConstraint,Numeric,Index,SmallInteger,JSON)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from .database import Base
import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, Text, DateTime, func


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    status = Column(String(20), default="active")
    tags = Column(ARRAY(String))
    device_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    devices = relationship("Device", back_populates="project", cascade="all, delete-orphan")


class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    identifier = Column(String(50), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="active")
    location = Column(String(200))
    device_metadata = Column(JSONB)
    model_version_id = Column(Integer, ForeignKey("device_model_versions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="devices")
    model_version = relationship("DeviceModelVersion", back_populates="devices")
    trainer_configs = relationship("TrainerConfig", back_populates="device", cascade="all, delete-orphan",
                                   passive_deletes=True)


class DeviceModel(Base):
    __tablename__ = "device_models"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    is_predefined = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    config_schema = Column(JSONB)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    versions = relationship("DeviceModelVersion", back_populates="model", cascade="all, delete-orphan")


class DeviceModelVersion(Base):
    __tablename__ = "device_model_versions"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    model_id = Column(Integer, ForeignKey("device_models.id", ondelete="CASCADE"), nullable=False)
    version = Column(String(20), nullable=False)
    description = Column(Text)
    config_schema = Column(JSONB)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    model = relationship("DeviceModel", back_populates="versions")
    devices = relationship("Device", back_populates="model_version")

    __table_args__ = (
        UniqueConstraint('model_id', 'version', name='uq_model_version'),
    )


class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False, index=True)
    data_type = Column(String(20), nullable=False)
    unit = Column(String(20))
    description = Column(Text)
    is_required = Column(Boolean, default=False)
    default_value = Column(Text)
    validation_rules = Column(JSONB)

    # 新增映射字段（可为空）
    data_source_id = Column(Integer, ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True)
    database_name = Column(String(100), nullable=True)
    table_name = Column(String(200), nullable=True)
    column_name = Column(String(100), default='PointValue')  # 默认值 'PointValue'
    timestamp_column = Column(String(100), default='UpdateDateTime')  # 默认值 'UpdateDateTime'

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ModelVersionFeature(Base):
    __tablename__ = "model_version_features"

    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("device_model_versions.id", ondelete="CASCADE"), nullable=False)
    feature_id = Column(Integer, ForeignKey("features.id", ondelete="CASCADE"), nullable=False)
    display_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_output = Column(Boolean, default=False, nullable=False, comment="标记是否为输出特征（可以多个）")
    is_primary_output = Column(Boolean, default=False, nullable=False,
                               comment="标记是否为主输出特征（每个版本只能有一个）")
    is_status = Column(Boolean, default=False, nullable=False, comment="标记是否为开关机状态特征")

    __table_args__ = (
        UniqueConstraint('version_id', 'feature_id', name='uq_version_feature'),
        # 使用部分唯一索引确保每个版本只有一个主输出
        CheckConstraint(
            "(is_primary_output = true) OR (is_primary_output = false)",
            name='ck_primary_output_or_not'
        ),
        # 可选：添加检查约束，确保主输出一定是输出
        CheckConstraint(
            "(is_primary_output = true AND is_output = true) OR (is_primary_output = false)",
            name='ck_primary_must_be_output'
        )
    )


class DeviceFeatureValue(Base):
    __tablename__ = "device_feature_values"
    timestamp = Column(DateTime(timezone=True), nullable=False, primary_key=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    feature_id = Column(Integer, ForeignKey("features.id", ondelete="CASCADE"), nullable=False, primary_key=True)
    # 将value从Text改为Float
    value = Column(Float, nullable=False)  # 原来是 Text
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # 添加关系
    device = relationship("Device")
    feature = relationship("Feature")


class DataSources(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    host = Column(String(100), nullable=False)
    port = Column(Integer, default=3306)
    database_name = Column(String(100), nullable=False)
    username = Column(String(100), nullable=False)
    password = Column(String(255))
    charset = Column(String(50), default='utf8mb4')
    timeout = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# ============ 关键修改：简化 FeatureTableMapping ============

class FeatureTableMapping(Base):
    __tablename__ = 'feature_table_mappings'

    id = Column(Integer, primary_key=True, index=True)
    data_source_id = Column(Integer, ForeignKey('data_sources.id'), nullable=False)
    database_name = Column(String(100), nullable=False)

    # 关键修改：不使用外键，只存储ID
    device_id = Column(Integer, nullable=False)  # 不再使用 ForeignKey

    feature_id = Column(Integer, ForeignKey('features.id'), nullable=False)
    table_name = Column(String(200), nullable=False)
    column_name = Column(String(100), default='PointValue')
    timestamp_column = Column(String(100), default='UpdateDateTime')
    is_active = Column(Boolean, default=True)
    sync_frequency = Column(Integer, default=15)
    last_sync_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 只保留简单的单向关系
    data_source = relationship("DataSources")
    feature = relationship("Feature")


class SyncHistory(Base):
    __tablename__ = 'sync_history'

    id = Column(Integer, primary_key=True, index=True)
    mapping_id = Column(Integer, ForeignKey('feature_table_mappings.id', ondelete="CASCADE"), nullable=False)
    sync_type = Column(String(20), nullable=False)
    records_count = Column(Integer)
    sync_duration = Column(Interval)
    status = Column(String(20), default='success')
    error_message = Column(Text)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    mapping = relationship("FeatureTableMapping")


# 设备模型训练信息模型
class DeviceModelTraining(Base):
    __tablename__ = "device_model_training"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)

    # 关联信息
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, unique=True)
    model_version_id = Column(Integer, ForeignKey("device_model_versions.id", ondelete="SET NULL"), nullable=True)

    # 训练配置
    model_type = Column(String(50), default='xgboost')
    last_trained_at = Column(DateTime(timezone=True), nullable=True)
    training_interval_minutes = Column(Integer, default=720)  # 默认12小时
    prediction_interval_minutes = Column(Integer, default=5)  # 默认5分钟

    # 状态信息
    training_status = Column(String(20), default='not_started')

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    device = relationship("Device", backref="training_info")
    model_version = relationship("DeviceModelVersion", backref="training_records")

    __table_args__ = (
        CheckConstraint(
            "training_status IN ('not_started', 'training', 'trained', 'failed')",
            name='ck_training_status'
        ),
        CheckConstraint(
            "training_interval_minutes > 0 AND prediction_interval_minutes > 0",
            name='ck_positive_intervals'
        ),
    )


class TrainingSchedule(Base):
    __tablename__ = "training_schedules"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)

    # 关联设备
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)


    # 计划类型：train（训练）或 predict（预测）
    schedule_type = Column(String(20), nullable=False)

    # 时间设置
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)  # None表示无限期

    # 间隔设置
    interval_value = Column(Integer, nullable=False)
    interval_unit = Column(String(10), nullable=False)  # minutes, hours, days

    # 状态
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)

    # 执行统计
    total_runs = Column(Integer, default=0)
    success_runs = Column(Integer, default=0)
    failed_runs = Column(Integer, default=0)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    device = relationship("Device", backref="training_schedules", passive_deletes=True)
    # 新增字段
    output_mode = Column(String(20), nullable=True)  # 'single' 或 'multi'
    output_count = Column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "schedule_type IN ('train', 'predict')",
            name='ck_schedule_type'
        ),
        CheckConstraint(
            "interval_unit IN ('minutes', 'hours', 'days')",
            name='ck_interval_unit'
        ),
        CheckConstraint(
            "interval_value > 0",
            name='ck_positive_interval'
        ),
        CheckConstraint(
            "end_time IS NULL OR end_time > start_time",
            name='ck_valid_time_range'
        ),
        CheckConstraint(
            "output_mode IN ('single', 'multi')",
            name='ck_output_mode'
        ),
        CheckConstraint(
            "output_count >= 1",
            name='ck_output_count_positive'
        ),
        # 当 schedule_type = 'predict' 时，这两个字段不能为空
        CheckConstraint(
            "(schedule_type != 'predict') OR (output_mode IS NOT NULL AND output_count IS NOT NULL)",
            name='ck_predict_output_not_null'
        ),
    )

#设备模型参数评估表
class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)

    # 基础 XGBoost 模型指标
    r_squared = Column(Numeric(10, 4), nullable=False)
    rmse = Column(Numeric(10, 4), nullable=False)
    mae = Column(Numeric(10, 4), nullable=False)

    # 新增：XGBoost+残差修正模型指标
    r_squared_residual = Column(Numeric(10, 4), nullable=True)
    rmse_residual = Column(Numeric(10, 4), nullable=True)
    mae_residual = Column(Numeric(10, 4), nullable=True)

    training_time = Column(Interval, nullable=False)
    training_data_size = Column(Integer, nullable=False)
    test_data_size = Column(Integer, nullable=False)
    feature_count = Column(Integer, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    device = relationship("Device", backref="model_evaluations")


class DeviceDataConfig(Base):
    __tablename__ = "device_data_configs"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)

    # 关联设备
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, unique=True)

    # 时间范围配置
    data_start_time = Column(DateTime(timezone=True), nullable=True)
    data_end_time = Column(DateTime(timezone=True), nullable=True)

    # 数据量配置
    max_rows_limit = Column(Integer, default=300000)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    device = relationship("Device", backref="data_config")

class TrainerConfig(Base):
    """训练器配置模型"""
    __tablename__ = "trainer_configs"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4, index=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    trainer_path = Column(String(500), nullable=False)
    trainer_type = Column(String(50), default="xgboost")
    is_primary = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, default=True)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    device = relationship("Device", back_populates="trainer_configs", passive_deletes=True)

    __table_args__ = (
        UniqueConstraint('device_id', 'trainer_path', name='uq_device_trainer_path'),
    )




class CoolingOptConfig(Base):
    """冷却侧优化配置表（可动态修改的约束）"""
    __tablename__ = "cooling_opt_config"

    id = Column(Integer, primary_key=True, index=True)
    # 冷却水回水温度范围
    return_temp_lower_limit = Column(Numeric(5, 2), default=1.00, comment="冷却水回水温度下限(℃) = 湿球温度+ n")
    return_temp_upper_limit = Column(Numeric(5, 2), default=32.00, comment="冷却水回水温度上限(℃)")
    # 冷却水供水温度范围
    supply_temp_lower_limit = Column(Numeric(5, 2), default=1.00, comment="冷却水供水温度下限(℃)= 湿球温度+ n")
    supply_temp_upper_limit = Column(Numeric(5, 2), default=40.00, comment="冷却水供水温度上限(℃)")
    # 冷却水温差范围
    temp_diff_lower_limit = Column(Numeric(5, 2), default=2.00, comment="冷却水温差下限(℃)")
    temp_diff_upper_limit = Column(Numeric(5, 2), default=8.00, comment="冷却水温差上限(℃)")
    # 散热量范围
    heat_dissipation_lower_limit = Column(Numeric(5, 2), default=95.00, comment="散热量下限(%)")
    heat_dissipation_upper_limit = Column(Numeric(5, 2), default=105.00, comment="散热量上限(%)")
    # 新增三个阈值参数
    return_temp_threshold = Column(Numeric(5, 2), default=0.50, comment="冷却水回水温度阈值(℃) ≥ ±0.5")
    temp_diff_threshold = Column(Numeric(5, 2), default=0.80, comment="冷却水温差阈值(℃) ≥ ±0.8")
    energy_saving_threshold = Column(Numeric(5, 2), default=2.00, comment="节能率阈值(%) ≥2")
    # 新增寻优周期（分钟）
    optimization_cycle_minutes = Column(Integer, default=5, comment="寻优周期（分钟）")
    r2_threshold = Column(Numeric(3, 2), default=0.60, nullable=False, comment="模型R²阈值")

    __table_args__ = (
        CheckConstraint("return_temp_upper_limit >= return_temp_lower_limit", name="ck_cooling_return_temp_range"),
        CheckConstraint("supply_temp_upper_limit >= supply_temp_lower_limit", name="ck_cooling_supply_temp_range"),
        CheckConstraint("temp_diff_upper_limit >= temp_diff_lower_limit", name="ck_cooling_temp_diff_range"),
        CheckConstraint("heat_dissipation_upper_limit >= heat_dissipation_lower_limit", name="ck_cooling_heat_dissipation_range"),
        # 新增阈值约束（确保为非负数）
        CheckConstraint("return_temp_threshold >= 0", name="ck_return_temp_threshold_nonnegative"),
        CheckConstraint("temp_diff_threshold >= 0", name="ck_temp_diff_threshold_nonnegative"),
        CheckConstraint("energy_saving_threshold >= 0", name="ck_energy_saving_threshold_nonnegative"),
        CheckConstraint("optimization_cycle_minutes >= 1", name="ck_optimization_cycle_positive"),
        CheckConstraint("r2_threshold >= 0 AND r2_threshold <= 1", name="ck_cooling_r2_threshold_range"),
    )



class CoolingOptParametersTotal(Base):
    """冷却侧优化参数记录表（总功率模型版本）"""
    __tablename__ = "cooling_opt_parameters_total"

    id = Column(Integer, primary_key=True, index=True)
    optimization_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="优化时间戳")
    applied = Column(Boolean, default=False, comment="是否已应用该优化")
    # 新增心跳字段
    heartbeat_timestamp = Column(DateTime(timezone=True), nullable=True, comment="最后一次心跳时间")
    heartbeat_state = Column(SmallInteger, default=0, comment="心跳状态（0/1翻转）")
    # 优化时使用的配置参数
    return_temp_lower_limit = Column(Numeric(5, 2), comment="冷却水回水温度下限(℃)")
    return_temp_upper_limit = Column(Numeric(5, 2), comment="冷却水回水温度上限(℃)")
    supply_temp_lower_limit = Column(Numeric(5, 2), comment="冷却水供水温度下限(℃)")
    supply_temp_upper_limit = Column(Numeric(5, 2), comment="冷却水供水温度上限(℃)")
    temp_diff_lower_limit = Column(Numeric(5, 2), comment="冷却水温差下限(℃)")
    temp_diff_upper_limit = Column(Numeric(5, 2), comment="冷却水温差上限(℃)")
    heat_dissipation_lower_limit = Column(Numeric(5, 2), comment="散热量下限(%)")
    heat_dissipation_upper_limit = Column(Numeric(5, 2), comment="散热量上限(%)")

    # 优化前当前值（总功率）
    current_total_power = Column(Numeric(8, 2), comment="当前系统总功率(kW)")
    current_host_total_power = Column(Numeric(8, 2), comment="当前主机总功率(kW)")
    current_cooling_tower_total_power = Column(Numeric(8, 2), comment="当前冷却塔总功率(kW)")
    current_cooling_pump_total_power = Column(Numeric(8, 2), comment="当前冷却泵总功率(kW)")
    current_supply_temp = Column(Numeric(5, 2), comment="当前冷却水供水温度(℃)")
    current_return_temp = Column(Numeric(5, 2), comment="当前冷却水回水温度(℃)")
    current_temp_diff = Column(Numeric(5, 2), comment="当前冷却水温差(℃)")
    current_heat_dissipation = Column(Numeric(5, 2), comment="当前散热量(%)")

    # 优化后结果（总功率）
    optimized_total_power = Column(Numeric(8, 2), comment="优化后系统总功率(kW)")
    optimized_host_total_power = Column(Numeric(8, 2), comment="优化后主机总功率(kW)")
    optimized_cooling_tower_total_power = Column(Numeric(8, 2), comment="优化后冷却塔总功率(kW)")
    optimized_cooling_pump_total_power = Column(Numeric(8, 2), comment="优化后冷却泵总功率(kW)")
    optimized_supply_temp = Column(Numeric(5, 2), comment="优化后冷却水供水温度(℃)")
    optimized_return_temp = Column(Numeric(5, 2), comment="优化后冷却水回水温度(℃)")
    optimized_temp_diff = Column(Numeric(5, 2), comment="优化后冷却水温差(℃)")
    optimized_heat_dissipation = Column(Numeric(5, 2), comment="优化后散热量(%)")

    # 差值
    diff_total_power = Column(Numeric(8, 2), comment="系统总功率差值(kW)")
    diff_host_total_power = Column(Numeric(8, 2), comment="主机总功率差值(kW)")
    diff_cooling_tower_total_power = Column(Numeric(8, 2), comment="冷却塔总功率差值(kW)")
    diff_cooling_pump_total_power = Column(Numeric(8, 2), comment="冷却泵总功率差值(kW)")
    diff_supply_temp = Column(Numeric(5, 2), comment="冷却水供水温度差值(℃)")
    diff_return_temp = Column(Numeric(5, 2), comment="冷却水回水温度差值(℃)")
    diff_temp_diff = Column(Numeric(5, 2), comment="冷却水温差差值(℃)")
    diff_heat_dissipation = Column(Numeric(5, 2), comment="散热量差值(%)")

    # 百分比差值
    percent_total_power = Column(Numeric(5, 2), comment="系统总功率节省百分比(%)")
    percent_host_total_power = Column(Numeric(5, 2), comment="主机总功率节省百分比(%)")
    percent_cooling_tower_total_power = Column(Numeric(5, 2), comment="冷却塔总功率节省百分比(%)")
    percent_cooling_pump_total_power = Column(Numeric(5, 2), comment="冷却泵总功率节省百分比(%)")

    # 统计信息
    total_energy_saving = Column(Numeric(8, 2), comment="预计总节能(kW)")
    energy_saving_percent = Column(Numeric(5, 2), comment="节能比例(%)")

    remarks = Column(Text, comment="备注")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # ---------- 新增下发标记字段 ----------
    optimized_return_temp_applied = Column(Boolean, default=False, comment="优化冷却水回水温度是否可以下发")
    optimized_temp_diff_applied = Column(Boolean, default=False, comment="优化冷却水温差是否可以下发")
    failure_reasons = Column(Text, nullable=True, comment="下发失败原因（多条用分号分隔）")

    __table_args__ = (
        Index("idx_cooling_opt_total_timestamp", optimization_timestamp.desc()),
        Index("idx_cooling_opt_total_applied", applied),
        Index("idx_cooling_opt_total_energy_saving", total_energy_saving.desc()),
    )


class ChilledOptConfig(Base):
    """冷冻水优化配置表（可动态修改的约束）"""
    __tablename__ = "chilled_opt_config"

    id = Column(Integer, primary_key=True, index=True)
    # 冷冻水回水温度范围
    return_temp_lower_limit = Column(Numeric(5, 2), default=9.00, comment="冷冻水回水温度下限(℃)")
    return_temp_upper_limit = Column(Numeric(5, 2), default=15.00, comment="冷冻水回水温度上限(℃)")
    # 冷冻水供水温度范围
    supply_temp_lower_limit = Column(Numeric(5, 2), default=7.00, comment="冷冻水供水温度下限(℃)")
    supply_temp_upper_limit = Column(Numeric(5, 2), default=10.00, comment="冷冻水供水温度上限(℃)")
    # 冷冻水温差范围
    temp_diff_lower_limit = Column(Numeric(5, 2), default=4.00, comment="冷冻水温差下限(℃)")
    temp_diff_upper_limit = Column(Numeric(5, 2), default=6.00, comment="冷冻水温差上限(℃)")
    # 新增三个阈值参数
    supply_temp_threshold = Column(Numeric(5, 2), default=0.50, comment="冷冻水供水温度阈值(℃) ≥ ±0.5")
    temp_diff_threshold = Column(Numeric(5, 2), default=0.80, comment="冷冻水温差阈值(℃) ≥ ±0.8")
    energy_saving_threshold = Column(Numeric(5, 2), default=2.00, comment="节能率阈值(%) ≥2")

    # 新增寻优周期（分钟）
    optimization_cycle_minutes = Column(Integer, default=5, comment="寻优周期（分钟）")
    r2_threshold = Column(Numeric(3, 2), default=0.60, nullable=False, comment="模型R²阈值")




    __table_args__ = (
        CheckConstraint("return_temp_upper_limit >= return_temp_lower_limit", name="ck_chilled_return_temp_range"),
        CheckConstraint("supply_temp_upper_limit >= supply_temp_lower_limit", name="ck_chilled_supply_temp_range"),
        CheckConstraint("temp_diff_upper_limit >= temp_diff_lower_limit", name="ck_chilled_temp_diff_range"),
        # 新增阈值非负约束
        CheckConstraint("supply_temp_threshold >= 0", name="ck_chilled_supply_threshold_nonnegative"),
        CheckConstraint("temp_diff_threshold >= 0", name="ck_chilled_temp_diff_threshold_nonnegative"),
        CheckConstraint("energy_saving_threshold >= 0", name="ck_chilled_energy_threshold_nonnegative"),
        CheckConstraint("optimization_cycle_minutes >= 1", name="ck_chilled_optimization_cycle_positive"),
        CheckConstraint("r2_threshold >= 0 AND r2_threshold <= 1", name="ck_chilled_r2_threshold_range"),
    )


class ChilledOptParametersTotal(Base):
    """冷冻水优化参数记录表（总功率模型版本）"""
    __tablename__ = "chilled_opt_parameters_total"

    id = Column(Integer, primary_key=True, index=True)
    optimization_timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment="优化时间戳")
    applied = Column(Boolean, default=False, comment="是否已应用该优化")

    # 新增心跳字段
    heartbeat_timestamp = Column(DateTime(timezone=True), nullable=True, comment="最后一次心跳时间")
    heartbeat_state = Column(SmallInteger, default=0, comment="心跳状态（0/1翻转）")
    # 优化时使用的配置参数
    return_temp_lower_limit = Column(Numeric(5, 2), comment="冷冻水回水温度下限(℃)")
    return_temp_upper_limit = Column(Numeric(5, 2), comment="冷冻水回水温度上限(℃)")
    supply_temp_lower_limit = Column(Numeric(5, 2), comment="冷冻水供水温度下限(℃)")
    supply_temp_upper_limit = Column(Numeric(5, 2), comment="冷冻水供水温度上限(℃)")
    temp_diff_lower_limit = Column(Numeric(5, 2), comment="冷冻水温差下限(℃)")
    temp_diff_upper_limit = Column(Numeric(5, 2), comment="冷冻水温差上限(℃)")

    # 优化前当前值（总功率）
    current_total_power = Column(Numeric(8, 2), comment="当前系统总功率(kW)")
    current_host_total_power = Column(Numeric(8, 2), comment="当前主机总功率(kW)")
    current_chilled_pump_total_power = Column(Numeric(8, 2), comment="当前冷冻泵总功率(kW)")
    current_supply_temp = Column(Numeric(5, 2), comment="当前冷冻水供水温度(℃)")
    current_return_temp = Column(Numeric(5, 2), comment="当前冷冻水回水温度(℃)")
    current_temp_diff = Column(Numeric(5, 2), comment="当前冷冻水温差(℃)")

    # 优化后结果（总功率）
    optimized_total_power = Column(Numeric(8, 2), comment="优化后系统总功率(kW)")
    optimized_host_total_power = Column(Numeric(8, 2), comment="优化后主机总功率(kW)")
    optimized_chilled_pump_total_power = Column(Numeric(8, 2), comment="优化后冷冻泵总功率(kW)")
    optimized_supply_temp = Column(Numeric(5, 2), comment="优化后冷冻水供水温度(℃)")
    optimized_return_temp = Column(Numeric(5, 2), comment="优化后冷冻水回水温度(℃)")
    optimized_temp_diff = Column(Numeric(5, 2), comment="优化后冷冻水温差(℃)")

    # 差值
    diff_total_power = Column(Numeric(8, 2), comment="系统总功率差值(kW)")
    diff_host_total_power = Column(Numeric(8, 2), comment="主机总功率差值(kW)")
    diff_chilled_pump_total_power = Column(Numeric(8, 2), comment="冷冻泵总功率差值(kW)")
    diff_supply_temp = Column(Numeric(5, 2), comment="冷冻水供水温度差值(℃)")
    diff_return_temp = Column(Numeric(5, 2), comment="冷冻水回水温度差值(℃)")
    diff_temp_diff = Column(Numeric(5, 2), comment="冷冻水温差差值(℃)")

    # 百分比差值
    percent_total_power = Column(Numeric(5, 2), comment="系统总功率节省百分比(%)")
    percent_host_total_power = Column(Numeric(5, 2), comment="主机总功率节省百分比(%)")
    percent_chilled_pump_total_power = Column(Numeric(5, 2), comment="冷冻泵总功率节省百分比(%)")

    # 统计信息
    total_energy_saving = Column(Numeric(8, 2), comment="预计总节能(kW)")
    energy_saving_percent = Column(Numeric(5, 2), comment="节能比例(%)")

    remarks = Column(Text, comment="备注")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # ---------- 新增下发标记字段 ----------
    optimized_supply_temp_applied = Column(Boolean, default=False, comment="优化冷冻水供水温度是否可以下发")
    optimized_temp_diff_applied = Column(Boolean, default=False, comment="优化冷冻水温差是否可以下发")
    failure_reasons = Column(Text, nullable=True, comment="下发失败原因（多条用分号分隔）")

    __table_args__ = (
        Index("idx_chilled_opt_total_timestamp", optimization_timestamp.desc()),
        Index("idx_chilled_opt_total_applied", applied),
        Index("idx_chilled_opt_total_energy_saving", total_energy_saving.desc()),
    )

class ChatConversation(Base):
    __tablename__ = "chat_conversations"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), default="新对话")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    messages = relationship("ChatMessage", back_populates="conversation")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"))
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    msg_metadata = Column(JSON, default={})  # 原来叫 metadata，已重命名
    created_at = Column(DateTime, default=datetime.utcnow)
    conversation = relationship("ChatConversation", back_populates="messages")

class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255), nullable=False, comment="文档来源文件名")
    content = Column(Text, nullable=False, comment="文本块内容")
    embedding = Column(Vector(768), nullable=False, comment="文本嵌入向量（768维）")
    chunk_index = Column(Integer, default=0, comment="原文件中的分块序号")
    created_at = Column(DateTime, server_default=func.now())
    file_id = Column(Integer, ForeignKey("knowledge_files.id"), nullable=False)


class KnowledgeFile(Base):
    __tablename__ = "knowledge_files"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    original_name = Column(String(255), nullable=False, comment="原始文件名")
    stored_path = Column(String(500), nullable=False, comment="服务器存储路径")
    file_size = Column(Integer, default=0, comment="文件大小（字节）")
    description = Column(Text, nullable=True, comment="文件描述")
    status = Column(String(20), default="pending", comment="状态: pending, indexing, completed, failed")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now(), nullable=True)