"""
文件处理器 - 用于生成CSV、JSON文件以及处理相关文件操作
backend/ml/data/file_processing.py
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union, Any
import logging
import shutil
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)


class FileProcessor:
    """文件处理器 - 用于生成和管理CSV、JSON等数据文件"""

    def __init__(self, base_data_dir: Optional[str] = None, max_folders_to_keep: int = 5):
        """
        初始化文件处理器

        参数:
        ----------
        base_data_dir : Optional[str]
            基础数据目录，如果为None则使用默认目录
            :param base_data_dir: 基础数据目录
        :param max_folders_to_keep: 每个项目-设备目录下保留的最大子文件夹数量
        """
        self.max_folders_to_keep = max_folders_to_keep
        if base_data_dir is None:
            # 默认数据目录：项目根目录下的data目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            backend_dir = os.path.dirname(os.path.dirname(current_dir))
            project_root = os.path.dirname(backend_dir)
            self.base_data_dir = os.path.join(project_root, 'data')
        else:
            self.base_data_dir = base_data_dir

        # 创建基础目录结构
        self._create_directory_structure()

    def clean_old_folders(self, project_device_dir: str) -> None:
        """
        清理项目-设备目录下旧的 data_* 文件夹，只保留最新的 max_folders_to_keep 个
        :param project_device_dir: 项目-设备目录的绝对路径
        """
        if not os.path.isdir(project_device_dir):
            return

        # 获取所有以 data_ 开头的子文件夹
        subdirs = [
            d for d in os.listdir(project_device_dir)
            if os.path.isdir(os.path.join(project_device_dir, d)) and d.startswith("data_")
        ]

        if len(subdirs) <= self.max_folders_to_keep:
            return

        # 按名称排序（假设名称包含可排序的时间戳）
        subdirs.sort(reverse=True)  # 最新的在前

        # 要删除的是除前 max_folders_to_keep 个之外的所有
        to_delete = subdirs[self.max_folders_to_keep:]

        for folder in to_delete:
            full_path = os.path.join(project_device_dir, folder)
            try:
                shutil.rmtree(full_path)
                logger.info(f"🧹 已删除旧文件夹: {full_path}")
            except Exception as e:
                logger.error(f"❌ 删除文件夹失败 {full_path}: {e}")
    def _create_directory_structure(self):
        """创建基础目录结构"""
        directories = [
            self.base_data_dir,
            os.path.join(self.base_data_dir, 'raw'),          # 原始数据
            os.path.join(self.base_data_dir, 'processed'),    # 处理后的数据
            os.path.join(self.base_data_dir, 'train'),        # 训练集
            os.path.join(self.base_data_dir, 'val'),          # 验证集
            os.path.join(self.base_data_dir, 'test'),         # 测试集
            os.path.join(self.base_data_dir, 'models'),       # 模型文件
            os.path.join(self.base_data_dir, 'results'),      # 结果文件
            os.path.join(self.base_data_dir, 'logs'),         # 日志文件
            os.path.join(self.base_data_dir, 'backups'),      # 备份文件
            os.path.join(self.base_data_dir, 'output')        # 新增：输出目录
        ]

        for directory in directories:
            os.makedirs(directory, exist_ok=True)

        logger.info(f"文件处理器初始化完成，基础目录: {self.base_data_dir}")

    def generate_timestamp(self, prefix: str = "") -> str:
        """
        生成带时间戳的字符串

        参数:
        ----------
        prefix : str
            前缀字符串

        返回:
        ----------
        str: 带时间戳的字符串
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if prefix:
            return f"{prefix}_{timestamp}"
        return timestamp

    def save_dataframe_to_csv(
            self,
            df: pd.DataFrame,
            filepath: str,
            index: bool = True,
            index_label: str = 'timestamp',
            encoding: str = 'utf-8',
            compression: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        保存DataFrame到CSV文件

        参数:
        ----------
        df : pd.DataFrame
            要保存的数据框
        filepath : str
            文件路径
        index : bool
            是否保存索引
        index_label : str
            索引列的名称
        encoding : str
            文件编码
        compression : Optional[str]
            压缩方式，如'gzip', 'bz2'等

        返回:
        ----------
        Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            if df is None or df.empty:
                return False, "数据框为空"

            # 确保目录存在
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # 保存到CSV
            df.to_csv(
                filepath,
                index=index,
                index_label=index_label if index else None,
                encoding=encoding,
                compression=compression
            )

            file_size = os.path.getsize(filepath) / 1024  # KB
            logger.info(f"✅ CSV文件保存成功: {filepath}")
            logger.info(f"   文件大小: {file_size:.2f} KB")
            logger.info(f"   数据形状: {df.shape}")
            if hasattr(df.index, 'min') and hasattr(df.index, 'max'):
                logger.info(f"   时间范围: {df.index.min()} 到 {df.index.max()}")

            return True, f"文件保存成功，大小: {file_size:.2f} KB"

        except Exception as e:
            error_msg = f"❌ 保存CSV文件失败: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def save_metadata_to_json(
            self,
            metadata: Dict[str, Any],
            filepath: str,
            indent: int = 2,
            encoding: str = 'utf-8'
    ) -> Tuple[bool, str]:
        """
        保存元数据到JSON文件

        参数:
        ----------
        metadata : Dict[str, Any]
            元数据字典
        filepath : str
            文件路径
        indent : int
            JSON缩进
        encoding : str
            文件编码

        返回:
        ----------
        Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # 保存到JSON
            with open(filepath, 'w', encoding=encoding) as f:
                json.dump(metadata, f, ensure_ascii=False, indent=indent)

            logger.info(f"✅ JSON元数据保存成功: {filepath}")
            return True, "元数据保存成功"

        except Exception as e:
            error_msg = f"❌ 保存JSON文件失败: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

    def save_raw_data_with_metadata(
            self,
            df: pd.DataFrame,
            device_info: Dict[str, Any],
            feature_info: List[Dict[str, Any]],
            custom_filename: Optional[str] = None,
            save_dir: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, str]]:
        """
        保存原始数据及元数据

        参数:
        ----------
        df : pd.DataFrame
            原始数据框
        device_info : Dict[str, Any]
            设备信息
        feature_info : List[Dict[str, Any]]
            特征信息列表
        custom_filename : Optional[str]
            自定义文件名（不含扩展名）
        save_dir : Optional[str]
            保存目录，如果为None则使用默认raw目录

        返回:
        ----------
        Tuple[bool, str, Dict[str, str]]: (是否成功, 消息, 文件信息字典)
        """
        try:
            if df is None or df.empty:
                return False, "数据框为空", {}

            # 确定保存目录
            if save_dir is None:
                save_dir = os.path.join(self.base_data_dir, 'raw')

            # 生成文件名
            if custom_filename:
                base_filename = custom_filename
            else:
                timestamp = self.generate_timestamp()
                device_name = device_info.get('device_name', 'unknown_device')
                feature_count = len(feature_info)
                base_filename = f"raw_{device_name}_{feature_count}features_{timestamp}"

            # 清理文件名
            base_filename = self._clean_filename(base_filename)

            # 生成文件路径
            csv_filename = f"{base_filename}.csv"
            json_filename = f"{base_filename}_metadata.json"
            csv_path = os.path.join(save_dir, csv_filename)
            json_path = os.path.join(save_dir, json_filename)

            # 准备元数据
            metadata = {
                "data_info": {
                    "data_type": "raw_data",
                    "data_shape": df.shape,
                    "timestamp_range": {
                        "start": df.index.min().isoformat() if not df.empty and hasattr(df.index, 'min') else None,
                        "end": df.index.max().isoformat() if not df.empty and hasattr(df.index, 'max') else None
                    },
                    "generated_at": datetime.now().isoformat()
                },
                "device_info": device_info,
                "feature_info": feature_info,
                "file_info": {
                    "csv_filename": csv_filename,
                    "json_filename": json_filename,
                    "save_dir": save_dir
                },
                "processing_info": {
                    "processor": "FileProcessor",
                    "version": "1.0"
                }
            }

            # 保存数据
            csv_success, csv_msg = self.save_dataframe_to_csv(df, csv_path)
            if not csv_success:
                return False, f"保存CSV失败: {csv_msg}", {}

            # 保存元数据
            json_success, json_msg = self.save_metadata_to_json(metadata, json_path)
            if not json_success:
                # 如果JSON保存失败，删除已保存的CSV文件
                if os.path.exists(csv_path):
                    os.remove(csv_path)
                return False, f"保存JSON失败: {json_msg}", {}

            file_info = {
                'csv_path': csv_path,
                'json_path': json_path,
                'csv_filename': csv_filename,
                'json_filename': json_filename,
                'base_filename': base_filename,
                'save_dir': save_dir
            }

            return True, "原始数据及元数据保存成功", file_info

        except Exception as e:
            error_msg = f"保存原始数据失败: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, {}

    def save_train_val_datasets(
            self,
            train_df: pd.DataFrame,
            val_df: pd.DataFrame,
            test_df: Optional[pd.DataFrame] = None,
            dataset_info: Optional[Dict[str, Any]] = None,
            base_filename: Optional[str] = None,
            save_dir: Optional[str] = None,
            split_ratios: Optional[Dict[str, float]] = None
    ) -> Tuple[bool, str, Dict[str, str]]:
        """
        保存训练集、验证集和测试集

        参数:
        ----------
        train_df : pd.DataFrame
            训练集数据
        val_df : pd.DataFrame
            验证集数据
        test_df : Optional[pd.DataFrame]
            测试集数据
        dataset_info : Optional[Dict[str, Any]]
            数据集信息
        base_filename : Optional[str]
            基础文件名（不含扩展名）
        save_dir : Optional[str]
            保存目录，如果为None则使用默认目录
        split_ratios : Optional[Dict[str, float]]
            分割比例

        返回:
        ----------
        Tuple[bool, str, Dict[str, str]]: (是否成功, 消息, 文件信息字典)
        """
        try:
            # 检查数据
            datasets = {'train': train_df, 'val': val_df}
            if test_df is not None:
                datasets['test'] = test_df

            for name, df in datasets.items():
                if df is None or df.empty:
                    return False, f"{name}数据集为空", {}

            # 确定保存目录
            if save_dir is None:
                save_dir = os.path.join(self.base_data_dir, 'processed')

            # 生成基础文件名
            if base_filename is None:
                timestamp = self.generate_timestamp()
                base_filename = f"dataset_{timestamp}"
            else:
                base_filename = self._clean_filename(base_filename)

            # 保存每个数据集
            file_info = {'base_filename': base_filename, 'save_dir': save_dir}

            for name, df in datasets.items():
                # 生成文件名
                filename = f"{base_filename}_{name}.csv"
                filepath = os.path.join(save_dir, filename)

                # 保存CSV
                success, msg = self.save_dataframe_to_csv(df, filepath)
                if not success:
                    return False, f"保存{name}集失败: {msg}", {}

                file_info[f'{name}_path'] = filepath
                file_info[f'{name}_filename'] = filename

            # 创建数据集元数据
            if dataset_info is None:
                dataset_info = {}

            # 添加分割信息
            if split_ratios is None:
                total_len = sum(len(df) for df in datasets.values())
                split_ratios = {}
                for name, df in datasets.items():
                    split_ratios[name] = len(df) / total_len if total_len > 0 else 0

            metadata = {
                "dataset_info": {
                    "type": "train_val_test_split",
                    "base_filename": base_filename,
                    "split_ratios": split_ratios,
                    "samples_count": {name: len(df) for name, df in datasets.items()},
                    "timestamp_range": {
                        name: {
                            "start": df.index.min().isoformat() if not df.empty and hasattr(df.index, 'min') else None,
                            "end": df.index.max().isoformat() if not df.empty and hasattr(df.index, 'max') else None
                        }
                        for name, df in datasets.items()
                    },
                    "features": list(train_df.columns) if not train_df.empty else [],
                    "generated_at": datetime.now().isoformat()
                },
                "additional_info": dataset_info,
                "file_info": file_info
            }

            # 保存元数据
            metadata_filename = f"{base_filename}_dataset_metadata.json"
            metadata_path = os.path.join(save_dir, metadata_filename)

            json_success, json_msg = self.save_metadata_to_json(metadata, metadata_path)
            if not json_success:
                # 删除已保存的CSV文件
                for name in datasets.keys():
                    if f'{name}_path' in file_info and os.path.exists(file_info[f'{name}_path']):
                        os.remove(file_info[f'{name}_path'])
                return False, f"保存数据集元数据失败: {json_msg}", {}

            file_info['metadata_path'] = metadata_path
            file_info['metadata_filename'] = metadata_filename

            logger.info(f"✅ 数据集保存完成: {base_filename}")
            logger.info(f"   训练集: {len(train_df)} 条")
            logger.info(f"   验证集: {len(val_df)} 条")
            if test_df is not None:
                logger.info(f"   测试集: {len(test_df)} 条")

            return True, "数据集保存成功", file_info

        except Exception as e:
            error_msg = f"保存数据集失败: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, {}

    # ========== 新增：按项目-设备-时间戳的目录结构保存 ==========

    def create_project_device_directory(
            self,
            project_name: str,
            device_name: str,
            timestamp: Optional[str] = None
    ) -> Tuple[bool, str, str]:
        """
        创建项目-设备-时间戳目录结构

        目录结构: backend/ml/data/output/{project_name}_{device_name}/data_{timestamp}/

        参数:
        ----------
        project_name : str
            项目名称
        device_name : str
            设备名称
        timestamp : Optional[str]
            时间戳，如果为None则自动生成

        返回:
        ----------
        Tuple[bool, str, str]: (是否成功, 消息, 目录路径)
        """
        try:
            # 清理项目名和设备名
            clean_project_name = self._clean_filename(project_name)
            clean_device_name = self._clean_filename(device_name)

            # 生成时间戳
            if timestamp is None:
                timestamp = self.generate_timestamp("data")
            else:
                # 确保时间戳格式正确
                timestamp = self._clean_filename(timestamp)

            # 构建目录路径
            project_device_dir = os.path.join(
                self.base_data_dir,
                'output',
                f"{clean_project_name}_{clean_device_name}"
            )

            # 创建data_时间戳子目录
            data_timestamp_dir = os.path.join(project_device_dir, timestamp)

            # 创建目录（如果不存在）
            os.makedirs(data_timestamp_dir, exist_ok=True)

            logger.info(f"✅ 创建目录结构: {data_timestamp_dir}")
            # 创建目录后，清理该项目-设备目录下的旧文件夹
            self.clean_old_folders(project_device_dir)
            return True, "目录创建成功", data_timestamp_dir

        except Exception as e:
            error_msg = f"创建目录结构失败: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, ""

    def save_training_pipeline_files(
            self,
            raw_df: pd.DataFrame,
            processed_df: pd.DataFrame,
            train_df: pd.DataFrame,
            val_df: pd.DataFrame,
            test_df: Optional[pd.DataFrame] = None,
            project_info: Dict[str, Any] = None,
            device_info: Dict[str, Any] = None,
            feature_info: List[Dict[str, Any]] = None,
            dataset_info: Optional[Dict[str, Any]] = None,
            split_ratios: Optional[Dict[str, float]] = None,
            timestamp: Optional[str] = None
    ) -> Tuple[bool, str, Dict[str, str]]:
        """
        保存训练管道所有文件到项目-设备-时间戳目录

        参数:
        ----------
        raw_df : pd.DataFrame
            原始数据
        processed_df : pd.DataFrame
            处理后的数据
        train_df : pd.DataFrame
            训练集数据
        val_df : pd.DataFrame
            验证集数据
        test_df : Optional[pd.DataFrame]
            测试集数据
        project_info : Dict[str, Any]
            项目信息
        device_info : Dict[str, Any]
            设备信息
        feature_info : List[Dict[str, Any]]
            特征信息
        dataset_info : Optional[Dict[str, Any]]
            数据集信息
        split_ratios : Optional[Dict[str, float]]
            分割比例
        timestamp : Optional[str]
            时间戳

        返回:
        ----------
        Tuple[bool, str, Dict[str, str]]: (是否成功, 消息, 文件信息字典)
        """
        try:
            # 检查必要信息
            if project_info is None:
                project_info = {}
            if device_info is None:
                device_info = {}
            if feature_info is None:
                feature_info = []

            # 获取项目名和设备名
            project_name = project_info.get('project_name', 'unknown_project')
            device_name = device_info.get('device_name', 'unknown_device')

            # 创建目录结构
            success, msg, save_dir = self.create_project_device_directory(
                project_name, device_name, timestamp
            )

            if not success:
                return False, msg, {}

            logger.info(f"📁 保存文件到目录: {save_dir}")

            # 准备文件信息字典
            file_info = {
                'save_dir': save_dir,
                'project_name': project_name,
                'device_name': device_name,
                'timestamp': timestamp or self.generate_timestamp("data")
            }

            # 1. 保存原始数据
            if raw_df is not None and not raw_df.empty:
                raw_filename = f"raw_data_{file_info['timestamp']}.csv"
                raw_path = os.path.join(save_dir, raw_filename)

                success, msg = self.save_dataframe_to_csv(raw_df, raw_path)
                if success:
                    file_info['raw_path'] = raw_path
                    file_info['raw_filename'] = raw_filename
                    logger.info(f"✅ 原始数据保存成功: {raw_filename}")
                else:
                    logger.warning(f"原始数据保存失败: {msg}")

            # 2. 保存处理后的数据
            if processed_df is not None and not processed_df.empty:
                processed_filename = f"processed_data_{file_info['timestamp']}.csv"
                processed_path = os.path.join(save_dir, processed_filename)

                success, msg = self.save_dataframe_to_csv(processed_df, processed_path)
                if success:
                    file_info['processed_path'] = processed_path
                    file_info['processed_filename'] = processed_filename
                    logger.info(f"✅ 处理数据保存成功: {processed_filename}")
                else:
                    logger.warning(f"处理数据保存失败: {msg}")

            # 3. 保存训练集
            if train_df is not None and not train_df.empty:
                train_filename = f"train_data_{file_info['timestamp']}.csv"
                train_path = os.path.join(save_dir, train_filename)

                success, msg = self.save_dataframe_to_csv(train_df, train_path)
                if success:
                    file_info['train_path'] = train_path
                    file_info['train_filename'] = train_filename
                    logger.info(f"✅ 训练集保存成功: {train_filename}")
                else:
                    logger.warning(f"训练集保存失败: {msg}")

            # 4. 保存验证集
            if val_df is not None and not val_df.empty:
                val_filename = f"val_data_{file_info['timestamp']}.csv"
                val_path = os.path.join(save_dir, val_filename)

                success, msg = self.save_dataframe_to_csv(val_df, val_path)
                if success:
                    file_info['val_path'] = val_path
                    file_info['val_filename'] = val_filename
                    logger.info(f"✅ 验证集保存成功: {val_filename}")
                else:
                    logger.warning(f"验证集保存失败: {msg}")

            # 5. 保存测试集
            if test_df is not None and not test_df.empty:
                test_filename = f"test_data_{file_info['timestamp']}.csv"
                test_path = os.path.join(save_dir, test_filename)

                success, msg = self.save_dataframe_to_csv(test_df, test_path)
                if success:
                    file_info['test_path'] = test_path
                    file_info['test_filename'] = test_filename
                    logger.info(f"✅ 测试集保存成功: {test_filename}")
                else:
                    logger.warning(f"测试集保存失败: {msg}")

            # 6. 保存元数据
            metadata = {
                "pipeline_info": {
                    "type": "training_pipeline",
                    "timestamp": file_info['timestamp'],
                    "generated_at": datetime.now().isoformat(),
                    "save_dir": save_dir
                },
                "project_info": project_info,
                "device_info": device_info,
                "feature_info": feature_info,
                "dataset_info": dataset_info or {},
                "split_ratios": split_ratios or {},
                "file_info": {k: v for k, v in file_info.items() if 'path' in k}
            }

            metadata_filename = f"pipeline_metadata_{file_info['timestamp']}.json"
            metadata_path = os.path.join(save_dir, metadata_filename)

            json_success, json_msg = self.save_metadata_to_json(metadata, metadata_path)
            if json_success:
                file_info['metadata_path'] = metadata_path
                file_info['metadata_filename'] = metadata_filename
                logger.info(f"✅ 管道元数据保存成功: {metadata_filename}")
            else:
                logger.warning(f"管道元数据保存失败: {json_msg}")

            # 7. 保存数据摘要
            summary_filename = f"data_summary_{file_info['timestamp']}.txt"
            summary_path = os.path.join(save_dir, summary_filename)

            # 创建数据摘要
            summary_content = self._generate_data_summary(
                raw_df, processed_df, train_df, val_df, test_df,
                project_info, device_info, feature_info
            )

            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(summary_content)

            file_info['summary_path'] = summary_path
            file_info['summary_filename'] = summary_filename
            logger.info(f"✅ 数据摘要保存成功: {summary_filename}")

            # 8. 保存配置信息（如果有）
            if dataset_info and 'config' in dataset_info:
                config_filename = f"training_config_{file_info['timestamp']}.json"
                config_path = os.path.join(save_dir, config_filename)

                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(dataset_info['config'], f, ensure_ascii=False, indent=2)

                file_info['config_path'] = config_path
                file_info['config_filename'] = config_filename
                logger.info(f"✅ 训练配置保存成功: {config_filename}")

            logger.info(f"🎉 所有训练管道文件已保存到: {save_dir}")
            logger.info(f"📊 保存的文件: {len([k for k in file_info.keys() if 'path' in k])} 个文件")

            return True, "训练管道文件保存成功", file_info

        except Exception as e:
            error_msg = f"保存训练管道文件失败: {e}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg, {}

    def _generate_data_summary(
            self,
            raw_df: Optional[pd.DataFrame],
            processed_df: Optional[pd.DataFrame],
            train_df: Optional[pd.DataFrame],
            val_df: Optional[pd.DataFrame],
            test_df: Optional[pd.DataFrame],
            project_info: Dict[str, Any],
            device_info: Dict[str, Any],
            feature_info: List[Dict[str, Any]]
    ) -> str:
        """生成数据摘要文本"""
        summary_lines = []

        # 标题
        summary_lines.append("=" * 80)
        summary_lines.append("训练数据管道 - 数据摘要")
        summary_lines.append("=" * 80)
        summary_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        summary_lines.append("")

        # 项目和设备信息
        summary_lines.append("📋 项目与设备信息:")
        summary_lines.append(f"  项目名称: {project_info.get('project_name', '未知')}")
        summary_lines.append(f"  项目代码: {project_info.get('project_code', '未知')}")
        summary_lines.append(f"  设备名称: {device_info.get('device_name', '未知')}")
        summary_lines.append(f"  设备ID: {device_info.get('device_id', '未知')}")
        summary_lines.append("")

        # 特征信息
        summary_lines.append("📊 特征信息:")
        summary_lines.append(f"  特征数量: {len(feature_info)}")
        for i, feature in enumerate(feature_info[:20], 1):  # 只显示前20个特征
            summary_lines.append(f"  {i}. {feature.get('feature_name', '未知')} ({feature.get('feature_code', '未知')})")
        if len(feature_info) > 20:
            summary_lines.append(f"  ... 还有 {len(feature_info) - 20} 个特征")
        summary_lines.append("")

        # 数据统计
        summary_lines.append("📈 数据统计:")

        datasets = [
            ("原始数据", raw_df),
            ("处理数据", processed_df),
            ("训练集", train_df),
            ("验证集", val_df),
            ("测试集", test_df)
        ]

        for name, df in datasets:
            if df is not None and not df.empty:
                summary_lines.append(f"  {name}:")
                summary_lines.append(f"    样本数: {len(df)}")
                summary_lines.append(f"    特征数: {len(df.columns)}")
                if hasattr(df.index, 'min') and hasattr(df.index, 'max'):
                    summary_lines.append(f"    时间范围: {df.index.min()} 到 {df.index.max()}")
                summary_lines.append("")

        # 分割比例
        total_samples = 0
        dataset_counts = {}

        for name, df in [("训练集", train_df), ("验证集", val_df), ("测试集", test_df)]:
            if df is not None and not df.empty:
                count = len(df)
                dataset_counts[name] = count
                total_samples += count

        if total_samples > 0:
            summary_lines.append("📊 数据集分割比例:")
            for name, count in dataset_counts.items():
                percentage = (count / total_samples) * 100
                summary_lines.append(f"  {name}: {count} 条 ({percentage:.1f}%)")
            summary_lines.append(f"  总计: {total_samples} 条")

        summary_lines.append("")
        summary_lines.append("=" * 80)

        return "\n".join(summary_lines)

    def load_dataframe_from_csv(
            self,
            filepath: str,
            parse_dates: bool = True,
            index_col: str = 'timestamp',
            encoding: str = 'utf-8',
            compression: Optional[str] = None
    ) -> Tuple[Optional[pd.DataFrame], str]:
        """
        从CSV文件加载DataFrame

        参数:
        ----------
        filepath : str
            CSV文件路径
        parse_dates : bool
            是否解析日期时间
        index_col : str
            索引列名
        encoding : str
            文件编码
        compression : Optional[str]
            压缩方式

        返回:
        ----------
        Tuple[Optional[pd.DataFrame], str]: (数据框, 消息)
        """
        try:
            if not os.path.exists(filepath):
                return None, f"文件不存在: {filepath}"

            # 读取CSV文件
            if parse_dates and index_col:
                df = pd.read_csv(
                    filepath,
                    parse_dates=[index_col],
                    index_col=index_col,
                    encoding=encoding,
                    compression=compression
                )
            else:
                df = pd.read_csv(
                    filepath,
                    encoding=encoding,
                    compression=compression
                )

            logger.info(f"✅ 从CSV加载数据成功: {filepath}")
            logger.info(f"   数据形状: {df.shape}")
            if not df.empty and hasattr(df.index, 'min'):
                logger.info(f"   时间范围: {df.index.min()} 到 {df.index.max()}")

            return df, "数据加载成功"

        except Exception as e:
            error_msg = f"❌ 加载CSV文件失败: {e}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg

    def load_metadata_from_json(
            self,
            filepath: str,
            encoding: str = 'utf-8'
    ) -> Tuple[Optional[Dict], str]:
        """
        从JSON文件加载元数据

        参数:
        ----------
        filepath : str
            JSON文件路径
        encoding : str
            文件编码

        返回:
        ----------
        Tuple[Optional[Dict], str]: (元数据字典, 消息)
        """
        try:
            if not os.path.exists(filepath):
                return None, f"文件不存在: {filepath}"

            with open(filepath, 'r', encoding=encoding) as f:
                metadata = json.load(f)

            logger.info(f"✅ 从JSON加载元数据成功: {filepath}")
            return metadata, "元数据加载成功"

        except Exception as e:
            error_msg = f"❌ 加载JSON文件失败: {e}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg

    def _clean_filename(self, filename: str) -> str:
        """
        清理文件名，移除非法字符

        参数:
        ----------
        filename : str
            原始文件名

        返回:
        ----------
        str: 清理后的文件名
        """
        # 保留字母、数字、下划线、连字符、点
        import re
        cleaned = re.sub(r'[^\w\-\.]', '_', filename)
        # 移除连续的下划线
        cleaned = re.sub(r'_+', '_', cleaned)
        # 移除开头和结尾的下划线或连字符
        cleaned = cleaned.strip('_-')
        return cleaned

    def list_data_files(
            self,
            data_type: str = 'all',
            pattern: Optional[str] = None,
            sort_by: str = 'modified',
            descending: bool = True
    ) -> List[Dict[str, Any]]:
        """
        列出数据文件

        参数:
        ----------
        data_type : str
            数据类型: 'raw', 'processed', 'train', 'val', 'test', 'all', 'output'
        pattern : Optional[str]
            文件名模式匹配
        sort_by : str
            排序方式: 'name', 'size', 'modified', 'created'
        descending : bool
            是否降序排序

        返回:
        ----------
        List[Dict[str, Any]]: 文件信息列表
        """
        try:
            files_info = []

            # 确定搜索目录
            if data_type == 'all':
                search_dirs = [
                    os.path.join(self.base_data_dir, 'raw'),
                    os.path.join(self.base_data_dir, 'processed'),
                    os.path.join(self.base_data_dir, 'train'),
                    os.path.join(self.base_data_dir, 'val'),
                    os.path.join(self.base_data_dir, 'test'),
                    os.path.join(self.base_data_dir, 'output')
                ]
            elif data_type == 'output':
                search_dirs = [os.path.join(self.base_data_dir, 'output')]
            else:
                search_dirs = [os.path.join(self.base_data_dir, data_type)]

            # 搜索文件
            for search_dir in search_dirs:
                if os.path.exists(search_dir):
                    for root, _, files in os.walk(search_dir):
                        for file in files:
                            if file.endswith(('.csv', '.json', '.txt', '.yaml', '.yml')):
                                # 如果指定了模式，检查是否匹配
                                if pattern and pattern not in file:
                                    continue

                                filepath = os.path.join(root, file)
                                stat = os.stat(filepath)

                                # 获取文件类型
                                if file.endswith('.csv'):
                                    file_type = 'data'
                                elif file.endswith('.json'):
                                    file_type = 'metadata'
                                elif file.endswith('.txt'):
                                    file_type = 'summary'
                                elif file.endswith(('.yaml', '.yml')):
                                    file_type = 'config'
                                else:
                                    file_type = 'other'

                                # 从路径推断数据类型
                                rel_path = os.path.relpath(root, self.base_data_dir)
                                inferred_type = rel_path.split(os.sep)[0] if os.sep in rel_path else rel_path

                                files_info.append({
                                    'filepath': filepath,
                                    'filename': file,
                                    'file_type': file_type,
                                    'data_type': inferred_type,
                                    'file_size_kb': round(stat.st_size / 1024, 2),
                                    'created_time': datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
                                    'modified_time': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                                    'directory': root,
                                    'has_metadata': file.endswith('.csv') and os.path.exists(filepath.replace('.csv', '_metadata.json'))
                                })

            # 排序
            if sort_by == 'name':
                files_info.sort(key=lambda x: x['filename'], reverse=descending)
            elif sort_by == 'size':
                files_info.sort(key=lambda x: x['file_size_kb'], reverse=descending)
            elif sort_by == 'modified':
                files_info.sort(key=lambda x: x['modified_time'], reverse=descending)
            elif sort_by == 'created':
                files_info.sort(key=lambda x: x['created_time'], reverse=descending)

            return files_info

        except Exception as e:
            logger.error(f"列出数据文件失败: {e}")
            return []

    def backup_file(self, filepath: str, backup_dir: Optional[str] = None) -> Tuple[bool, str]:
        """
        备份文件

        参数:
        ----------
        filepath : str
            原文件路径
        backup_dir : Optional[str]
            备份目录，如果为None则使用默认备份目录

        返回:
        ----------
        Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            if not os.path.exists(filepath):
                return False, f"原文件不存在: {filepath}"

            # 确定备份目录
            if backup_dir is None:
                backup_dir = os.path.join(self.base_data_dir, 'backups')
                os.makedirs(backup_dir, exist_ok=True)

            # 生成备份文件名
            filename = os.path.basename(filepath)
            timestamp = self.generate_timestamp()
            backup_filename = f"{filename.rsplit('.', 1)[0]}_backup_{timestamp}.{filename.rsplit('.', 1)[1]}"
            backup_path = os.path.join(backup_dir, backup_filename)

            # 复制文件
            shutil.copy2(filepath, backup_path)

            logger.info(f"✅ 文件备份成功: {filepath} -> {backup_path}")
            return True, f"文件备份成功: {backup_path}"

        except Exception as e:
            error_msg = f"备份文件失败: {e}"
            logger.error(error_msg)
            return False, error_msg

    def delete_file(self, filepath: str, backup: bool = True) -> Tuple[bool, str]:
        """
        删除文件

        参数:
        ----------
        filepath : str
            文件路径
        backup : bool
            是否先备份

        返回:
        ----------
        Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            if not os.path.exists(filepath):
                return False, f"文件不存在: {filepath}"

            # 如果需要，先备份
            if backup:
                backup_success, backup_msg = self.backup_file(filepath)
                if not backup_success:
                    return False, f"备份失败，取消删除: {backup_msg}"

            # 删除文件
            os.remove(filepath)
            logger.info(f"✅ 文件删除成功: {filepath}")
            return True, "文件删除成功"

        except Exception as e:
            error_msg = f"删除文件失败: {e}"
            logger.error(error_msg)
            return False, error_msg

    def get_data_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        获取数据统计摘要

        参数:
        ----------
        df : pd.DataFrame
            数据框

        返回:
        ----------
        Dict[str, Any]: 统计摘要
        """
        if df is None or df.empty:
            return {}

        summary = {
            'shape': df.shape,
            'columns': list(df.columns),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'missing_values': df.isnull().sum().to_dict(),
            'missing_percentage': (df.isnull().sum() / len(df) * 100).round(2).to_dict()
        }

        # 数值列的统计
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            summary['numeric_stats'] = {
                col: {
                    'min': float(df[col].min()),
                    'max': float(df[col].max()),
                    'mean': float(df[col].mean()),
                    'std': float(df[col].std()),
                    'median': float(df[col].median()),
                    'q25': float(df[col].quantile(0.25)),
                    'q75': float(df[col].quantile(0.75))
                }
                for col in numeric_cols
            }

        # 时间索引信息
        if hasattr(df.index, 'min') and hasattr(df.index, 'max'):
            summary['time_range'] = {
                'start': df.index.min().isoformat() if not df.empty else None,
                'end': df.index.max().isoformat() if not df.empty else None,
                'duration_days': (df.index.max() - df.index.min()).days if not df.empty else 0,
                'total_samples': len(df)
            }

        return summary

    def save_data_summary(
            self,
            df: pd.DataFrame,
            filepath: str,
            format: str = 'json'
    ) -> Tuple[bool, str]:
        """
        保存数据统计摘要

        参数:
        ----------
        df : pd.DataFrame
            数据框
        filepath : str
            文件路径
        format : str
            保存格式: 'json', 'yaml', 'txt'

        返回:
        ----------
        Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            summary = self.get_data_summary(df)
            if not summary:
                return False, "无法生成统计摘要"

            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            if format == 'json':
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, ensure_ascii=False, indent=2)
            elif format == 'yaml':
                with open(filepath, 'w', encoding='utf-8') as f:
                    yaml.dump(summary, f, default_flow_style=False)
            elif format == 'txt':
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"数据统计摘要\n")
                    f.write(f"============\n\n")
                    f.write(f"数据形状: {summary['shape'][0]} 行 × {summary['shape'][1]} 列\n\n")
                    f.write(f"列信息:\n")
                    for col, dtype in summary['dtypes'].items():
                        f.write(f"  - {col}: {dtype}\n")
                    f.write(f"\n缺失值统计:\n")
                    for col, count in summary['missing_values'].items():
                        percentage = summary['missing_percentage'][col]
                        f.write(f"  - {col}: {count} ({percentage}%)\n")
                    if 'time_range' in summary:
                        f.write(f"\n时间范围:\n")
                        f.write(f"  开始: {summary['time_range']['start']}\n")
                        f.write(f"  结束: {summary['time_range']['end']}\n")
                        f.write(f"  时长: {summary['time_range']['duration_days']} 天\n")
                        f.write(f"  样本数: {summary['time_range']['total_samples']}\n")
            else:
                return False, f"不支持的格式: {format}"

            logger.info(f"✅ 数据统计摘要保存成功: {filepath}")
            return True, "统计摘要保存成功"

        except Exception as e:
            error_msg = f"保存统计摘要失败: {e}"
            logger.error(error_msg)
            return False, error_msg


# 单例模式
_file_processor = None


def get_file_processor(base_data_dir: Optional[str] = None) -> FileProcessor:
    """获取文件处理器单例"""
    global _file_processor
    if _file_processor is None:
        _file_processor = FileProcessor(base_data_dir)
    return _file_processor