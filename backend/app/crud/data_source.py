# app/crud/data_source.py
from sqlalchemy.orm import Session
import datetime  # 确保 datetime 已导入
from .. import schemas  # 添加这行！这是关键
# 重要：将导入移到函数内部！
def get_data_sources(db: Session, skip: int = 0, limit: int = 100):
    from .. import models  # 延迟导入
    return db.query(models.DataSources).offset(skip).limit(limit).all()

def create_data_source(db: Session, data_source: schemas.DataSourceCreate):
    from .. import models, schemas  # 延迟导入
    data_source_dict = data_source.dict(exclude={"status"})
    db_data_source = models.DataSources(**data_source_dict)
    db.add(db_data_source)
    db.commit()
    db.refresh(db_data_source)
    return db_data_source

def get_data_source(db: Session, data_source_id: int):
    from .. import models  # 延迟导入
    return db.query(models.DataSources).filter(models.DataSources.id == data_source_id).first()


# 其他函数同理修改（只展示关键部分）
def update_data_source(db: Session, data_source_id: int, data_source: schemas.DataSourceUpdate):
    from .. import models, schemas  # 延迟导入
    db_data_source = get_data_source(db, data_source_id)
    if db_data_source:
        for key, value in data_source.dict(exclude_unset=True).items():
            setattr(db_data_source, key, value)
        db.commit()
        db.refresh(db_data_source)
    return db_data_source

def get_mapping(db: Session, data_source_id: int, database: str):
    from .. import models  # 延迟导入
    return db.query(models.Mappings).filter(
        models.Mappings.data_source_id == data_source_id,
        models.Mappings.database == database
    ).first()

def save_mapping(db: Session, mapping: schemas.MappingCreate):
    from .. import models, schemas  # 延迟导入
    db_mapping = models.Mappings(
        data_source_id=mapping.data_source_id,
        database=mapping.database,
        tables=mapping.tables,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(db_mapping)
    db.commit()
    db.refresh(db_mapping)
    return db_mapping

# get_tables 和 test_connection 无需修改（不依赖 models/schemas）
def get_tables(db: Session, data_source_id: int, database: str):
    return [
        "forecast_host1_power",
        "forecast_host1_temperature",
        # ... 其他表名
    ]

def test_connection(db: Session, connection: schemas.DataSourceTest):
    import random
    return {
        "status": "success" if random.random() > 0.2 else "error",
        "message": "Connection successful" if random.random() > 0.2 else "Connection failed"
    }


def delete_data_source(db: Session, data_source_id: int):
    from .. import models  # 延迟导入

    # 1. 先删除该数据源的所有特征映射
    db.query(models.FeatureTableMapping).filter(
        models.FeatureTableMapping.data_source_id == data_source_id
    ).delete()

    # 2. 删除数据源本身
    db_data_source = db.query(models.DataSources).filter(models.DataSources.id == data_source_id).first()
    if db_data_source:
        db.delete(db_data_source)
        db.commit()
        return db_data_source
    return None