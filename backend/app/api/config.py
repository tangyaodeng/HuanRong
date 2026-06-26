# app/api/config.py 用这个真实的数据库信息测试连接
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from starlette.responses import JSONResponse

from .. import models, database, schemas
from .. import crud
import mysql.connector
from datetime import datetime
import re
router = APIRouter(
    prefix="/config",
    tags=["config"],
)


# 数据源管理
@router.get("/data-sources", response_model=List[schemas.DataSource])
def get_data_sources(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    data_sources = crud.get_data_sources(db, skip=skip, limit=limit)
    return data_sources


@router.post("/data-sources", response_model=schemas.DataSource)
def create_data_source(data_source: schemas.DataSourceCreate, db: Session = Depends(database.get_db)):
    return crud.create_data_source(db=db, data_source=data_source)


@router.get("/data-sources/{data_source_id}", response_model=schemas.DataSource)
def get_data_source(data_source_id: int, db: Session = Depends(database.get_db)):
    db_data_source = crud.get_data_source(db, data_source_id=data_source_id)
    if db_data_source is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    return db_data_source


@router.put("/data-sources/{data_source_id}", response_model=schemas.DataSource)
def update_data_source(data_source_id: int, data_source: schemas.DataSourceUpdate,
                       db: Session = Depends(database.get_db)):
    db_data_source = crud.update_data_source(db, data_source_id=data_source_id, data_source=data_source)
    if db_data_source is None:
        raise HTTPException(status_code=404, detail="Data source not found")
    return db_data_source


@router.delete("/data-sources/{data_source_id}", response_model=schemas.DataSource)
def delete_data_source(data_source_id: int, db: Session = Depends(database.get_db)):
    try:
        # 检查数据源是否存在
        db_data_source = crud.get_data_source(db, data_source_id=data_source_id)
        if db_data_source is None:
            raise HTTPException(status_code=404, detail="Data source not found")

        # 记录数据源信息用于返回
        data_source_info = {
            "id": db_data_source.id,
            "name": db_data_source.name,
            "host": db_data_source.host,
            "database_name": db_data_source.database_name
        }

        # 调用CRUD删除函数（会同时删除映射）
        deleted_data_source = crud.delete_data_source(db, data_source_id=data_source_id)

        if deleted_data_source:
            # 返回被删除的数据源信息
            return deleted_data_source
        else:
            raise HTTPException(status_code=500, detail="删除失败")

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除数据源失败: {str(e)}")


# 连接测试
@router.post("/data-sources/test")
async def test_connection(data: schemas.DataSourceTest):
    # 🔥 关键修复：检查必要参数是否为空
    if not data.host.strip() or not data.database_name.strip() or not data.username.strip():
        raise HTTPException(
            status_code=400,
            detail="主机地址、数据库名、用户名不能为空"
        )

    # 检查端口范围（防止输入负数或超大数）
    if not 1 <= data.port <= 65535:
        raise HTTPException(
            status_code=400,
            detail="端口必须在1-65535之间"
        )

    # 尝试连接
    try:
        connection = mysql.connector.connect(
            host=data.host,
            port=data.port,
            database=data.database_name,
            user=data.username,
            password=data.password,
            charset=data.charset,
            connect_timeout=data.timeout
        )

        # 测试查询以验证连接
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()

        cursor.close()
        connection.close()
        return {"status": "success", "message": "连接成功！"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# 数据库和表管理
@router.get("/data-sources/{data_source_id}/databases")
def get_databases(data_source_id: int, db: Session = Depends(database.get_db)):
    # 实际项目中应查询数据库列表
    return ["industrial_forecast", "forecast_history"]


@router.get("/data-sources/{data_source_id}/databases/{database}/tables")
def get_tables(data_source_id: int, database: str, db: Session = Depends(database.get_db)):
    # 从数据库获取数据源配置
    data_source = db.query(models.DataSources).filter(
        models.DataSources.id == data_source_id,
        models.DataSources.is_active == True
    ).first()

    if not data_source:
        raise HTTPException(status_code=404, detail="数据源不存在或已停用")

    try:
        # 连接到MySQL数据库
        connection = mysql.connector.connect(
            host=data_source.host,
            port=data_source.port,
            database=database,  # 使用传入的database参数
            user=data_source.username,
            password=data_source.password,
            charset=data_source.charset or 'utf8mb4',
            connect_timeout=data_source.timeout or 10
        )

        cursor = connection.cursor()

        # 查询所有表名
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        # 提取表名列表
        table_names = [table[0] for table in tables]

        cursor.close()
        connection.close()

        # 只返回以特定前缀开头的表（可选，根据实际需求调整）
        # 例如：只返回以forecast_或historical_开头的表
        filtered_tables = []
        for table_name in table_names:
            if (table_name.lower().startswith('forecast_') or
                    table_name.lower().startswith('historical_')):
                filtered_tables.append(table_name)
            # 或者返回所有表
            # filtered_tables.append(table_name)

        return filtered_tables if filtered_tables else table_names

    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表列表失败: {str(e)}")


# mysql映射特征表列表 - 新增接口
# @router.get("/mapping/mysql_featuretables")
# def get_mysql_featuretables(
#         data_source_id: Optional[int] = None,
#         database: Optional[str] = None,
#         db: Session = Depends(database.get_db)
# ):
#     """
#     查询选择数据源和数据库的所有表名
#     """
#     try:
#         # 检查参数
#         if not data_source_id or not database:
#             raise HTTPException(
#                 status_code=400,
#                 detail="请提供数据源ID和数据库名"
#             )
#
#         # 从数据库获取数据源配置
#         data_source = db.query(models.DataSources).filter(
#             models.DataSources.id == data_source_id,
#             models.DataSources.is_active == True
#         ).first()
#
#         if not data_source:
#             raise HTTPException(status_code=404, detail="数据源不存在或已停用")
#
#         # 连接到MySQL数据库
#         connection = mysql.connector.connect(
#             host=data_source.host,
#             port=data_source.port,
#             database=database,
#             user=data_source.username,
#             password=data_source.password,
#             charset=data_source.charset or 'utf8mb4',
#             connect_timeout=data_source.timeout or 10
#         )
#
#         cursor = connection.cursor()
#
#         try:
#             # 查询所有表名
#             cursor.execute("SHOW TABLES")
#             tables = cursor.fetchall()
#
#             # 提取表名列表
#             table_names = [table[0] for table in tables]
#
#             # 获取表的详细信息（可选）
#             table_details = []
#             for table_name in table_names:
#                 try:
#                     # 获取表结构信息
#                     cursor.execute(f"DESCRIBE `{table_name}`")
#                     columns = cursor.fetchall()
#
#                     # 查找时间戳和特征值列
#                     timestamp_columns = []
#                     value_columns = []
#
#                     for column in columns:
#                         column_name = column[0]
#                         column_type = column[1].lower()
#
#                         # 判断是否是时间戳列
#                         if any(keyword in column_name.lower() for keyword in
#                                ['time', 'date', 'datetime', 'timestamp', 'update']):
#                             timestamp_columns.append({
#                                 "name": column_name,
#                                 "type": column_type
#                             })
#
#                         # 判断是否是特征值列
#                         elif any(keyword in column_name.lower() for keyword in
#                                  ['value', 'power', 'temp', 'humidity', 'pressure', 'flow', 'speed']):
#                             value_columns.append({
#                                 "name": column_name,
#                                 "type": column_type
#                             })
#
#                     table_details.append({
#                         "table_name": table_name,
#                         "description": get_table_description(table_name),
#                         "column_count": len(columns),
#                         "timestamp_columns": timestamp_columns,
#                         "value_columns": value_columns,
#                         "has_valid_structure": len(timestamp_columns) > 0 and len(value_columns) > 0
#                     })
#
#                 except Exception as e:
#                     # 如果获取表结构失败，只返回表名
#                     table_details.append({
#                         "table_name": table_name,
#                         "description": get_table_description(table_name),
#                         "error": f"无法获取表结构: {str(e)}",
#                         "has_valid_structure": False
#                     })
#
#         finally:
#             cursor.close()
#             connection.close()
#
#         return {
#             "data_source": {
#                 "id": data_source.id,
#                 "name": data_source.name,
#                 "host": data_source.host,
#                 "database": database
#             },
#             "tables": table_details,
#             "total_tables": len(table_names)
#         }
#
#     except mysql.connector.Error as e:
#         raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"获取特征表列表失败: {str(e)}")

@router.get("/mapping/mysql_featuretables")
def get_mysql_featuretables(
        data_source_id: Optional[int] = None,
        database: Optional[str] = None,
        db: Session = Depends(database.get_db)
):
    """
    查询选择数据源和数据库中所有以 xmhf_zlz2_ 开头的表名
    """
    try:
        # 检查参数
        if not data_source_id or not database:
            raise HTTPException(
                status_code=400,
                detail="请提供数据源ID和数据库名"
            )

        # 从数据库获取数据源配置
        data_source = db.query(models.DataSources).filter(
            models.DataSources.id == data_source_id,
            models.DataSources.is_active == True
        ).first()

        if not data_source:
            raise HTTPException(status_code=404, detail="数据源不存在或已停用")

        # 连接到MySQL数据库
        connection = mysql.connector.connect(
            host=data_source.host,
            port=data_source.port,
            database=database,
            user=data_source.username,
            password=data_source.password,
            charset=data_source.charset or 'utf8mb4',
            connect_timeout=data_source.timeout or 10
        )

        cursor = connection.cursor()

        try:
            # 定义要查询的表名前缀
            PREFIXES = ["xmhf_zlz2_ai", "composite_", "xmhf_zlz2_di","dev-zlz-plc-ai2","hrdz_zlz_ai","hrdz_zlz_di"]

            # 构建多前缀 LIKE 查询
            like_clauses = " OR ".join(["table_name LIKE %s"] * len(PREFIXES))
            sql = f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s 
                  AND ({like_clauses})
            """
            params = [database] + [f"{prefix}%" for prefix in PREFIXES]
            cursor.execute(sql, params)

            tables = cursor.fetchall()
            table_names = [table[0] for table in tables]

            # 获取表的详细信息（只对匹配的表执行）
            table_details = []
            for table_name in table_names:
                try:
                    # 获取表结构信息
                    cursor.execute(f"DESCRIBE `{table_name}`")
                    columns = cursor.fetchall()

                    # 查找时间戳和特征值列
                    timestamp_columns = []
                    value_columns = []

                    for column in columns:
                        column_name = column[0]
                        column_type = column[1].lower()

                        # 判断是否是时间戳列
                        if any(keyword in column_name.lower() for keyword in
                               ['time', 'date', 'datetime', 'timestamp', 'update']):
                            timestamp_columns.append({
                                "name": column_name,
                                "type": column_type
                            })
                        # 判断是否是特征值列
                        elif any(keyword in column_name.lower() for keyword in
                                 ['value', 'power', 'temp', 'humidity', 'pressure', 'flow', 'speed']):
                            value_columns.append({
                                "name": column_name,
                                "type": column_type
                            })

                    table_details.append({
                        "table_name": table_name,
                        "description": get_table_description(table_name),
                        "column_count": len(columns),
                        "timestamp_columns": timestamp_columns,
                        "value_columns": value_columns,
                        "has_valid_structure": len(timestamp_columns) > 0 and len(value_columns) > 0
                    })

                except Exception as e:
                    # 如果获取表结构失败，只返回表名
                    table_details.append({
                        "table_name": table_name,
                        "description": get_table_description(table_name),
                        "error": f"无法获取表结构: {str(e)}",
                        "has_valid_structure": False
                    })

        finally:
            cursor.close()
            connection.close()

        return {
            "data_source": {
                "id": data_source.id,
                "name": data_source.name,
                "host": data_source.host,
                "database": database
            },
            "tables": table_details,
            "total_tables": len(table_names)   # 返回过滤后的数量
        }

    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取特征表列表失败: {str(e)}")
# 已使用特征

# 特征映射
@router.post("/mappings", response_model=schemas.Mapping)
def save_mapping(mapping: schemas.MappingCreate, db: Session = Depends(database.get_db)):
    return crud.save_mapping(db, mapping)


@router.get("/mappings/{data_source_id}/{database}", response_model=schemas.Mapping)
def get_mapping(data_source_id: int, database: str, db: Session = Depends(database.get_db)):
    db_mapping = crud.get_mapping(db, data_source_id, database)
    if db_mapping is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return db_mapping


# 映射相关API - 根据你的要求添加
@router.get("/mapping/project")
def get_mapping_project(data_source_id: int, database: str, db: Session = Depends(database.get_db)):
    """
    获取项目列表（用于映射配置）
    注意：这里只是示例，实际可能需要根据数据源和数据库筛选项目
    """
    try:
        # 查询所有活跃的项目
        projects = db.query(models.Project).filter(
            models.Project.status == "active"
        ).all()

        return [
            {
                "id": project.id,
                "name": project.name,
                "code": project.code,
                "description": project.description,
                "status": project.status,
                "device_count": project.device_count,
                "created_at": project.created_at.isoformat() if project.created_at else None,
                "updated_at": project.updated_at.isoformat() if project.updated_at else None
            }
            for project in projects
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取项目列表失败: {str(e)}")


@router.get("/mapping/device")
def get_mapping_device(project_id: int, db: Session = Depends(database.get_db)):
    """
    获取项目下的设备列表（用于映射配置）
    """
    try:
        # 验证项目是否存在
        project = db.query(models.Project).filter(
            models.Project.id == project_id,
            models.Project.status == "active"
        ).first()

        if not project:
            raise HTTPException(status_code=404, detail="项目不存在或已停用")

        # 查询项目下的设备
        devices = db.query(models.Device).filter(
            models.Device.project_id == project_id,
            models.Device.status == "active"
        ).all()

        result = []
        for device in devices:
            device_data = {
                "id": device.id,
                "name": device.name,
                "identifier": device.identifier,
                "description": device.description,
                "status": device.status,
                "location": device.location,
                "project_id": device.project_id,
                "model_version_id": device.model_version_id,
                "created_at": device.created_at.isoformat() if device.created_at else None,
                "updated_at": device.updated_at.isoformat() if device.updated_at else None
            }

            # 如果设备有模型版本，获取模型信息
            if device.model_version_id:
                model_version = db.query(models.DeviceModelVersion).filter(
                    models.DeviceModelVersion.id == device.model_version_id
                ).first()

                if model_version:
                    device_data["model_version"] = {
                        "id": model_version.id,
                        "version": model_version.version,
                        "description": model_version.description,
                        "model_id": model_version.model_id
                    }

                    # 获取模型名称
                    device_model = db.query(models.DeviceModel).filter(
                        models.DeviceModel.id == model_version.model_id
                    ).first()

                    if device_model:
                        device_data["model_name"] = device_model.name
                        device_data["model_code"] = device_model.code

            result.append(device_data)

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取设备列表失败: {str(e)}")


@router.get("/mapping/device/{device_id}/features")
def get_mapping_device_features(device_id: int, db: Session = Depends(database.get_db)):
    """
    获取设备的特征列表（用于映射配置）
    """
    try:
        # 验证设备是否存在
        device = db.query(models.Device).filter(
            models.Device.id == device_id,
            models.Device.status == "active"
        ).first()

        if not device:
            raise HTTPException(status_code=404, detail="设备不存在或已停用")

        # 如果没有模型版本，返回空列表
        if not device.model_version_id:
            return []

        # 查询设备模型版本对应的特征
        model_version_features = db.query(models.ModelVersionFeature).filter(
            models.ModelVersionFeature.version_id == device.model_version_id
        ).all()

        if not model_version_features:
            return []

        # 获取所有特征的详细信息
        feature_ids = [mvf.feature_id for mvf in model_version_features]
        features = db.query(models.Feature).filter(
            models.Feature.id.in_(feature_ids)
        ).all()

        # 转换为字典以便快速查找
        features_dict = {feature.id: feature for feature in features}

        result = []
        for mvf in model_version_features:
            feature = features_dict.get(mvf.feature_id)
            if feature:
                # 获取设备特征值（如果存在）
                device_feature_value = db.query(models.DeviceFeatureValue).filter(
                    models.DeviceFeatureValue.device_id == device_id,
                    models.DeviceFeatureValue.feature_id == feature.id
                ).first()

                feature_data = {
                    "id": feature.id,
                    "name": feature.name,
                    "code": feature.code,
                    "data_type": feature.data_type,
                    "unit": feature.unit,
                    "description": feature.description,
                    "is_required": feature.is_required,
                    "default_value": feature.default_value,
                    "display_order": mvf.display_order,
                    "current_value": device_feature_value.value if device_feature_value else None,
                    "category": get_feature_category(feature.code),
                    # 新增：返回特征本身的默认映射字段
                    "data_source_id": feature.data_source_id,
                    "database_name": feature.database_name,
                    "table_name": feature.table_name,
                    "column_name": feature.column_name,
                    "timestamp_column": feature.timestamp_column
                }
                result.append(feature_data)

        # 按显示顺序排序
        result.sort(key=lambda x: x.get("display_order", 0))

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取设备特征失败: {str(e)}")


# 辅助函数：获取表描述
def get_table_description(table_name: str) -> str:
    """
    根据表名推断表描述
    """
    table_lower = table_name.lower()

    if table_lower.startswith('forecast_'):
        if 'host1' in table_lower:
            return "主机1预测数据"
        elif 'host2' in table_lower:
            return "主机2预测数据"
        elif 'machine1' in table_lower:
            return "机器1预测数据"
        elif 'machine2' in table_lower:
            return "机器2预测数据"
        elif 'room1' in table_lower:
            return "房间1预测数据"
        else:
            return "预测数据"

    elif table_lower.startswith('historical_'):
        if '2023' in table_lower:
            return "2023年历史数据"
        elif '2024' in table_lower:
            return "2024年历史数据"
        elif 'temperature' in table_lower:
            return "历史温度数据"
        elif 'power' in table_lower:
            return "历史功率数据"
        else:
            return "历史数据"

    elif table_lower.startswith('realtime_'):
        return "实时数据"

    elif table_lower.startswith('sensor_'):
        return "传感器数据"

    else:
        return "特征数据表"


# 改为普通函数，而不是实例方法
def get_feature_category(feature_code: str) -> str:
    """
    根据特征代码推断特征类别
    """
    if not feature_code:
        return '其他参数'

    feature_code_lower = feature_code.lower()

    if any(keyword in feature_code_lower for keyword in ['power', 'current', 'voltage', 'electric']):
        return '电气参数'
    elif any(keyword in feature_code_lower for keyword in ['temperature', 'humidity', 'pressure']):
        return '环境参数'
    elif any(keyword in feature_code_lower for keyword in ['speed', 'rpm', 'velocity']):
        return '机械参数'
    elif any(keyword in feature_code_lower for keyword in ['flow', 'rate', 'volume']):
        return '流体参数'
    else:
        return '其他参数'


# 特征映射相关API
# 在 app/api/config.py 中修改相关函数

@router.post("/feature-mappings", response_model=schemas.FeatureMapping)
def save_feature_mapping(mapping: schemas.FeatureMappingCreate, db: Session = Depends(database.get_db)):
    """
    保存特征表映射配置
    """
    try:
        # 检查数据源是否存在
        data_source = db.query(models.DataSources).filter(
            models.DataSources.id == mapping.data_source_id,
            models.DataSources.is_active == True
        ).first()

        if not data_source:
            raise HTTPException(status_code=404, detail="数据源不存在或已停用")

        # 检查设备是否存在 - 手动检查
        device = db.query(models.Device).filter(
            models.Device.id == mapping.device_id,
            models.Device.status == 'active'
        ).first()

        if not device:
            raise HTTPException(status_code=404, detail="设备不存在或已停用")

        # 检查特征是否存在
        feature = db.query(models.Feature).filter(
            models.Feature.id == mapping.feature_id
        ).first()

        if not feature:
            raise HTTPException(status_code=404, detail="特征不存在")

        # 检查是否已存在相同设备的特征映射
        existing_mapping = db.query(models.FeatureTableMapping).filter(
            models.FeatureTableMapping.device_id == mapping.device_id,
            models.FeatureTableMapping.feature_id == mapping.feature_id
        ).first()

        if existing_mapping:
            # 更新现有映射
            existing_mapping.data_source_id = mapping.data_source_id
            existing_mapping.database_name = mapping.database_name
            existing_mapping.table_name = mapping.table_name
            existing_mapping.column_name = mapping.column_name or 'PointValue'
            existing_mapping.timestamp_column = mapping.timestamp_column or 'UpdateDateTime'
            existing_mapping.is_active = mapping.is_active
            existing_mapping.sync_frequency = mapping.sync_frequency or 15
            existing_mapping.updated_at = datetime.now()

            db.commit()
            db.refresh(existing_mapping)
            return existing_mapping
        else:
            # 创建新映射
            db_mapping = models.FeatureTableMapping(
                data_source_id=mapping.data_source_id,
                database_name=mapping.database_name,
                device_id=mapping.device_id,  # 直接存储ID
                feature_id=mapping.feature_id,
                table_name=mapping.table_name,
                column_name=mapping.column_name or 'PointValue',
                timestamp_column=mapping.timestamp_column or 'UpdateDateTime',
                is_active=mapping.is_active,
                sync_frequency=mapping.sync_frequency or 15,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

            db.add(db_mapping)
            db.commit()
            db.refresh(db_mapping)
            return db_mapping

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"保存映射失败: {str(e)}")


@router.get("/feature-mappings/{device_id}")
def get_device_feature_mappings(device_id: int, db: Session = Depends(database.get_db)):
    """
    获取设备的所有特征映射
    """
    try:
        # 检查设备是否存在
        device = db.query(models.Device).filter(
            models.Device.id == device_id,
            models.Device.status == 'active'
        ).first()

        if not device:
            raise HTTPException(status_code=404, detail="设备不存在或已停用")

        # 查询设备的所有特征映射
        mappings = db.query(models.FeatureTableMapping).filter(
            models.FeatureTableMapping.device_id == device_id
        ).all()

        result = []
        for mapping in mappings:
            # 获取特征信息
            feature = db.query(models.Feature).filter(
                models.Feature.id == mapping.feature_id
            ).first()

            # 获取数据源信息
            data_source = db.query(models.DataSources).filter(
                models.DataSources.id == mapping.data_source_id
            ).first()

            mapping_data = {
                "id": mapping.id,
                "data_source": {
                    "id": data_source.id if data_source else None,
                    "name": data_source.name if data_source else "未知数据源",
                    "host": data_source.host if data_source else "",
                    "database": mapping.database_name
                },
                "device": {
                    "id": device.id,
                    "name": device.name,
                    "identifier": device.identifier
                },
                "feature": {
                    "id": feature.id if feature else None,
                    "name": feature.name if feature else "未知特征",
                    "code": feature.code if feature else "",
                    "unit": feature.unit if feature else ""
                },
                "table_name": mapping.table_name,
                "column_name": mapping.column_name,
                "timestamp_column": mapping.timestamp_column,
                "is_active": mapping.is_active,
                "sync_frequency": mapping.sync_frequency,
                "last_sync_at": mapping.last_sync_at.isoformat() if mapping.last_sync_at else None,
                "created_at": mapping.created_at.isoformat() if mapping.created_at else None
            }
            result.append(mapping_data)

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取特征映射失败: {str(e)}")


@router.delete("/feature-mappings/{mapping_id}")
def delete_feature_mapping(mapping_id: int, db: Session = Depends(database.get_db)):
    """
    删除特征映射
    """
    try:
        mapping = db.query(models.FeatureTableMapping).filter(
            models.FeatureTableMapping.id == mapping_id
        ).first()

        if not mapping:
            raise HTTPException(status_code=404, detail="映射不存在")

        db.delete(mapping)
        db.commit()

        return {"status": "success", "message": "映射删除成功"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"删除映射失败: {str(e)}")


@router.post("/feature-mappings/{mapping_id}/test")
def test_feature_mapping(mapping_id: int, db: Session = Depends(database.get_db)):
    """
    测试特征映射连接
    """
    try:
        mapping = db.query(models.FeatureTableMapping).filter(
            models.FeatureTableMapping.id == mapping_id
        ).first()

        if not mapping:
            raise HTTPException(status_code=404, detail="映射不存在")

        data_source = db.query(models.DataSources).filter(
            models.DataSources.id == mapping.data_source_id
        ).first()

        if not data_source:
            raise HTTPException(status_code=404, detail="数据源不存在")

        # 连接到MySQL数据库
        connection = mysql.connector.connect(
            host=data_source.host,
            port=data_source.port,
            database=mapping.database_name,
            user=data_source.username,
            password=data_source.password,
            charset=data_source.charset or 'utf8mb4',
            connect_timeout=data_source.timeout or 10
        )

        cursor = connection.cursor()

        try:
            # 检查表是否存在
            cursor.execute(f"SHOW TABLES LIKE '{mapping.table_name}'")
            tables = cursor.fetchall()

            if not tables:
                return {"status": "error", "message": f"表 {mapping.table_name} 不存在"}

            # 检查列是否存在
            cursor.execute(f"DESCRIBE `{mapping.table_name}`")
            columns = cursor.fetchall()

            column_names = [col[0] for col in columns]

            if mapping.column_name not in column_names:
                return {"status": "error", "message": f"列 {mapping.column_name} 不存在"}

            if mapping.timestamp_column not in column_names:
                return {"status": "error", "message": f"时间戳列 {mapping.timestamp_column} 不存在"}

            # 获取最近一条数据作为示例
            cursor.execute(f"""
                SELECT {mapping.timestamp_column}, {mapping.column_name}
                FROM `{mapping.table_name}`
                ORDER BY {mapping.timestamp_column} DESC
                LIMIT 1
            """)

            sample_data = cursor.fetchone()

            return {
                "status": "success",
                "message": "映射测试成功",
                "sample_data": {
                    "timestamp": sample_data[0] if sample_data else None,
                    "value": sample_data[1] if sample_data else None
                }
            }

        finally:
            cursor.close()
            connection.close()

    except mysql.connector.Error as e:
        return {"status": "error", "message": f"数据库连接失败: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"测试失败: {str(e)}"}


# 批量保存特征映射
# app/api/config.py - 修改 save_batch_feature_mappings 函数的关键部分

@router.post("/feature-mappings/batch")
def save_batch_feature_mappings(mappings: List[schemas.FeatureMappingCreate],
                                db: Session = Depends(database.get_db)):
    try:
        # 1. 验证设备和特征是否存在（可选，增强健壮性）
        device_ids = {m.device_id for m in mappings}
        feature_ids = {m.feature_id for m in mappings}
        devices = {d.id: d for d in db.query(models.Device).filter(models.Device.id.in_(device_ids)).all()}
        features = {f.id: f for f in db.query(models.Feature).filter(models.Feature.id.in_(feature_ids)).all()}
        missing_devices = device_ids - devices.keys()
        missing_features = feature_ids - features.keys()
        if missing_devices or missing_features:
            raise HTTPException(
                status_code=400,
                detail=f"设备不存在: {missing_devices}，特征不存在: {missing_features}"
            )

        # 2. 仅保留设备内重复检查（同一设备内不允许使用相同的表+列）
        device_tables = {}
        existing_mapping_map = {}  # 缓存每个设备+特征的旧映射，用于更新

        for idx, mapping_data in enumerate(mappings):
            # 查询设备+特征是否已有旧映射（用于更新）
            existing = db.query(models.FeatureTableMapping).filter(
                models.FeatureTableMapping.device_id == mapping_data.device_id,
                models.FeatureTableMapping.feature_id == mapping_data.feature_id
            ).first()
            existing_mapping_map[idx] = existing

            # 设备内重复检查
            device_key = f"{mapping_data.device_id}_{mapping_data.data_source_id}_{mapping_data.database_name}"
            if device_key not in device_tables:
                device_tables[device_key] = set()
            table_key = f"{mapping_data.table_name}_{mapping_data.column_name or 'PointValue'}"
            if table_key in device_tables[device_key]:
                # 同一设备内重复使用同一表列，拒绝
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "同一设备内不允许重复使用相同的表列",
                        "conflict": {
                            "device_id": mapping_data.device_id,
                            "table_name": mapping_data.table_name,
                            "column_name": mapping_data.column_name or 'PointValue'
                        }
                    }
                )
            device_tables[device_key].add(table_key)

        # 3. 执行删除+新增（同一事务）
        results = []
        for idx, mapping_data in enumerate(mappings):
            try:
                existing = existing_mapping_map[idx]
                if existing:
                    db.delete(existing)
                    db.flush()

                db_mapping = models.FeatureTableMapping(
                    data_source_id=mapping_data.data_source_id,
                    database_name=mapping_data.database_name,
                    device_id=mapping_data.device_id,
                    feature_id=mapping_data.feature_id,
                    table_name=mapping_data.table_name,
                    column_name=mapping_data.column_name or 'PointValue',
                    timestamp_column=mapping_data.timestamp_column or 'UpdateDateTime',
                    is_active=mapping_data.is_active,
                    sync_frequency=mapping_data.sync_frequency or 15,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                db.add(db_mapping)
                results.append({
                    "feature_id": mapping_data.feature_id,
                    "status": "success",
                    "message": "映射已保存"
                })
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"保存过程中发生错误: {str(e)}")

        db.commit()

        # 4. 获取新映射的ID并返回
        final_results = []
        for idx, res in enumerate(results):
            if res["status"] == "success":
                mapping = db.query(models.FeatureTableMapping).filter(
                    models.FeatureTableMapping.device_id == mappings[idx].device_id,
                    models.FeatureTableMapping.feature_id == mappings[idx].feature_id
                ).first()
                res["mapping_id"] = mapping.id if mapping else None
            final_results.append(res)

        return {
            "total": len(mappings),
            "success": len([r for r in final_results if r["status"] == "success"]),
            "failed": len([r for r in final_results if r["status"] == "error"]),
            "results": final_results
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"批量保存失败: {str(e)}")


@router.post("/data-sources/{data_source_id}/databases/{database}/create-table")
def create_table(data_source_id: int, database: str, table_data: dict, db: Session = Depends(database.get_db)):
    """
    在指定数据源中创建特征表
    """
    try:
        # 获取数据源配置
        data_source = db.query(models.DataSources).filter(
            models.DataSources.id == data_source_id,
            models.DataSources.is_active == True
        ).first()

        if not data_source:
            raise HTTPException(status_code=404, detail="数据源不存在或已停用")

        table_name = table_data.get("table_name")
        if not table_name:
            raise HTTPException(status_code=400, detail="表名不能为空")

        # 改进的表名验证规则
        # MySQL官方规则：https://dev.mysql.com/doc/refman/8.0/en/identifiers.html
        table_name_pattern = r'^[a-zA-Z_][a-zA-Z0-9_\$#@\-]*$'

        if not re.match(table_name_pattern, table_name):
            raise HTTPException(
                status_code=400,
                detail="表名格式错误。规则：<br>"
                       "1. 以字母或下划线开头<br>"
                       "2. 允许：字母、数字、下划线(_)、短横线(-)、美元符号($)、井号(#)、at符号(@)<br>"
                       "3. 长度：2-64字符"
            )

        # 长度验证
        if len(table_name) < 2:
            raise HTTPException(status_code=400, detail="表名太短，至少需要2个字符")

        if len(table_name) > 64:
            raise HTTPException(status_code=400, detail="表名太长，不能超过64个字符")

        # 检查连续的短横线或下划线
        if re.search(r'[-_]{2,}', table_name):
            raise HTTPException(status_code=400, detail="表名不能包含连续的短横线或下划线")

        # 检查开头和结尾
        if re.match(r'^[-$#@]', table_name) or re.search(r'[-_]$', table_name):
            raise HTTPException(status_code=400, detail="表名不能以短横线或特殊字符开头，不能以下划线或短横线结尾")

        # 检查是否纯数字
        if table_name.isdigit():
            raise HTTPException(status_code=400, detail="表名不能是纯数字")

        # MySQL保留关键字检查（常见关键字）
        reserved_keywords = {
            'select', 'insert', 'update', 'delete', 'create', 'drop', 'alter',
            'table', 'database', 'index', 'view', 'procedure', 'function',
            'trigger', 'event', 'temporary', 'if', 'exists', 'where', 'from',
            'set', 'values', 'into', 'null', 'not', 'and', 'or', 'like', 'in',
            'between', 'is', 'default', 'auto_increment', 'primary', 'key',
            'unique', 'foreign', 'references', 'constraint', 'check'
        }

        if table_name.lower() in reserved_keywords:
            raise HTTPException(status_code=400, detail=f"表名 '{table_name}' 是MySQL保留关键字，请使用其他名称")

        # 可选：检查表名是否容易引起SQL注入
        dangerous_patterns = [
            r'--', r'/\*', r'\*/', r';', r'\x00', r'\\', r"'", r'"'
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, table_name):
                raise HTTPException(status_code=400, detail="表名包含不安全的字符")

        try:
            # 连接到MySQL数据库
            connection = mysql.connector.connect(
                host=data_source.host,
                port=data_source.port,
                database=database,
                user=data_source.username,
                password=data_source.password,
                charset=data_source.charset or 'utf8mb4',
                connect_timeout=data_source.timeout or 10
            )

            cursor = connection.cursor()

            try:
                # 使用反引号包裹表名，支持特殊字符
                safe_table_name = f"`{table_name}`"

                # 检查表是否已存在（使用反引号）
                cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                existing_tables = cursor.fetchall()

                if existing_tables:
                    raise HTTPException(status_code=400, detail=f"表 '{table_name}' 已存在")

                # 创建表 - 使用安全的表名
                create_table_sql = f"""
                CREATE TABLE {safe_table_name} (
                  `UpdateDateTime` datetime DEFAULT NULL,
                  `PointValue` float DEFAULT NULL,
                  `id` int NOT NULL AUTO_INCREMENT,
                  PRIMARY KEY (`id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
                """

                cursor.execute(create_table_sql)

                # 添加索引以提高查询性能
                try:
                    add_index_sql = f"""
                    ALTER TABLE {safe_table_name} 
                    ADD INDEX `idx_{table_name}_update_time` (`UpdateDateTime`)
                    """
                    cursor.execute(add_index_sql)
                except Exception as index_error:
                    # 索引创建失败不影响表创建，只是记录警告
                    print(f"创建索引失败: {index_error}")

                connection.commit()

                # 验证表创建成功
                cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                created_tables = cursor.fetchall()

                if not created_tables:
                    raise HTTPException(status_code=500, detail="表创建失败")

                # 获取表结构信息
                cursor.execute(f"DESCRIBE {safe_table_name}")
                columns = cursor.fetchall()

                column_info = []
                for col in columns:
                    column_info.append({
                        "name": col[0],
                        "type": col[1],
                        "nullable": col[2] == "YES",
                        "default": col[4],
                        "extra": col[5]
                    })

                return {
                    "status": "success",
                    "message": f"表 '{table_name}' 创建成功",
                    "table_name": table_name,
                    "full_table_name": f"{database}.{table_name}",
                    "columns": column_info,
                    "row_count": 0,  # 新表没有数据
                    "created_at": datetime.now().isoformat()
                }

            finally:
                cursor.close()
                connection.close()

        except mysql.connector.Error as e:
            error_msg = str(e).lower()

            # 友好的错误消息
            if "already exists" in error_msg:
                raise HTTPException(status_code=400, detail=f"表 '{table_name}' 已存在")
            elif "access denied" in error_msg:
                raise HTTPException(status_code=403, detail="数据库访问被拒绝，请检查用户权限")
            elif "unknown database" in error_msg:
                raise HTTPException(status_code=400, detail=f"数据库 '{database}' 不存在")
            elif "syntax error" in error_msg:
                # 可能是表名导致的语法错误
                raise HTTPException(status_code=400, detail=f"表名 '{table_name}' 包含无效字符")
            else:
                # 其他数据库错误
                raise HTTPException(status_code=500, detail=f"数据库错误: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建表失败: {str(e)}")