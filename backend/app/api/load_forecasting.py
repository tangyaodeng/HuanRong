# backend/app/api/load_forecasting.py
"""
负荷预测API路由
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
import pymysql
from pymysql.cursors import DictCursor
import json
from collections import defaultdict
from ..config import settings

router = APIRouter(prefix="/load_forecasting", tags=["load_forecasting"])

MYSQL_CONFIG = {
    'host': settings.MYSQL_HOST,
    'port': settings.MYSQL_PORT,
    'user': settings.MYSQL_USER,
    'password': settings.MYSQL_PASSWORD,
    'database': settings.MYSQL_DATABASE,
    'charset': settings.MYSQL_CHARSET
}

# 请根据实际情况调整以下常量
DEVICE_ID = 10                     # 设备ID
TARGET_FEATURE_ID = 257            # 目标特征ID（对应 hourly_cooling_energy）
PREDICTION_TABLE = "pre-multistep_composite_hourly_cooling_energy_total"


def get_mysql_connection():
    try:
        conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=DictCursor)
        return conn
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")


@router.get("/predictions")
async def get_predictions():
    """获取最新负荷预测数据（小时、日、周、月聚合）"""
    conn = get_mysql_connection()
    try:
        with conn.cursor() as cursor:
            # 查询最新一条预测记录（按 ForecastStartTime 降序）
            cursor.execute(f"""
                SELECT DeviceID, TargetFeatureID, ForecastStartTime, StepMinutes, PredictionArray
                FROM `{PREDICTION_TABLE}`
                WHERE DeviceID = %s AND TargetFeatureID = %s
                ORDER BY ForecastStartTime DESC
                LIMIT 1
            """, (DEVICE_ID, TARGET_FEATURE_ID))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="暂无预测数据")

            device_id = row['DeviceID']
            forecast_start = row['ForecastStartTime']
            step_minutes = row['StepMinutes']
            prediction_json = row['PredictionArray']

            # 解析 JSON 数组
            predictions = json.loads(prediction_json) if isinstance(prediction_json, str) else prediction_json
            if not predictions:
                raise HTTPException(status_code=500, detail="预测数据为空")

            # 生成时间序列
            hourly = []
            current_time = forecast_start
            for val in predictions:
                hourly.append({
                    "timestamp": current_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "value": round(float(val), 4)
                })
                current_time += timedelta(minutes=step_minutes)

            # 按天聚合
            daily_dict = defaultdict(float)
            for item in hourly:
                day_key = item["timestamp"][:10]  # YYYY-MM-DD
                daily_dict[day_key] += item["value"]

            daily = [{"date": k, "total": round(v, 2)} for k, v in sorted(daily_dict.items())]

            # 按周聚合（ISO 周，每周从周一开始）
            weekly_dict = defaultdict(float)
            for item in hourly:
                ts = datetime.strptime(item["timestamp"], '%Y-%m-%d %H:%M:%S')
                iso_year, iso_week, _ = ts.isocalendar()
                week_key = f"{iso_year}-W{iso_week:02d}"
                weekly_dict[week_key] += item["value"]

            weekly = [{"week": k, "total": round(v, 2)} for k, v in sorted(weekly_dict.items())]

            # 按月聚合
            monthly_dict = defaultdict(float)
            for item in hourly:
                month_key = item["timestamp"][:7]  # YYYY-MM
                monthly_dict[month_key] += item["value"]

            monthly = [{"month": k, "total": round(v, 2)} for k, v in sorted(monthly_dict.items())]

            return {
                "device_id": device_id,
                "forecast_start": forecast_start.strftime('%Y-%m-%d %H:%M:%S'),
                "forecast_end": (current_time - timedelta(minutes=step_minutes)).strftime('%Y-%m-%d %H:%M:%S'),
                "step_minutes": step_minutes,
                "hourly": hourly,
                "daily": daily,
                "weekly": weekly,
                "monthly": monthly,
                "data_status": "真实数据"
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询预测失败: {str(e)}")
    finally:
        conn.close()