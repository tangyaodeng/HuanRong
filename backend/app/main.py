# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import sys
import logging

# 设置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from .config import settings
from .api import (projects, device, device_models, features, config, model_training, monitoring,
                  model_evaluation,data_config,trainer_config,cooling_opt_config,chilled_opt_config,chat,load_forecasting,knowledge_feeding)

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
# 挂载API路由

app.include_router(projects.router, prefix=settings.API_V1_STR)
app.include_router(device.router, prefix=settings.API_V1_STR)
app.include_router(device_models.router, prefix=settings.API_V1_STR)
app.include_router(features.router, prefix=settings.API_V1_STR)
app.include_router(config.router, prefix=settings.API_V1_STR)
app.include_router(model_training.router, prefix=settings.API_V1_STR)
app.include_router(monitoring.router, prefix=settings.API_V1_STR)
app.include_router(model_evaluation.router, prefix=settings.API_V1_STR)
app.include_router(data_config.router, prefix=settings.API_V1_STR)
app.include_router(trainer_config.router, prefix=settings.API_V1_STR)
app.include_router(cooling_opt_config.router, prefix=settings.API_V1_STR)
app.include_router(chilled_opt_config.router, prefix=settings.API_V1_STR)
app.include_router(chat.router, prefix=settings.API_V1_STR)
app.include_router(load_forecasting.router, prefix=settings.API_V1_STR)
app.include_router(knowledge_feeding.router, prefix=settings.API_V1_STR)



# 挂载静态文件（前端）
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/frontend", StaticFiles(directory=frontend_path), name="frontend")
    logger.info(f"已挂载前端静态文件: {frontend_path}")

# 根路由
@app.get("/")
async def root():
    return {
        "message": "工业负荷预测系统API",
        "version": settings.VERSION,
        "docs": "/docs",
        "frontend": "/frontend/index.html"
    }

# 健康检查
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# ====== 添加调度器生命周期管理 ======
@app.on_event("startup")
async def startup_event():
    """应用启动时执行"""
    # 调度器已由 run_scheduler.py 独立管理，不在 FastAPI 中启动
    logger.info("FastAPI startup: scheduler managed by run_scheduler.py")
    # try:
    #     # 启动训练计划调度器
    #     from .services.scheduler import get_scheduler
    #     scheduler = get_scheduler()
    #     scheduler.start()
    #     logger.info("✅ 训练计划调度器已启动")
    # except Exception as e:
    #     logger.error(f"❌ 启动调度器失败: {str(e)}")


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时执行"""
    # 调度器已由 run_scheduler.py 独立管理，不在 FastAPI 中停止
    logger.info("FastAPI shutdown: scheduler stop handled by run_scheduler.py")
    # try:
    #     from .services.scheduler import get_scheduler
    #     scheduler = get_scheduler()
    #     scheduler.stop()
    #     logger.info("训练计划调度器已停止")
    # except Exception as e:
    #     logger.error(f"停止调度器失败: {str(e)}")


