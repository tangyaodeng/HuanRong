"""
模型训练模块初始化 - 支持动态加载不同设备的训练器
"""
import importlib
from typing import Dict, Any
import yaml
import os
import logging

logger = logging.getLogger(__name__)

# YAML配置路径
CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'config',
    'device_trainers.yaml'
)

def load_trainer_config() -> Dict[str, Any]:
    """加载设备训练器配置文件"""
    try:
        if not os.path.exists(CONFIG_PATH):
            logger.warning(f"配置文件不存在: {CONFIG_PATH}，使用默认配置")
            return {
                'default': {
                    'primary_trainer': 'ml.models.trainers.device11_xgboost_v1.XGBoostTrainer',
                    'trainer_list': ['ml.models.trainers.device11_xgboost_v1.XGBoostTrainer'],
                    'description': '默认训练器配置'
                }
            }

        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return config.get('device_trainer_config', {})
    except Exception as e:
        logger.error(f"加载训练器配置失败: {e}")
        raise

def get_device_trainer(device_id: int):
    """
    根据设备ID获取对应的训练器实例

    Args:
        device_id: 设备ID

    Returns:
        XGBoostTrainer实例

    Raises:
        ImportError: 无法导入训练器
    """
    # 加载配置
    config = load_trainer_config()

    # 构建设备键名
    device_key = f"device{device_id}"

    # 获取设备配置，如果没有则使用默认配置
    device_config = config.get(device_key, config.get('default'))

    if not device_config:
        raise ValueError(f"设备 {device_id} 的配置未找到，且没有默认配置")

    # 获取首选训练器
    primary_trainer_path = device_config.get('primary_trainer')
    if not primary_trainer_path:
        # 如果首选训练器不存在，使用列表中的第一个
        trainer_list = device_config.get('trainer_list', [])
        if not trainer_list:
            raise ValueError(f"设备 {device_id} 的训练器列表为空")
        primary_trainer_path = trainer_list[0]

    logger.info(f"设备 {device_id} 使用训练器: {primary_trainer_path}")

    try:
        # 动态导入训练器
        module_path, class_name = primary_trainer_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        trainer_class = getattr(module, class_name)

        return trainer_class()
    except Exception as e:
        logger.error(f"导入训练器 {primary_trainer_path} 失败: {e}")

        # 如果首选训练器失败，尝试备选训练器
        trainer_list = device_config.get('trainer_list', [])
        for i, trainer_path in enumerate(trainer_list):
            if trainer_path == primary_trainer_path:
                continue  # 跳过已经尝试过的

            try:
                logger.info(f"尝试备选训练器 {i+1}: {trainer_path}")
                module_path, class_name = trainer_path.rsplit('.', 1)
                module = importlib.import_module(module_path)
                trainer_class = getattr(module, class_name)

                return trainer_class()
            except Exception as inner_e:
                logger.error(f"备选训练器 {trainer_path} 也失败: {inner_e}")
                continue

        # 所有训练器都失败，抛出异常
        raise ImportError(f"设备 {device_id} 的所有训练器导入失败")

# 旧的导出方式保持兼容（可选）
# 由于两个文件都有XGBoostTrainer，这里只导出get_device_trainer函数
__all__ = ['get_device_trainer']