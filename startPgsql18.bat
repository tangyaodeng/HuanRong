@echo off
setlocal enabledelayedexpansion
set "SERVICE_NAME=postgresql-x64-18"
set "LOG_FILE=%USERPROFILE%\pgsql_startup.log"

echo [%date% %time%] ========== 开始检查 PostgreSQL 服务 ========== >> "%LOG_FILE%"

REM 1. 检查服务当前状态
sc query "%SERVICE_NAME%" | findstr /i "RUNNING" >nul
if %errorlevel% equ 0 (
    echo [%date% %time%] 服务已在运行，无需操作。 >> "%LOG_FILE%"
    exit /b 0
)

REM 2. 服务存在但未运行，尝试启动
echo [%date% %time%] 服务未运行，正在启动... >> "%LOG_FILE%"
net start "%SERVICE_NAME%"
if %errorlevel% equ 0 (
    echo [%date% %time%] 服务启动成功。 >> "%LOG_FILE%"
    exit /b 0
)

REM 3. 启动失败，可能卡死，先停止再启动
echo [%date% %time%] 启动失败（错误码 %errorlevel%），尝试停止后重新启动... >> "%LOG_FILE%"
net stop "%SERVICE_NAME%" >nul 2>&1
timeout /t 5 /nobreak >nul
net start "%SERVICE_NAME%"
if %errorlevel% equ 0 (
    echo [%date% %time%] 停止后重新启动成功。 >> "%LOG_FILE%"
) else (
    echo [%date% %time%] 重新启动仍然失败，错误码: %errorlevel% >> "%LOG_FILE%"
)

exit /b 0