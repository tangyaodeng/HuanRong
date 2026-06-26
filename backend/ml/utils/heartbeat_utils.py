# backend/ml/utils/heartbeat_utils.py
import logging
from sqlalchemy import create_engine, text
from typing import Optional


def update_heartbeat(postgres_engine, table_name: str, logger: logging.Logger) -> bool:
    """
    更新指定表的最新记录的心跳时间戳和状态（0/1翻转）

    Args:
        postgres_engine: SQLAlchemy 引擎对象
        table_name: 目标表名（如 'cooling_opt_parameters_total'）
        logger: 日志记录器

    Returns:
        bool: 是否成功
    """
    try:
        if postgres_engine is None:
            logger.warning("PostgreSQL未连接，无法更新心跳")
            return False

        with postgres_engine.connect() as conn:
            # 检查表中是否有记录
            check_sql = text(f"SELECT COUNT(*) FROM {table_name}")
            count = conn.execute(check_sql).scalar()

            if count == 0:
                # 无记录时插入一条初始占位记录
                insert_sql = text(f"""
                    INSERT INTO {table_name} 
                    (optimization_timestamp, heartbeat_timestamp, heartbeat_state, remarks)
                    VALUES (NOW(), NOW(), 0, '心跳初始化记录')
                """)
                conn.execute(insert_sql)
                conn.commit()
                logger.info(f"表 {table_name} 创建初始心跳记录")
                return True

            # 获取最新记录的 id 和当前 heartbeat_state
            latest_sql = text(f"""
                SELECT id, COALESCE(heartbeat_state, 0) as state 
                FROM {table_name} 
                ORDER BY id DESC LIMIT 1
            """)
            row = conn.execute(latest_sql).fetchone()
            if row:
                new_state = 1 - row.state  # 翻转
                update_sql = text(f"""
                    UPDATE {table_name} 
                    SET heartbeat_timestamp = NOW(), heartbeat_state = :state
                    WHERE id = :id
                """)
                conn.execute(update_sql, {"state": new_state, "id": row.id})
                conn.commit()
                logger.debug(f"表 {table_name} 心跳更新成功: id={row.id}, state={new_state}")
                return True
            else:
                logger.warning(f"表 {table_name} 无记录，无法更新心跳")
                return False
    except Exception as e:
        logger.error(f"更新心跳失败 (表 {table_name}): {e}")
        return False