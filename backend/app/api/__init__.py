# 导入所有API路由
from . import projects
from . import device
from . import device_models
from . import features
from . import config
from . import model_training
from . import monitoring  # 添加监控路由

# 导出所有路由
__all__ = [
    "projects",
    "device",
    "device_models",
    "features",
    "config",
    "model_training",
    "monitoring"  # 添加监控路由
]