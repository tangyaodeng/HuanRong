"""
简化的XGBoost模型训练器 backend/ml/models/trainers/device11_xgboost_v1.py
"""
import xgboost as xgb
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import logging
import pickle
from datetime import datetime
from sklearn.metrics import mean_squared_error
from sklearn.multioutput import MultiOutputRegressor
import time
from collections import deque

logger = logging.getLogger(__name__)

class XGBoostTrainer:
    """增强版 XGBoost 训练器，支持残差修正模型"""

    def __init__(self):
        self.model = None               # 基础模型 (xgb.Booster)
        self.residual_model = None       # 残差修正模型 (sklearn 估计器，可选)
        self.model_params = {}
        self.training_stats = {}
        self.feature_importance = {}
        self.feature_names = []          # 特征名称列表

        # 新增：残差滞后相关属性
        self.residual_lags = 0
        self.residual_mean = 0.0
        self.residual_std = 1.0
        self.use_standardize = False
        self.best_alpha = 1.0  # 默认不收缩

    def _flatten_X(self, X: np.ndarray) -> np.ndarray:
        """
        如果输入是 3D (样本, 时间步, 特征)，展平为 2D (样本, 时间步*特征)
        否则原样返回。
        """
        if X is None:
            return None
        if len(X.shape) == 3:
            n_samples, look_back, n_features = X.shape
            return X.reshape(n_samples, look_back * n_features)
        return X

    def _get_default_params(self) -> Dict:
        """返回默认训练参数"""
        return {
            'objective': 'reg:squarederror',
            'n_estimators': 200,
            'max_depth': 6,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'random_state': 42,
            'n_jobs': -1,
            'eval_metric': ['rmse', 'mae'],
            'early_stopping_rounds': 30,
            'reg_alpha': 1.0,
            'reg_lambda': 1.0,
            'min_child_weight': 1,
            'gamma': 0.0,
            'verbosity': 0,
            'booster': 'gbtree',
            'base_score': 0.5,
        }

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        params: Optional[Dict] = None,
        early_stopping_rounds: int = 30,
        feature_names: Optional[List[str]] = None,
        train_residual_model: bool = True,          # 新增：是否训练残差模型
        residual_model_type: str = 'xgb_simple',    # 残差模型类型（预留扩展）
        residual_lags: int = 5,  # 新增：残差滞后步数
        residual_standardize: bool = False,  # 新增：是否标准化残差
        residual_objective: str = 'reg:squarederror'  # 新增：残差模型目标函数
    ) -> Dict:
        """
        训练 XGBoost 模型，并可选的训练残差修正模型。

        参数：
            X_train, y_train: 训练数据
            X_val, y_val: 验证数据（用于早停）
            params: 模型参数
            early_stopping_rounds: 早停轮数
            feature_names: 特征名称列表
            train_residual_model: 是否训练残差模型
            residual_model_type: 残差模型类型，目前仅支持 'xgb_simple'
                新增参数：
            residual_lags: 残差滞后步数，用于为残差模型添加历史残差特征
            residual_standardize: 是否对残差进行标准化（均值为0，方差为1）
            residual_objective: 残差模型的目标函数，如 'reg:squarederror', 'reg:tweedie'
        """
        start_time = time.time()

        # 1. 基础模型训练
        model_params = self._get_default_params()
        if params:
            model_params.update(params)
        if early_stopping_rounds:
            model_params['early_stopping_rounds'] = early_stopping_rounds

        self.model_params = model_params
        logger.info(f"开始训练基础 XGBoost 模型，参数: {model_params}")

        # 记录特征名称
        if feature_names:
            self.feature_names = feature_names
        else:
            if len(X_train.shape) == 2:
                self.feature_names = [f'feature_{i}' for i in range(X_train.shape[1])]
            elif len(X_train.shape) == 3:
                n_samples, look_back, n_features = X_train.shape
                self.feature_names = [f't{i}_f{j}' for i in range(look_back) for j in range(n_features)]

        # 展平训练数据（基础模型内部可能需要）
        X_train_flat = self._flatten_X(X_train)
        X_val_flat = self._flatten_X(X_val) if X_val is not None else None

        # 处理 y 维度：如果 y 是多步预测，取第一步作为目标（简化）
        if len(y_train.shape) > 1 and y_train.shape[1] > 1:
            y_train_1d = y_train[:, 0]
            logger.info("多步预测：仅使用第一步作为训练目标")
        else:
            y_train_1d = y_train

        if y_val is not None and len(y_val.shape) > 1 and y_val.shape[1] > 1:
            y_val_1d = y_val[:, 0]
        else:
            y_val_1d = y_val

        # 创建 DMatrix
        dtrain = xgb.DMatrix(X_train_flat, label=y_train_1d, feature_names=self.feature_names)
        eval_set = []
        if X_val_flat is not None and y_val_1d is not None:
            dval = xgb.DMatrix(X_val_flat, label=y_val_1d, feature_names=self.feature_names)
            eval_set = [(dtrain, 'train'), (dval, 'val')]

        # 训练基础模型
        self.model = xgb.train(
            model_params,
            dtrain,
            num_boost_round=model_params.get('n_estimators', 200),
            evals=eval_set if eval_set else None,
            early_stopping_rounds=model_params.get('early_stopping_rounds', 30),
            verbose_eval=10
        )

        # 计算训练集上的基础预测（用于残差计算）
        y_train_pred_base = self._predict_base(X_train)

        # 2. 训练残差模型
        if train_residual_model:
            logger.info("开始训练残差修正模型...")
            residuals = y_train_1d - y_train_pred_base

            # 保存残差滞后步数及标准化标志
            self.residual_lags = residual_lags
            self.use_standardize = residual_standardize

            # 准备残差模型训练数据（基础特征 + 可选滞后特征）
            X_train_res = X_train_flat.copy()

            # 如果需要添加滞后特征
            if residual_lags > 0:
                # 构造残差滞后特征矩阵
                lag_features = self._build_residual_lags(residuals, residual_lags)
                X_train_res = np.hstack([X_train_res, lag_features])
                logger.info(f"已添加 {residual_lags} 步残差滞后特征，新特征维度: {X_train_res.shape[1]}")

            # 可选：残差标准化
            if residual_standardize:
                self.residual_mean = np.mean(residuals)
                self.residual_std = np.std(residuals) if np.std(residuals) > 0 else 1.0
                residuals_scaled = (residuals - self.residual_mean) / self.residual_std
                logger.info(f"残差标准化: mean={self.residual_mean:.4f}, std={self.residual_std:.4f}")
            else:
                residuals_scaled = residuals

            # 训练残差模型
            if residual_model_type == 'xgb_simple':
                from xgboost import XGBRegressor
                res_params = {
                    'n_estimators': 20,
                    'max_depth': 2,
                    'learning_rate': 0.05,
                    'subsample': 0.6,
                    'colsample_bytree': 0.6,
                    'reg_alpha': 2.0,  # 增加L1正则
                    'reg_lambda': 2.0,  # 增加L2正则
                    'random_state': 42,
                    'n_jobs': -1,
                    'verbosity': 0,
                    'objective': residual_objective  # 使用传入的目标函数
                }

                if len(residuals_scaled.shape) > 1 and residuals_scaled.shape[1] > 1:
                    base_est = XGBRegressor(**res_params)
                    self.residual_model = MultiOutputRegressor(base_est)
                else:
                    self.residual_model = XGBRegressor(**res_params)

                self.residual_model.fit(X_train_res, residuals_scaled)

                # 评估残差模型在训练集上的效果
                res_pred_scaled = self.residual_model.predict(X_train_res)
                if residual_standardize:
                    res_pred = res_pred_scaled * self.residual_std + self.residual_mean
                else:
                    res_pred = res_pred_scaled
                res_rmse = np.sqrt(mean_squared_error(residuals, res_pred))
                logger.info(f"残差模型训练完成，训练集残差预测 RMSE: {res_rmse:.4f}")

                # 验证集评估（如果有）
                if X_val_flat is not None and y_val_1d is not None:
                    y_val_pred_base = self._predict_base(X_val)
                    val_residuals = y_val_1d - y_val_pred_base

                    # 构建验证集滞后特征（使用训练集残差？注意：验证集滞后特征应使用验证集自身的真实残差，但这里我们无法提前知道验证集残差）
                    # 简化处理：对于验证集，我们只能使用训练集末尾的残差填充？这里为了评估，我们可以使用验证集真实的残差滞后（但会造成数据泄露）
                    # 实际应用中，应在验证集上模拟预测流程，使用历史真实残差。这里仅作演示，使用验证集真实残差滞后（不推荐，但便于评估）
                    X_val_res = X_val_flat.copy()
                    if residual_lags > 0:
                        # 注意：这里用了验证集自身的残差，实际预测时不可用，仅用于评估模型拟合能力
                        val_lag_features = self._build_residual_lags(val_residuals, residual_lags)
                        X_val_res = np.hstack([X_val_res, val_lag_features])

                    val_res_pred_scaled = self.residual_model.predict(X_val_res)
                    if residual_standardize:
                        val_res_pred = val_res_pred_scaled * self.residual_std + self.residual_mean
                    else:
                        val_res_pred = val_res_pred_scaled
                    val_res_rmse = np.sqrt(mean_squared_error(val_residuals, val_res_pred))
                    logger.info(
                        f"残差模型在验证集上的残差预测 RMSE: {val_res_rmse:.4f} (注意：验证集使用了真实残差滞后，指标可能偏乐观)")

            else:
                logger.warning(f"未知的残差模型类型 '{residual_model_type}'，跳过残差训练")


        # 3. 收集训练统计
        training_time = time.time() - start_time

        # 计算训练集指标（基础模型）
        train_metrics = self._calculate_metrics(y_train_1d, y_train_pred_base)

        # 计算验证集指标（如果有）
        val_metrics = {}
        if X_val is not None and y_val is not None:
            y_val_pred_base = self._predict_base(X_val)
            val_metrics = self._calculate_metrics(y_val_1d, y_val_pred_base)

        # 特征重要性
        self.feature_importance = self._get_feature_importance(X_train_flat)

        # 保存训练统计
        self.training_stats = {
            'training_time_seconds': training_time,
            'model_params': model_params,
            'train_metrics': train_metrics,
            'val_metrics': val_metrics,
            'feature_importance': self.feature_importance,
            'data_shapes': {
                'X_train': X_train.shape,
                'y_train': y_train.shape,
                'X_val': X_val.shape if X_val is not None else None,
                'y_val': y_val.shape if y_val is not None else None
            },
            'feature_names': self.feature_names,
            'data_stats': {
                'y_train_mean': float(np.mean(y_train)),
                'y_train_std': float(np.std(y_train)) if np.std(y_train) > 0 else 1.0,
                'y_val_mean': float(np.mean(y_val)) if y_val is not None else None,
                'y_val_std': float(np.std(y_val)) if y_val is not None else None
            },
            'residual_model_trained': train_residual_model
        }
        # ========== 滚动评估 + 最优 alpha 搜索 ==========
        if X_val is not None and y_val is not None and train_residual_model and self.residual_model is not None:
            logger.info("开始对验证集进行滚动评估，并搜索最优收缩系数 alpha ...")

            # 准备验证集数据
            X_val_flat = self._flatten_X(X_val)
            y_val_1d = y_val[:, 0] if len(y_val.shape) > 1 and y_val.shape[1] > 1 else y_val
            y_val_1d = np.asarray(y_val_1d).flatten()

            # 计算基础模型预测值（批量）
            y_pred_base = self._predict_base(X_val).flatten()

            # 初始化残差历史队列（使用训练集最后 residual_lags 个真实残差）
            X_train_flat = self._flatten_X(X_train)
            y_train_1d = y_train[:, 0] if len(y_train.shape) > 1 and y_train.shape[1] > 1 else y_train
            y_train_pred_base = self._predict_base(X_train).flatten()
            train_residuals = y_train_1d - y_train_pred_base

            from collections import deque
            hist_residuals = deque(maxlen=self.residual_lags) if self.residual_lags > 0 else None
            if self.residual_lags > 0:
                hist_residuals.extend(train_residuals[-self.residual_lags:])
                while len(hist_residuals) < self.residual_lags:
                    hist_residuals.appendleft(0.0)

            # 滚动预测，存储基础预测和残差预测
            base_preds = []
            residual_preds = []
            for i in range(len(X_val_flat)):
                x = X_val_flat[i:i + 1]

                # 构造残差模型输入
                if self.residual_lags > 0:
                    lag_list = list(hist_residuals)
                    if len(lag_list) < self.residual_lags:
                        lag_list = [0.0] * (self.residual_lags - len(lag_list)) + lag_list
                    lag_features = np.array(lag_list).reshape(1, -1)
                    x_res = np.hstack([x, lag_features])
                else:
                    x_res = x

                # 预测残差
                residual_scaled = self.residual_model.predict(x_res)
                if self.use_standardize:
                    residual = residual_scaled * self.residual_std + self.residual_mean
                else:
                    residual = residual_scaled
                if isinstance(residual, np.ndarray) and residual.ndim == 2:
                    residual = residual.flatten()[0]
                else:
                    residual = float(residual)

                base_pred = self._predict_base(x).flatten()[0]
                base_preds.append(base_pred)
                residual_preds.append(residual)

                # 更新历史队列（使用真实残差）
                true_residual = y_val_1d[i] - base_pred
                if self.residual_lags > 0:
                    hist_residuals.append(true_residual)

            base_preds = np.array(base_preds)
            residual_preds = np.array(residual_preds)

            # 搜索最优 alpha (0.0 ~ 1.0, step 0.01)
            alphas = np.arange(0, 1.05, 0.01)
            best_alpha = 1.0
            best_rmse = float('inf')
            best_metrics = None

            for alpha in alphas:
                y_pred_alpha = base_preds + alpha * residual_preds
                metrics = self._calculate_metrics(y_val_1d, y_pred_alpha)
                if metrics['rmse'] < best_rmse:
                    best_rmse = metrics['rmse']
                    best_alpha = alpha
                    best_metrics = metrics

            logger.info(f"最优收缩系数 alpha = {best_alpha:.2f}, 整体 RMSE = {best_rmse:.4f}")
            self.best_alpha = best_alpha  # 保存到实例属性

            # 打印对比表格（使用最优 alpha 的指标）
            logger.info("=" * 70)
            logger.info("模型性能对比 (验证集 - 滚动评估 + 最优收缩)")
            logger.info("=" * 70)
            logger.info(f"{'指标':<12} {'基础XGBoost':>18} {'XGBoost+残差(最优α)':>22} {'改善':>12}")
            logger.info("-" * 70)
            base_metrics = self._calculate_metrics(y_val_1d, base_preds)
            for metric in ['rmse', 'mae', 'r2_score', 'mape']:
                base_val = base_metrics.get(metric, 0)
                total_val = best_metrics.get(metric, 0)
                if metric in ['rmse', 'mae', 'mape']:
                    improvement = (base_val - total_val) / base_val * 100 if base_val != 0 else 0
                    arrow = "↓" if improvement > 0 else "↑"
                    logger.info(
                        f"{metric.upper():<12} {base_val:>18.4f} {total_val:>22.4f} {arrow}{abs(improvement):>10.2f}%")
                else:
                    improvement = total_val - base_val
                    arrow = "↑" if improvement > 0 else "↓"
                    logger.info(
                        f"{metric.upper():<12} {base_val:>18.4f} {total_val:>22.4f} {arrow}{abs(improvement):>10.4f}")
            logger.info("=" * 70)

            # 将对比结果保存到 training_stats（可选）
            self.training_stats['comparison_with_residual'] = {
                'best_alpha': float(best_alpha),
                'base_model_metrics': base_metrics,
                'total_model_metrics': best_metrics,
                'improvement': {
                    'rmse_improvement_pct': (base_metrics['rmse'] - best_metrics['rmse']) / base_metrics[
                        'rmse'] * 100 if base_metrics['rmse'] != 0 else 0,
                    'mae_improvement_pct': (base_metrics['mae'] - best_metrics['mae']) / base_metrics['mae'] * 100 if
                    base_metrics['mae'] != 0 else 0,
                    'r2_increase': best_metrics['r2_score'] - base_metrics['r2_score'],
                    'mape_improvement_pct': (base_metrics['mape'] - best_metrics['mape']) / base_metrics[
                        'mape'] * 100 if base_metrics['mape'] != 0 else 0,
                }
            }
        else:
            if X_val is not None and y_val is not None:
                logger.info("跳过滚动评估（残差模型未训练或无验证集）")

        logger.info(f"✅ 基础模型训练完成，耗时 {training_time:.2f} 秒")
        return self.training_stats

    def _predict_base(self, X: np.ndarray) -> np.ndarray:
        """仅使用基础模型进行预测（内部使用）"""
        if self.model is None:
            raise ValueError("基础模型未训练")
        X_flat = self._flatten_X(X)
        dmatrix = xgb.DMatrix(X_flat, feature_names=self.feature_names)
        return self.model.predict(dmatrix)

    def _build_residual_lags(self, residuals: np.ndarray, lags: int) -> np.ndarray:
        """
        为每个样本构建前 lags 个残差作为特征。
        假设 residuals 按时间顺序排列，第一个样本前没有足够历史，用0填充。
        返回形状为 (n_samples, lags) 的矩阵。
        """
        n_samples = len(residuals)
        lag_matrix = np.zeros((n_samples, lags))
        for i in range(n_samples):
            start = max(0, i - lags)
            end = i
            # 将历史残差放入矩阵的最后几列（最新的在前？）
            # 例如：lag_features[i, -len(available):] = residuals[start:end]
            # 为简单起见，我们统一将历史残差按时间从远到近填充到前几列
            # 或者按最近到最远填充。这里我们选择最近的在最后一列
            available = residuals[start:end]
            if len(available) > 0:
                lag_matrix[i, -len(available):] = available
        return lag_matrix
    def predict(self, X: np.ndarray, historical_residuals: Optional[List[float]] = None) -> np.ndarray:
        """
        综合预测：基础模型预测 + 残差模型预测。

        参数：
            X: 输入特征
            historical_residuals: 可选，历史残差队列（长度等于 residual_lags），
                                  用于构造当前样本的滞后特征。如果未提供且 residual_lags>0，
                                  则假设历史残差为0，并给出警告。
        返回：
            修正后的预测值。
        """
        if self.model is None:
            raise ValueError("模型未加载")

        # 基础预测
        base_pred = self._predict_base(X)

        # 如果有残差模型，加上残差预测
        if self.residual_model is not None:
            X_flat = self._flatten_X(X)

            # 如果需要滞后特征
            if self.residual_lags > 0:
                if historical_residuals is None:
                    logger.warning("未提供历史残差，将使用0填充滞后特征，可能影响修正效果")
                    lag_features = np.zeros((X_flat.shape[0], self.residual_lags))
                else:
                    # 将历史残差队列转换为与样本数相同的特征矩阵
                    # 假设 historical_residuals 是一个列表，长度为 residual_lags，最近的残差在最后
                    # 对于批量预测，每个样本应使用相同的历史残差？实际上如果样本是连续的，历史残差应逐步更新
                    # 简化：假设所有样本共用同一个历史残差队列（仅适用于单步预测）
                    lag_features = np.tile(historical_residuals, (X_flat.shape[0], 1))

                X_pred = np.hstack([X_flat, lag_features])
            else:
                X_pred = X_flat

            residual_pred_scaled = self.residual_model.predict(X_pred)

            # 反标准化
            if self.use_standardize:
                residual_pred = residual_pred_scaled * self.residual_std + self.residual_mean
            else:
                residual_pred = residual_pred_scaled

            # 形状对齐
            if base_pred.ndim == 1 and residual_pred.ndim == 2 and residual_pred.shape[1] == 1:
                residual_pred = residual_pred.ravel()
            elif base_pred.ndim == 2 and residual_pred.ndim == 1:
                residual_pred = residual_pred.reshape(-1, 1)

            if base_pred.shape != residual_pred.shape:
                logger.error(f"基础预测形状 {base_pred.shape} 与残差预测形状 {residual_pred.shape} 不匹配，将忽略残差模型")
                return base_pred

            return base_pred + residual_pred
        else:
            return base_pred

    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        """计算评估指标"""
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        y_true = np.array(y_true).flatten()
        y_pred = np.array(y_pred).flatten()
        min_len = min(len(y_true), len(y_pred))
        y_true = y_true[:min_len]
        y_pred = y_pred[:min_len]

        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_true, y_pred)
        r2 = r2_score(y_true, y_pred)

        mask = y_true != 0
        if mask.any():
            mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
        else:
            mape = 0.0

        return {
            'mse': float(mse),
            'rmse': float(rmse),
            'mae': float(mae),
            'r2_score': float(r2),
            'mape': float(mape),
            'samples': int(min_len)
        }

    def _get_feature_importance(self, X_train_flat: np.ndarray) -> Dict:
        """获取特征重要性"""
        if self.model is None:
            return {}
        try:
            importance_dict = self.model.get_score(importance_type='weight')
            importance_list = []
            for i, name in enumerate(self.feature_names):
                imp = importance_dict.get(f'f{i}', 0)
                importance_list.append({'feature': name, 'importance': float(imp)})
            importance_list.sort(key=lambda x: x['importance'], reverse=True)
            return {
                'importance_df': importance_list,
                'top_features': importance_list[:20],
                'total_features': len(importance_list),
                'max_importance': max([item['importance'] for item in importance_list]) if importance_list else 0
            }
        except Exception as e:
            logger.warning(f"获取特征重要性失败: {e}")
            return {}

    def save_model(self, filepath: str, training_config: Optional[Dict] = None) -> bool:
        """保存模型（包含基础模型和残差模型）到文件"""
        try:
            if self.model is None:
                logger.error("基础模型未训练，无法保存")
                return False

            model_data = {
                'model': self.model,
                'residual_model': self.residual_model,      # 可能为 None
                'model_params': self.model_params,
                'training_stats': self.training_stats,
                'feature_importance': self.feature_importance,
                'feature_names': self.feature_names,
                'saved_at': datetime.now().isoformat(),
                'training_config': training_config if training_config else {},
                'residual_lags': self.residual_lags,
                'residual_mean': self.residual_mean,
                'residual_std': self.residual_std,
                'use_standardize': self.use_standardize,
                'best_alpha': getattr(self, 'best_alpha', 1.0),   # <--- 新增这一行

            }
            with open(filepath, 'wb') as f:
                pickle.dump(model_data, f)
            logger.info(f"✅ 模型已保存到 {filepath} (包含残差模型: {self.residual_model is not None})")
            return True
        except Exception as e:
            logger.error(f"保存模型失败: {e}")
            return False

    def load_model(self, model_path: str) -> bool:
        try:
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)
            self.model = model_data['model']
            self.residual_model = model_data.get('residual_model')
            self.model_params = model_data.get('model_params', {})
            self.training_stats = model_data.get('training_stats', {})
            self.feature_importance = model_data.get('feature_importance', {})
            self.feature_names = model_data.get('feature_names', [])
            self.residual_lags = model_data.get('residual_lags', 0)
            self.residual_mean = model_data.get('residual_mean', 0.0)
            self.residual_std = model_data.get('residual_std', 1.0)
            self.use_standardize = model_data.get('use_standardize', False)
            self.best_alpha = model_data.get('best_alpha', 1.0)  # 加载 best_alpha
            logger.info(f"✅ 模型已从 {model_path} 加载 (含残差模型: {self.residual_model is not None})")
            return True
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False

    def get_model_info(self) -> Dict:
        """获取模型信息"""
        return {
            'model_type': 'xgboost',
            'model_params': self.model_params,
            'feature_importance': self.feature_importance,
            'training_stats': self.training_stats,
            'is_trained': self.model is not None,
            'feature_names': self.feature_names,
            'has_residual_model': self.residual_model is not None
        }