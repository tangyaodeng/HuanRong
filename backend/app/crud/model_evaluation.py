from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime,timedelta
from .. import models, schemas


class ModelEvaluationCRUD:
    def __init__(self, db: Session):
        self.db = db

    # 创建设备模型评估记录
    # 修改 ModelEvaluationCRUD 类中的 create_model_evaluation 方法

    def create_model_evaluation(
            self,
            device_id: int,
            r_squared: float,
            rmse: float,
            mae: float,
            training_time: int,  # 秒
            training_data_size: int,
            test_data_size: int,
            feature_count: int,
            r_squared_residual: Optional[float] = None,
            rmse_residual: Optional[float] = None,
            mae_residual: Optional[float] = None
    ) -> models.ModelEvaluation:
        try:
            # 限制数值范围
            r_squared = max(-9999.9999, min(r_squared, 9999.9999))
            rmse = max(0.0, min(rmse, 9999.9999))
            mae = max(0.0, min(mae, 9999.9999))
            if r_squared_residual is not None:
                r_squared_residual = max(-9999.9999, min(r_squared_residual, 9999.9999))
            if rmse_residual is not None:
                rmse_residual = max(0.0, min(rmse_residual, 9999.9999))
            if mae_residual is not None:
                mae_residual = max(0.0, min(mae_residual, 9999.9999))

            training_time_delta = timedelta(seconds=training_time)

            db_evaluation = models.ModelEvaluation(
                model_id=device_id,
                r_squared=r_squared,
                rmse=rmse,
                mae=mae,
                training_time=training_time_delta,
                training_data_size=training_data_size,
                test_data_size=test_data_size,
                feature_count=feature_count,
                r_squared_residual=r_squared_residual,
                rmse_residual=rmse_residual,
                mae_residual=mae_residual
            )
            self.db.add(db_evaluation)
            self.db.commit()
            self.db.refresh(db_evaluation)
            return db_evaluation
        except Exception as e:
            self.db.rollback()
            raise e

    # 获取设备的最新评估记录
    def get_latest_evaluation_by_device(self, device_id: int) -> Optional[models.ModelEvaluation]:
        """获取设备的最新评估记录"""
        return self.db.query(models.ModelEvaluation).filter(
            models.ModelEvaluation.model_id == device_id
        ).order_by(
            models.ModelEvaluation.created_at.desc()
        ).first()

    # 获取设备的所有评估记录
    def get_device_evaluations(
            self,
            device_id: int,
            limit: int = 10
    ) -> List[models.ModelEvaluation]:
        """获取设备的所有评估记录"""
        return self.db.query(models.ModelEvaluation).filter(
            models.ModelEvaluation.model_id == device_id
        ).order_by(
            models.ModelEvaluation.created_at.desc()
        ).limit(limit).all()

    # 如果必须通过训练记录查找评估，可以考虑其他方法
    def get_evaluation_by_device_and_time(self, device_id: int, created_after: datetime) -> Optional[
        models.ModelEvaluation]:
        """根据设备ID和时间查找评估记录"""
        return self.db.query(models.ModelEvaluation).filter(
            models.ModelEvaluation.model_id == device_id,
            models.ModelEvaluation.created_at >= created_after
        ).order_by(models.ModelEvaluation.created_at.desc()).first()

    # 删除评估记录
    def delete_evaluation(self, evaluation_id: int) -> bool:
        """删除评估记录"""
        evaluation = self.db.query(models.ModelEvaluation).filter(
            models.ModelEvaluation.id == evaluation_id
        ).first()

        if evaluation:
            self.db.delete(evaluation)
            self.db.commit()
            return True
        return False

    # 获取评估统计
    def get_evaluation_stats(self, device_id: Optional[int] = None) -> Dict[str, Any]:
        """获取评估统计信息"""
        query = self.db.query(models.ModelEvaluation)

        if device_id:
            query = query.filter(models.ModelEvaluation.model_id == device_id)

        total = query.count()

        if total == 0:
            return {
                "total": 0,
                "avg_r_squared": 0,
                "avg_rmse": 0,
                "avg_mae": 0,
                "best_r_squared": 0
            }

        # 计算平均值
        avg_r_squared = query.with_entities(
            func.avg(models.ModelEvaluation.r_squared)
        ).scalar()

        avg_rmse = query.with_entities(
            func.avg(models.ModelEvaluation.rmse)
        ).scalar()

        avg_mae = query.with_entities(
            func.avg(models.ModelEvaluation.mae)
        ).scalar()

        # 最佳R²
        best_evaluation = query.order_by(
            models.ModelEvaluation.r_squared.desc()
        ).first()

        return {
            "total": total,
            "avg_r_squared": float(avg_r_squared) if avg_r_squared else 0,
            "avg_rmse": float(avg_rmse) if avg_rmse else 0,
            "avg_mae": float(avg_mae) if avg_mae else 0,
            "best_r_squared": best_evaluation.r_squared if best_evaluation else 0
        }