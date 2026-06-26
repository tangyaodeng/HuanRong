# backend/app/api/monitoring.py
"""
实时监控API路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict
import pymysql
from pymysql.cursors import DictCursor
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

MYSQL_CONFIG = {
    'host': settings.MYSQL_HOST,
    'port': settings.MYSQL_PORT,
    'user': settings.MYSQL_USER,
    'password': settings.MYSQL_PASSWORD,
    'database': settings.MYSQL_DATABASE,
    'charset': settings.MYSQL_CHARSET
}

def get_mysql_connection():
    try:
        connection = pymysql.connect(
            host=MYSQL_CONFIG['host'],
            port=MYSQL_CONFIG['port'],
            user=MYSQL_CONFIG['user'],
            password=MYSQL_CONFIG['password'],
            database=MYSQL_CONFIG['database'],
            charset=MYSQL_CONFIG['charset'],
            cursorclass=DictCursor
        )
        return connection
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MySQL连接失败: {str(e)}")


def _validate_table_name(name: str) -> None:
    if not name.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail=f"非法表名: {name}")


def _query_table_rows(cursor, table_name: str, start_time: Optional[str],
                      end_time: Optional[str], limit: int) -> List[Dict]:
    """查询单表原始数据，返回 [{timestamp, value}, ...]。
    若表不存在则返回空列表，不抛异常。"""
    # 先检查表是否存在
    cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
    if not cursor.fetchone():
        return []

    where_parts = []
    params = []
    if start_time:
        where_parts.append("UpdateDateTime >= %s")
        params.append(start_time)
    if end_time:
        where_parts.append("UpdateDateTime <= %s")
        params.append(end_time)
    where_clause = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

    query = f"""
        SELECT UpdateDateTime AS timestamp, PointValue AS value
        FROM `{table_name}`
        {where_clause}
        ORDER BY UpdateDateTime ASC
        LIMIT %s
    """
    params.append(limit)
    cursor.execute(query, params)
    return cursor.fetchall()


def _align_to_buckets(rows: List[Dict], resample_minutes: int) -> Dict[datetime, float]:
    """
    将单表原始数据对齐到 resample_minutes 分钟整点桶。
    每个桶取该表在桶边界之前最近的一条非空值。
    返回 {bucket_ts: value, ...}
    """
    if not rows or resample_minutes <= 0:
        # 不重采样时保留原始时间戳
        return {row["timestamp"]: float(row["value"])
                for row in rows if row["value"] is not None}

    buckets = {}
    for row in rows:
        if row["value"] is None:
            continue
        ts = row["timestamp"]
        # 四舍五入到最近的整点桶（避免因计算延迟导致9:39的数据落到9:35桶）
        half_interval = timedelta(minutes=resample_minutes / 2)
        adjusted = ts + half_interval
        bucket_ts = adjusted - timedelta(
            minutes=adjusted.minute % resample_minutes,
            seconds=adjusted.second,
            microseconds=adjusted.microsecond
        )
        val = float(row["value"])
        # 每个桶保留时间戳最新的那条（后出现的覆盖先出现的）
        if bucket_ts not in buckets or ts > buckets[bucket_ts][1]:
            buckets[bucket_ts] = (val, ts)
    return {k: v[0] for k, v in buckets.items()}


@router.get("/realtime-data")
async def get_realtime_data(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    limit: int = Query(500),
    category: str = Query(..., description="监控类别: host, cooling_tower, cooling_pump, chilled_pump"),
    resample: int = Query(5, description="重采样间隔（分钟），0 表示不重采样")
):
    cat_config = settings.MONITORING_CATEGORIES.get(category)
    if not cat_config:
        raise HTTPException(status_code=400, detail=f"不支持的监控类别: {category}")

    pred_tables = cat_config.get("pred_tables", [])
    actual_tables = cat_config.get("actual_tables", [])
    if not pred_tables and not actual_tables:
        raise HTTPException(status_code=500, detail="监控表配置为空（pred_tables 和 actual_tables 均为空）")

    latest_time = None
    connection = None

    # ---- 查询所有表，每个表返回 {bucket_ts: value} ----
    pred_table_buckets = {}   # {table_name: {bucket_ts: value, ...}, ...}
    actual_table_buckets = {}

    try:
        connection = get_mysql_connection()
        with connection.cursor() as cursor:
            for table_name in pred_tables:
                _validate_table_name(table_name)
                rows = _query_table_rows(cursor, table_name, start_time, end_time, limit)
                pred_table_buckets[table_name] = _align_to_buckets(rows, resample)

                cursor.execute(f"SELECT MAX(UpdateDateTime) FROM `{table_name}`")
                t = cursor.fetchone()["MAX(UpdateDateTime)"]
                if t and (latest_time is None or t > latest_time):
                    latest_time = t

            for table_name in actual_tables:
                _validate_table_name(table_name)
                rows = _query_table_rows(cursor, table_name, start_time, end_time, limit)
                actual_table_buckets[table_name] = _align_to_buckets(rows, resample)

                cursor.execute(f"SELECT MAX(UpdateDateTime) FROM `{table_name}`")
                t = cursor.fetchone()["MAX(UpdateDateTime)"]
                if t and (latest_time is None or t > latest_time):
                    latest_time = t

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询数据失败: {str(e)}")
    finally:
        if connection:
            connection.close()

    # ---- 汇总：收集所有桶时间戳，按桶加和 ----
    all_buckets = set()
    for tb in pred_table_buckets.values():
        all_buckets.update(tb.keys())
    for tb in actual_table_buckets.values():
        all_buckets.update(tb.keys())

    processed_data = []
    for bucket_ts in sorted(all_buckets):
        pred_sum = sum(
            pred_table_buckets[tn].get(bucket_ts, 0.0)
            for tn in pred_table_buckets
        )
        actual_sum = sum(
            actual_table_buckets[tn].get(bucket_ts, 0.0)
            for tn in actual_table_buckets
        )
        processed_data.append({
            "timestamp": bucket_ts.isoformat(),
            "predicted_value": round(pred_sum, 4) if pred_tables else None,
            "actual_value": round(actual_sum, 4) if actual_tables else None,
        })

    stats = calculate_statistics(processed_data)

    return {
        "data": processed_data,
        "stats": stats,
        "latest_update_time": latest_time.isoformat() if latest_time else None,
        "total": len(processed_data),
        "query_time": datetime.now().isoformat(),
        "category": category,
        "pred_table_count": len(pred_tables),
        "actual_table_count": len(actual_tables),
    }

def calculate_statistics(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not data:
        return {"total_points": 0, "accuracy": 0, "avg_predicted": 0, "avg_actual": 0,
                "max_error": 0, "min_error": 0, "mae": 0}

    errors, predicted_values, actual_values = [], [], []
    for item in data:
        if item["actual_value"] is not None and item["predicted_value"] is not None:
            errors.append(abs(item["actual_value"] - item["predicted_value"]))
            predicted_values.append(item["predicted_value"])
            actual_values.append(item["actual_value"])

    if errors:
        mae = sum(errors) / len(errors)
        avg_predicted = sum(predicted_values) / len(predicted_values)
        avg_actual = sum(actual_values) / len(actual_values)
        relative_mae = mae / avg_actual if avg_actual > 0 else 0
        accuracy = max(0, 1 - relative_mae)
        return {
            "total_points": len(data),
            "accuracy": round(accuracy, 4),
            "avg_predicted": round(avg_predicted, 2),
            "avg_actual": round(avg_actual, 2),
            "max_error": round(max(errors), 2),
            "min_error": round(min(errors), 2),
            "mae": round(mae, 2)
        }
    else:
        return {
            "total_points": len(data), "accuracy": 0, "avg_predicted": 0, "avg_actual": 0,
            "max_error": 0, "min_error": 0, "mae": 0
        }


@router.get("/stats")
async def get_monitoring_stats():
    """
    获取监控统计数据
    """
    try:
        connection = get_mysql_connection()

        with connection.cursor() as cursor:
            # 获取总数据量
            cursor.execute("SELECT COUNT(*) as total FROM `pre-composite_total_host_meter`")
            total_result = cursor.fetchone()

            # 获取最新数据时间
            cursor.execute("SELECT MAX(UpdateDateTime) as latest_data FROM `pre-composite_total_host_meter`")
            latest_data_result = cursor.fetchone()

            # 获取预测精度统计数据
            cursor.execute("""
                SELECT 
                    AVG(ABS(PointValue - ActualValue) / NULLIF(ActualValue, 0)) * 100 as avg_error_percent,
                    COUNT(CASE WHEN ABS(PointValue - ActualValue) / NULLIF(ActualValue, 0) < 0.05 THEN 1 END) * 100.0 / COUNT(*) as accuracy_rate
                FROM `pre-composite_total_host_meter`
                WHERE ActualValue IS NOT NULL AND ActualValue != 0
            """)
            accuracy_result = cursor.fetchone()

            # 获取设备统计
            cursor.execute("SELECT COUNT(DISTINCT DeviceID) as device_count FROM `pre-composite_total_host_meter`")
            device_result = cursor.fetchone()

        connection.close()

        return {
            "total_records": total_result["total"] if total_result else 0,
            "latest_data_time": latest_data_result["latest_data"].isoformat() if latest_data_result and
                                                                                 latest_data_result[
                                                                                     "latest_data"] else None,
            "avg_error_percent": round(accuracy_result["avg_error_percent"], 2) if accuracy_result and accuracy_result[
                "avg_error_percent"] else 0,
            "accuracy_rate": round(accuracy_result["accuracy_rate"], 2) if accuracy_result and accuracy_result[
                "accuracy_rate"] else 0,
            "device_count": device_result["device_count"] if device_result else 0,
            "update_frequency": "5分钟",
            "last_update": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/system-status")
async def get_system_status():
    """
    获取系统状态
    """
    try:
        connection = get_mysql_connection()

        with connection.cursor() as cursor:
            # 检查数据更新频率
            cursor.execute("""
                SELECT 
                    MAX(PredictionTime) as last_prediction,
                    COUNT(*) as last_hour_count
                FROM `pre-composite_total_host_meter`
                WHERE PredictionTime >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """)
            frequency_result = cursor.fetchone()

            # 检查数据质量
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_count,
                    COUNT(CASE WHEN ActualValue IS NOT NULL THEN 1 END) as actual_count,
                    COUNT(CASE WHEN PointValue IS NOT NULL THEN 1 END) as predicted_count
                FROM `pre-composite_total_host_meter`
                WHERE UpdateDateTime >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            """)
            quality_result = cursor.fetchone()

        connection.close()

        # 计算更新频率状态
        last_prediction = frequency_result["last_prediction"] if frequency_result else None
        if last_prediction:
            last_prediction_time = last_prediction
            time_diff = (datetime.now() - last_prediction_time).total_seconds() / 60  # 分钟

            if time_diff <= 10:  # 10分钟内
                update_status = "正常"
                update_color = "success"
            elif time_diff <= 30:  # 30分钟内
                update_status = "警告"
                update_color = "warning"
            else:
                update_status = "异常"
                update_color = "danger"
        else:
            update_status = "无数据"
            update_color = "danger"

        # 计算数据质量
        if quality_result and quality_result["total_count"] > 0:
            actual_ratio = quality_result["actual_count"] / quality_result["total_count"]
            predicted_ratio = quality_result["predicted_count"] / quality_result["total_count"]

            if actual_ratio > 0.9 and predicted_ratio > 0.9:
                quality_status = "优秀"
                quality_color = "success"
            elif actual_ratio > 0.7 and predicted_ratio > 0.7:
                quality_status = "良好"
                quality_color = "info"
            else:
                quality_status = "需要检查"
                quality_color = "warning"
        else:
            quality_status = "无数据"
            quality_color = "danger"

        return {
            "update_status": {
                "status": update_status,
                "color": update_color,
                "last_prediction": last_prediction.isoformat() if last_prediction else None,
                "last_hour_count": frequency_result["last_hour_count"] if frequency_result else 0
            },
            "data_quality": {
                "status": quality_status,
                "color": quality_color,
                "total_count": quality_result["total_count"] if quality_result else 0,
                "actual_count": quality_result["actual_count"] if quality_result else 0,
                "predicted_count": quality_result["predicted_count"] if quality_result else 0
            },
            "system_time": datetime.now().isoformat(),
            "database_connection": "正常"
        }

    except Exception as e:
        return {
            "update_status": {
                "status": "连接失败",
                "color": "danger",
                "last_prediction": None,
                "last_hour_count": 0
            },
            "data_quality": {
                "status": "连接失败",
                "color": "danger",
                "total_count": 0,
                "actual_count": 0,
                "predicted_count": 0
            },
            "system_time": datetime.now().isoformat(),
            "database_connection": f"异常: {str(e)}"
        }