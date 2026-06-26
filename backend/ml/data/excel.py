"""
Excel数据导入MySQL工具 - 直接完整导入AI22数据
"""

import pandas as pd
import numpy as np
import pymysql
from datetime import datetime, timedelta
import os
import logging
import warnings
import re  # 添加正则表达式模块
warnings.filterwarnings('ignore')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExcelToMySQLImporterFixed:
    """Excel数据导入MySQL工具类 - 修复重复时间戳问题"""

    def __init__(self):
        # MySQL数据库配置
        self.MYSQL_CONFIG = {
            'host': "192.168.5.100",
            'port': 3306,
            'user': "admin1",
            'password': "Jlk@123456",
            'database': "jh_hisdata",
            'charset': "utf8mb4"
        }

        # 目标表名
        self.target_table = "dev-zlz-plc-ai22"

        # Excel文件路径
        self.excel_file_path = r"D:\桌面\智慧暖通AI预测系统\训练数据\有cop列版\6月份数据主机数据.xlsx"

        # 连接对象
        self.connection = None
        self.cursor = None

    def connect_to_mysql(self) -> bool:
        """连接到MySQL数据库"""
        try:
            self.connection = pymysql.connect(
                host=self.MYSQL_CONFIG['host'],
                port=self.MYSQL_CONFIG['port'],
                user=self.MYSQL_CONFIG['user'],
                password=self.MYSQL_CONFIG['password'],
                database=self.MYSQL_CONFIG['database'],
                charset=self.MYSQL_CONFIG['charset']
            )
            self.cursor = self.connection.cursor()
            logger.info(f"✅ 成功连接到MySQL数据库: {self.MYSQL_CONFIG['host']}")
            return True
        except Exception as e:
            logger.error(f"❌ 连接MySQL数据库失败: {e}")
            return False

    def disconnect_from_mysql(self):
        """断开MySQL连接"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        logger.info("✅ MySQL连接已关闭")

    def check_table_exists(self, table_name: str) -> bool:
        """检查表是否存在"""
        try:
            check_query = f"""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            AND table_name = %s
            """
            self.cursor.execute(check_query, (self.MYSQL_CONFIG['database'], table_name))
            result = self.cursor.fetchone()
            exists = result[0] > 0

            if exists:
                logger.info(f"✅ 表 '{table_name}' 存在")
            else:
                logger.warning(f"⚠️ 表 '{table_name}' 不存在")

            return exists
        except Exception as e:
            logger.error(f"❌ 检查表是否存在失败: {e}")
            return False

    def get_table_structure(self, table_name: str):
        """获取表结构"""
        try:
            # 先检查表是否存在唯一索引或主键
            query = f"""
            SHOW INDEX FROM `{table_name}` 
            WHERE Key_name = 'PRIMARY' OR Non_unique = 0
            """
            self.cursor.execute(query)
            indexes = self.cursor.fetchall()

            if indexes:
                logger.info(f"📊 表 '{table_name}' 的索引信息:")
                for idx in indexes:
                    logger.info(f"  - 索引名: {idx[2]}, 列: {idx[4]}, 类型: {'主键' if idx[2] == 'PRIMARY' else '唯一索引'}")

            # 获取列信息
            query = f"DESCRIBE `{table_name}`"
            self.cursor.execute(query)
            columns_info = self.cursor.fetchall()

            logger.info(f"📊 表 '{table_name}' 结构:")
            for col in columns_info:
                logger.info(f"  - {col[0]}: {col[1]} ({col[2]})")

            return columns_info
        except Exception as e:
            logger.error(f"❌ 获取表结构失败: {e}")
            return []

    def find_target_column(self, df_columns):
        """智能查找目标数据列"""
        # 方法1: 精确匹配目标表名对应的列
        target_name = self.target_table.upper()  # 转换为大写

        # 尝试不同的匹配模式
        patterns = [
            # 精确匹配模式
            lambda col: str(col).upper() == target_name,

            # 包含目标表名的模式
            lambda col: target_name in str(col).upper(),

            # 匹配AI22（精确数字匹配）
            lambda col: re.search(r'AI22\D', str(col).upper()) and not re.search(r'AI22[0-9]', str(col).upper()),

            # 匹配dev-zlz-plc-ai22的变体
            lambda col: re.search(r'DEV[^A-Z]*ZLZ[^A-Z]*PLC[^A-Z]*AI22', str(col).upper()),

            # 最后尝试：包含AI22但不包含其他数字的模式
            lambda col: 'AI22' in str(col).upper() and not any(f'AI22{i}' in str(col).upper() for i in range(3, 10))
        ]

        matched_columns = []

        for col in df_columns:
            col_str = str(col)
            col_upper = col_str.upper()

            for pattern_idx, pattern_func in enumerate(patterns):
                if pattern_func(col_str):
                    matched_columns.append((col, pattern_idx, col_str))
                    break

        if matched_columns:
            # 按照匹配优先级排序（pattern_idx越小优先级越高）
            matched_columns.sort(key=lambda x: x[1])
            logger.info(f"📋 找到 {len(matched_columns)} 个可能的匹配列:")
            for col, priority, col_str in matched_columns:
                logger.info(f"  - '{col_str}' (匹配优先级: {priority})")

            # 返回优先级最高的列
            return matched_columns[0][0]

        return None

    def analyze_excel_structure(self):
        """分析Excel文件结构，确定如何正确读取数据"""
        try:
            if not os.path.exists(self.excel_file_path):
                logger.error(f"❌ Excel文件不存在: {self.excel_file_path}")
                return None

            logger.info(f"🔍 开始分析Excel文件结构: {self.excel_file_path}")

            # 读取前几行来了解数据结构
            df = pd.read_excel(self.excel_file_path, nrows=20)

            logger.info(f"📋 Excel文件形状: {df.shape}")
            logger.info(f"📋 所有列名列表:")
            for i, col in enumerate(df.columns):
                logger.info(f"  列{i+1}: '{col}'")

            # 查找时间列
            time_column = None
            for col in df.columns:
                col_str = str(col)
                if any(keyword in col_str for keyword in ['时间', 'Time', 'TIMESTAMP', 'timestamp', '日期']):
                    time_column = col
                    logger.info(f"🔍 找到时间列: '{col_str}'")
                    break

            if time_column:
                logger.info(f"🔍 使用时间列: '{time_column}'")

                # 检查时间列的值
                unique_times = df[time_column].nunique()
                total_rows = len(df)
                logger.info(f"📊 时间列统计: 唯一值 {unique_times}, 总行数 {total_rows}")

                # 查看重复的时间戳
                time_counts = df[time_column].value_counts()
                duplicates = time_counts[time_counts > 1]

                if not duplicates.empty:
                    logger.warning(f"⚠️ 发现 {len(duplicates)} 个重复的时间戳:")
                    for time_val, count in duplicates.head(5).items():
                        logger.warning(f"  - {time_val}: 重复 {count} 次")

            # 查找目标数据列
            target_column = self.find_target_column(df.columns)

            if target_column:
                logger.info(f"🎯 找到目标数据列: '{target_column}'")

                # 检查该列的数据
                non_null_count = df[target_column].count()
                unique_count = df[target_column].nunique()
                logger.info(f"📊 目标列统计: 非空值: {non_null_count}, 唯一值: {unique_count}")

                # 显示前几个非空值
                non_null_values = df[target_column].dropna().head()
                if len(non_null_values) > 0:
                    logger.info(f"📊 目标列前几个值: {list(non_null_values)}")
                else:
                    logger.warning("⚠️ 目标列前几行均为空值")
            else:
                logger.warning("⚠️ 未找到目标数据列，将显示所有可能的数据列:")
                for col in df.columns:
                    if 'AI' in str(col).upper():
                        logger.info(f"  - '{col}'")

            return df.head(10)

        except Exception as e:
            logger.error(f"❌ 分析Excel文件失败: {e}", exc_info=True)
            return None

    def read_excel_data_intelligently(self) -> pd.DataFrame:
        """智能读取Excel数据，处理重复时间戳问题"""
        try:
            if not os.path.exists(self.excel_file_path):
                logger.error(f"❌ Excel文件不存在: {self.excel_file_path}")
                return pd.DataFrame()

            logger.info(f"📖 正在智能读取Excel文件: {self.excel_file_path}")

            # 1. 读取整个文件
            df = pd.read_excel(self.excel_file_path, engine='openpyxl')
            logger.info(f"📊 读取到原始数据: {df.shape[0]} 行, {df.shape[1]} 列")

            # 2. 查找时间列
            time_col = None
            for col in df.columns:
                col_str = str(col)
                if any(keyword in col_str for keyword in ['时间', 'Time', 'TIMESTAMP', 'timestamp', '日期']):
                    time_col = col
                    logger.info(f"🔍 识别到时间列: '{col_str}'")
                    break

            if not time_col:
                # 尝试第一列作为时间列
                logger.warning("⚠️ 未找到时间列，尝试使用第一列作为时间列")
                time_col = df.columns[0]

            # 3. 查找目标数据列
            target_col = self.find_target_column(df.columns)

            if not target_col:
                logger.error("❌ 未找到目标数据列，可用的AI相关列:")
                for col in df.columns:
                    col_str = str(col).upper()
                    if 'AI' in col_str:
                        logger.error(f"  - '{col}'")
                return pd.DataFrame()

            logger.info(f"🎯 使用目标数据列: '{target_col}'")

            # 4. 提取需要的列
            df = df[[time_col, target_col]].copy()
            df = df.rename(columns={time_col: 'timestamp', target_col: 'value'})

            # 5. 处理时间戳
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

            # 6. 处理数值
            df['value'] = pd.to_numeric(df['value'], errors='coerce')

            # 对数值进行四舍五入，保留2位小数
            df['value'] = df['value'].round(2)

            # 7. 删除完全为NaN的行
            original_count = len(df)
            df = df.dropna(subset=['timestamp', 'value'])
            logger.info(f"📊 清理后数据: {len(df)} 行 (删除了 {original_count - len(df)} 行)")

            if len(df) == 0:
                logger.error("❌ 清理后数据为空，请检查数据格式")
                return pd.DataFrame()

            # 8. 检查时间戳重复情况
            duplicate_info = df['timestamp'].duplicated()
            duplicate_count = duplicate_info.sum()

            if duplicate_count > 0:
                logger.warning(f"⚠️ 发现 {duplicate_count} 个重复时间戳")

                # 显示重复的例子
                duplicate_times = df[df['timestamp'].duplicated(keep=False)]['timestamp'].unique()[:5]
                for time_val in duplicate_times:
                    duplicate_rows = df[df['timestamp'] == time_val]
                    logger.warning(f"  - {time_val}: {len(duplicate_rows)} 条记录, 值: {list(duplicate_rows['value'])}")

                # 策略：对于重复的时间戳，取平均值
                df = df.groupby('timestamp')['value'].mean().reset_index()
                df['value'] = df['value'].round(2)
                logger.info(f"📊 去重后数据: {len(df)} 行")

            # 9. 格式转换
            df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

            # 10. 数据统计
            logger.info(f"✅ 成功处理 {len(df)} 行数据")
            logger.info(f"📊 数值范围: {df['value'].min():.2f} ~ {df['value'].max():.2f}")
            logger.info(f"📊 平均值: {df['value'].mean():.2f}")

            logger.info(f"📊 最终数据示例 (前5行):")
            for i, (timestamp, value) in enumerate(zip(df['timestamp'].head(5), df['value'].head(5))):
                logger.info(f"  第{i+1}行: {timestamp} -> {value:.2f}")

            return df

        except Exception as e:
            logger.error(f"❌ 读取Excel文件失败: {e}", exc_info=True)
            return pd.DataFrame()

    def insert_data_to_mysql_safely(self, df: pd.DataFrame, batch_size: int = 100):
        """安全地将数据插入MySQL表，处理重复键问题"""
        if df.empty:
            logger.warning("⚠️ 没有数据需要插入")
            return 0, 0

        success_count = 0
        error_count = 0

        try:
            # 首先检查表是否有唯一索引
            check_index_query = f"""
            SHOW INDEX FROM `{self.target_table}` 
            WHERE Key_name = 'PRIMARY' OR Non_unique = 0
            """
            self.cursor.execute(check_index_query)
            indexes = self.cursor.fetchall()

            has_unique_index = False
            for idx in indexes:
                if idx[2] == 'PRIMARY' or idx[1] == 0:
                    has_unique_index = True
                    logger.warning(f"⚠️ 表有{'主键' if idx[2] == 'PRIMARY' else '唯一索引'}: {idx[4]}")

            if has_unique_index:
                logger.info("🔄 检测到表有唯一约束，将使用REPLACE INTO语句")
                insert_query = f"""
                REPLACE INTO `{self.target_table}` (UpdateDateTime, PointValue)
                VALUES (%s, %s)
                """
            else:
                logger.info("🔄 表无唯一约束，将使用INSERT IGNORE语句")
                insert_query = f"""
                INSERT IGNORE INTO `{self.target_table}` (UpdateDateTime, PointValue)
                VALUES (%s, %s)
                """

            # 转换为适合插入的格式
            data_to_insert = []
            for _, row in df.iterrows():
                timestamp = row['timestamp']
                value = float(row['value'])

                # 确保时间戳格式正确
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        try:
                            timestamp = pd.to_datetime(timestamp)
                            timestamp = timestamp.to_pydatetime()
                        except Exception as e:
                            logger.warning(f"⚠️ 时间戳格式错误: {timestamp}, 错误: {e}")
                            error_count += 1
                            continue

                data_to_insert.append((timestamp, value))

            # 分批插入数据
            total_rows = len(data_to_insert)
            logger.info(f"📤 准备插入 {total_rows} 行数据到表 '{self.target_table}'")

            for i in range(0, total_rows, batch_size):
                batch = data_to_insert[i:i + batch_size]
                try:
                    self.cursor.executemany(insert_query, batch)
                    self.connection.commit()
                    success_count += len(batch)
                    logger.info(f"✅ 成功插入批次 {i//batch_size + 1}: {len(batch)} 行")
                except Exception as e:
                    self.connection.rollback()
                    error_count += len(batch)
                    logger.error(f"❌ 插入批次 {i//batch_size + 1} 失败: {e}")

                    # 如果是重复键错误，尝试逐条插入
                    if 'Duplicate' in str(e):
                        logger.info("🔄 尝试逐条插入...")
                        for item in batch:
                            try:
                                self.cursor.execute(insert_query, item)
                                self.connection.commit()
                                success_count += 1
                            except Exception as e2:
                                if 'Duplicate' in str(e2):
                                    logger.warning(f"⚠️ 跳过重复记录: {item[0]}")
                                else:
                                    logger.error(f"❌ 插入记录失败: {item[0]}, 错误: {e2}")
                                    error_count += 1

            return success_count, error_count

        except Exception as e:
            logger.error(f"❌ 插入数据失败: {e}")
            self.connection.rollback()
            return success_count, error_count

    def verify_specific_data(self, timestamps):
        """验证特定时间戳的数据"""
        try:
            results = []
            for ts in timestamps:
                query = f"""
                SELECT UpdateDateTime, PointValue 
                FROM `{self.target_table}` 
                WHERE UpdateDateTime = %s
                """
                self.cursor.execute(query, (ts,))
                result = self.cursor.fetchone()

                if result:
                    results.append((ts, result[1]))
                    logger.info(f"✅ 找到数据: {result[0]} -> {result[1]:.2f}")
                else:
                    logger.warning(f"⚠️ 未找到时间戳 {ts} 的数据")
                    results.append((ts, None))

            return results

        except Exception as e:
            logger.error(f"❌ 验证数据失败: {e}")
            return []

    def run_full_import(self):
        """运行完整导入模式"""
        logger.info("=" * 60)
        logger.info("开始完整数据导入 (AI22列)")
        logger.info("=" * 60)

        # 1. 连接数据库
        if not self.connect_to_mysql():
            return False

        try:
            # 2. 检查表是否存在
            if not self.check_table_exists(self.target_table):
                logger.error(f"❌ 目标表 '{self.target_table}' 不存在，无法继续")
                return False

            # 3. 获取表结构
            self.get_table_structure(self.target_table)

            # 4. 先分析Excel结构
            logger.info("🔍 先分析Excel文件结构...")
            sample_data = self.analyze_excel_structure()

            if sample_data is None:
                logger.error("❌ Excel文件结构分析失败")
                return False

            # 5. 读取Excel数据（完整模式）
            df = self.read_excel_data_intelligently()

            if df.empty:
                logger.error("❌ Excel数据读取失败或数据为空")
                return False

            # 6. 插入数据到MySQL
            logger.info("🔄 开始插入数据到MySQL...")
            success_count, error_count = self.insert_data_to_mysql_safely(df, batch_size=500)

            logger.info("=" * 60)
            logger.info("📊 最终插入结果:")
            logger.info(f"  ✅ 成功插入: {success_count} 行")
            logger.info(f"  ❌ 插入失败: {error_count} 行")
            if success_count + error_count > 0:
                logger.info(f"  📈 成功率: {success_count/(success_count+error_count)*100:.1f}%")
            logger.info("=" * 60)

            if success_count > 0:
                # 7. 验证数据
                logger.info("🔍 验证插入的数据...")

                # 验证样本数据
                sample_timestamps = df['timestamp'].head(5).tolist()
                self.verify_specific_data(sample_timestamps)

                # 查看总体统计
                query = f"""
                SELECT 
                    COUNT(*) as total_count,
                    MIN(UpdateDateTime) as earliest,
                    MAX(UpdateDateTime) as latest,
                    AVG(PointValue) as avg_value,
                    MIN(PointValue) as min_value,
                    MAX(PointValue) as max_value
                FROM `{self.target_table}`
                """
                self.cursor.execute(query)
                stats = self.cursor.fetchone()

                logger.info("📊 表统计信息:")
                logger.info(f"  - 总记录数: {stats[0]}")
                logger.info(f"  - 最早时间: {stats[1]}")
                logger.info(f"  - 最晚时间: {stats[2]}")
                logger.info(f"  - 平均值: {stats[3]:.2f}")
                logger.info(f"  - 最小值: {stats[4]:.2f}")
                logger.info(f"  - 最大值: {stats[5]:.2f}")

                return True
            else:
                logger.error("❌ 没有数据成功插入")
                return False

        except Exception as e:
            logger.error(f"❌ 导入过程中发生错误: {e}", exc_info=True)
            return False
        finally:
            self.disconnect_from_mysql()


def main():
    """主函数 - 直接运行完整导入"""
    importer = ExcelToMySQLImporterFixed()

    print("=" * 60)
    print("Excel数据导入MySQL工具 - AI22列数据完整导入")
    print("=" * 60)
    print("注意：此程序将直接导入所有数据，不进行测试！")

    # 直接运行完整导入
    success = importer.run_full_import()
    if success:
        print("\n✅ 完整导入成功！")
    else:
        print("\n❌ 完整导入失败，请检查错误信息。")

    print("\n程序执行完毕。")
    print("=" * 60)


if __name__ == "__main__":
    main()