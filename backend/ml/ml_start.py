"""
ML启动器 - 处理real_train接口，协调训练和预测流程
backend/ml/ml_start.py
"""
import sys
import os
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime
import time
import copy
import pandas as pd
import importlib
import numpy as np
# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from ml.data.loader import get_data_loader
from ml.data.preprocessor import get_preprocessor
from ml.models import get_device_trainer
from app import models

logger = logging.getLogger(__name__)


class MLStart:
    """ML启动器 - 处理real_train接口，协调训练和预测流程"""

    def __init__(self, db_session=None):
        self.db_session = db_session
        self.data_loader = None
        self.trainer = None

    @staticmethod
    def _write_training_log(entry: dict) -> None:
        """将训练结果追加写入当日 JSONL 日志文件"""
        try:
            import json
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
            os.makedirs(log_dir, exist_ok=True)
            # 清理超过7天的旧训练日志
            try:
                from app.utils.log_cleanup import cleanup_old_logs
                cleanup_old_logs(log_dir, "training_", keep_days=7)
            except Exception:
                pass
            log_file = os.path.join(log_dir, f"training_{datetime.now().strftime('%Y-%m-%d')}.jsonl")
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False, default=str) + '\n')
        except Exception as ex:
            logger.warning(f"写入训练日志文件失败: {ex}")

    def get_device_trainer_from_db(self, device_id: int):
        """从数据库获取设备的训练器配置"""
        try:
            # 查询设备的主训练器配置
            trainer_config = self.db_session.query(models.TrainerConfig).filter(
                models.TrainerConfig.device_id == device_id,
                models.TrainerConfig.is_primary == True,
                models.TrainerConfig.is_active == True
            ).first()

            if not trainer_config:
                # 如果没有主配置，查找第一个活跃配置
                trainer_config = self.db_session.query(models.TrainerConfig).filter(
                    models.TrainerConfig.device_id == device_id,
                    models.TrainerConfig.is_active == True
                ).first()

            if not trainer_config:
                logger.warning(f"设备 {device_id} 没有配置训练器，使用默认训练器")
                # 使用默认训练器
                return self._get_default_trainer()

            # 根据 trainer_path 动态导入训练器
            trainer_path = trainer_config.trainer_path
            logger.info(f"设备 {device_id} 使用训练器: {trainer_path}")

            try:
                # 动态导入训练器
                module_path, class_name = trainer_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                trainer_class = getattr(module, class_name)

                return trainer_class()
            except Exception as e:
                logger.error(f"导入训练器 {trainer_path} 失败: {e}")
                # 回退到默认训练器
                return self._get_default_trainer()

        except Exception as e:
            logger.error(f"从数据库获取训练器配置失败: {e}")
            return self._get_default_trainer()

    def _get_default_trainer(self):
        """获取默认训练器"""
        try:
            from ml.models.trainers.device11_xgboost_v1 import XGBoostTrainer
            return XGBoostTrainer()
        except Exception as e:
            logger.error(f"加载默认训练器失败: {e}")
            raise
    def real_train_device_model(
            self,
            device_id: int,
            target_feature: str,
            config: Optional[Dict] = None
    ) -> Dict:
        """训练设备模型 - 简化版，不进行复杂的数据处理"""
        start_time = time.time()
        total_duration = 0  # 初始化
        logs = []

        # 解决Windows中文路径编码问题
        import os
        os.environ['JOBLIB_TEMP_FOLDER'] = 'C:\\temp_joblib'  # 设置英文临时文件夹路径
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        os.environ['PYTHONUTF8'] = '1'

        # 创建临时文件夹
        temp_dir = 'C:\\temp_joblib'
        if not os.path.exists(temp_dir):
            try:
                os.makedirs(temp_dir, exist_ok=True)
                logger.info(f"创建临时文件夹: {temp_dir}")
            except Exception as e:
                logger.warning(f"创建临时文件夹失败: {e}")
        result = {
            'device_id': device_id,
            'target_feature': target_feature,
            'training_success': False,
            'error_message': '训练过程未完成',
            'training_details': {},
            'trained_at': datetime.now().isoformat()
        }

        # 在 return result 之前添加
        def convert_numpy_types(obj):
            """递归转换 numpy 类型为 Python 原生类型"""
            if isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            elif isinstance(obj, tuple):
                return tuple(convert_numpy_types(item) for item in obj)
            elif isinstance(obj, (np.float32, np.float64)):
                return float(obj)
            elif isinstance(obj, (np.int32, np.int64)):
                return int(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            else:
                return obj

        result = convert_numpy_types(result)
        def log_message(message: str, level: str = "INFO"):
            """记录日志消息"""
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                "timestamp": timestamp,
                "level": level,
                "message": message
            }
            logs.append(log_entry)
            if level == "ERROR":
                logger.error(message)
            elif level == "WARNING":
                logger.warning(message)
            else:
                logger.info(message)

        try:
            log_message(f"🚀 开始训练设备 {device_id} 的模型")
            log_message(f"🎯 目标特征: {target_feature}")

            # 1. 初始化训练组件
            log_message("🔄 初始化训练组件")
            try:
                from ..data.loader import get_data_loader
            except ImportError as e:
                from ml.data.loader import get_data_loader

            self.data_loader = get_data_loader(self.db_session)

            # 修改这里：根据设备ID动态获取训练器
            try:
                log_message(f"🔧 正在为设备 {device_id} 加载训练器...")
                # self.trainer = get_device_trainer(device_id)
                self.trainer = self.get_device_trainer_from_db(device_id)
                log_message(f"✅ 训练器初始化完成: {self.trainer.__class__.__name__}")
            except Exception as e:
                log_message(f"❌ 训练器初始化失败: {e}", "ERROR")
                raise
            # ========== 新增：训练器能力检测与配置同步 ==========
            trainer_output_dim = getattr(self.trainer, 'output_dim', 1)
            cfg_forecast_horizon = config.get('forecast_horizon', 1)

            if trainer_output_dim > 1:
                if cfg_forecast_horizon == 1:
                    log_message(f"⚠️ 训练器 {self.trainer.__class__.__name__} 要求 output_dim={trainer_output_dim}，"
                                f"但配置 forecast_horizon=1，已自动修改为 {trainer_output_dim}。", "WARNING")
                    config['forecast_horizon'] = trainer_output_dim
                elif cfg_forecast_horizon != trainer_output_dim:
                    raise ValueError(
                        f"训练器期望 output_dim={trainer_output_dim}，但配置 forecast_horizon={cfg_forecast_horizon}，"
                        f"请修改配置使其一致。"
                    )
            else:
                if cfg_forecast_horizon > 1:
                    raise ValueError(
                        f"训练器 {self.trainer.__class__.__name__} 是单步预测模型（output_dim=1），"
                        f"但配置 forecast_horizon={cfg_forecast_horizon}。请使用多步训练器或调整 forecast_horizon=1。"
                    )

            if not self.data_loader or not self.trainer:
                raise ValueError("无法初始化训练组件")

            log_message("✅ 训练组件初始化完成")

            # 2. 配置 - 简化配置
            default_config = {
                'lookback_days': 180,  # 减少回溯天数
                'train_ratio': 0.8,
                'look_back': 3,
                'forecast_horizon': 1,
                'use_random_split': False,
                'auto_detect_frequency': True,
                'data_filtering': {
                    'filter_zero_target': True,
                    'min_target_value': 0.1,
                },
                # 简化的预处理配置
                'preprocessing_config': {
                    'missing_value_method': 'forward_fill',
                    'outlier_method': 'iqr',
                    'outlier_threshold': 3.0,
                    'create_time_features': False,  # 禁用时间特征
                    'create_smart_time_features': False,  # 禁用智能时间特征
                    'lag_periods': [],  # 不创建滞后特征
                    'rolling_windows': [],  # 不创建滚动窗口
                    'rolling_stats': [],  # 不计算滚动统计
                    'scaling_method': None,  # 不进行缩放
                    'fix_distribution': False,
                    'max_total_features': 30,
                    'simple_mode': True,
                    'use_original_features_only': True
                },
            }

            if config:
                # 深度合并配置
                merged_config = copy.deepcopy(default_config)
                for key, value in config.items():
                    if key in merged_config and isinstance(value, dict) and isinstance(merged_config[key], dict):
                        merged_config[key].update(value)
                    else:
                        merged_config[key] = value
                config = merged_config
            else:
                config = default_config

            log_message(f"✅ 使用配置: 回溯{config['lookback_days']}天, look_back={config['look_back']}")
            # 在 ml_start.py 中，配置 data_config 后
            forecast_horizon = config.get('forecast_horizon', 1)
            if forecast_horizon > 1:
                # 1. 确保预处理配置存在
                if 'preprocessing_config' not in config:
                    config['preprocessing_config'] = {}
                # 2. 禁用所有可能泄露的特征工程
                config['preprocessing_config']['create_smart_time_features'] = False
                config['preprocessing_config']['lag_periods'] = []
                config['preprocessing_config']['rolling_windows'] = []
                # 3. 可选：禁用时间特征（其实安全，但为了简化可保留）
                config['preprocessing_config']['create_time_features'] = False
            # 3. 获取设备信息
            log_message(f"🔍 获取设备 {device_id} 信息")
            from app import models

            device = self.db_session.query(models.Device).filter(
                models.Device.id == device_id
            ).first()

            if not device:
                raise ValueError(f"设备 {device_id} 未找到")

            log_message(f"📋 设备信息: {device.name} ({device.identifier})")

            # 4. 获取模型版本和特征
            log_message("🔍 获取设备模型版本和特征")
            model_version_id = device.model_version_id
            if not model_version_id:
                raise ValueError(f"设备 {device_id} 未关联模型版本")

            # 获取模型版本的所有特征
            model_version_features = self.db_session.query(
                models.ModelVersionFeature,
                models.Feature
            ).join(
                models.Feature, models.ModelVersionFeature.feature_id == models.Feature.id
            ).filter(
                models.ModelVersionFeature.version_id == model_version_id
            ).all()

            if not model_version_features:
                raise ValueError(f"模型版本 {model_version_id} 没有关联任何特征")

            # 分离输入特征和输出特征
            input_features = []
            output_features = []
            primary_output_feature = None

            for mvf, feature in model_version_features:
                if mvf.is_output:
                    output_features.append(feature)
                    if mvf.is_primary_output:
                        primary_output_feature = feature
                        log_message(f"🏆 找到主输出特征: {feature.code}")
                else:
                    input_features.append(feature)

            # 检查输出特征
            if not output_features:
                raise ValueError(f"模型版本 {model_version_id} 没有设置输出特征(is_output=True)")

            # 如果没有指定主输出特征，使用第一个输出特征作为主输出
            if not primary_output_feature and output_features:
                primary_output_feature = output_features[0]
                log_message(f"⚠️ 未设置主输出特征，使用第一个输出特征: {primary_output_feature.code}", "WARNING")

            # 使用指定的目标特征或主输出特征
            if target_feature:
                # 验证目标特征是否在输出特征中
                target_feature_obj = None
                for feature in output_features:
                    if feature.code == target_feature:
                        target_feature_obj = feature
                        break

                if not target_feature_obj:
                    log_message(f"⚠️ 指定的目标特征 {target_feature} 不在输出特征中，使用主输出特征", "WARNING")
                    target_feature_obj = primary_output_feature
                    target_feature = primary_output_feature.code
            else:
                # 未指定目标特征，使用主输出特征
                target_feature_obj = primary_output_feature
                target_feature = primary_output_feature.code

            # 记录输出特征信息
            output_feature_codes = [f.code for f in output_features]
            log_message(f"🎯 输出特征: {', '.join(output_feature_codes)}")
            log_message(f"🎯 主输出特征: {target_feature}")

            # 获取所有特征代码（包括输入和输出）
            all_feature_codes = [f.code for f in (input_features + output_features)]
            log_message(f"📊 模型版本包含: {len(input_features)} 个输入特征, {len(output_features)} 个输出特征")

            # 5. 获取特征映射配置
            log_message("🔍 获取特征映射配置")
            feature_ids = [f.id for f in (input_features + output_features)]
            mappings = self.db_session.query(
                models.FeatureTableMapping
            ).filter(
                models.FeatureTableMapping.device_id == device_id,
                models.FeatureTableMapping.feature_id.in_(feature_ids),
                models.FeatureTableMapping.is_active == True
            ).all()

            if not mappings:
                raise ValueError(f"设备 {device_id} 没有配置特征映射")

            log_message(f"✅ 找到 {len(mappings)} 个特征映射")

            # 6. 加载训练数据（简化版）
            log_message("📥 开始从MySQL加载训练数据...")

            # 简化数据加载配置
            data_config = {
                'lookback_days': config['lookback_days'],
                'data_filtering': config['data_filtering'],
                'use_random_split': config['use_random_split'],
                'auto_detect_frequency': config['auto_detect_frequency'],
                'look_back': config['look_back']
            }
            # ========== 新增：为多步预测启用自动重采样 ==========
            forecast_horizon = config.get('forecast_horizon', 1)  # 注意：这里需要提前获取 forecast_horizon
            data_config['resample_to_target_freq'] = forecast_horizon > 1
            # ==================================================
            data_dict = self.data_loader.load_training_data(
                device_id=device_id,
                target_feature=target_feature,
                feature_codes=all_feature_codes,
                config=data_config,
                train_ratio=config['train_ratio'],
                lookback_days=config['lookback_days']
            )

            if not data_dict or 'train_data' not in data_dict:
                error_msg = "无法加载训练数据"
                log_message(error_msg, "ERROR")
                raise ValueError(error_msg)

            # 获取训练和测试数据
            train_df = data_dict['train_data']
            test_df = data_dict.get('test_data')

            # 简单的数据检查
            if isinstance(train_df, list):
                train_df = pd.DataFrame(train_df)
                log_message(f"✅ 列表转换为DataFrame，形状: {train_df.shape}")
            elif not isinstance(train_df, pd.DataFrame):
                raise ValueError(f"数据格式不支持: {type(train_df)}")

            if test_df is not None and not isinstance(test_df, pd.DataFrame):
                log_message(f"⚠️ 测试数据格式不支持: {type(test_df)}，忽略测试集", "WARNING")
                test_df = None

            log_message(f"✅ 数据加载成功: 训练集 {len(train_df)} 条记录, {len(train_df.columns)} 个特征")
            if test_df is not None:
                log_message(f"✅ 测试集 {len(test_df)} 条记录")

            # 替换为使用预处理器：
            log_message("🔄 使用完整预处理器流水线...")

            # 1. 获取预处理器
            preprocessor = get_preprocessor()

            # 对训练集进行处理：分离特征和目标，只对特征进行预处理
            feature_cols_all = [col for col in train_df.columns if col != target_feature]
            train_features = train_df[feature_cols_all]
            train_target = train_df[target_feature]

            train_features_processed = preprocessor.preprocess_pipeline(
                df=train_features,
                target_feature=target_feature,  # 传递目标特征名称（仅用于日志）
                config=config.get('preprocessing_config', {}),
                fit_scaler=True
            )
            if not train_features_processed or 'processed_data' not in train_features_processed:
                raise ValueError("训练集预处理失败")
            train_features = train_features_processed['processed_data']
            # 重新组合训练集
            train_df = pd.concat([train_features, train_target], axis=1)

            # 对测试集进行处理（使用训练集拟合的缩放器）
            if test_df is not None and not test_df.empty:
                test_features = test_df[feature_cols_all]
                test_target = test_df[target_feature]
                test_features_processed = preprocessor.preprocess_pipeline(
                    df=test_features,
                    target_feature=target_feature,
                    config=config.get('preprocessing_config', {}),
                    fit_scaler=False
                )
                if test_features_processed and 'processed_data' in test_features_processed:
                    test_features = test_features_processed['processed_data']
                    test_df = pd.concat([test_features, test_target], axis=1)
                else:
                    log_message("⚠️ 测试集预处理失败，忽略测试集", "WARNING")
                    test_df = None

            log_message(f"✅ 预处理器处理完成，训练集形状: {train_df.shape}")

            # 在预处理器中处理多输出特征（支持多步序列）
            forecast_horizon = config.get('forecast_horizon', 1)
            look_back = config.get('look_back', 24)  # 历史窗口大小，单位与数据采样间隔一致
            log_message(f"🔍 实际接收到的 forecast_horizon = {forecast_horizon}, look_back = {look_back}")

            if forecast_horizon > 1:
                log_message(f"🔧 检测到多步预测模式: look_back={look_back}, forecast_horizon={forecast_horizon}")

                # 调用预处理器构造序列数据
                preprocessor = get_preprocessor()  # 已存在
                training_sequences = preprocessor.prepare_for_training(
                    data_dict={
                        'train_data': train_df,
                        'test_data': test_df  # 验证集使用 test_df（如果存在）
                    },
                    target_feature=target_feature,
                    look_back=look_back,
                    forecast_horizon=forecast_horizon
                )
                if training_sequences:
                    log_message(f"✅ 序列构造完成: X_train={training_sequences['X_train'].shape}, "
                                f"y_train={training_sequences['y_train'].shape}")
                    # 如果 y_train 的列数不等于 forecast_horizon，给出错误提示
                    if training_sequences['y_train'].shape[1] != forecast_horizon:
                        log_message(f"⚠️ 警告: y_train 列数为 {training_sequences['y_train'].shape[1]}, "
                                    f"但 forecast_horizon={forecast_horizon}", "WARNING")
                if not training_sequences:
                    raise ValueError("构造训练序列失败")

                X_train = training_sequences['X_train']  # shape: (n_samples, look_back, n_features)
                y_train = training_sequences['y_train']  # shape: (n_samples, forecast_horizon)
                X_val = training_sequences.get('X_test')
                y_val = training_sequences.get('y_test')
                feature_cols = training_sequences['feature_columns']

                log_message(f"✅ 序列构造完成: X_train={X_train.shape}, y_train={y_train.shape}")
                if X_val is not None:
                    log_message(f"   X_val={X_val.shape}, y_val={y_val.shape}")
                # 调试：打印特征列和目标列信息
                log_message(f"特征列（前10个）: {feature_cols[:10]}")
                log_message(f"目标特征 '{target_feature}' 是否在特征列中: {target_feature in feature_cols}")

                # 打印第一个样本的 X 和 y
                if X_train is not None and len(X_train) > 0:
                    log_message(f"第一个样本 X (前5个特征的前3个时间步):\n{X_train[0, :3, :5]}")
                    log_message(f"第一个样本 y: {y_train[0]}")
                # 多输出标志（多步预测时 y 是多维）
                multi_output = True
                output_feature_codes = [target_feature]  # 仅用于元数据，实际 y 已包含多步值

            else:
                # 原有单步预测逻辑（完全保持不变）
                multi_output = len(output_features) > 1
                if multi_output:
                    feature_cols = [col for col in train_df.columns if col not in output_feature_codes]
                    X_train = train_df[feature_cols].values
                    y_train = train_df[output_feature_codes].values
                    X_val = None
                    y_val = None
                    if test_df is not None and all(f in test_df.columns for f in output_feature_codes):
                        X_val = test_df[feature_cols].values
                        y_val = test_df[output_feature_codes].values
                else:
                    feature_cols = [col for col in train_df.columns if col != target_feature]
                    X_train = train_df[feature_cols].values
                    y_train = train_df[target_feature].values
                    X_val = None
                    y_val = None
                    if test_df is not None and target_feature in test_df.columns:
                        X_val = test_df[feature_cols].values
                        y_val = test_df[target_feature].values

            # 训练模型时传递多输出信息
            log_message("🧠 开始训练模型...")

            xgboost_params = self.trainer._get_default_params()

            # 训练模型，传递输出特征信息
            # 从配置中读取残差模型参数，如果没有则使用默认值
            # 获取训练器的可接受参数
            import inspect
            sig = inspect.signature(self.trainer.train)
            valid_params = sig.parameters

            # 基础参数字典（所有训练器都支持）
            train_kwargs = {
                'X_train': X_train,
                'y_train': y_train,
                'X_val': X_val,
                'y_val': y_val,
                'params': xgboost_params,
                'early_stopping_rounds': 30,
                'feature_names': feature_cols,
                # 注意：不再硬编码 train_residual_model，让训练器使用自己的默认值
            }

            # 可选参数（可能包含 None，稍后过滤）
            optional_params = {
                'output_features': output_feature_codes if multi_output else None,
                'primary_output_feature': target_feature,
            }

            # 仅当配置中显式指定了残差相关参数时才添加（让训练器使用自己的默认值）
            if 'train_residual_model' in config:
                optional_params['train_residual_model'] = config['train_residual_model']
            if 'residual_lags' in config:
                optional_params['residual_lags'] = config['residual_lags']
            if 'residual_standardize' in config:
                optional_params['residual_standardize'] = config['residual_standardize']
            if 'residual_objective' in config:
                optional_params['residual_objective'] = config['residual_objective']

            # 移除 optional_params 中值为 None 的项（例如 output_features 为 None 时）
            optional_params = {k: v for k, v in optional_params.items() if v is not None}

            # 合并参数：只传递训练器接受的参数
            for key, value in optional_params.items():
                if key in valid_params:
                    train_kwargs[key] = value

            # 调用训练
            training_stats = self.trainer.train(**train_kwargs)
            if not training_stats:
                raise ValueError("训练结果为空，模型训练失败")

            training_time = training_stats.get('training_time_seconds', 0)
            train_metrics = training_stats.get('train_metrics', {})
            val_metrics = training_stats.get('val_metrics', {})

            # 打印性能指标
            print("\n" + "=" * 60)
            print("📊 训练集性能指标:")
            print("=" * 60)

            if multi_output and isinstance(train_metrics, dict):
                # 判断是否为多步输出模式（包含 overall_rmse）
                if 'overall_rmse' in train_metrics:
                    # XGBoostMultiStepTrainer 返回的扁平指标
                    print(f"  Overall RMSE: {train_metrics['overall_rmse']:.4f}")
                    print(f"  Samples: {train_metrics['samples']}")
                    print(f"  Output Dimension: {train_metrics['output_dim']}")
                    step_rmse = train_metrics.get('step_rmse', [])
                    if step_rmse:
                        print(f"  Step RMSE (first 5): {[round(x, 4) for x in step_rmse[:5]]}")
                else:
                    # 原有的多输出特征模式（每个特征一个字典）
                    for output_name, metrics in train_metrics.items():
                        print(f"\n  输出特征: {output_name}")
                        print(f"    RMSE: {metrics.get('rmse', 0):.4f}")
                        print(f"    MAE: {metrics.get('mae', 0):.4f}")
                        print(f"    MAPE: {metrics.get('mape', 0):.4f}%")
                        print(f"    R²: {metrics.get('r2_score', 0):.4f}")
                        print(f"    样本数: {metrics.get('samples', 0)}")
                    # 计算并显示平均指标（仅在嵌套字典模式下）
                    r2_scores = [m.get('r2_score', 0) for m in train_metrics.values()]
                    rmse_scores = [m.get('rmse', 0) for m in train_metrics.values()]
                    avg_r2 = sum(r2_scores) / len(r2_scores) if r2_scores else 0
                    avg_rmse = sum(rmse_scores) / len(rmse_scores) if rmse_scores else 0
                    print(f"\n  训练集平均指标:")
                    print(f"    平均 R²: {avg_r2:.4f}")
                    print(f"    平均 RMSE: {avg_rmse:.4f}")
            else:
                # 单输出模式
                print(f"  RMSE: {train_metrics.get('rmse', 0):.4f}")
                print(f"  MAE: {train_metrics.get('mae', 0):.4f}")
                print(f"  MAPE: {train_metrics.get('mape', 0):.4f}%")
                print(f"  R²: {train_metrics.get('r2_score', 0):.4f}")
                print(f"  样本数: {train_metrics.get('samples', 0)}")

            if val_metrics:
                print("\n" + "=" * 60)
                print("📊 验证集性能指标:")
                print("=" * 60)

                if multi_output and isinstance(val_metrics, dict):
                    if 'overall_rmse' in val_metrics:
                        print(f"  Overall RMSE: {val_metrics['overall_rmse']:.4f}")
                        print(f"  Samples: {val_metrics['samples']}")
                        print(f"  Output Dimension: {val_metrics['output_dim']}")
                        step_rmse = val_metrics.get('step_rmse', [])
                        if step_rmse:
                            print(f"  Step RMSE (first 5): {[round(x, 4) for x in step_rmse[:5]]}")
                        # ========== 关键修复 ==========
                        r2_score_val = 0.0  # 多步预测没有单一的 R² 值，设为 0
                    else:
                        # 原有的多输出特征模式（每个特征一个字典）
                        for output_name, metrics in val_metrics.items():
                            print(f"\n  输出特征: {output_name}")
                            print(f"    RMSE: {metrics.get('rmse', 0):.4f}")
                            print(f"    MAE: {metrics.get('mae', 0):.4f}")
                            print(f"    MAPE: {metrics.get('mape', 0):.4f}%")
                            print(f"    R²: {metrics.get('r2_score', 0):.4f}")
                            print(f"    样本数: {metrics.get('samples', 0)}")
                        # 计算平均指标
                        r2_scores = [m.get('r2_score', 0) for m in val_metrics.values()]
                        rmse_scores = [m.get('rmse', 0) for m in val_metrics.values()]
                        avg_r2 = sum(r2_scores) / len(r2_scores) if r2_scores else 0
                        avg_rmse = sum(rmse_scores) / len(rmse_scores) if rmse_scores else 0
                        print(f"\n  验证集平均指标:")
                        print(f"    平均 R²: {avg_r2:.4f}")
                        print(f"    平均 RMSE: {avg_rmse:.4f}")
                        r2_score_val = avg_r2
                else:
                    # 单输出模式
                    print(f"  RMSE: {val_metrics.get('rmse', 0):.4f}")
                    print(f"  MAE: {val_metrics.get('mae', 0):.4f}")
                    print(f"  MAPE: {val_metrics.get('mape', 0):.4f}%")
                    print(f"  R²: {val_metrics.get('r2_score', 0):.4f}")
                    print(f"  样本数: {val_metrics.get('samples', 0)}")
                    r2_score_val = val_metrics.get('r2_score', 0)
            else:
                r2_score_val = 0

            print("\n" + "=" * 60)
            print("⏱️  训练时间统计:")
            print("=" * 60)
            print(f"  训练时间: {training_time:.2f}秒")
            print(f"  总耗时: {time.time() - start_time:.2f}秒")
            print("=" * 60 + "\n")

            log_message(f"✅ 模型训练完成，耗时 {training_time:.2f} 秒")
            log_message(f"📊 验证集R²分数: {r2_score_val:.4f}")
            # ========== 新增：提前计算总耗时 ==========
            end_time = time.time()
            total_duration = end_time - start_time

            # 10. 保存评估结果到数据库（可选）
            try:
                log_message("💾 保存评估结果到数据库...", "INFO")
                from app.crud.model_evaluation import ModelEvaluationCRUD
                from app.crud.model_training import TrainingCRUD

                training_crud = TrainingCRUD(self.db_session)
                evaluation_crud = ModelEvaluationCRUD(self.db_session)

                # 获取训练记录
                training_record = training_crud.get_training_by_device(device_id)

                # 计算训练时间
                training_time_seconds = int(total_duration)   # 使用整个流程的总耗时

                # 计算数据大小
                train_data_size = len(train_df)
                test_data_size = len(test_df) if test_df is not None else 0
                feature_count = len(feature_cols)

                # 计算多输出的平均评估指标
                # 计算多输出的平均评估指标
                avg_r2 = 0
                avg_rmse = 0
                avg_mae = 0

                if multi_output and isinstance(train_metrics, dict) and isinstance(val_metrics, dict):
                    # 如果有验证集，使用验证集指标；否则使用训练集指标
                    metrics_source = val_metrics if val_metrics else train_metrics

                    # 判断是否为多步输出模式（扁平字典，包含 'overall_rmse'）
                    if 'overall_rmse' in metrics_source:
                        # 扁平字典模式：XGBoostMultiStepTrainer 返回的指标
                        avg_rmse = metrics_source.get('overall_rmse', 0)
                        # 扁平字典中没有 MAE，可以从 step_rmse 计算平均（可选），这里简单设为 0
                        avg_mae = 0
                        avg_r2 = 0  # 多步预测没有单一的 R² 值
                        log_message(f"📊 多步输出整体 RMSE: {avg_rmse:.4f}")
                    else:
                        # 嵌套字典模式（多输出特征）
                        r2_scores = []
                        rmse_scores = []
                        mae_scores = []
                        for output_name, metrics in metrics_source.items():
                            if isinstance(metrics, dict):
                                if 'r2_score' in metrics:
                                    r2_scores.append(metrics['r2_score'])
                                if 'rmse' in metrics:
                                    rmse_scores.append(metrics['rmse'])
                                if 'mae' in metrics:
                                    mae_scores.append(metrics['mae'])
                        avg_r2 = sum(r2_scores) / len(r2_scores) if r2_scores else 0
                        avg_rmse = sum(rmse_scores) / len(rmse_scores) if rmse_scores else 0
                        avg_mae = sum(mae_scores) / len(mae_scores) if mae_scores else 0
                        log_message(f"📊 多输出平均指标: R²={avg_r2:.4f}, RMSE={avg_rmse:.4f}, MAE={avg_mae:.4f}")

                        # 记录每个输出特征的详细指标（仅嵌套字典模式）
                        output_features_metrics = {
                            output_name: {
                                'train': train_metrics.get(output_name, {}),
                                'val': val_metrics.get(output_name, {})
                            }
                            for output_name in output_feature_codes
                        }
                        training_stats['output_features_metrics'] = output_features_metrics

                else:
                    # 单输出模式
                    avg_r2 = r2_score_val
                    avg_rmse = val_metrics.get('rmse',
                                               train_metrics.get('rmse', 0)) if val_metrics else train_metrics.get(
                        'rmse', 0)
                    avg_mae = val_metrics.get('mae', train_metrics.get('mae', 0)) if val_metrics else train_metrics.get(
                        'mae', 0)

                # ========== 新增：提取残差修正模型指标 ==========
                r_squared_res = None
                rmse_res = None
                mae_res = None
                if 'comparison_with_residual' in training_stats:
                    total_metrics = training_stats['comparison_with_residual'].get('total_model_metrics')
                    if total_metrics:
                        r_squared_res = total_metrics.get('r2_score')
                        rmse_res = total_metrics.get('rmse')
                        mae_res = total_metrics.get('mae')
                        log_message(f"残差修正模型指标: R²={r_squared_res:.4f}, RMSE={rmse_res:.4f}, MAE={mae_res:.4f}",
                                    "INFO")
                # =============================================

                # 保存评估记录（包含基础模型和残差模型指标）
                evaluation_record = evaluation_crud.create_model_evaluation(
                    device_id=device_id,
                    r_squared=avg_r2,
                    rmse=avg_rmse,
                    mae=avg_mae,
                    training_time=training_time_seconds,
                    training_data_size=train_data_size,
                    test_data_size=test_data_size,
                    feature_count=feature_count,
                    r_squared_residual=r_squared_res,
                    rmse_residual=rmse_res,
                    mae_residual=mae_res
                )
                if evaluation_record:
                    log_message(f"✅ 评估结果已保存到数据库，记录ID: {evaluation_record.id}", "SUCCESS")
                    # 保存详细的多输出指标到额外的JSON字段（如果需要）
                    if multi_output and 'output_features_metrics' in training_stats:
                        # 可以将详细指标保存到其他表或JSON字段
                        # 这里我们只记录日志，因为数据库表结构未修改
                        log_message(f"📋 多输出详细指标已保存到训练统计中", "INFO")

            except Exception as e:
                log_message(f"⚠️ 保存评估结果时出错: {e}", "WARNING")

            # 11. 构建结果
            data_sources_info = []
            for mapping in mappings:
                # 获取数据源信息
                data_source = self.db_session.query(models.DataSources).filter(
                    models.DataSources.id == mapping.data_source_id
                ).first() if hasattr(mapping, 'data_source_id') else None

                # 获取特征信息
                feature = self.db_session.query(models.Feature).filter(
                    models.Feature.id == mapping.feature_id
                ).first() if hasattr(mapping, 'feature_id') else None

                data_sources_info.append({
                    'data_source_id': getattr(mapping, 'data_source_id', None),
                    'database': getattr(data_source, 'database_name', '未知') if data_source else '未知',
                    'table': getattr(mapping, 'table_name', '未知'),
                    'feature': getattr(feature, 'code', '未知') if feature else '未知',
                    'feature_name': getattr(feature, 'name', '未知') if feature else '未知'
                })

            end_time = time.time()
            total_duration = end_time - start_time

            # 计算多输出的平均性能指标
            performance_metrics = {}
            if multi_output and isinstance(train_metrics, dict):
                # 如果有验证集，使用验证集指标；否则使用训练集指标
                metrics_source = val_metrics if val_metrics and isinstance(val_metrics, dict) else train_metrics

                # 判断是否为扁平字典（多步输出模式）
                if 'overall_rmse' in metrics_source:
                    # 扁平字典模式：直接使用整体 RMSE，没有 R² 和 MAE
                    performance_metrics = {
                        'r2_score': 0,
                        'rmse': metrics_source.get('overall_rmse', 0),
                        'mae': 0,
                        'mape': None,
                        'is_multi_output': True,
                        'output_count': len(output_feature_codes),
                        'output_features': output_feature_codes,
                        'detailed_metrics': {
                            'train': train_metrics,
                            'val': val_metrics if val_metrics else {}
                        }
                    }
                else:
                    # 嵌套字典模式（多输出特征）
                    r2_scores = []
                    rmse_scores = []
                    mae_scores = []
                    for output_name, metrics in metrics_source.items():
                        if isinstance(metrics, dict):
                            if 'r2_score' in metrics:
                                r2_scores.append(metrics['r2_score'])
                            if 'rmse' in metrics:
                                rmse_scores.append(metrics['rmse'])
                            if 'mae' in metrics:
                                mae_scores.append(metrics['mae'])
                    performance_metrics = {
                        'r2_score': sum(r2_scores) / len(r2_scores) if r2_scores else 0,
                        'rmse': sum(rmse_scores) / len(rmse_scores) if rmse_scores else 0,
                        'mae': sum(mae_scores) / len(mae_scores) if mae_scores else 0,
                        'mape': None,
                        'is_multi_output': True,
                        'output_count': len(output_feature_codes),
                        'output_features': output_feature_codes,
                        'detailed_metrics': {
                            'train': train_metrics,
                            'val': val_metrics if val_metrics else {}
                        }
                    }
            else:
                # 单输出模式
                performance_metrics = {
                    'r2_score': r2_score_val,
                    'rmse': val_metrics.get('rmse', train_metrics.get('rmse', 0)) if val_metrics else train_metrics.get(
                        'rmse', 0),
                    'mae': val_metrics.get('mae', train_metrics.get('mae', 0)) if val_metrics else train_metrics.get(
                        'mae', 0),
                    'mape': val_metrics.get('mape', train_metrics.get('mape', 0)) if val_metrics else train_metrics.get(
                        'mape', 0),
                    'is_multi_output': False
                }

            # 构建成功结果
            result = {
                'device_id': device_id,
                'target_feature': target_feature,
                'training_success': True,
                'model_info': self.trainer.get_model_info(),
                'data_info': {
                    'train_samples': len(train_df),
                    'test_samples': len(test_df) if test_df is not None else 0,
                    'feature_count': len(feature_cols),
                    'look_back': config['look_back'],
                    'forecast_horizon': config['forecast_horizon'],
                    'total_features_loaded': len(all_feature_codes),
                    'data_source': f"MySQL - {len(mappings)} 个映射表"
                },
                'performance_metrics': performance_metrics,  # 更新为新的格式
                'training_details': {
                    'training_time_seconds': training_time,
                    'total_duration_seconds': total_duration,
                    'start_time': start_time,
                    'end_time': end_time,
                    'model_params': training_stats.get('model_params', {}),
                    'data_shapes': training_stats.get('data_shapes', {}),
                    'feature_importance': training_stats.get('feature_importance', {}).get('top_features', []),
                    'training_logs': logs,
                    'multi_output': multi_output,
                    'output_features': output_feature_codes if multi_output else [target_feature],
                    'output_metrics': {
                        'train': train_metrics,
                        'val': val_metrics if val_metrics else {}
                    }
                },
                'config': config,
                'trained_at': datetime.now().isoformat(),
                'data_sources': data_sources_info
            }

            log_message(f"🎉 设备 {device_id} 模型训练完成，总耗时 {total_duration:.2f} 秒", "SUCCESS")

            if multi_output:
                # 多输出模式：显示每个输出特征的性能
                if val_metrics and isinstance(val_metrics, dict):
                    # 判断是否为扁平字典（多步输出模式）
                    if 'overall_rmse' in val_metrics:
                        # 扁平字典模式：显示整体指标
                        log_message(f"📈 多步输出整体 RMSE: {val_metrics['overall_rmse']:.4f}")
                        log_message(f"📈 样本数: {val_metrics['samples']}")
                        log_message(f"📈 输出维度: {val_metrics['output_dim']}")
                    else:
                        # 嵌套字典模式（多输出特征）
                        for output_name, metrics in val_metrics.items():
                            if isinstance(metrics, dict):
                                log_message(
                                    f"📈 输出特征 {output_name}: R²={metrics.get('r2_score', 0):.4f}, RMSE={metrics.get('rmse', 0):.4f}")
                        # 计算平均
                        r2_scores = [m.get('r2_score', 0) for m in val_metrics.values() if isinstance(m, dict)]
                        avg_r2 = sum(r2_scores) / len(r2_scores) if r2_scores else 0
                        log_message(f"📊 多输出平均性能: R²={avg_r2:.4f}")
                else:
                    # 如果没有验证集，使用训练集指标
                    if train_metrics and isinstance(train_metrics, dict):
                        if 'overall_rmse' in train_metrics:
                            log_message(f"📈 多步输出整体 RMSE: {train_metrics['overall_rmse']:.4f}")
                            log_message(f"📈 样本数: {train_metrics['samples']}")
                            log_message(f"📈 输出维度: {train_metrics['output_dim']}")
                        else:
                            for output_name, metrics in train_metrics.items():
                                if isinstance(metrics, dict):
                                    log_message(
                                        f"📈 输出特征 {output_name}: R²={metrics.get('r2_score', 0):.4f}, RMSE={metrics.get('rmse', 0):.4f}")
                            r2_scores = [m.get('r2_score', 0) for m in train_metrics.values() if isinstance(m, dict)]
                            avg_r2 = sum(r2_scores) / len(r2_scores) if r2_scores else 0
                            log_message(f"📊 多输出平均性能: R²={avg_r2:.4f}")

            else:
                # 单输出模式
                log_message(f"📈 最终性能: R²={r2_score_val:.4f}, RMSE={result['performance_metrics']['rmse']:.4f}")

            # 12. 保存模型文件
            try:
                log_message("💾 保存模型文件...", "INFO")

                # 保存模型文件
                base_dir = os.path.dirname(os.path.abspath(__file__))
                model_dir = os.path.join(base_dir,"models","saved_models")
                os.makedirs(model_dir, exist_ok=True)

                # 构建模型文件名
                model_filename = f"xgboost_device_{device_id}_{target_feature}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
                model_path = os.path.join(model_dir, model_filename)

                # 清理旧模型
                try:
                    pattern = f"xgboost_device_{device_id}_{target_feature}_*.pkl"
                    existing_models = [f for f in os.listdir(model_dir) if
                                       f.startswith(f"xgboost_device_{device_id}_{target_feature}_") and f.endswith(
                                           '.pkl')]

                    if existing_models:
                        log_message(f"找到 {len(existing_models)} 个历史模型文件，正在清理...", "INFO")
                        for old_model in existing_models:
                            try:
                                os.remove(os.path.join(model_dir, old_model))
                                log_message(f"  已删除旧模型: {old_model}", "INFO")
                            except Exception as e:
                                log_message(f"  删除旧模型失败 {old_model}: {e}", "WARNING")
                except Exception as e:
                    log_message(f"清理旧模型时出错: {e}", "WARNING")

                # 准备训练配置
                training_config = {
                    **config,
                    'data_sources': data_sources_info,
                    'target_feature': target_feature,
                    'device_id': device_id,
                    'look_back': config['look_back'],
                    'output_feature_code': target_feature,
                    'model_version_id': model_version_id,
                    'feature_names': feature_cols,
                    'multi_output': multi_output,  # 添加多输出标志
                    'output_features': output_feature_codes if multi_output else [target_feature]
                }

                # 添加输出特征ID
                if multi_output and 'target_feature_obj' in locals() and target_feature_obj:
                    training_config['output_feature_id'] = target_feature_obj.id
                    training_config['primary_output_feature'] = target_feature
                    training_config['all_output_features'] = output_feature_codes
                elif not multi_output and 'target_feature_obj' in locals() and target_feature_obj:
                    training_config['output_feature_id'] = target_feature_obj.id
                else:
                    training_config['output_feature_id'] = None

                # 保存模型
                save_success = self.trainer.save_model(model_path, training_config=training_config)

                if save_success:
                    log_message("✅ 模型保存成功", "SUCCESS")
                else:
                    log_message("⚠️ 保存模型文件失败", "WARNING")

            except Exception as e:
                log_message(f"⚠️ 保存模型时出错: {e}", "WARNING")
            result = convert_numpy_types(result)
            # 写入训练日志
            training_log = {
                'timestamp': datetime.now().isoformat(),
                'device_id': device_id,
                'target_feature': target_feature,
                'training_success': True,
                'r2_score': result.get('performance_metrics', {}).get('r2_score'),
                'rmse': result.get('performance_metrics', {}).get('rmse'),
                'mae': result.get('performance_metrics', {}).get('mae'),
                'training_time_s': round(training_time, 2),
                'train_samples': result.get('data_info', {}).get('train_samples'),
                'test_samples': result.get('data_info', {}).get('test_samples'),
                'feature_count': result.get('data_info', {}).get('feature_count'),
                'trainer_name': self.trainer.__class__.__name__ if self.trainer else None,
            }
            self._write_training_log(training_log)
            return result

        except Exception as e:
            error_msg = f"训练失败: {str(e)}"
            log_message(error_msg, "ERROR")
            logger.error(f"设备模型训练失败: {e}", exc_info=True)

            end_time = time.time()
            total_duration = end_time - start_time

            # 构建失败结果
            result.update({
                'training_success': False,
                'error_message': error_msg,
                'training_details': {
                    'training_logs': logs,
                    'start_time': start_time,
                    'end_time': end_time,
                    'total_duration_seconds': total_duration,
                    'error': str(e)
                }
            })
            # 写入训练日志
            training_log = {
                'timestamp': datetime.now().isoformat(),
                'device_id': device_id,
                'target_feature': target_feature,
                'training_success': False,
                'error_message': error_msg,
                'training_time_s': round(total_duration, 2),
                'trainer_name': self.trainer.__class__.__name__ if self.trainer else None,
            }
            self._write_training_log(training_log)
            return result



# 单例模式
_ml_start = None


def get_ml_start(db_session=None) -> MLStart:
    """获取ML启动器单例"""
    global _ml_start
    if _ml_start is None:
        _ml_start = MLStart(db_session)
    elif db_session and _ml_start.db_session is None:
        _ml_start.db_session = db_session
    return _ml_start