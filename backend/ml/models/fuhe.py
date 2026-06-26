"""
冷量预测器 - 基于天气数据预测未来冷量（5分钟间隔）
backend/ml/models/cooling_predictor_5min.py
"""
import pickle
import numpy as np
import pandas as pd
import os
import sys
from typing import Dict, List, Tuple, Optional
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import xgboost as xgb

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CoolingCapacityPredictor5Min:
    """冷量预测器 - 基于5分钟间隔天气数据预测未来冷量"""

    def __init__(self):
        # MySQL数据库配置
        self.mysql_config = {
            'host': "192.168.5.100",
            'port': 3306,
            'user': "admin1",
            'password': "Jlk@123456",
            'database': "jh_hisdata",
            'charset': "utf8mb4"
        }

        # 天气特征表映射（5分钟间隔数据）
        self.weather_tables = {
            'outdoor_temperature': "dev-zlz-plc-ai21",
            'outdoor_humidity': "dev-zlz-plc-ai22",
            'wet_bulb_temperature': "dev-zlz-plc-ai23",
        }

        # 模型文件路径
        self.model_dir = os.path.join(os.path.dirname(__file__), "saved_models")
        self.cooling_model_pattern = "xgboost_device_15_instant_cooling_capacity"

        # 模型对象
        self.cooling_model = None
        self.model_feature_names = []
        self.model_info = {}

        # 数据库连接
        self.engine = None

        # 预测参数
        self.prediction_interval_minutes = 5  # 5分钟间隔
        self.predictions_per_hour = 12  # 每小时预测12次（5分钟*12=60分钟）

    def connect_database(self):
        """连接MySQL数据库"""
        try:
            encoded_password = quote_plus(self.mysql_config['password'])
            connection_string = (
                f"mysql+pymysql://{self.mysql_config['user']}:{encoded_password}"
                f"@{self.mysql_config['host']}:{self.mysql_config['port']}/{self.mysql_config['database']}"
                f"?charset={self.mysql_config['charset']}"
            )

            self.engine = create_engine(
                connection_string,
                pool_recycle=300,
                pool_pre_ping=True,
                echo=False
            )

            # 测试连接
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info("✅ 成功连接到MySQL数据库")
            return True

        except Exception as e:
            logger.error(f"❌ 连接数据库失败: {e}")
            return False

    def find_cooling_model(self):
        """查找冷量模型文件"""
        try:
            if not os.path.exists(self.model_dir):
                logger.error(f"❌ 模型目录不存在: {self.model_dir}")
                return None

            model_files = []
            for file in os.listdir(self.model_dir):
                if file.startswith(self.cooling_model_pattern) and file.endswith('.pkl'):
                    model_files.append(file)

            if not model_files:
                logger.error(f"❌ 未找到冷量模型文件")
                return None

            model_files.sort(reverse=True)
            latest_model = model_files[0]
            model_path = os.path.join(self.model_dir, latest_model)

            logger.info(f"✅ 找到冷量模型: {latest_model}")
            return model_path

        except Exception as e:
            logger.error(f"❌ 查找模型失败: {e}")
            return None

    def load_cooling_model(self):
        """加载冷量预测模型"""
        try:
            model_path = self.find_cooling_model()
            if not model_path:
                return False

            logger.info(f"加载冷量模型: {model_path}")
            with open(model_path, 'rb') as f:
                model_data = pickle.load(f)

            self.cooling_model = model_data['model']
            self.model_feature_names = model_data.get('feature_names', [])
            self.model_info = {
                'model_params': model_data.get('model_params', {}),
                'training_stats': model_data.get('training_stats', {}),
                'feature_importance': model_data.get('feature_importance', {}),
                'saved_at': model_data.get('saved_at', '未知时间')
            }

            logger.info(f"✅ 冷量模型加载成功")
            logger.info(f"  - 特征数: {len(self.model_feature_names)}")
            logger.info(f"  - 特征名: {self.model_feature_names}")
            logger.info(f"  - 模型保存时间: {self.model_info['saved_at']}")
            return True

        except Exception as e:
            logger.error(f"❌ 加载模型失败: {e}")
            return False

    def get_5min_weather_data(self, start_time: datetime, days: int = 3):
        """获取5分钟间隔的天气数据"""
        try:
            if self.engine is None:
                logger.warning("⚠️ 数据库未连接，使用模拟5分钟天气数据")
                return self.generate_5min_mock_weather_data(start_time, days)

            end_time = start_time + timedelta(days=days)

            weather_data = {}
            logger.info(f"📊 获取5分钟天气数据: {start_time} 到 {end_time}")

            for feature_name, table_name in self.weather_tables.items():
                try:
                    # 查询5分钟间隔数据（假设数据库中有足够细粒度的数据）
                    query = f"""
                    SELECT UpdateDateTime, PointValue
                    FROM `{table_name}`
                    WHERE UpdateDateTime >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'
                      AND UpdateDateTime < '{end_time.strftime('%Y-%m-%d %H:%M:%S')}'
                      AND MINUTE(UpdateDateTime) % 5 = 0  -- 5分钟间隔
                    ORDER BY UpdateDateTime
                    """

                    with self.engine.connect() as conn:
                        result = conn.execute(text(query))
                        rows = result.fetchall()

                    if rows:
                        timestamps = [row[0] for row in rows]
                        values = [float(row[1]) for row in rows]

                        weather_data[feature_name] = pd.Series(
                            values,
                            index=pd.DatetimeIndex(timestamps),
                            name=feature_name
                        )
                        logger.info(f"  {feature_name}: 获取到 {len(values)} 条5分钟数据")
                    else:
                        # 如果没有5分钟数据，尝试获取所有数据并重采样
                        logger.info(f"  {feature_name}: 尝试重采样到5分钟间隔")
                        weather_data[feature_name] = self.resample_to_5min(
                            table_name, start_time, end_time, feature_name
                        )

                except Exception as e:
                    logger.warning(f"获取 {feature_name} 5分钟数据失败: {e}")
                    continue

            # 检查数据完整性
            for feature_name in self.weather_tables.keys():
                if feature_name not in weather_data or weather_data[feature_name].empty:
                    logger.warning(f"  {feature_name}: 数据缺失，使用模拟数据")
                    if 'mock_data' not in locals():
                        mock_data = self.generate_5min_mock_weather_data(start_time, days)
                    weather_data[feature_name] = mock_data[feature_name]

            return weather_data

        except Exception as e:
            logger.error(f"❌ 获取5分钟天气数据失败: {e}")
            return self.generate_5min_mock_weather_data(start_time, days)

    def resample_to_5min(self, table_name: str, start_time: datetime, end_time: datetime, feature_name: str):
        """将数据重采样到5分钟间隔"""
        try:
            # 查询原始数据
            query = f"""
            SELECT UpdateDateTime, PointValue
            FROM `{table_name}`
            WHERE UpdateDateTime >= '{start_time.strftime('%Y-%m-%d %H:%M:%S')}'
              AND UpdateDateTime < '{end_time.strftime('%Y-%m-%d %H:%M:%S')}'
            ORDER BY UpdateDateTime
            """

            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                rows = result.fetchall()

            if not rows:
                return pd.Series([], index=pd.DatetimeIndex([]), name=feature_name)

            timestamps = [row[0] for row in rows]
            values = [float(row[1]) for row in rows]

            # 创建DataFrame并重采样
            df = pd.DataFrame({'value': values}, index=pd.DatetimeIndex(timestamps))

            # 重采样到5分钟，使用线性插值
            df_resampled = df.resample('5T').mean()
            df_resampled['value'] = df_resampled['value'].interpolate(method='linear')

            # 确保数据在时间范围内
            mask = (df_resampled.index >= start_time) & (df_resampled.index < end_time)
            df_resampled = df_resampled[mask]

            return pd.Series(
                df_resampled['value'].values,
                index=df_resampled.index,
                name=feature_name
            )

        except Exception as e:
            logger.error(f"重采样 {feature_name} 失败: {e}")
            return pd.Series([], index=pd.DatetimeIndex([]), name=feature_name)

    def generate_5min_mock_weather_data(self, start_time: datetime, days: int):
        """生成5分钟间隔的模拟天气数据"""
        logger.info(f"生成5分钟模拟天气数据: {start_time} 起 {days} 天")

        # 生成5分钟时间序列
        total_minutes = days * 24 * 60
        minutes_step = self.prediction_interval_minutes
        timestamps = [start_time + timedelta(minutes=i) for i in range(0, total_minutes, minutes_step)]

        weather_data = {}

        # 室外温度 - 使用正弦函数模拟日变化
        base_temp = 25.0
        daily_amplitude = 5.0

        # 生成5分钟间隔的温度数据
        temp_values = []
        for i, ts in enumerate(timestamps):
            # 计算从开始时间起的小时数
            hours_from_start = i * minutes_step / 60
            # 日变化 + 随机波动
            temp = base_temp + daily_amplitude * np.sin(2 * np.pi * hours_from_start / 24 - np.pi/2)
            temp += np.random.normal(0, 0.5)  # 随机波动
            temp_values.append(temp)

        weather_data['outdoor_temperature'] = pd.Series(
            temp_values,
            index=pd.DatetimeIndex(timestamps),
            name='outdoor_temperature'
        )

        # 室外湿度 - 与温度负相关
        humidity_values = []
        for temp in temp_values:
            humidity = 60 - (temp - 25) * 2 + np.random.normal(0, 3)
            humidity = max(30, min(90, humidity))  # 限制范围
            humidity_values.append(humidity)

        weather_data['outdoor_humidity'] = pd.Series(
            humidity_values,
            index=pd.DatetimeIndex(timestamps),
            name='outdoor_humidity'
        )

        # 湿球温度
        wet_bulb_values = []
        for temp, humidity in zip(temp_values, humidity_values):
            wet_bulb = temp - 5 - (humidity / 100) * 2 + np.random.normal(0, 0.3)
            wet_bulb_values.append(wet_bulb)

        weather_data['wet_bulb_temperature'] = pd.Series(
            wet_bulb_values,
            index=pd.DatetimeIndex(timestamps),
            name='wet_bulb_temperature'
        )

        logger.info(f"✅ 5分钟模拟天气数据生成完成，共 {len(timestamps)} 个数据点")
        return weather_data

    def prepare_prediction_features(self, weather_data: Dict, timestamp_index: int):
        """准备预测特征"""
        try:
            features = []

            # 按照模型的特征名称顺序准备特征
            for feature_name in self.model_feature_names:
                found = False

                # 匹配天气特征
                for weather_feature in weather_data.keys():
                    if weather_feature in feature_name or feature_name in weather_feature:
                        if timestamp_index < len(weather_data[weather_feature]):
                            features.append(weather_data[weather_feature].iloc[timestamp_index])
                            found = True
                            break

                if not found:
                    # 使用默认值
                    if 'temperature' in feature_name.lower():
                        default_val = 25.0
                    elif 'humidity' in feature_name.lower():
                        default_val = 60.0
                    elif 'wet' in feature_name.lower() or 'bulb' in feature_name.lower():
                        default_val = 20.0
                    else:
                        default_val = 0.0

                    features.append(default_val)

            features_array = np.array(features).reshape(1, -1)
            return features_array

        except Exception as e:
            logger.error(f"❌ 准备预测特征失败: {e}")
            return None

    def predict_5min_cooling(self, start_time: datetime, days: int = 3):
        """预测5分钟间隔的冷量"""
        try:
            # 获取5分钟天气数据
            weather_data = self.get_5min_weather_data(start_time, days)

            if not weather_data:
                logger.error("❌ 无法获取天气数据")
                return None

            # 确定数据点数量（所有特征的数据点数量应该相同）
            data_lengths = [len(weather_data[feat]) for feat in weather_data]
            if len(set(data_lengths)) > 1:
                logger.warning("⚠️ 天气特征数据长度不一致")

            # 使用最短的数据长度
            data_points = min(data_lengths)

            predictions = []
            timestamps = []

            logger.info(f"🔮 开始预测 {data_points} 个5分钟点的冷量...")

            for i in range(data_points):
                try:
                    # 准备特征
                    features_array = self.prepare_prediction_features(weather_data, i)

                    if features_array is None:
                        logger.warning(f"⚠️ 时间点 {i} 特征准备失败")
                        continue

                    # 预测
                    dmatrix = xgb.DMatrix(features_array, feature_names=self.model_feature_names)
                    prediction = self.cooling_model.predict(dmatrix)

                    # 记录结果
                    prediction_value = float(prediction[0])
                    predictions.append(prediction_value)

                    # 获取时间戳
                    if i < len(weather_data['outdoor_temperature']):
                        timestamps.append(weather_data['outdoor_temperature'].index[i])
                    else:
                        # 计算时间戳
                        minutes_offset = i * self.prediction_interval_minutes
                        timestamp = start_time + timedelta(minutes=minutes_offset)
                        timestamps.append(timestamp)

                    # 每60个点（5小时）打印一次进度
                    if i % 60 == 0 or i == data_points - 1:
                        timestamp_str = timestamps[-1].strftime('%m-%d %H:%M')
                        logger.info(f"  {timestamp_str}: {prediction_value:.2f} kW")

                except Exception as e:
                    logger.warning(f"时间点 {i} 预测失败: {e}")
                    predictions.append(0.0)
                    if i < len(timestamps):
                        timestamps.append(timestamps[-1] + timedelta(minutes=self.prediction_interval_minutes))
                    else:
                        timestamps.append(start_time + timedelta(minutes=i * self.prediction_interval_minutes))

            # 创建结果DataFrame
            result_df = pd.DataFrame({
                'timestamp': timestamps,
                'cooling_kw': predictions
            })

            logger.info(f"✅ 5分钟冷量预测完成，共 {len(predictions)} 个预测点")
            return result_df

        except Exception as e:
            logger.error(f"❌ 5分钟冷量预测失败: {e}")
            return None

    def calculate_hourly_average_from_5min(self, predictions_5min: pd.DataFrame):
        """从5分钟预测计算每小时平均冷量"""
        try:
            if predictions_5min is None or predictions_5min.empty:
                return None

            # 确保时间戳是datetime类型
            predictions_5min['timestamp'] = pd.to_datetime(predictions_5min['timestamp'])

            # 创建小时分组列（使用小时开始时间）
            predictions_5min['hour_group'] = predictions_5min['timestamp'].dt.floor('H')

            # 计算每小时的平均值
            hourly_avg = predictions_5min.groupby('hour_group')['cooling_kw'].agg(['mean', 'count']).reset_index()
            hourly_avg.columns = ['hour_start', 'avg_cooling_kw', 'data_points_count']

            # 只保留完整的小时（12个数据点）
            complete_hours = hourly_avg[hourly_avg['data_points_count'] >= self.predictions_per_hour].copy()

            logger.info(f"✅ 每小时平均冷量计算完成，共 {len(complete_hours)} 个完整小时")

            return complete_hours[['hour_start', 'avg_cooling_kw']]

        except Exception as e:
            logger.error(f"❌ 计算每小时平均冷量失败: {e}")
            return None

    def calculate_daily_cooling_from_hourly(self, hourly_avg_cooling: pd.DataFrame):
        """从每小时平均冷量计算每日冷量"""
        try:
            if hourly_avg_cooling is None or hourly_avg_cooling.empty:
                return None

            # 确保时间戳是datetime类型
            hourly_avg_cooling['hour_start'] = pd.to_datetime(hourly_avg_cooling['hour_start'])

            # 添加日期列
            hourly_avg_cooling['date'] = hourly_avg_cooling['hour_start'].dt.date

            # 按日期分组，将小时冷量相加（kW → kWh）
            daily_cooling = hourly_avg_cooling.groupby('date')['avg_cooling_kw'].sum().reset_index()
            daily_cooling.columns = ['date', 'daily_cooling_kwh']

            logger.info(f"✅ 每日冷量计算完成，共 {len(daily_cooling)} 天")
            return daily_cooling

        except Exception as e:
            logger.error(f"❌ 计算每日冷量失败: {e}")
            return None

    def predict_future_cooling_5min(self, start_time_str: str):
        """基于5分钟数据预测未来冷量"""
        try:
            # 解析开始时间
            try:
                start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M")
                # 调整到最近的5分钟
                minute = start_time.minute
                remainder = minute % 5
                if remainder != 0:
                    start_time = start_time - timedelta(minutes=remainder)
                    logger.info(f"调整开始时间到最近的5分钟: {start_time.strftime('%Y-%m-%d %H:%M')}")
            except Exception as e:
                logger.error(f"❌ 时间格式错误: {e}")
                return None

            logger.info(f"\n📅 基于5分钟数据的冷量预测")
            logger.info(f"预测开始时间: {start_time_str}")
            logger.info("=" * 60)

            # 1. 预测5分钟间隔冷量（3天）
            logger.info("🔮 步骤1: 预测5分钟间隔冷量")
            predictions_5min = self.predict_5min_cooling(start_time, days=3)

            if predictions_5min is None:
                logger.error("❌ 5分钟冷量预测失败")
                return None

            # 2. 计算每小时平均冷量
            logger.info("📊 步骤2: 计算每小时平均冷量")
            hourly_avg_df = self.calculate_hourly_average_from_5min(predictions_5min)

            # 3. 计算3天逐日冷量
            logger.info("📈 步骤3: 计算逐日冷量")
            daily_3day_df = self.calculate_daily_cooling_from_hourly(hourly_avg_df)

            # 4. 预测一周数据（如果需要）
            weekly_daily_df = None
            if daily_3day_df is not None and len(daily_3day_df) < 7:
                remaining_days = 7 - len(daily_3day_df)
                extra_start = start_time + timedelta(days=3)

                logger.info(f"📅 补充预测剩余 {remaining_days} 天")
                extra_predictions_5min = self.predict_5min_cooling(extra_start, remaining_days)

                if extra_predictions_5min is not None:
                    extra_hourly_avg = self.calculate_hourly_average_from_5min(extra_predictions_5min)
                    extra_daily = self.calculate_daily_cooling_from_hourly(extra_hourly_avg)

                    if extra_daily is not None:
                        weekly_daily_df = pd.concat([daily_3day_df, extra_daily], ignore_index=True)

            if weekly_daily_df is None:
                weekly_daily_df = daily_3day_df

            return {
                'start_time': start_time.strftime('%Y-%m-%d %H:%M'),
                '5min_predictions': predictions_5min,  # 5分钟预测
                'hourly_average_predictions': hourly_avg_df,  # 每小时平均
                'daily_3day_predictions': daily_3day_df,  # 3天逐日
                'weekly_daily_predictions': weekly_daily_df  # 一周逐日
            }

        except Exception as e:
            logger.error(f"❌ 未来冷量预测失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def print_5min_predictions_summary(self, results: Dict):
        """打印5分钟预测结果摘要"""
        if not results:
            logger.error("❌ 没有预测结果可展示")
            return

        print("\n" + "=" * 80)
        print("未来冷量预测结果 (基于5分钟数据)")
        print(f"预测开始时间: {results['start_time']}")
        print(f"预测间隔: {self.prediction_interval_minutes}分钟")
        print("=" * 80)

        # 打印5分钟数据摘要
        if results['5min_predictions'] is not None:
            df_5min = results['5min_predictions']
            print(f"\n📊 5分钟间隔预测摘要:")
            print(f"  总数据点: {len(df_5min)}")
            print(f"  时间范围: {df_5min['timestamp'].min()} 到 {df_5min['timestamp'].max()}")
            print(f"  平均冷量: {df_5min['cooling_kw'].mean():.2f} kW")
            print(f"  最大冷量: {df_5min['cooling_kw'].max():.2f} kW")
            print(f"  最小冷量: {df_5min['cooling_kw'].min():.2f} kW")

        # 打印每小时平均冷量（前24小时）
        if results['hourly_average_predictions'] is not None:
            print(f"\n📊 未来24小时每小时平均冷量:")
            print("-" * 60)
            print(f"{'时间':^20} {'平均冷量(kW)':^15} {'数据点数':^10}")
            print("-" * 60)

            df_hourly = results['hourly_average_predictions']
            for i in range(min(24, len(df_hourly))):
                hour_time = df_hourly['hour_start'].iloc[i]
                cooling = df_hourly['avg_cooling_kw'].iloc[i]
                print(f"{hour_time.strftime('%m-%d %H:%M'):^20} {cooling:^15.2f} {'12/12':^10}")
            print("-" * 60)

        # 打印3天逐日冷量
        if results['daily_3day_predictions'] is not None:
            print(f"\n📊 未来3天逐日冷量预测:")
            print("-" * 50)
            print(f"{'日期':^15} {'日冷量(kWh)':^15}")
            print("-" * 50)

            df_daily = results['daily_3day_predictions']
            for _, row in df_daily.iterrows():
                print(f"{row['date'].strftime('%Y-%m-%d'):^15} {row['daily_cooling_kwh']:^15.2f}")
            print("-" * 50)

        # 打印一周逐日冷量
        if results['weekly_daily_predictions'] is not None:
            print(f"\n📊 未来一周逐日冷量预测:")
            print("-" * 50)
            print(f"{'日期':^15} {'日冷量(kWh)':^15}")
            print("-" * 50)

            df_weekly = results['weekly_daily_predictions']
            total_cooling = df_weekly['daily_cooling_kwh'].sum()

            for _, row in df_weekly.iterrows():
                print(f"{row['date'].strftime('%Y-%m-%d'):^15} {row['daily_cooling_kwh']:^15.2f}")

            print("-" * 50)
            print(f"{'总计':^15} {total_cooling:^15.2f}")
            print(f"{'日均':^15} {total_cooling / len(df_weekly):^15.2f}")
            print("-" * 50)

        print("\n" + "=" * 80)

    def save_5min_predictions_to_csv(self, results: Dict):
        """保存5分钟预测结果到CSV文件"""
        try:
            # 创建结果目录
            results_dir = os.path.join(os.path.dirname(__file__), "prediction_results_5min")
            os.makedirs(results_dir, exist_ok=True)

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            start_time_str = results['start_time'].replace(' ', '_').replace(':', '')
            filename = f"cooling_prediction_5min_{start_time_str}_{timestamp}"

            # 保存5分钟预测
            if results['5min_predictions'] is not None:
                filepath = os.path.join(results_dir, f"{filename}_5min.csv")
                results['5min_predictions'].to_csv(filepath, index=False, encoding='utf-8-sig')
                logger.info(f"✅ 5分钟预测已保存: {filepath}")

            # 保存每小时平均预测
            if results['hourly_average_predictions'] is not None:
                filepath = os.path.join(results_dir, f"{filename}_hourly_avg.csv")
                results['hourly_average_predictions'].to_csv(filepath, index=False, encoding='utf-8-sig')
                logger.info(f"✅ 每小时平均预测已保存: {filepath}")

            # 保存一周逐日预测
            if results['weekly_daily_predictions'] is not None:
                filepath = os.path.join(results_dir, f"{filename}_weekly_daily.csv")
                results['weekly_daily_predictions'].to_csv(filepath, index=False, encoding='utf-8-sig')
                logger.info(f"✅ 一周逐日预测已保存: {filepath}")

            # 保存汇总报告
            report_path = os.path.join(results_dir, f"{filename}_summary.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("基于5分钟数据的未来冷量预测报告\n")
                f.write("=" * 60 + "\n")
                f.write(f"预测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"预测开始时间: {results['start_time']}\n")
                f.write(f"预测间隔: {self.prediction_interval_minutes}分钟\n")
                f.write(f"每小时预测次数: {self.predictions_per_hour}\n")
                f.write(f"模型: {self.cooling_model_pattern}\n")
                f.write(f"特征: {self.model_feature_names}\n")
                f.write("\n")

                if results['5min_predictions'] is not None:
                    df = results['5min_predictions']
                    f.write("5分钟预测摘要:\n")
                    f.write(f"  总数据点: {len(df)}\n")
                    f.write(f"  平均冷量: {df['cooling_kw'].mean():.2f} kW\n")
                    f.write(f"  最大冷量: {df['cooling_kw'].max():.2f} kW\n")
                    f.write(f"  最小冷量: {df['cooling_kw'].min():.2f} kW\n")
                    f.write("\n")

                if results['weekly_daily_predictions'] is not None:
                    f.write("一周逐日冷量预测:\n")
                    f.write("-" * 40 + "\n")
                    df = results['weekly_daily_predictions']
                    total = df['daily_cooling_kwh'].sum()
                    for _, row in df.iterrows():
                        f.write(f"{row['date'].strftime('%Y-%m-%d')}: {row['daily_cooling_kwh']:.2f} kWh\n")
                    f.write(f"\n总计: {total:.2f} kWh\n")
                    f.write(f"日均: {total / len(df):.2f} kWh\n")

            logger.info(f"✅ 预测报告已保存: {report_path}")

        except Exception as e:
            logger.error(f"❌ 保存结果失败: {e}")

    def run_5min_prediction(self, start_time_str: str):
        """运行基于5分钟数据的冷量预测流程"""
        logger.info("🚀 开始基于5分钟数据的未来冷量预测")
        logger.info("=" * 60)
        logger.info(f"📅 预测开始时间: {start_time_str}")

        # 1. 连接数据库
        self.connect_database()

        # 2. 加载冷量模型
        if not self.load_cooling_model():
            logger.error("❌ 模型加载失败，无法继续预测")
            return False

        # 3. 进行预测
        results = self.predict_future_cooling_5min(start_time_str)

        if not results:
            logger.error("❌ 预测失败")
            return False

        # 4. 打印结果摘要
        self.print_5min_predictions_summary(results)

        # 5. 保存结果
        self.save_5min_predictions_to_csv(results)

        logger.info("✅ 基于5分钟数据的预测完成！")
        return True


def main():
    """主函数"""
    predictor = CoolingCapacityPredictor5Min()

    try:
        print("\n" + "=" * 60)
        print("基于5分钟数据的未来冷量预测器")
        print("=" * 60)
        print(f"预测间隔: {predictor.prediction_interval_minutes}分钟")
        print(f"每小时预测次数: {predictor.predictions_per_hour}次")
        print("=" * 60)

        # 获取用户输入的预测开始时间
        default_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        # 调整到最近的5分钟
        current_time = datetime.now()
        minute = current_time.minute
        remainder = minute % 5
        if remainder != 0:
            default_time = (current_time - timedelta(minutes=remainder)).strftime("%Y-%m-%d %H:%M")

        user_input = input(f"请输入预测开始时间 (格式: YYYY-MM-DD HH:MM) [默认: {default_time}]: ").strip()

        if not user_input:
            start_time = default_time
        else:
            start_time = user_input

        success = predictor.run_5min_prediction(start_time)

        if success:
            print("\n🎉 基于5分钟数据的预测成功完成！")
            print("📁 结果已保存到 prediction_results_5min 目录")
        else:
            print("\n❌ 预测失败，请检查日志")

    except KeyboardInterrupt:
        print("\n\n⏹️ 用户中断预测")
    except Exception as e:
        print(f"\n❌ 预测过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()