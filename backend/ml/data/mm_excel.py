"""
Excel数据导入MySQL工具 - 多表批量导入（支持多文件）
支持通过字典配置一次插入多个表
支持读取同级目录下多个相同结构的Excel文件
"""

import pandas as pd
import numpy as np
import pymysql
from datetime import datetime, timedelta
import os
import glob
import logging
import warnings
import re

warnings.filterwarnings('ignore')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExcelToMySQLMultiImporter:
    """Excel数据导入MySQL工具类 - 支持多表批量导入和多文件读取"""

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

        # Excel文件路径（可以是单个文件、文件夹或通配符模式）
        # 选项1: 单个文件
        # self.excel_file_pattern = r"D:\桌面\智慧暖通AI预测系统\训练数据\7月份数据主机数据.xlsx"

        # 选项2: 文件夹路径（读取该文件夹下所有.xlsx文件）
        # self.excel_file_pattern = r"D:\桌面\智慧暖通AI预测系统\训练数据\*.xlsx"

        # 选项3: 特定模式的文件（如所有月份的主机数据）
        # self.excel_file_pattern = r"D:\桌面\智慧暖通AI预测系统\训练数据\*月份数据主机数据.xlsx"

        # 选项4: 读取冷却塔数据
        self.excel_file_pattern = r"D:\桌面\智慧暖通AI预测系统\训练数据\*月份数据冷却塔数据.xlsx"

        # 选项4: 读取水泵数据
        # self.excel_file_pattern = r"D:\桌面\智慧暖通AI预测系统\训练数据\*月份数据水泵数据.xlsx"

        # 是否递归搜索子目录
        self.recursive_search = False

        # 文件扩展名过滤
        self.file_extensions = ['.xlsx', '.xls']

        # 列与表的映射关系
        # 格式：{excel列名：数据表名}
        self.column_table_mapping = {
            # '系统散热量':'composite_system_heat_dissipation',
            '冷却水温差': 'composite_cooling_water_temp_diff',
            '冷却泵流量': 'composite_cooling_pump_flow',
            # '':'',
            # 可以根据需要添加更多映射
        }

        # 连接对象
        self.connection = None
        self.cursor = None

        # 存储找到的所有Excel文件
        self.excel_files = []

    def get_excel_files(self):
        """获取所有符合条件的Excel文件"""
        try:
            # 清空文件列表
            self.excel_files = []

            # 如果传入的是文件夹路径
            if os.path.isdir(self.excel_file_pattern):
                folder_path = self.excel_file_pattern
                for ext in self.file_extensions:
                    pattern = os.path.join(folder_path, f"*{ext}")
                    files = glob.glob(pattern, recursive=self.recursive_search)
                    self.excel_files.extend(files)

            # 如果传入的是通配符模式
            elif '*' in self.excel_file_pattern:
                files = glob.glob(self.excel_file_pattern, recursive=self.recursive_search)
                self.excel_files.extend(files)

            # 如果传入的是单个文件路径
            elif os.path.isfile(self.excel_file_pattern):
                self.excel_files.append(self.excel_file_pattern)

            # 去除重复的文件路径
            self.excel_files = list(set(self.excel_files))

            # 过滤出存在的文件
            self.excel_files = [f for f in self.excel_files if os.path.exists(f)]

            # 按文件名排序
            self.excel_files.sort()

            if not self.excel_files:
                logger.warning(f"⚠️ 没有找到符合条件的Excel文件: {self.excel_file_pattern}")
                return False

            logger.info(f"📁 找到 {len(self.excel_files)} 个Excel文件:")
            for i, file_path in enumerate(self.excel_files, 1):
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
                logger.info(f"  {i}. {file_name} ({file_size:.2f} MB)")

            return True

        except Exception as e:
            logger.error(f"❌ 获取Excel文件失败: {e}")
            return False

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
                    logger.info(
                        f"  - 索引名: {idx[2]}, 列: {idx[4]}, 类型: {'主键' if idx[2] == 'PRIMARY' else '唯一索引'}")

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

    def find_time_column(self, df_columns):
        """查找时间列"""
        for col in df_columns:
            col_str = str(col)
            if any(keyword in col_str for keyword in ['时间', 'Time', 'TIMESTAMP', 'timestamp', '日期', 'DateTime']):
                logger.info(f"🔍 找到时间列: '{col_str}'")
                return col

        # 如果没有找到时间相关列，尝试第一列
        logger.warning(f"⚠️ 未找到时间列，使用第一列作为时间列: '{df_columns[0]}'")
        return df_columns[0]

    def find_target_columns(self, df_columns):
        """查找所有目标数据列"""
        found_columns = []

        # 首先尝试精确匹配
        for target_col in self.column_table_mapping.keys():
            for excel_col in df_columns:
                if str(excel_col).strip() == str(target_col).strip():
                    found_columns.append((excel_col, target_col))
                    logger.info(f"✅ 精确匹配到列: Excel列 '{excel_col}' -> 目标列 '{target_col}'")
                    break

        # 如果没有精确匹配，尝试模糊匹配
        if len(found_columns) < len(self.column_table_mapping):
            for target_col in self.column_table_mapping.keys():
                if target_col not in [fc[1] for fc in found_columns]:
                    for excel_col in df_columns:
                        excel_col_str = str(excel_col).upper()
                        target_col_str = str(target_col).upper()

                        # 模糊匹配逻辑
                        matched = False

                        # 情况1: 完全相等（去除空格）
                        if excel_col_str.replace(' ', '') == target_col_str.replace(' ', ''):
                            matched = True

                        # 情况2: 完全相等（去除空格和特殊字符）
                        elif (excel_col_str.replace('-', '').replace('_', '').replace(' ', '') ==
                              target_col_str.replace('-', '').replace('_', '').replace(' ', '')):
                            matched = True

                        # 情况3: 目标列是Excel列的子串，但需要确保后面不是数字
                        elif target_col_str in excel_col_str:
                            # 找到目标列在Excel列中的位置
                            index = excel_col_str.find(target_col_str)
                            # 检查目标列后面的字符
                            next_char_index = index + len(target_col_str)
                            # 如果后面还有字符且是数字，则跳过
                            if next_char_index < len(excel_col_str):
                                next_char = excel_col_str[next_char_index]
                                if next_char.isdigit():
                                    continue  # 跳过这种情况，避免AI23匹配AI231
                            matched = True

                        # 情况4: Excel列是目标列的子串，但需要确保后面不是数字
                        elif excel_col_str in target_col_str:
                            # 找到Excel列在目标列中的位置
                            index = target_col_str.find(excel_col_str)
                            # 检查Excel列后面的字符
                            next_char_index = index + len(excel_col_str)
                            # 如果后面还有字符且是数字，则跳过
                            if next_char_index < len(target_col_str):
                                next_char = target_col_str[next_char_index]
                                if next_char.isdigit():
                                    continue  # 跳过这种情况
                            matched = True

                        if matched:
                            found_columns.append((excel_col, target_col))
                            logger.info(f"✅ 模糊匹配到列: Excel列 '{excel_col}' -> 目标列 '{target_col}'")
                            break

        # 检查是否有未找到的列
        missing_columns = set(self.column_table_mapping.keys()) - set([fc[1] for fc in found_columns])
        if missing_columns:
            logger.warning(f"⚠️ 以下目标列在Excel中未找到: {missing_columns}")
            logger.info("📋 Excel中的可用列:")
            for i, col in enumerate(df_columns):
                logger.info(f"  列{i + 1}: '{col}'")

        return found_columns

    def analyze_excel_structure(self, file_path):
        """分析单个Excel文件结构"""
        try:
            if not os.path.exists(file_path):
                logger.error(f"❌ Excel文件不存在: {file_path}")
                return None

            file_name = os.path.basename(file_path)
            logger.info(f"🔍 分析Excel文件结构: {file_name}")

            # 读取前几行来了解数据结构
            df = pd.read_excel(file_path, nrows=20)

            logger.info(f"📋 文件 '{file_name}' 形状: {df.shape}")
            logger.info(f"📋 所有列名列表:")
            for i, col in enumerate(df.columns):
                logger.info(f"  列{i + 1}: '{col}'")

            # 查找时间列
            time_column = self.find_time_column(df.columns)

            # 查找目标数据列
            found_columns = self.find_target_columns(df.columns)

            if found_columns:
                logger.info(f"🎯 在 '{file_name}' 中找到 {len(found_columns)} 个目标列:")
                for excel_col, target_col in found_columns:
                    logger.info(
                        f"  - Excel列 '{excel_col}' -> 目标列 '{target_col}' -> 表 '{self.column_table_mapping[target_col]}'")

                    # 检查该列的数据
                    non_null_count = df[excel_col].count()
                    unique_count = df[excel_col].nunique()
                    logger.info(f"    📊 统计: 非空值: {non_null_count}, 唯一值: {unique_count}")

            return df.head(5)

        except Exception as e:
            logger.error(f"❌ 分析Excel文件 '{file_path}' 失败: {e}", exc_info=True)
            return None

    def read_excel_data_for_multi_tables(self):
        """为多表读取所有Excel文件数据"""
        try:
            # 获取所有Excel文件
            if not self.get_excel_files():
                return {}

            logger.info(f"📖 开始读取 {len(self.excel_files)} 个Excel文件...")

            # 初始化数据字典，用于存储所有文件的数据
            # 结构: {表名: DataFrame}
            all_data_for_tables = {}

            for file_idx, file_path in enumerate(self.excel_files, 1):
                file_name = os.path.basename(file_path)
                logger.info(f"📄 正在处理文件 ({file_idx}/{len(self.excel_files)}): {file_name}")

                try:
                    # 1. 读取整个文件
                    df = pd.read_excel(file_path, engine='openpyxl')
                    logger.info(f"  📊 读取到原始数据: {df.shape[0]} 行, {df.shape[1]} 列")

                    # 2. 查找时间列
                    time_col = self.find_time_column(df.columns)

                    # 3. 查找目标数据列
                    found_columns = self.find_target_columns(df.columns)

                    if not found_columns:
                        logger.warning(f"  ⚠️ 文件 '{file_name}' 中未找到任何目标数据列，跳过此文件")
                        continue

                    # 4. 为每个目标列准备数据
                    for excel_col, target_col in found_columns:
                        table_name = self.column_table_mapping[target_col]

                        logger.info(f"  🔧 处理列 '{excel_col}' -> 表 '{table_name}'")

                        # 提取需要的列
                        df_table = df[[time_col, excel_col]].copy()
                        df_table = df_table.rename(columns={time_col: 'timestamp', excel_col: 'value'})

                        # 处理时间戳
                        df_table['timestamp'] = pd.to_datetime(df_table['timestamp'], errors='coerce')

                        # 处理数值
                        df_table['value'] = pd.to_numeric(df_table['value'], errors='coerce')
                        df_table['value'] = df_table['value'].round(2)

                        # 删除完全为NaN的行
                        original_count = len(df_table)
                        df_table = df_table.dropna(subset=['timestamp', 'value'])
                        cleaned_count = len(df_table)
                        logger.info(f"    清理后数据: {cleaned_count} 行 (删除了 {original_count - cleaned_count} 行)")

                        if len(df_table) == 0:
                            logger.warning(f"    ⚠️ 清理后数据为空，跳过此列")
                            continue

                        # 检查时间戳重复情况
                        duplicate_count = df_table['timestamp'].duplicated().sum()

                        if duplicate_count > 0:
                            logger.warning(f"    ⚠️ 发现 {duplicate_count} 个重复时间戳")

                            # 对于重复的时间戳，取平均值
                            df_table = df_table.groupby('timestamp')['value'].mean().reset_index()
                            df_table['value'] = df_table['value'].round(2)
                            logger.info(f"    📊 去重后数据: {len(df_table)} 行")

                        # 格式转换
                        df_table['timestamp'] = df_table['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

                        # 添加文件名信息（可选）
                        df_table['source_file'] = file_name

                        # 数据统计
                        logger.info(f"    ✅ 成功处理 {len(df_table)} 行数据")
                        if len(df_table) > 0:
                            logger.info(
                                f"    📊 数值范围: {df_table['value'].min():.2f} ~ {df_table['value'].max():.2f}")
                            logger.info(f"    📊 平均值: {df_table['value'].mean():.2f}")

                        # 将当前文件的数据添加到总数据中
                        if table_name not in all_data_for_tables:
                            all_data_for_tables[table_name] = df_table
                        else:
                            # 合并数据
                            all_data_for_tables[table_name] = pd.concat(
                                [all_data_for_tables[table_name], df_table],
                                ignore_index=True
                            )

                except Exception as e:
                    logger.error(f"❌ 处理文件 '{file_name}' 失败: {e}", exc_info=True)
                    continue

            # 5. 对所有表的数据进行最终处理（去重、排序）
            logger.info("🔄 对所有表的数据进行最终处理...")
            for table_name in list(all_data_for_tables.keys()):
                df_table = all_data_for_tables[table_name]

                if df_table.empty:
                    del all_data_for_tables[table_name]
                    continue

                # 按时间戳排序
                df_table = df_table.sort_values('timestamp')

                # 最终去重（如果有跨文件的重复）
                original_count = len(df_table)
                df_table = df_table.drop_duplicates(subset=['timestamp'])
                if original_count != len(df_table):
                    logger.info(f"📊 表 '{table_name}' 跨文件去重: {original_count} -> {len(df_table)} 行")

                # 重置索引
                df_table = df_table.reset_index(drop=True)
                all_data_for_tables[table_name] = df_table

                logger.info(f"📊 表 '{table_name}' 最终数据量: {len(df_table)} 行")
                if len(df_table) > 0:
                    logger.info(
                        f"📊 表 '{table_name}' 时间范围: {df_table['timestamp'].min()} 至 {df_table['timestamp'].max()}")

            return all_data_for_tables

        except Exception as e:
            logger.error(f"❌ 读取Excel文件失败: {e}", exc_info=True)
            return {}

    def insert_data_to_table(self, table_name: str, df: pd.DataFrame, batch_size: int = 100):
        """将数据插入到指定表中"""
        if df.empty:
            logger.warning(f"⚠️ 表 '{table_name}' 没有数据需要插入")
            return 0, 0

        success_count = 0
        error_count = 0

        try:
            # 检查表是否有唯一索引
            check_index_query = f"""
            SHOW INDEX FROM `{table_name}` 
            WHERE Key_name = 'PRIMARY' OR Non_unique = 0
            """
            self.cursor.execute(check_index_query)
            indexes = self.cursor.fetchall()

            has_unique_index = False
            for idx in indexes:
                if idx[2] == 'PRIMARY' or idx[1] == 0:
                    has_unique_index = True
                    logger.warning(f"⚠️ 表 '{table_name}' 有{'主键' if idx[2] == 'PRIMARY' else '唯一索引'}: {idx[4]}")

            if has_unique_index:
                logger.info(f"🔄 检测到表 '{table_name}' 有唯一约束，将使用REPLACE INTO语句")
                insert_query = f"""
                REPLACE INTO `{table_name}` (UpdateDateTime, PointValue)
                VALUES (%s, %s)
                """
            else:
                logger.info(f"🔄 表 '{table_name}' 无唯一约束，将使用INSERT IGNORE语句")
                insert_query = f"""
                INSERT IGNORE INTO `{table_name}` (UpdateDateTime, PointValue)
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
            logger.info(f"📤 准备插入 {total_rows} 行数据到表 '{table_name}'")

            for i in range(0, total_rows, batch_size):
                batch = data_to_insert[i:i + batch_size]
                try:
                    self.cursor.executemany(insert_query, batch)
                    self.connection.commit()
                    success_count += len(batch)
                    logger.info(f"✅ 表 '{table_name}' 成功插入批次 {i // batch_size + 1}: {len(batch)} 行")
                except Exception as e:
                    self.connection.rollback()
                    error_count += len(batch)
                    logger.error(f"❌ 表 '{table_name}' 插入批次 {i // batch_size + 1} 失败: {e}")

                    # 如果是重复键错误，尝试逐条插入
                    if 'Duplicate' in str(e):
                        logger.info(f"🔄 表 '{table_name}' 尝试逐条插入...")
                        for item in batch:
                            try:
                                self.cursor.execute(insert_query, item)
                                self.connection.commit()
                                success_count += 1
                            except Exception as e2:
                                if 'Duplicate' in str(e2):
                                    logger.warning(f"⚠️ 表 '{table_name}' 跳过重复记录: {item[0]}")
                                else:
                                    logger.error(f"❌ 表 '{table_name}' 插入记录失败: {item[0]}, 错误: {e2}")
                                    error_count += 1

            return success_count, error_count

        except Exception as e:
            logger.error(f"❌ 表 '{table_name}' 插入数据失败: {e}")
            self.connection.rollback()
            return success_count, error_count

    def verify_table_data(self, table_name: str, timestamps):
        """验证特定表的数据"""
        try:
            results = []
            for ts in timestamps:
                query = f"""
                SELECT UpdateDateTime, PointValue 
                FROM `{table_name}` 
                WHERE UpdateDateTime = %s
                """
                self.cursor.execute(query, (ts,))
                result = self.cursor.fetchone()

                if result:
                    results.append((ts, result[1]))
                    logger.info(f"✅ 表 '{table_name}' 找到数据: {result[0]} -> {result[1]:.2f}")
                else:
                    logger.warning(f"⚠️ 表 '{table_name}' 未找到时间戳 {ts} 的数据")
                    results.append((ts, None))

            return results

        except Exception as e:
            logger.error(f"❌ 表 '{table_name}' 验证数据失败: {e}")
            return []

    def analyze_all_excel_files(self):
        """分析所有Excel文件的结构"""
        logger.info("🔍 开始分析所有Excel文件结构...")

        if not self.get_excel_files():
            return False

        all_files_info = {}

        for file_path in self.excel_files:
            file_name = os.path.basename(file_path)
            logger.info(f"📋 分析文件: {file_name}")

            try:
                # 读取前几行
                df = pd.read_excel(file_path, nrows=5)
                columns = list(df.columns)

                all_files_info[file_name] = {
                    'path': file_path,
                    'columns': columns,
                    'shape': df.shape,
                    'sample': df.head(3)
                }

                logger.info(f"  📊 列数: {len(columns)}")
                logger.info(f"  📊 前5列: {columns[:5]}")

            except Exception as e:
                logger.error(f"❌ 读取文件 '{file_name}' 失败: {e}")
                all_files_info[file_name] = {'error': str(e)}

        return all_files_info

    def run_multi_table_import(self):
        """运行多表导入模式"""
        logger.info("=" * 60)
        logger.info("开始多表批量数据导入（多文件模式）")
        logger.info("=" * 60)

        logger.info("📋 配置的列表映射:")
        for excel_col, table_name in self.column_table_mapping.items():
            logger.info(f"  - Excel列 '{excel_col}' -> 表 '{table_name}'")

        # 1. 连接数据库
        if not self.connect_to_mysql():
            return False

        try:
            # 2. 检查所有表是否存在
            all_tables_exist = True
            for table_name in self.column_table_mapping.values():
                if not self.check_table_exists(table_name):
                    all_tables_exist = False
                    logger.error(f"❌ 目标表 '{table_name}' 不存在，无法继续")

            if not all_tables_exist:
                return False

            # 3. 可选：先分析所有Excel文件结构
            logger.info("🔍 分析所有Excel文件结构...")
            files_info = self.analyze_all_excel_files()

            if not files_info:
                logger.error("❌ 没有找到可用的Excel文件")
                return False

            # 4. 读取所有Excel数据（多文件多表模式）
            data_for_tables = self.read_excel_data_for_multi_tables()

            if not data_for_tables:
                logger.error("❌ Excel数据读取失败或数据为空")
                return False

            # 5. 插入数据到各个MySQL表
            logger.info("🔄 开始批量插入数据到MySQL...")

            total_results = {}

            for table_name, df in data_for_tables.items():
                logger.info(f"📤 处理表: '{table_name}'")
                success_count, error_count = self.insert_data_to_table(table_name, df, batch_size=500)
                total_results[table_name] = (success_count, error_count)

                logger.info(f"  📊 表 '{table_name}' 插入结果:")
                logger.info(f"    ✅ 成功插入: {success_count} 行")
                logger.info(f"    ❌ 插入失败: {error_count} 行")
                if success_count + error_count > 0:
                    success_rate = success_count / (success_count + error_count) * 100 if (
                                                                                                  success_count + error_count) > 0 else 0
                    logger.info(f"    📈 成功率: {success_rate:.1f}%")

            # 6. 汇总结果
            logger.info("=" * 60)
            logger.info("📊 批量导入汇总结果:")

            total_success = 0
            total_error = 0

            for table_name, (success, error) in total_results.items():
                total_success += success
                total_error += error
                logger.info(f"  - 表 '{table_name}': ✅ {success} 行, ❌ {error} 行")

            logger.info(f"📊 总计: ✅ {total_success} 行, ❌ {total_error} 行")
            if total_success + total_error > 0:
                total_success_rate = total_success / (total_success + total_error) * 100
                logger.info(f"📊 总成功率: {total_success_rate:.1f}%")
            logger.info("=" * 60)

            if total_success > 0:
                # 7. 验证数据
                logger.info("🔍 验证插入的数据...")

                for table_name, df in data_for_tables.items():
                    if df.empty:
                        continue

                    # 验证样本数据
                    sample_timestamps = df['timestamp'].head(3).tolist()
                    self.verify_table_data(table_name, sample_timestamps)

                    # 查看表统计
                    query = f"""
                    SELECT 
                        COUNT(*) as total_count,
                        MIN(UpdateDateTime) as earliest,
                        MAX(UpdateDateTime) as latest,
                        AVG(PointValue) as avg_value,
                        MIN(PointValue) as min_value,
                        MAX(PointValue) as max_value
                    FROM `{table_name}`
                    """
                    self.cursor.execute(query)
                    stats = self.cursor.fetchone()

                    logger.info(f"📊 表 '{table_name}' 统计信息:")
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
    """主函数 - 运行多表批量导入"""
    importer = ExcelToMySQLMultiImporter()

    print("=" * 60)
    print("Excel数据导入MySQL工具 - 多表批量导入（多文件模式）")
    print("=" * 60)
    print(f"文件匹配模式: {importer.excel_file_pattern}")
    print("\n当前配置的列表映射:")

    for excel_col, table_name in importer.column_table_mapping.items():
        print(f"  - Excel列 '{excel_col}' -> 表 '{table_name}'")

    print("\n注意：此程序将批量导入所有匹配文件中的所有配置表中的数据！")
    print("=" * 60)

    # 确认是否继续
    response = input("\n是否开始导入? (y/n): ")
    if response.lower() != 'y':
        print("操作已取消。")
        return

    # 运行多表批量导入
    success = importer.run_multi_table_import()
    if success:
        print("\n✅ 多表批量导入成功！")
    else:
        print("\n❌ 多表批量导入失败，请检查错误信息。")

    print("\n程序执行完毕。")
    print("=" * 60)


if __name__ == "__main__":
    main()