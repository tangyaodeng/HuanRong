"""
简化的XGBoost模型训练器 backend/ml/models/trainers/device7_xgboost_v1.py
"""
import xgboost as xgb
import numpy as np
from typing import Dict, Optional, List
import logging
import pickle
from datetime import datetime
from sklearn.multioutput import MultiOutputRegressor
from sklearn.metrics import mean_squared_error
import time

logger = logging.getLogger(__name__)

class XGBoostMultiStepTrainer:
    """
    多步负荷预测训练器（未来24小时）
    使用 MultiOutputRegressor 包装 XGBRegressor
    """

    def __init__(self):
        self.model = None               # MultiOutputRegressor 对象
        self.output_dim = 24            # 预测步长
        self.model_params = {}
        self.training_stats = {}
        self.feature_importance = {}
        self.feature_names = []
        # 残差模型（可选，多输出情况下复杂度较高，建议先禁用）
        self.residual_model = None
        self.residual_lags = 0
        self.residual_mean = 0.0
        self.residual_std = 1.0
        self.use_standardize = False
        self.best_alpha = 1.0

    def _flatten_X(self, X: np.ndarray) -> np.ndarray:
        if X is None:
            return None
        if len(X.shape) == 3:
            n_samples, look_back, n_features = X.shape
            return X.reshape(n_samples, look_back * n_features)
        return X

    def _get_default_params(self) -> Dict:
        return {
            'n_estimators': 200,
            'max_depth': 6,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'n_jobs': -1,
            'reg_alpha': 1.0,
            'reg_lambda': 1.0,
            'min_child_weight': 1,
            'gamma': 0.0,
            'verbosity': 0,
            'objective': 'reg:squarederror',
        }

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,          # 形状 (n_samples, output_dim)
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        params: Optional[Dict] = None,
        early_stopping_rounds: int = 30,
        feature_names: Optional[List[str]] = None,
        output_dim: int = 24,         # 新增参数
        train_residual_model: bool = False,   # 多输出下暂不启用残差
        **kwargs
    ) -> Dict:
        start_time = time.time()

        # 1. 参数设置
        self.output_dim = output_dim
        model_params = self._get_default_params()
        if params:
            model_params.update(params)

        # 多输出时不能使用 xgb.train 的 early_stopping（因为 MultiOutputRegressor 不直接支持）
        # 我们采用内部 XGBRegressor 的 early_stopping_rounds（需传递 eval_set）
        model_params.pop('early_stopping_rounds', None)

        # 2. 特征名称记录
        if feature_names:
            self.feature_names = feature_names
        else:
            if len(X_train.shape) == 2:
                self.feature_names = [f'feature_{i}' for i in range(X_train.shape[1])]
            else:
                n_samples, look_back, n_features = X_train.shape
                self.feature_names = [f't{i}_f{j}' for i in range(look_back) for j in range(n_features)]

        # 3. 展平 X（如果需要）
        X_train_flat = self._flatten_X(X_train)
        X_val_flat = self._flatten_X(X_val) if X_val is not None else None

        # 4. 确保 y 是二维 (n_samples, output_dim)
        if y_train.ndim == 1:
            # 如果只给了一维，假设是单步，广播到多步（不合理，但兼容）
            y_train = y_train.reshape(-1, 1)
        if y_train.shape[1] != output_dim:
            logger.warning(f"y_train 的列数 ({y_train.shape[1]}) 与 output_dim ({output_dim}) 不一致，将截断或填充")
            if y_train.shape[1] > output_dim:
                y_train = y_train[:, :output_dim]
            else:
                pad = np.zeros((y_train.shape[0], output_dim - y_train.shape[1]))
                y_train = np.hstack([y_train, pad])

        # 5. 创建 MultiOutputRegressor
        from xgboost import XGBRegressor
        base_estimator = XGBRegressor(**model_params)
        self.model = MultiOutputRegressor(base_estimator, n_jobs=model_params.get('n_jobs', -1))

        # 6. 训练（注意：MultiOutputRegressor 不支持传入 eval_set 做早停，只能通过每个子模型的 early_stopping_rounds）
        #    但 XGBRegressor 的 early_stopping 需要 eval_set，这里简化：先不使用早停，或手动实现
        #    我们去掉 early_stopping，因为 MultiOutputRegressor 无法传递多个 eval_set
        #    如果需要早停，需自行实现循环。
        logger.info("开始训练多输出 XGBoost 模型（每个输出维度独立训练）...")
        self.model.fit(X_train_flat, y_train)

        # 7. 评估训练集性能
        y_train_pred = self.model.predict(X_train_flat)  # shape (n_samples, output_dim)
        train_metrics = self._calculate_multistep_metrics(y_train, y_train_pred)

        # 8. 验证集评估
        val_metrics = {}
        if X_val_flat is not None and y_val is not None:
            y_val_pred = self.model.predict(X_val_flat)
            val_metrics = self._calculate_multistep_metrics(y_val, y_val_pred)

        # 9. 特征重要性（多输出模型无法直接获取，取第一个子模型的重要性作为参考）
        if hasattr(self.model.estimators_[0], 'feature_importances_'):
            importances = self.model.estimators_[0].feature_importances_
            self.feature_importance = {
                'importance_array': importances.tolist(),
                'top_features': sorted(zip(self.feature_names, importances), key=lambda x: x[1], reverse=True)[:20]
            }

        # 10. 训练统计
        training_time = time.time() - start_time
        self.training_stats = {
            'training_time_seconds': training_time,
            'model_params': model_params,
            'output_dim': output_dim,
            'train_metrics': train_metrics,
            'val_metrics': val_metrics,
            'feature_importance': self.feature_importance,
            'feature_names': self.feature_names,
        }
        logger.info(f"✅ 多步训练完成，耗时 {training_time:.2f} 秒")
        # 在 train() 方法中，训练结束后添加：
        y_train_array = y_train  # shape (n_samples, output_dim)
        if y_train_array.ndim == 2:
            # 多输出：为每个输出分别计算统计量，或统一计算（取决于业务）
            self.target_mean = np.mean(y_train_array, axis=0)  # shape (output_dim,)
            self.target_std = np.std(y_train_array, axis=0)
        else:
            self.target_mean = np.mean(y_train_array)
            self.target_std = np.std(y_train_array)

        # 将统计量存入 training_stats 供保存
        self.training_stats['standardization_stats'] = {
            'target_mean': self.target_mean.tolist() if isinstance(self.target_mean, np.ndarray) else self.target_mean,
            'target_std': self.target_std.tolist() if isinstance(self.target_std, np.ndarray) else self.target_std,
            'method': 'standard'
        }
        return self.training_stats

    def _calculate_multistep_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        """计算多步预测的整体指标（平均RMSE、按步长RMSE等）"""
        y_true = np.asarray(y_true)
        y_pred = np.asarray(y_pred)
        n_samples, n_steps = y_true.shape

        # 整体 RMSE（所有预测值一起计算）
        overall_rmse = np.sqrt(mean_squared_error(y_true.flatten(), y_pred.flatten()))
        # 每个步长的 RMSE
        step_rmse = [np.sqrt(mean_squared_error(y_true[:, i], y_pred[:, i])) for i in range(n_steps)]

        return {
            'overall_rmse': float(overall_rmse),
            'step_rmse': step_rmse,
            'samples': n_samples,
            'output_dim': n_steps,
        }

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        预测未来 output_dim 个时间点的值
        返回形状: (n_samples, output_dim)
        """
        if self.model is None:
            raise ValueError("模型未训练")
        X_flat = self._flatten_X(X)
        pred = self.model.predict(X_flat)   # shape (n_samples, output_dim)
        return pred

    def save_model(self, filepath: str, training_config: Optional[Dict] = None) -> bool:
        try:
            model_data = {
                'model': self.model,
                'output_dim': self.output_dim,
                'model_params': self.model_params,
                'training_stats': self.training_stats,
                'feature_names': self.feature_names,
                'saved_at': datetime.now().isoformat(),
                'training_config': training_config or {},
                # 残差相关（可省略）
                'residual_lags': 0,
                'use_standardize': False,
                'best_alpha': 1.0,
                'target_mean': getattr(self, 'target_mean', None),
                'target_std': getattr(self, 'target_std', None),
                'scaler': getattr(self, 'scaler', None),  # 如果有 scaler 对象
            }
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            logger.info(f"✅ 多步模型已保存到 {filepath}")
            return True
        except Exception as e:
            logger.error(f"保存模型失败: {e}")
            return False

    def load_model(self, model_path: str) -> bool:
        try:
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
            self.model = model_data['model']
            self.output_dim = model_data.get('output_dim', 24)
            self.model_params = model_data.get('model_params', {})
            self.training_stats = model_data.get('training_stats', {})
            self.feature_names = model_data.get('feature_names', [])
            logger.info(f"✅ 多步模型已从 {model_path} 加载，输出维度={self.output_dim}")
            return True
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False

    def get_model_info(self) -> Dict:
        return {
            'model_type': 'xgboost_multistep',
            'output_dim': self.output_dim,
            'is_trained': self.model is not None,
            'feature_names': self.feature_names,
        }