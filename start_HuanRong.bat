@echo off
chcp 65001 >nul
title 启动所有服务

set PROJECT_ROOT=D:\py-learn\HuanRong
set VENV_PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe

:: 0. 启动 Redis（带防重复检查）
set REDIS_PATH=C:\Users\Administrator\Desktop\Redis-8.6.1-Windows-x64-cygwin-with-Service\Redis-8.6.1-Windows-x64-cygwin-with-Service
set REDIS_PORT=6379

:: 检查 redis-server 进程是否存在
tasklist /FI "IMAGENAME eq redis-server.exe" 2>nul | find /I "redis-server.exe" >nul
if %errorlevel% equ 0 (
    echo [Redis] 进程已在运行，跳过启动。
) else (
    :: 二次确认端口未被其他程序占用
    netstat -ano | findstr ":%REDIS_PORT% " >nul
    if %errorlevel% equ 0 (
        echo [Redis] 端口 %REDIS_PORT% 已被占用（可能被其他程序使用），跳过启动。
    ) else (
        echo [Redis] 正在启动...
        start "Redis Server" cmd /k "cd /d "%REDIS_PATH%" && redis-server.exe"
    )
)

:: 终端1：FastAPI后端
start "FastAPI Backend" cmd /k "cd /d %PROJECT_ROOT%\backend && %VENV_PYTHON% start.py"

:: 终端2：冷却水优化调度器
::start "Cooling Opt Scheduler" cmd /k "cd /d %PROJECT_ROOT%\backend\ml\models && %VENV_PYTHON% cooling_opt_model.py"

:: 终端3：冷冻水优化调度器
::start "Chilled Opt Scheduler" cmd /k "cd /d %PROJECT_ROOT%\backend\ml\models && %VENV_PYTHON% chilled_opt_model.py"

:: 终端4：复合特征同步处理器
start "Feature Sync" cmd /k "cd /d %PROJECT_ROOT%\backend\ml\data && %VENV_PYTHON% composite_feature_processor.py --mode sync"

:: 终端5：Celery Worker
start "Celery Worker" cmd /k "cd /d %PROJECT_ROOT%\backend && %VENV_PYTHON% -m celery -A app.celery_app worker --loglevel=info"

echo All services started.
timeout /t 3 >nul
exit