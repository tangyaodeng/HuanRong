import os
import pandas as pd
import pymysql
from pymysql import Error
from datetime import datetime
import re
from typing import List, Tuple, Dict
import time
#设备4
# sfld	  zblcftemp	  hftemp  sftemp  xftemp   qblcftemp    zsjr1temp	zs1cftemp	 zsjs1value  	hfld	zs2cftemp	 zblvalue
#送风露点 中表冷出风温度 回风温度 送风温度 新风温度 前表冷出风温度 再生1加热温度 再生1出风温度 再生1加热开度值  回风露点 再生2出风温度 中表冷开度
#设备6
# hftemp   hfhumi	sftemp	sfhumi	xftemp	 qblcftemp     zsjr1temp  zs1cftemp    zsjs1value	 hblvalue
# 回风温度  回风湿度  送风温度 送风湿度 新风温度 前表冷出风温度 再生1加热温度 再生1出风温度 再生1加热开度值  后表冷开度

class ExcelToMySQLImporter:
    def __init__(self):
        # 数据库配置
        self.db_config = {
            'host': "192.168.5.100",
            'port': 3306,
            'user': "admin1",
            'password': "Jlk@123456",
            'database': "yinpai",
            'charset': "utf8mb4",
            'connect_timeout': 30  # 添加连接超时
        }

        # Excel文件目录
        self.excel_dir = r"D:\桌面\智慧暖通AI预测系统\一注4和正极搅拌6\正极搅拌6\2、再生加热温度再生出风温度再生加热开度后表冷开度"

        # 表名后缀映射
        self.column_table_mapping = {
            'hftemp': 'D6_hftemp',
            'hfhumi': 'D6_hfhumi',
            'sftemp': 'D6_sftemp',
            'sfhumi': 'D6_sfhumi',
            'xftemp': 'D6_xftemp',
            'qblcftemp': 'D6_qblcftemp',
            'zsjr1temp': 'D6_zsjr1temp',
            'zs1cftemp': 'D6_zs1cftemp',
            'zsjs1value': 'D6_zsjs1value',
            'hblvalue': 'D6_hblvalue',
        }

        # 目标列名（B2到G2可能包含的内容）
        self.target_columns = [
            'hftemp', 'hfhumi', 'sftemp', 'sfhumi', 'xftemp', 'qblcftemp',
            'zsjr1temp', 'zs1cftemp', 'zsjs1value', 'hblvalue'
        ]

    def get_matching_files(self) -> List[str]:
        """获取匹配的Excel文件列表"""
        matching_files = []

        try:
            if not os.path.exists(self.excel_dir):
                print(f"目录不存在: {self.excel_dir}")
                return matching_files

            for filename in os.listdir(self.excel_dir):
                if not filename.endswith('.xlsx'):
                    continue

                # 规则1: 包含特定字符串的文件
                if "送风露点中表冷出风温度回风温度送风温度新风温度前表冷温度" in filename:
                    matching_files.append(os.path.join(self.excel_dir, filename))

                # 规则2: 以"设备点位-"开头的文件
                elif filename.startswith("设备点位-") and filename.endswith(".xlsx"):
                    matching_files.append(os.path.join(self.excel_dir, filename))

            print(f"找到 {len(matching_files)} 个匹配的文件")
            return matching_files

        except Exception as e:
            print(f"获取文件列表时出错: {e}")
            return []

    def find_target_columns_in_header(self, df: pd.DataFrame, filepath: str) -> Dict[str, int]:
        """
        在表头行中查找目标列，返回列名到列索引的映射
        搜索范围：B2到G2（第2行，列B到G）
        """
        column_mapping = {}

        try:
            # 第2行（索引1）的B到G列（索引1-6）
            for col_idx in range(1, 7):  # B到G列
                if col_idx < len(df.columns):
                    cell_value = df.iat[1, col_idx]  # 第2行，列索引col_idx
                    if pd.notna(cell_value):
                        cell_value_str = str(cell_value).strip()

                        # 检查是否匹配任何目标列名
                        for target_col in self.target_columns:
                            if cell_value_str == target_col:
                                column_mapping[target_col] = col_idx
                                print(f"  找到列: {target_col} 在 列索引 {col_idx}")
                                break

            print(f"文件 {os.path.basename(filepath)} 找到的列: {list(column_mapping.keys())}")
            return column_mapping

        except Exception as e:
            print(f"查找表头列时出错: {e}")
            return {}

    def process_excel_file(self, filepath: str) -> bool:
        """处理单个Excel文件"""
        try:
            print(f"\n正在处理文件: {os.path.basename(filepath)}")

            # 读取Excel文件（不自动识别表头）
            df = pd.read_excel(filepath, header=None, engine='openpyxl')

            if df.empty:
                print("Excel文件为空")
                return False

            # 查找目标列
            column_mapping = self.find_target_columns_in_header(df, filepath)

            if not column_mapping:
                print("未找到任何目标列，跳过此文件")
                return False

            # 获取时间戳列（A列，索引0）
            data_rows = []
            for row_idx in range(3, len(df)):  # 从第4行开始（索引3）
                timestamp = df.iat[row_idx, 0]

                # 跳过时间戳为空的行
                if pd.isna(timestamp):
                    continue

                # 处理时间戳
                try:
                    if isinstance(timestamp, (int, float)):
                        # 如果是Excel日期序列号，转换为datetime
                        timestamp = pd.Timestamp('1899-12-30') + pd.Timedelta(days=timestamp)
                    elif isinstance(timestamp, str):
                        # 如果是字符串，尝试解析
                        timestamp = pd.to_datetime(timestamp)

                    # 确保是datetime类型
                    if not isinstance(timestamp, pd.Timestamp):
                        continue

                except Exception as e:
                    print(f"时间戳解析失败 (行{row_idx + 1}): {timestamp}, 错误: {e}")
                    continue

                # 收集数据
                row_data = {'timestamp': timestamp}
                for col_name, col_idx in column_mapping.items():
                    if col_idx < len(df.columns):
                        value = df.iat[row_idx, col_idx]
                        # 如果值为空，设置为0
                        row_data[col_name] = float(value) if pd.notna(value) else 0.0
                    else:
                        row_data[col_name] = 0.0

                data_rows.append(row_data)

            print(f"读取到 {len(data_rows)} 行数据")

            if not data_rows:
                print("没有有效数据")
                return False

            # 插入数据库
            return self.insert_to_database(data_rows, column_mapping)

        except Exception as e:
            print(f"处理文件 {filepath} 时出错: {e}")
            return False

    def test_database_connection(self) -> bool:
        """测试数据库连接"""
        try:
            print("测试数据库连接...")
            connection = pymysql.connect(**self.db_config)
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            print("数据库连接测试成功")
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False

    def insert_to_database(self, data_rows: List[Dict], column_mapping: Dict[str, int]) -> bool:
        """将数据插入数据库"""
        connection = None
        cursor = None

        try:
            print("开始连接数据库...")
            start_time = time.time()

            # 连接数据库
            connection = pymysql.connect(**self.db_config)
            cursor = connection.cursor()

            print(f"数据库连接成功，耗时: {time.time() - start_time:.2f}秒")

            total_inserted = 0
            batch_size = 100  # 每批插入100条记录

            print(f"开始插入数据，共{len(data_rows)}行，{len(column_mapping)}列...")
            insert_start_time = time.time()

            # 使用批量插入优化性能
            for i, row_data in enumerate(data_rows):
                timestamp = row_data['timestamp']

                # 只插入在column_mapping中存在的列
                for col_name in column_mapping.keys():
                    if col_name in row_data:
                        table_name = f"D6_{col_name}"
                        value = row_data[col_name]

                        # 插入数据
                        insert_sql = f"""
                            INSERT INTO `{table_name}` (UpdateDateTime, PointValue)
                            VALUES (%s, %s)
                        """

                        try:
                            cursor.execute(insert_sql, (timestamp, value))
                            total_inserted += 1

                            # 每批提交一次
                            if total_inserted % batch_size == 0:
                                connection.commit()
                                print(f"  已插入 {total_inserted} 条记录...")

                        except Error as e:
                            print(f"插入数据到表 {table_name} 时出错: {e}")
                            # 继续处理其他数据
                            continue

                # 显示进度
                if (i + 1) % 100 == 0:
                    elapsed_time = time.time() - insert_start_time
                    print(f"  处理进度: {i + 1}/{len(data_rows)} 行，耗时: {elapsed_time:.2f}秒")

            # 提交剩余的数据
            connection.commit()

            total_time = time.time() - insert_start_time
            print(f"成功插入 {total_inserted} 条记录，耗时: {total_time:.2f}秒")
            print(f"平均速度: {total_inserted / total_time:.2f} 条/秒")

            return True

        except Error as e:
            print(f"数据库连接或操作失败: {e}")
            if connection:
                connection.rollback()
            return False

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def create_tables_if_not_exist(self):
        """创建表（如果不存在）"""
        connection = None
        cursor = None

        try:
            print("创建或检查表结构...")
            connection = pymysql.connect(**self.db_config)
            cursor = connection.cursor()

            create_table_sqls = [
                """
                CREATE TABLE IF NOT EXISTS `D6_sfld`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_zblcftemp`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_hftemp`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_sftemp`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_xftemp`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_qblcftemp`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_zsjr1temp`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_zs1cftemp`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_zsjs1value`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_hfld`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_zs2cftemp`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """,
                """
                CREATE TABLE IF NOT EXISTS `D6_zblvalue`(
                    `UpdateDateTime` datetime DEFAULT NULL,
                    `PointValue` float DEFAULT NULL
                ) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci;
                """
            ]

            for i, sql in enumerate(create_table_sqls):
                cursor.execute(sql)
                print(f"  创建表 {i + 1}/{len(create_table_sqls)}...")

            connection.commit()
            print("所有表已创建或已存在")

        except Error as e:
            print(f"创建表时出错: {e}")

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def run(self):
        """运行导入程序"""
        print("开始导入Excel数据到MySQL数据库")
        print("=" * 50)

        # 测试数据库连接
        if not self.test_database_connection():
            print("数据库连接测试失败，请检查网络和数据库配置")
            return

        # 创建表（如果不存在）
        self.create_tables_if_not_exist()

        # 获取匹配的Excel文件
        excel_files = self.get_matching_files()

        if not excel_files:
            print("没有找到匹配的Excel文件")
            return

        # 处理每个Excel文件
        success_count = 0
        total_start_time = time.time()

        for filepath in excel_files:
            file_start_time = time.time()
            print(f"\n开始处理文件: {os.path.basename(filepath)}")

            if self.process_excel_file(filepath):
                success_count += 1
                file_time = time.time() - file_start_time
                print(f"文件处理完成，耗时: {file_time:.2f}秒")
            else:
                print(f"文件处理失败: {os.path.basename(filepath)}")

        total_time = time.time() - total_start_time
        print("\n" + "=" * 50)
        print(f"导入完成！成功处理 {success_count}/{len(excel_files)} 个文件")
        print(f"总耗时: {total_time:.2f}秒")


def main():
    """主函数"""
    # 安装所需库：
    # pip install pandas openpyxl pymysql

    importer = ExcelToMySQLImporter()
    importer.run()


if __name__ == "__main__":
    main()