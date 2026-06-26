"""
机器学习模块初始化
"""
from .data import get_data_loader, get_preprocessor
__all__ = [
    'get_data_loader',
    'get_preprocessor',
]