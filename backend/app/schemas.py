#app/shcemas.py
import pytz
from pydantic import BaseModel, Field, validator, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid as uuid_pkg
from uuid import UUID

# 基础模型
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="项目名称")
    code: str = Field(..., min_length=1, max_length=50, description="项目代码")
    description: Optional[str] = Field(None, description="项目描述")
    status: str = Field("active", description="项目状态")
    tags: Optional[List[str]] = Field(None, description="项目标签")

    @validator("code")
    def validate_code(cls, v):
        if not all(c.isalnum() or c == '_' for c in v):
            raise ValueError("项目代码只能包含字母、数字和下划线")
        return v

    @validator("status")
    def validate_status(cls, v):
        if v not in ["active", "inactive"]:
            raise ValueError("状态只能是 'active' 或 'inactive'")
        return v


# 创建项目
class ProjectCreate(ProjectBase):
    pass


# 更新项目
class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None


# 项目响应
class Project(ProjectBase):
    id: int
    uuid: uuid_pkg.UUID
    device_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 项目列表响应（包含分页信息）
class ProjectList(BaseModel):
    projects: List[Project]
    total: int
    page: int
    page_size: int
    total_pages: int
    overview: Optional[Dict[str, Any]] = None


# 项目统计
class ProjectStats(BaseModel):
    total_projects: int
    active_projects: int
    total_devices: int


# 设备基础模型
class DeviceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    identifier: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None
    status: str = Field("active")
    location: Optional[str] = None
    device_metadata: Optional[Dict[str, Any]] = None  # 改为 device_metadata


# 设备创建模型
class DeviceCreate(DeviceBase):
    project_id: int


# 设备响应
class Device(DeviceBase):
    id: int
    uuid: uuid_pkg.UUID
    project_id: int
    created_at: datetime
    updated_at: datetime
    last_predict_run_at: Optional[datetime] = None   # 新增

    class Config:
        from_attributes = True


# 设备列表响应
class DeviceList(BaseModel):
    devices: List[Device]
    total: int
    project_id: int
    project_name: str


# 设备列表分页响应
class DeviceListPaginated(BaseModel):
    devices: List[Device]
    total: int
    page: int
    page_size: int
    total_pages: int

# 设备模型相关模型
class DeviceModelBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="设备模型名称")
    code: str = Field(..., min_length=1, max_length=50, description="设备模型代码")
    description: Optional[str] = None
    is_predefined: bool = Field(False, description="是否为预定义模型")
    is_active: bool = Field(True, description="是否启用")
    config_schema: Optional[Dict[str, Any]] = Field(None, description="配置架构")

    @validator("code")
    def validate_code(cls, v):
        if not all(c.isalnum() or c == '_' for c in v):
            raise ValueError("设备模型代码只能包含字母、数字和下划线")
        return v


class DeviceModelCreate(DeviceModelBase):
    pass


class DeviceModelUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None
    is_predefined: Optional[bool] = None
    is_active: Optional[bool] = None
    config_schema: Optional[Dict[str, Any]] = None


class DeviceModel(DeviceModelBase):
    id: int
    uuid: uuid_pkg.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceModelList(BaseModel):
    device_models: List[DeviceModel]
    total: int
    page: int
    page_size: int
    total_pages: int


# 设备模型版本相关模型
class DeviceModelVersionBase(BaseModel):
    version: str = Field(..., min_length=1, max_length=20, description="版本号")
    description: Optional[str] = None
    config_schema: Optional[Dict[str, Any]] = Field(None, description="版本特定配置架构")
    is_active: bool = Field(True, description="是否启用")


class DeviceModelVersionCreate(DeviceModelVersionBase):
    model_id: int = Field(..., description="所属设备模型ID")


class DeviceModelVersionUpdate(BaseModel):
    version: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = None
    config_schema: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class DeviceModelVersion(DeviceModelVersionBase):
    id: int
    uuid: uuid_pkg.UUID
    model_id: int
    created_at: datetime
    updated_at: datetime
    model: Optional[DeviceModel] = None

    class Config:
        from_attributes = True


class DeviceModelVersionList(BaseModel):
    versions: List[DeviceModelVersion]
    total: int
    page: int
    page_size: int
    total_pages: int


# 特征相关模型
class FeatureBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="特征名称")
    code: str = Field(..., min_length=1, max_length=50, description="特征代码")
    data_type: str = Field(..., description="数据类型")
    unit: Optional[str] = Field(None, max_length=20, description="单位")
    description: Optional[str] = None
    is_required: bool = Field(False, description="是否必需")
    default_value: Optional[str] = None
    validation_rules: Optional[Dict[str, Any]] = Field(None, description="验证规则")

    # 新增映射字段（全部可选）
    data_source_id: Optional[int] = Field(None, description="数据源ID")
    database_name: Optional[str] = Field(None, description="数据库名")
    table_name: Optional[str] = Field(None, description="表名")
    column_name: Optional[str] = Field('PointValue', description="列名")
    timestamp_column: Optional[str] = Field('UpdateDateTime', description="时间戳列名")

    @validator("code")
    def validate_code(cls, v):
        if not all(c.isalnum() or c == '_' for c in v):
            raise ValueError("特征代码只能包含字母、数字和下划线")
        return v

    @validator("data_type")
    def validate_data_type(cls, v):
        if v not in ["string", "number", "boolean", "array"]:
            raise ValueError("数据类型必须是: string, number, boolean, array")
        return v


class FeatureCreate(FeatureBase):
    pass


class FeatureUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=50)
    data_type: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=20)
    description: Optional[str] = None
    is_required: Optional[bool] = None
    default_value: Optional[str] = None
    validation_rules: Optional[Dict[str, Any]] = None

    # 新增可空映射字段
    data_source_id: Optional[int] = Field(None, description="数据源ID")
    database_name: Optional[str] = Field(None, description="数据库名")
    table_name: Optional[str] = Field(None, description="表名")
    column_name: Optional[str] = Field(None, description="列名")
    timestamp_column: Optional[str] = Field(None, description="时间戳列名")

class Feature(FeatureBase):
    id: int
    uuid: uuid_pkg.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FeatureList(BaseModel):
    features: List[Feature]
    total: int
    page: int
    page_size: int
    total_pages: int


# 模型版本特征关联模型
class ModelVersionFeatureBase(BaseModel):
    feature_id: int = Field(..., description="特征ID")
    display_order: int = Field(0, description="显示顺序")


class ModelVersionFeatureCreate(ModelVersionFeatureBase):
    version_id: int = Field(..., description="模型版本ID")


class ModelVersionFeature(ModelVersionFeatureBase):
    id: int
    version_id: int
    created_at: datetime
    feature: Optional[Feature] = None
    is_output: bool = Field(default=False, description="是否为输出特征")
    is_status: bool = Field(default=False, description="是否为开关机状态特征")
    is_primary_output: bool = Field(default=False, description="是否为主输出特征（每个版本只能有一个）")
    class Config:
        from_attributes = True


class ModelVersionFeaturesUpdate(BaseModel):
    features: List[ModelVersionFeatureBase] = Field(..., description="特征列表")


# 设备特征值模型
class DeviceFeatureValueBase(BaseModel):
    feature_id: int = Field(..., description="特征ID")
    value: Optional[str] = None


class DeviceFeatureValueCreate(DeviceFeatureValueBase):
    device_id: int = Field(..., description="设备ID")


class DeviceFeatureValueUpdate(BaseModel):
    value: Optional[str] = None


class DeviceFeatureValue(DeviceFeatureValueBase):
    id: int
    device_id: int
    created_at: datetime
    updated_at: datetime
    feature: Optional[Feature] = None

    class Config:
        from_attributes = True


# 设备详情模型（包含模型和特征） 先查有哪些设备，设备都用了哪些模型以及版本，
class DeviceDetail(Device):
    model_version: Optional[DeviceModelVersion] = None
    feature_values: Optional[List[DeviceFeatureValue]] = None

    class Config:
        from_attributes = True

class DataSourceBase(BaseModel):
    name: str
    host: str
    port: int
    database_name: str
    username: str
    password: Optional[str] = None
    charset: str = "utf8mb4"
    timeout: int = 10
    status: str = "disconnected"
    is_active: bool = True

class DataSourceCreate(DataSourceBase):
    pass

class DataSourceUpdate(DataSourceBase):
    pass

class DataSource(DataSourceBase):
    id: int

    class Config:
        orm_mode = True

class DataSourceTest(BaseModel):
    host: str
    port: int
    database_name: str
    username: str
    password: Optional[str] = None
    charset: str = "utf8mb4"
    timeout: int = 10

class MappingBase(BaseModel):
    data_source_id: int
    database: str
    tables: Dict[str, Dict[str, bool]]  # {table_name: {feature_id: int, enabled: bool}}

class MappingCreate(MappingBase):
    pass

class Mapping(MappingBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class SyncRequest(BaseModel):
    data_source_id: int
    database: str

class HistoryCheck(BaseModel):
    start_date: str
    end_date: str
    data_source_id: int
    database: str

class HistoryImport(BaseModel):
    start_date: str
    end_date: str
    data_source_id: int
    database: str


# 特征映射创建模型
class FeatureMappingCreate(BaseModel):
    data_source_id: int = Field(..., description="数据源ID")
    database_name: str = Field(..., description="数据库名称")
    device_id: int = Field(..., description="设备ID")
    feature_id: int = Field(..., description="特征ID")
    table_name: str = Field(..., description="表名")
    column_name: Optional[str] = Field('PointValue', description="列名，默认为PointValue")
    timestamp_column: Optional[str] = Field('UpdateDateTime', description="时间戳列名，默认为UpdateDateTime")
    is_active: Optional[bool] = Field(True, description="是否启用")
    sync_frequency: Optional[int] = Field(15, description="同步频率（分钟）")


# 特征映射响应模型
class FeatureMapping(BaseModel):
    id: int
    data_source_id: int
    database_name: str
    device_id: int
    feature_id: int
    table_name: str
    column_name: str
    timestamp_column: str
    is_active: bool
    sync_frequency: int
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# 批量保存结果模型
class BatchSaveResult(BaseModel):
    feature_id: int
    status: str  # 'success' 或 'error'
    message: str
    mapping_id: Optional[int]


# 批量保存响应模型
class BatchSaveResponse(BaseModel):
    total: int
    success: int
    failed: int
    results: List[BatchSaveResult]


# 训练配置模型
class TrainingConfig(BaseModel):
    """训练配置模型"""
    device_id: int = Field(..., description="设备ID")
    target_feature: Optional[str] = Field(None, description="目标特征")
    secondary_target_feature: Optional[str] = Field(None, description="次目标特征")
    lookback_days: Optional[int] = Field(30, ge=1, le=365, description="回溯天数")
    train_ratio: Optional[float] = Field(0.8, ge=0.5, le=0.95, description="训练集比例")

    # 时间参数
    train_start_time: Optional[datetime] = Field(None, description="训练开始时间")
    train_end_time: Optional[datetime] = Field(None, description="训练结束时间")
    predict_start_time: Optional[datetime] = Field(None, description="预测开始时间")
    predict_end_time: Optional[datetime] = Field(None, description="预测结束时间")

    # 间隔设置
    train_interval_hours: Optional[int] = Field(12, ge=1, le=720, description="训练间隔小时数")
    predict_interval_minutes: Optional[int] = Field(5, ge=1, le=1440, description="预测间隔分钟数")

    # 模型参数
    look_back: Optional[int] = Field(24, ge=1, le=168, description="历史时间步长")
    forecast_horizon: Optional[int] = Field(1, ge=1, le=24, description="预测步长")

    # 模型参数
    xgboost_params: Optional[Dict[str, Any]] = Field(None, description="XGBoost参数")

    # 预处理配置
    preprocessing_config: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {
            'missing_value_method': 'interpolate',
            'outlier_method': 'iqr',
            'create_time_features': True,
            'lag_periods': [1, 2, 3, 6, 12, 24],
            'rolling_windows': [3, 6, 12, 24],
            'scaling_method': 'standard'
        },
        description="预处理配置"
    )


class TrainingScheduleSettings(BaseModel):
    """训练设置模型"""
    device_id: int = Field(..., description="设备ID")

    # 训练设置
    train_start_time: Optional[datetime] = Field(None, description="训练开始时间")
    train_interval_value: int = Field(12, description="训练间隔值")
    train_interval_unit: str = Field('hours', description="训练间隔单位")
    train_end_time: Optional[datetime] = Field(None, description="训练结束时间")
    train_is_active: Optional[bool] = Field(True, description="训练计划是否激活")  # 新增

    # 预测设置
    predict_start_time: Optional[datetime] = Field(None, description="预测开始时间")
    predict_interval_value: int = Field(5, description="预测间隔值")
    predict_interval_unit: str = Field('minutes', description="预测间隔单位")
    predict_end_time: Optional[datetime] = Field(None, description="预测结束时间")
    predict_is_active: Optional[bool] = Field(True, description="预测计划是否激活")  # 新增
    # 新增：输出模式与输出数量（仅对预测计划有效）
    output_mode: Optional[str] = Field(None, description="输出模式：single（单输出）或 multi（多输出）")
    output_count: Optional[int] = Field(None, ge=1, description="输出数量，单输出时固定为1，多输出时可配置")

    @validator('output_mode')
    def validate_output_mode(cls, v):
        if v is not None and v not in ['single', 'multi']:
            raise ValueError('output_mode 必须是 single 或 multi')
        return v


class TrainingScheduleSettingsResponse(BaseModel):
    """训练设置响应"""
    device_id: int
    message: str
    output_mode: Optional[str] = None
    output_count: Optional[int] = None
    class Config:
        from_attributes = True

class TrainingSchedule(BaseModel):
    """训练计划模型"""
    device_id: int
    schedule_type: str = Field(..., description="计划类型：train或predict")
    start_time: datetime
    end_time: datetime
    interval_value: int
    interval_unit: str = Field(..., description="间隔单位")
    is_active: bool = True

    @validator('schedule_type')
    def validate_schedule_type(cls, v):
        if v not in ['train', 'predict']:
            raise ValueError("计划类型必须是 'train' 或 'predict'")
        return v

    @validator('interval_unit')
    def validate_interval_unit(cls, v):
        if v not in ['minutes', 'hours', 'days']:
            raise ValueError("间隔单位必须是 'minutes', 'hours' 或 'days'")
        return v


class TrainingScheduleResponse(BaseModel):
    id: int
    device_id: int
    schedule_type: str
    start_time: datetime
    end_time: Optional[datetime] = None  # 明确声明为Optional
    interval_value: int
    interval_unit: str
    next_run_at: datetime
    is_active: bool
    total_runs: int = 0
    success_runs: int = 0
    failed_runs: int = 0
    last_run_at: Optional[datetime] = None  # 同样处理
    created_at: datetime
    updated_at: datetime
    output_mode: Optional[str] = None  # 新增
    output_count: Optional[int] = None  # 新增
    # 添加自定义验证器，确保时间格式正确
    @validator('start_time', 'end_time', 'next_run_at', 'last_run_at', 'created_at', 'updated_at', pre=True)
    def parse_datetime(cls, value):
        if value is None:
            return None
        if isinstance(value, datetime):
            # 确保有时区信息
            if value.tzinfo is None:
                return value.replace(tzinfo=pytz.UTC)
            return value
        # 尝试解析字符串
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return value

    class Config:
        orm_mode = True


# 设备模型训练基础模型
class DeviceModelTrainingBase(BaseModel):
    model_type: str = Field('xgboost', description="模型类型")
    training_interval_minutes: int = Field(720, ge=1, description="训练间隔（分钟）")
    prediction_interval_minutes: int = Field(5, ge=1, description="预测间隔（分钟）")
    training_status: str = Field('not_started', description="训练状态")

    @validator('training_status')
    def validate_training_status(cls, v):
        if v not in ['not_started', 'training', 'trained', 'failed']:
            raise ValueError("训练状态必须是: not_started, training, trained, failed")
        return v


# 创建设备模型训练配置
class DeviceModelTrainingCreate(DeviceModelTrainingBase):
    device_id: int = Field(..., description="设备ID")
    model_version_id: Optional[int] = Field(None, description="模型版本ID")


# 更新设备模型训练配置
class DeviceModelTrainingUpdate(BaseModel):
    model_type: Optional[str] = Field(None, description="模型类型")
    last_trained_at: Optional[datetime] = Field(None, description="最后训练时间")
    training_interval_minutes: Optional[int] = Field(None, ge=1, description="训练间隔（分钟）")
    prediction_interval_minutes: Optional[int] = Field(None, ge=1, description="预测间隔（分钟）")
    training_status: Optional[str] = Field(None, description="训练状态")
    model_version_id: Optional[int] = Field(None, description="模型版本ID")

    @validator('training_status')
    def validate_training_status(cls, v):
        if v is not None and v not in ['not_started', 'training', 'trained', 'failed']:
            raise ValueError("训练状态必须是: not_started, training, trained, failed")
        return v


# 设备模型训练响应模型
class DeviceModelTraining(DeviceModelTrainingBase):
    id: int
    uuid: uuid_pkg.UUID
    device_id: int
    model_version_id: Optional[int]
    last_trained_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# 设备模型训练详情响应模型
class DeviceModelTrainingDetail(DeviceModelTraining):
    device: Optional["Device"] = None
    model_version: Optional["DeviceModelVersion"] = None
    project: Optional["Project"] = None
    device_model: Optional["DeviceModel"] = None

    class Config:
        from_attributes = True


# 设备模型训练列表响应模型
class DeviceModelTrainingList(BaseModel):
    trainings: List[DeviceModelTrainingDetail]
    total: int
    page: int
    page_size: int
    total_pages: int


# 训练统计信息模型
class TrainingStats(BaseModel):
    total_devices: int = 0
    trained_devices: int = 0
    training_devices: int = 0
    failed_devices: int = 0
    avg_r2_score: float = 0.0
    avg_training_time_minutes: float = 0.0


# 训练配置保存响应模型
class TrainingConfigResponse(BaseModel):
    device_id: int
    training_interval_minutes: int
    prediction_interval_minutes: int
    model_type: str
    message: str


# 开始训练请求模型
class StartTrainingRequest(BaseModel):
    device_id: int
    model_version_id: Optional[int] = None
    training_config: Optional[Dict[str, Any]] = None


# 训练状态响应模型
class TrainingStatusResponse(BaseModel):
    device_id: int
    training_status: str
    last_trained_at: Optional[datetime]



# 批量训练请求模型
class BatchTrainingRequest(BaseModel):
    device_ids: List[int] = Field(..., min_items=1, description="设备ID列表")
    training_config: Optional[Dict[str, Any]] = Field(None, description="训练配置")


# 批量训练响应模型
class BatchTrainingResponse(BaseModel):
    total: int
    success: int
    failed: int
    results: List[Dict[str, Any]]


# Model Evaluation Schemas
class ModelEvaluationBase(BaseModel):
    device_id: int = Field(..., description="设备ID")
    r_squared: float = Field(..., ge=-10000, le=10000, description="R²分数")
    rmse: float = Field(..., ge=0, description="RMSE")
    mae: float = Field(..., ge=0, description="MAE")
    training_time: int = Field(..., ge=0, description="训练时间（秒）")
    training_data_size: int = Field(..., ge=0, description="训练数据量")
    test_data_size: int = Field(..., ge=0, description="测试数据量")
    feature_count: int = Field(..., ge=0, description="特征数量")
    # 新增：残差修正模型指标（可选）
    r_squared_residual: Optional[float] = Field(None, ge=-10000, le=10000)
    rmse_residual: Optional[float] = Field(None, ge=0)
    mae_residual: Optional[float] = Field(None, ge=0)

    class Config:
        orm_mode = True
        from_attributes = True


class ModelEvaluationCreate(ModelEvaluationBase):
    pass


class ModelEvaluationResponse(ModelEvaluationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeviceMetricsResponse(BaseModel):
    device_id: int
    device_name: str
    project_name: str
    model_name: str
    model_version: str
    latest_evaluation: Optional[ModelEvaluationResponse] = None
    performance_summary: Optional[Dict[str, Any]] = None
    last_train_run_at: Optional[datetime] = None  # 新增

class DeviceDataConfigBase(BaseModel):
    """设备数据配置基础模式"""
    device_id: int
    data_start_time: Optional[datetime] = None
    data_end_time: Optional[datetime] = None
    max_rows_limit: Optional[int] = 300000

    class Config:
        from_attributes = True


class DeviceDataConfigCreate(DeviceDataConfigBase):
    """创建设备数据配置"""
    pass


class DeviceDataConfigUpdate(BaseModel):
    """更新设备数据配置"""
    data_start_time: Optional[datetime] = None
    data_end_time: Optional[datetime] = None
    max_rows_limit: Optional[int] = None

    class Config:
        from_attributes = True


class DeviceDataConfigResponse(DeviceDataConfigBase):
    """设备数据配置响应"""
    id: int
    uuid: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 训练器配置基础模型
class TrainerConfigBase(BaseModel):
    """训练器配置基础模型"""
    device_id: int = Field(..., description="设备ID")
    trainer_path: Optional[str] = Field(None, description="训练器路径")  # 改为 Optional，移除长度限制
    trainer_type: str = Field("xgboost", description="训练器类型")
    is_primary: bool = Field(False, description="是否为主配置")
    is_active: bool = Field(True, description="是否启用")
    description: Optional[str] = Field(None, description="配置描述")

    @validator("trainer_path")
    def validate_trainer_path(cls, v):
        if v is None:  # 允许为空，因为后端会自动生成
            return v
        import re
        pattern = r'^([a-zA-Z0-9_]+\.)*[a-zA-Z0-9_]+(\.[A-Z][a-zA-Z0-9_]*)?$'
        if not re.match(pattern, v):
            raise ValueError("训练器路径格式不正确")
        return v


# 创建训练器配置
class TrainerConfigCreate(TrainerConfigBase):
    pass


# 更新训练器配置
class TrainerConfigUpdate(BaseModel):
    """更新训练器配置模型"""
    trainer_path: Optional[str] = Field(None, min_length=1, max_length=500)
    trainer_type: Optional[str] = Field(None, description="训练器类型")
    is_primary: Optional[bool] = Field(None, description="是否为主配置")
    is_active: Optional[bool] = Field(None, description="是否启用")
    description: Optional[str] = Field(None, description="配置描述")

    @validator("trainer_path")
    def validate_trainer_path(cls, v):
        if v is not None:
            import re
            pattern = r'^([a-zA-Z0-9_]+\.)*[a-zA-Z0-9_]+(\.[A-Z][a-zA-Z0-9_]*)?$'
            if not re.match(pattern, v):
                raise ValueError("训练器路径格式不正确")
        return v

    @validator("trainer_type")
    def validate_trainer_type(cls, v):
        if v is not None:
            allowed_types = ["xgboost", "lightgbm", "catboost", "pytorch", "tensorflow", "sklearn"]
            if v.lower() not in allowed_types:
                raise ValueError(f"训练器类型必须是以下之一: {', '.join(allowed_types)}")
            return v.lower()
        return v


# 训练器配置响应模型
class TrainerConfigResponse(TrainerConfigBase):
    """训练器配置响应模型"""
    id: int
    uuid: UUID
    created_at: datetime
    updated_at: datetime
    device_name: Optional[str] = None
    project_name: Optional[str] = None

    class Config:
        from_attributes = True


# 训练器配置详情响应模型
class TrainerConfigDetail(TrainerConfigResponse):
    """训练器配置详情模型"""
    device: Optional["Device"] = None
    project: Optional["Project"] = None


# 训练器配置列表响应模型
class TrainerConfigList(BaseModel):
    """训练器配置列表响应模型"""
    configs: List[TrainerConfigResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# 批量创建训练器配置
class BatchTrainerConfigCreate(BaseModel):
    """批量创建训练器配置模型"""
    configs: List[TrainerConfigCreate] = Field(..., min_items=1, description="配置列表")


# 批量创建响应
class BatchTrainerConfigResponse(BaseModel):
    """批量创建训练器配置响应模型"""
    total: int
    success: int
    failed: int
    results: List[Dict[str, Any]]


# 设置主配置请求
class SetPrimaryTrainerConfigRequest(BaseModel):
    """设置主训练器配置请求"""
    config_id: int = Field(..., description="配置ID")


# 复制配置请求
class CopyTrainerConfigRequest(BaseModel):
    """复制训练器配置请求"""
    source_device_id: int = Field(..., description="源设备ID")
    target_device_ids: List[int] = Field(..., min_items=1, description="目标设备ID列表")
    overwrite: bool = Field(False, description="是否覆盖现有配置")


# 复制配置响应
class CopyTrainerConfigResponse(BaseModel):
    """复制训练器配置响应"""
    total_targets: int
    copied: int
    skipped: int
    failed: int
    results: List[Dict[str, Any]]


# 训练器配置统计
class TrainerConfigStats(BaseModel):
    """训练器配置统计"""
    total_configs: int
    active_configs: int
    primary_configs: int
    by_trainer_type: Dict[str, int]
    by_device: List[Dict[str, Any]]


# 设备训练器配置概览
class DeviceTrainerConfigOverview(BaseModel):
    """设备训练器配置概览"""
    device_id: int
    device_name: str
    project_name: str
    primary_config: Optional[TrainerConfigResponse] = None
    active_configs: int
    total_configs: int
    last_updated: Optional[datetime] = None


# 训练器类型统计
class TrainerTypeStats(BaseModel):
    """训练器类型统计"""
    trainer_type: str
    count: int
    percentage: float



# ---------- 冷却侧配置 ----------
class CoolingOptConfigBase(BaseModel):
    return_temp_lower_limit: Optional[float] = Field(1.00, description="冷却水回水温度下限(℃) = 湿球温度+ n")
    return_temp_upper_limit: Optional[float] = Field(32.00, description="冷却水回水温度上限(℃)")
    supply_temp_lower_limit: Optional[float] = Field(1.00, description="冷却水供水温度下限(℃)= 湿球温度+ n")
    supply_temp_upper_limit: Optional[float] = Field(40.00, description="冷却水供水温度上限(℃)")
    temp_diff_lower_limit: Optional[float] = Field(2.00, description="冷却水温差下限(℃)")
    temp_diff_upper_limit: Optional[float] = Field(8.00, description="冷却水温差上限(℃)")
    heat_dissipation_lower_limit: Optional[float] = Field(95.00, description="散热量下限(%)")
    heat_dissipation_upper_limit: Optional[float] = Field(105.00, description="散热量上限(%)")
    # 新增三个阈值参数
    return_temp_threshold: Optional[float] = Field(0.50, ge=0, description="冷却水回水温度阈值(℃) ≥ ±0.5")
    temp_diff_threshold: Optional[float] = Field(0.80, ge=0, description="冷却水温差阈值(℃) ≥ ±0.8")
    energy_saving_threshold: Optional[float] = Field(2.00, ge=0, description="节能率阈值(%) ≥2")
    optimization_cycle_minutes: Optional[int] = Field(5, ge=1, description="寻优周期（分钟）")
    r2_threshold: Optional[float] = Field(0.60, ge=0, le=1, description="模型R²阈值")
    @field_validator("return_temp_upper_limit")
    def validate_return_temp_range(cls, v, info):
        if v is not None and info.data.get("return_temp_lower_limit") is not None:
            if v < info.data["return_temp_lower_limit"]:
                raise ValueError("回水温度上限必须大于或等于下限")
        return v

    @field_validator("supply_temp_upper_limit")
    def validate_supply_temp_range(cls, v, info):
        if v is not None and info.data.get("supply_temp_lower_limit") is not None:
            if v < info.data["supply_temp_lower_limit"]:
                raise ValueError("供水温度上限必须大于或等于下限")
        return v

    @field_validator("temp_diff_upper_limit")
    def validate_temp_diff_range(cls, v, info):
        if v is not None and info.data.get("temp_diff_lower_limit") is not None:
            if v < info.data["temp_diff_lower_limit"]:
                raise ValueError("温差上限必须大于或等于下限")
        return v

    @field_validator("heat_dissipation_upper_limit")
    def validate_heat_dissipation_range(cls, v, info):
        if v is not None and info.data.get("heat_dissipation_lower_limit") is not None:
            if v < info.data["heat_dissipation_lower_limit"]:
                raise ValueError("散热量上限必须大于或等于下限")
        return v
        # 可选：添加新字段的简单验证

    @field_validator("return_temp_threshold", "temp_diff_threshold", "energy_saving_threshold")
    def validate_threshold_nonnegative(cls, v):
        if v is not None and v < 0:
            raise ValueError("阈值不能为负数")
        return v

    @field_validator("r2_threshold")
    def validate_r2_threshold(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError("R²阈值必须在0到1之间")
        return v

class CoolingOptConfigCreate(CoolingOptConfigBase):
    pass


class CoolingOptConfigUpdate(CoolingOptConfigBase):
    pass


class CoolingOptConfigResponse(CoolingOptConfigBase):
    id: int

    class Config:
        from_attributes = True


# ---------- 冷却侧优化参数（总功率） ----------
class CoolingOptParametersTotalBase(BaseModel):
    optimization_timestamp: datetime
    applied: Optional[bool] = False
    heartbeat_timestamp: Optional[datetime] = None
    heartbeat_state: Optional[int] = None

    # 配置参数
    return_temp_lower_limit: Optional[float] = None
    return_temp_upper_limit: Optional[float] = None
    supply_temp_lower_limit: Optional[float] = None
    supply_temp_upper_limit: Optional[float] = None
    temp_diff_lower_limit: Optional[float] = None
    temp_diff_upper_limit: Optional[float] = None
    heat_dissipation_lower_limit: Optional[float] = None
    heat_dissipation_upper_limit: Optional[float] = None

    # 当前值
    current_total_power: Optional[float] = None
    current_host_total_power: Optional[float] = None
    current_cooling_tower_total_power: Optional[float] = None
    current_cooling_pump_total_power: Optional[float] = None
    current_supply_temp: Optional[float] = None
    current_return_temp: Optional[float] = None
    current_temp_diff: Optional[float] = None
    current_heat_dissipation: Optional[float] = None

    # 优化后值
    optimized_total_power: Optional[float] = None
    optimized_host_total_power: Optional[float] = None
    optimized_cooling_tower_total_power: Optional[float] = None
    optimized_cooling_pump_total_power: Optional[float] = None
    optimized_supply_temp: Optional[float] = None
    optimized_return_temp: Optional[float] = None
    optimized_temp_diff: Optional[float] = None
    optimized_heat_dissipation: Optional[float] = None

    # 差值
    diff_total_power: Optional[float] = None
    diff_host_total_power: Optional[float] = None
    diff_cooling_tower_total_power: Optional[float] = None
    diff_cooling_pump_total_power: Optional[float] = None
    diff_supply_temp: Optional[float] = None
    diff_return_temp: Optional[float] = None
    diff_temp_diff: Optional[float] = None
    diff_heat_dissipation: Optional[float] = None

    # 百分比差值
    percent_total_power: Optional[float] = None
    percent_host_total_power: Optional[float] = None
    percent_cooling_tower_total_power: Optional[float] = None
    percent_cooling_pump_total_power: Optional[float] = None

    # 统计
    total_energy_saving: Optional[float] = None
    energy_saving_percent: Optional[float] = None

    remarks: Optional[str] = None
    updated_at: Optional[datetime] = None
    # ---------- 新增下发标记字段 ----------
    optimized_return_temp_applied: Optional[bool] = False
    optimized_temp_diff_applied: Optional[bool] = False
    # ---------- 新增失败原因字段 ----------
    failure_reasons: Optional[str] = None


class CoolingOptParametersTotalResponse(CoolingOptParametersTotalBase):
    id: int

    class Config:
        from_attributes = True


class CoolingOptParametersTotalList(BaseModel):
    parameters: List[CoolingOptParametersTotalResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------- 冷冻侧配置 ----------
class ChilledOptConfigBase(BaseModel):
    return_temp_lower_limit: Optional[float] = Field(9.00, description="冷冻水回水温度下限(℃)")
    return_temp_upper_limit: Optional[float] = Field(15.00, description="冷冻水回水温度上限(℃)")
    supply_temp_lower_limit: Optional[float] = Field(7.00, description="冷冻水供水温度下限(℃)")
    supply_temp_upper_limit: Optional[float] = Field(10.00, description="冷冻水供水温度上限(℃)")
    temp_diff_lower_limit: Optional[float] = Field(4.00, description="冷冻水温差下限(℃)")
    temp_diff_upper_limit: Optional[float] = Field(6.00, description="冷冻水温差上限(℃)")
    # 新增三个阈值参数
    supply_temp_threshold: Optional[float] = Field(0.50, ge=0, description="冷冻水供水温度阈值(℃) ≥ ±0.5")
    temp_diff_threshold: Optional[float] = Field(0.80, ge=0, description="冷冻水温差阈值(℃) ≥ ±0.8")
    energy_saving_threshold: Optional[float] = Field(2.00, ge=0, description="节能率阈值(%) ≥2")
    optimization_cycle_minutes: Optional[int] = Field(5, ge=1, description="寻优周期（分钟）")
    r2_threshold: Optional[float] = Field(0.60, ge=0, le=1, description="模型R²阈值")
    
    @field_validator("return_temp_upper_limit")
    def validate_return_temp_range(cls, v, info):
        if v is not None and info.data.get("return_temp_lower_limit") is not None:
            if v < info.data["return_temp_lower_limit"]:
                raise ValueError("回水温度上限必须大于或等于下限")
        return v

    @field_validator("supply_temp_upper_limit")
    def validate_supply_temp_range(cls, v, info):
        if v is not None and info.data.get("supply_temp_lower_limit") is not None:
            if v < info.data["supply_temp_lower_limit"]:
                raise ValueError("供水温度上限必须大于或等于下限")
        return v

    @field_validator("temp_diff_upper_limit")
    def validate_temp_diff_range(cls, v, info):
        if v is not None and info.data.get("temp_diff_lower_limit") is not None:
            if v < info.data["temp_diff_lower_limit"]:
                raise ValueError("温差上限必须大于或等于下限")
        return v

    @field_validator("supply_temp_threshold", "temp_diff_threshold", "energy_saving_threshold")
    def validate_threshold_nonnegative(cls, v):
        if v is not None and v < 0:
            raise ValueError("阈值不能为负数")
        return v
    
    @field_validator("r2_threshold")
    def validate_r2_threshold(cls, v):
        if v is not None and (v < 0 or v > 1):
            raise ValueError("R²阈值必须在0到1之间")
        return v


class ChilledOptConfigCreate(ChilledOptConfigBase):
    pass


class ChilledOptConfigUpdate(ChilledOptConfigBase):
    pass


class ChilledOptConfigResponse(ChilledOptConfigBase):
    id: int

    class Config:
        from_attributes = True


# ---------- 冷冻侧优化参数（总功率） ----------
class ChilledOptParametersTotalBase(BaseModel):
    optimization_timestamp: datetime
    applied: Optional[bool] = False
    heartbeat_timestamp: Optional[datetime] = None
    heartbeat_state: Optional[int] = None

    # 配置参数
    return_temp_lower_limit: Optional[float] = None
    return_temp_upper_limit: Optional[float] = None
    supply_temp_lower_limit: Optional[float] = None
    supply_temp_upper_limit: Optional[float] = None
    temp_diff_lower_limit: Optional[float] = None
    temp_diff_upper_limit: Optional[float] = None

    # 当前值
    current_total_power: Optional[float] = None
    current_host_total_power: Optional[float] = None
    current_chilled_pump_total_power: Optional[float] = None
    current_supply_temp: Optional[float] = None
    current_return_temp: Optional[float] = None
    current_temp_diff: Optional[float] = None

    # 优化后值
    optimized_total_power: Optional[float] = None
    optimized_host_total_power: Optional[float] = None
    optimized_chilled_pump_total_power: Optional[float] = None
    optimized_supply_temp: Optional[float] = None
    optimized_return_temp: Optional[float] = None
    optimized_temp_diff: Optional[float] = None

    # 差值
    diff_total_power: Optional[float] = None
    diff_host_total_power: Optional[float] = None
    diff_chilled_pump_total_power: Optional[float] = None
    diff_supply_temp: Optional[float] = None
    diff_return_temp: Optional[float] = None
    diff_temp_diff: Optional[float] = None

    # 百分比差值
    percent_total_power: Optional[float] = None
    percent_host_total_power: Optional[float] = None
    percent_chilled_pump_total_power: Optional[float] = None

    # 统计
    total_energy_saving: Optional[float] = None
    energy_saving_percent: Optional[float] = None

    remarks: Optional[str] = None
    updated_at: Optional[datetime] = None
    # ---------- 新增下发标记字段 ----------
    optimized_supply_temp_applied: Optional[bool] = False
    optimized_temp_diff_applied: Optional[bool] = False
    # ---------- 新增失败原因字段 ----------
    failure_reasons: Optional[str] = None


class ChilledOptParametersTotalResponse(ChilledOptParametersTotalBase):
    id: int

    class Config:
        from_attributes = True


class ChilledOptParametersTotalList(BaseModel):
    parameters: List[ChilledOptParametersTotalResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ---------- 优化迭代数据（用于前端图表） ----------
class CoolingOptIterationCombination(BaseModel):
    index: int
    cooling_inlet_temp: float
    cooling_return_temp: float
    actual_inlet_temp: float
    actual_return_temp: float
    delta_temp: float
    host_power: float
    cooling_pump_power: float   # 原为 pump_power
    cooling_tower_power: float  # 原为 tower_power
    total_power: float
    system_heat_dissipation: float
    heat_dissipation_percent: float
    power_diff: float
    power_diff_percent: float


class CoolingOptIterationResponse(BaseModel):
    timestamp: str
    combinations: List[CoolingOptIterationCombination]


class CoolingOptIterationPageResponse(BaseModel):
    total: int
    page: int
    page_size: int
    combinations: List[CoolingOptIterationCombination]


class ChilledOptIterationCombination(BaseModel):
    index: int
    chilled_inlet_temp: float
    chilled_return_temp: float
    actual_inlet_temp: float
    actual_return_temp: float
    delta_temp: float
    host_power: float
    pump_power: float  # 冷冻泵总功率
    total_power: float
    power_diff: float
    power_diff_percent: float


class ChilledOptIterationResponse(BaseModel):
    timestamp: str
    combinations: List[ChilledOptIterationCombination]


class ChilledOptIterationPageResponse(BaseModel):
    total: int
    page: int
    page_size: int
    combinations: List[ChilledOptIterationCombination]

# 优化统计信息（通用）
class OptimizationStats(BaseModel):
    total_optimizations: int
    applied_optimizations: int
    total_energy_saving: float
    avg_energy_saving_percent: float
    recent_optimizations: List[Dict[str, Any]]

# 设备字段历史数据响应（用于图表）
class DeviceHistoryFieldResponse(BaseModel):
    timestamp: datetime
    current_value: Optional[float] = None
    optimized_value: Optional[float] = None

    class Config:
        from_attributes = True

# ---------- 知识投喂 ----------
class KnowledgeFileBase(BaseModel):
    original_name: str
    description: Optional[str] = None

class KnowledgeFileCreate(KnowledgeFileBase):
    pass

class KnowledgeFileOut(KnowledgeFileBase):
    id: int
    stored_path: str
    file_size: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Pydantic v2 用 from_attributes，v1 用 orm_mode = True

class KnowledgeFileList(BaseModel):
    items: List[KnowledgeFileOut]
    total: int
    page: int
    page_size: int
    total_pages: int

class KnowledgeFileStats(BaseModel):
    total: int
    pending: int
    indexing: int
    completed: int
    failed: int
# 在文件末尾添加前向引用，解决循环引用问题
from . import models as models_module