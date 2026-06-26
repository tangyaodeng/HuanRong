from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException
from .. import models, schemas

class CoolingOptCRUD:
    """冷却侧优化CRUD操作（包含配置和参数）"""

    # ==================== 配置相关操作 ====================

    def get_config(self, db: Session) -> Optional[models.CoolingOptConfig]:
        return db.query(models.CoolingOptConfig).first()

    def update_config(self, db: Session, config_update: schemas.CoolingOptConfigUpdate) -> models.CoolingOptConfig:
        config = self.get_config(db)
        if not config:
            raise HTTPException(status_code=404, detail="未找到配置")

        # 原有范围校验（保持不变）
        if (config_update.return_temp_upper_limit is not None and
                config_update.return_temp_lower_limit is not None and
                config_update.return_temp_upper_limit < config_update.return_temp_lower_limit):
            raise HTTPException(status_code=400, detail="回水温度上限必须大于或等于下限")

        if (config_update.supply_temp_upper_limit is not None and
                config_update.supply_temp_lower_limit is not None and
                config_update.supply_temp_upper_limit < config_update.supply_temp_lower_limit):
            raise HTTPException(status_code=400, detail="供水温度上限必须大于或等于下限")

        if (config_update.temp_diff_upper_limit is not None and
                config_update.temp_diff_lower_limit is not None and
                config_update.temp_diff_upper_limit < config_update.temp_diff_lower_limit):
            raise HTTPException(status_code=400, detail="温差上限必须大于或等于下限")

        if (config_update.heat_dissipation_upper_limit is not None and
                config_update.heat_dissipation_lower_limit is not None and
                config_update.heat_dissipation_upper_limit < config_update.heat_dissipation_lower_limit):
            raise HTTPException(status_code=400, detail="散热量上限必须大于或等于下限")

        # ========== 新增阈值字段的非负校验 ==========
        if config_update.return_temp_threshold is not None and config_update.return_temp_threshold < 0:
            raise HTTPException(status_code=400, detail="回水温度阈值不能为负数")
        if config_update.temp_diff_threshold is not None and config_update.temp_diff_threshold < 0:
            raise HTTPException(status_code=400, detail="温差阈值不能为负数")
        if config_update.energy_saving_threshold is not None and config_update.energy_saving_threshold < 0:
            raise HTTPException(status_code=400, detail="节能率阈值不能为负数")
        if config_update.optimization_cycle_minutes is not None and config_update.optimization_cycle_minutes < 1:
            raise HTTPException(status_code=400, detail="寻优周期必须大于等于1分钟")
        if config_update.r2_threshold is not None and (config_update.r2_threshold < 0 or config_update.r2_threshold > 1):
            raise HTTPException(status_code=400, detail="R²阈值必须在0到1之间")
        # 更新字段（使用 Pydantic v2 的 model_dump）
        update_data = config_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(config, field):
                setattr(config, field, value)

        db.add(config)
        db.commit()
        db.refresh(config)
        return config

    # ==================== 参数相关操作 ====================

    def get_parameters(
            self,
            db: Session,
            skip: int = 0,
            limit: int = 100,
            applied: Optional[bool] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
    ) -> List[models.CoolingOptParametersTotal]:
        query = db.query(models.CoolingOptParametersTotal)
        if applied is not None:
            query = query.filter(models.CoolingOptParametersTotal.applied == applied)
        if start_date:
            query = query.filter(models.CoolingOptParametersTotal.optimization_timestamp >= start_date)
        if end_date:
            query = query.filter(models.CoolingOptParametersTotal.optimization_timestamp <= end_date)
        return query.order_by(desc(models.CoolingOptParametersTotal.optimization_timestamp)).offset(skip).limit(limit).all()

    def count_parameters(
            self,
            db: Session,
            applied: Optional[bool] = None,
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None
    ) -> int:
        query = db.query(models.CoolingOptParametersTotal)
        if applied is not None:
            query = query.filter(models.CoolingOptParametersTotal.applied == applied)
        if start_date:
            query = query.filter(models.CoolingOptParametersTotal.optimization_timestamp >= start_date)
        if end_date:
            query = query.filter(models.CoolingOptParametersTotal.optimization_timestamp <= end_date)
        return query.count()

    def get_latest_parameters(self, db: Session) -> Optional[models.CoolingOptParametersTotal]:
        return db.query(models.CoolingOptParametersTotal).order_by(
            desc(models.CoolingOptParametersTotal.optimization_timestamp)
        ).first()

    def get_parameter_by_id(self, db: Session, parameter_id: int) -> Optional[models.CoolingOptParametersTotal]:
        return db.query(models.CoolingOptParametersTotal).filter(
            models.CoolingOptParametersTotal.id == parameter_id
        ).first()

    def get_optimization_stats(self, db: Session, days: int = 30) -> schemas.OptimizationStats:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        optimizations = db.query(models.CoolingOptParametersTotal).filter(
            models.CoolingOptParametersTotal.optimization_timestamp.between(start_date, end_date)
        ).all()

        total_optimizations = len(optimizations)
        applied_optimizations = len([o for o in optimizations if o.applied])

        total_energy_saving = sum([o.total_energy_saving or 0 for o in optimizations])
        avg_energy_saving_percent = sum([o.energy_saving_percent or 0 for o in optimizations]) / total_optimizations if total_optimizations > 0 else 0

        recent_optimizations = []
        for opt in optimizations[:5]:
            recent_optimizations.append({
                "id": opt.id,
                "timestamp": opt.optimization_timestamp,
                "energy_saving": float(opt.total_energy_saving or 0),
                "saving_percent": float(opt.energy_saving_percent or 0),
                "applied": opt.applied,
                "total_power_diff": float(opt.diff_total_power or 0)
            })

        return schemas.OptimizationStats(
            total_optimizations=total_optimizations,
            applied_optimizations=applied_optimizations,
            total_energy_saving=float(total_energy_saving),
            avg_energy_saving_percent=float(avg_energy_saving_percent),
            recent_optimizations=recent_optimizations
        )

    def get_device_field_history(self, db: Session, field: str, start_date: datetime, end_date: datetime,
                                 limit: int = 100) -> List[Dict]:
        field_map = {
            'total_power': ('current_total_power', 'optimized_total_power'),
            'host_total_power': ('current_host_total_power', 'optimized_host_total_power'),
            'cooling_tower_total_power': ('current_cooling_tower_total_power', 'optimized_cooling_tower_total_power'),
            'cooling_pump_total_power': ('current_cooling_pump_total_power', 'optimized_cooling_pump_total_power'),
            'supply_temp': ('current_supply_temp', 'optimized_supply_temp'),
            'return_temp': ('current_return_temp', 'optimized_return_temp'),
            'temp_diff': ('current_temp_diff', 'optimized_temp_diff'),
            'heat_dissipation': ('current_heat_dissipation', 'optimized_heat_dissipation'),
        }
        if field not in field_map:
            raise ValueError(f"不支持的字段标识: {field}，支持的标识: {list(field_map.keys())}")

        current_col, optimized_col = field_map[field]

        query = db.query(
            models.CoolingOptParametersTotal.optimization_timestamp.label('timestamp'),
            getattr(models.CoolingOptParametersTotal, current_col).label('current_value'),
            getattr(models.CoolingOptParametersTotal, optimized_col).label('optimized_value')
        ).filter(
            models.CoolingOptParametersTotal.optimization_timestamp.between(start_date, end_date)
        ).order_by(models.CoolingOptParametersTotal.optimization_timestamp).limit(limit)

        results = query.all()
        return [
            {
                "timestamp": r.timestamp,
                "current_value": float(r.current_value) if r.current_value is not None else None,
                "optimized_value": float(r.optimized_value) if r.optimized_value is not None else None
            }
            for r in results
        ]