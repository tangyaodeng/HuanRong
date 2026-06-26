// 模型训练页面逻辑
const ModelTrainingManager = {
    // 状态
    state: {
        currentPage: 1,
        pageSize: 20,
        totalDevices: 0,
        filters: {
            projectId: null,
            deviceId: null,
//            status: null,
            planStatus: null // 新增：训练计划状态筛选
        },
        selectedModel: null,
        selectedDevice: null
    },

    // 显示数据配置弹窗
    showDataConfig: async function(deviceId, deviceName, projectName) {
        console.log(`⚙️ 显示数据配置弹窗，设备ID: ${deviceId}`);
        this.state.selectedDevice = deviceId;
        try {
            const deviceConfig = await ModelTrainingAPI.getDeviceDataConfig(deviceId);
            const defaultConfig = await ModelTrainingAPI.getDefaultDataConfig();
            document.getElementById('data-config-project-name').textContent = projectName;
            document.getElementById('data-config-device-name').textContent = deviceName;
            this.populateDataConfigForm(deviceConfig, defaultConfig);
            document.getElementById('data-config-modal').classList.add('active');
        } catch (error) {
            console.error('❌ 加载数据配置失败:', error);
            this.showNotification('加载数据配置失败', 'error');
        }
    },

    // 填充数据配置表单
    populateDataConfigForm: function(deviceConfig, defaultConfig) {
        console.log('📝 填充数据配置表单', { deviceConfig, defaultConfig });
        const formatLocalDateTime = (dateString) => {
            if (!dateString) return '';
            try {
                const date = new Date(dateString);
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                const hours = String(date.getHours()).padStart(2, '0');
                const minutes = String(date.getMinutes()).padStart(2, '0');
                return `${year}-${month}-${day}T${hours}:${minutes}`;
            } catch (e) {
                return dateString;
            }
        };
        const startTime = deviceConfig.data_start_time || defaultConfig.DEFAULT_START_TIME;
        document.getElementById('data-start-time').value = formatLocalDateTime(startTime);
        document.getElementById('data-start-time-default').textContent = formatLocalDateTime(defaultConfig.DEFAULT_START_TIME);
        const endTime = deviceConfig.data_end_time || defaultConfig.DEFAULT_END_TIME;
        document.getElementById('data-end-time').value = formatLocalDateTime(endTime);
        document.getElementById('data-end-time-default').textContent = formatLocalDateTime(defaultConfig.DEFAULT_END_TIME);
        const maxRows = deviceConfig.max_rows_limit || defaultConfig.MAX_ROWS_DEFAULT;
        document.getElementById('max-rows').value = maxRows;
        document.getElementById('max-rows-default').textContent = defaultConfig.MAX_ROWS_DEFAULT;
    },

    // 保存数据配置
    saveDataConfig: async function() {
        console.log('💾 保存数据配置...');
        const deviceId = this.state.selectedDevice;
        if (!deviceId) {
            this.showNotification('请先选择设备', 'error');
            return;
        }
        try {
            const config = {
                data_start_time: document.getElementById('data-start-time').value ?
                    new Date(document.getElementById('data-start-time').value).toISOString() : null,
                data_end_time: document.getElementById('data-end-time').value ?
                    new Date(document.getElementById('data-end-time').value).toISOString() : null,
                max_rows_limit: parseInt(document.getElementById('max-rows').value) || 300000,
            };
            console.log('📦 数据配置数据:', config);
            if (!config.data_start_time || !config.data_end_time || !config.max_rows_limit) {
                this.showNotification('请填写所有必填项', 'error');
                return;
            }
            const startTime = new Date(config.data_start_time);
            const endTime = new Date(config.data_end_time);
            if (endTime <= startTime) {
                this.showNotification('结束时间必须晚于开始时间', 'error');
                return;
            }
            if (config.max_rows_limit < 1000 || config.max_rows_limit > 1000000) {
                this.showNotification('最大行数应在1000到1000000之间', 'error');
                return;
            }
            this.showLoading('正在保存数据配置...');
            const result = await ModelTrainingAPI.saveDeviceDataConfig(deviceId, config);
            console.log('✅ 保存成功:', result);
            this.showNotification('数据配置保存成功！', 'success');
            document.getElementById('data-config-modal').classList.remove('active');
            this.state.selectedDevice = null;
        } catch (error) {
            console.error('❌ 保存数据配置失败:', error);
            this.showNotification(`保存失败: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    },
    // 计算并更新平均精度
calculateAndUpdateAvgAccuracy: function(devices) {
    const r2Scores = [];
    for (const device of devices) {
        const r2 = device.latest_r2_score;
        if (r2 !== null && r2 !== undefined && typeof r2 === 'number' && !isNaN(r2)) {
            r2Scores.push(r2);
        }
    }
    let avgAccuracy = 0;
    let avgPercent = 0;
    if (r2Scores.length > 0) {
        const sum = r2Scores.reduce((a, b) => a + b, 0);
        avgAccuracy = sum / r2Scores.length;
        avgPercent = avgAccuracy * 100; // 转为百分比
    }
    const avgElem = document.getElementById('avg-accuracy');
    if (avgElem) {
        avgElem.textContent = `${avgPercent.toFixed(1)}%`;
        avgElem.title = `基于 ${r2Scores.length} 个设备的最新 R² 计算，平均 R² = ${avgAccuracy.toFixed(4)}`;
    }
},
    // 重置为默认配置
    resetToDefaults: async function() {
        if (!confirm('确定要重置为默认配置吗？这将清除所有自定义设置。')) {
            return;
        }
        try {
            const defaultConfig = await ModelTrainingAPI.getDefaultDataConfig();
            this.populateDataConfigForm({}, defaultConfig);
            this.showNotification('已重置为默认配置', 'info');
        } catch (error) {
            console.error('❌ 重置配置失败:', error);
            this.showNotification('重置配置失败', 'error');
        }
    },
    getSelectedDevices() {
    const checkboxes = document.querySelectorAll('.device-checkbox:checked');
    const deviceIds = [];
    checkboxes.forEach(cb => {
        const id = parseInt(cb.getAttribute('data-device-id'));
        if (!isNaN(id)) deviceIds.push(id);
    });
    return deviceIds;
},
bindSelectAll() {
    const selectAllCheckbox = document.getElementById('select-all');
    if (!selectAllCheckbox) return;

    // 移除原有监听器，避免重复绑定
    const newCheckbox = selectAllCheckbox.cloneNode(true);
    selectAllCheckbox.parentNode.replaceChild(newCheckbox, selectAllCheckbox);

    newCheckbox.addEventListener('change', (e) => {
        const isChecked = e.target.checked;
        const allCheckboxes = document.querySelectorAll('.device-checkbox');
        allCheckboxes.forEach(cb => {
            cb.checked = isChecked;
        });
    });
},
// 根据输出模式控制预测步长输入框（仅用于界面提示，不再禁用）
updateForecastHorizonByMode: function() {
    const modeSelect = document.getElementById('output-mode');
    const horizonInput = document.getElementById('forecast-horizon');
    if (!modeSelect || !horizonInput) return;
    const isMulti = modeSelect.value === 'multi';
    if (isMulti) {
        horizonInput.placeholder = "直接多步输出步数（1-24）";
    } else {
        horizonInput.placeholder = "递归预测步数（1-24）";
    }
    // 不再禁用输入框，也不强制改值为1
},
    // 绑定数据配置弹窗事件
    bindDataConfigModalEvents: function() {
        const modal = document.getElementById('data-config-modal');
        if (!modal) return;
        const closeBtns = modal.querySelectorAll('.modal-close, #data-config-cancel');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                modal.classList.remove('active');
                this.state.selectedDevice = null;
            });
        });
        document.getElementById('data-config-save')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.saveDataConfig();
        });
        document.getElementById('data-config-reset')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.resetToDefaults();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                e.preventDefault();
                modal.classList.remove('active');
                this.state.selectedDevice = null;
            }
        });
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                e.preventDefault();
                modal.classList.remove('active');
                this.state.selectedDevice = null;
            }
        });
    },

    // 真实训练
    // ==================== 修改后的 realTraining ====================
realTraining: async function(deviceId, deviceName) {
    console.log(`⚡ 真实训练设备 ${deviceId}: ${deviceName}`);
    const confirmed = await this.showConfirmDialog(
        `确定要执行真实训练设备 "${deviceName}" 吗？`,
        '这将从MySQL加载真实数据并训练XGBoost模型，训练一次后不会自动预测。'
    );
    if (!confirmed) return;
    try {
        // 获取输出模式和步长
        const modeSelect = document.getElementById('output-mode');
        const horizonInput = document.getElementById('forecast-horizon');
        let forecastHorizon = horizonInput ? parseInt(horizonInput.value) : 1;
        if (isNaN(forecastHorizon)) forecastHorizon = 1;
        this.showLoading('正在从MySQL加载数据并训练模型...');
        const result = await ModelTrainingAPI.realTraining(deviceId, {
            lookback_days: 30,
            train_ratio: 0.8,
            look_back: 24,
            forecast_horizon: forecastHorizon   // 使用修正后的步长
        });
        console.log('✅ 真实训练结果:', result);
        if (result.training_success) {
            this.showNotification(`设备 ${deviceName} 真实训练成功！R²分数: ${result.performance_metrics?.r2_score?.toFixed(4) || 'N/A'}`, 'success');
            this.showTrainingDetails(result);
            setTimeout(() => this.loadDeviceModels(), 1000);
        } else {
            this.showNotification(`真实训练失败: ${result.error_message || '未知错误'}`, 'error');
        }
    } catch (error) {
        console.error('❌ 真实训练失败:', error);
        this.showNotification(`真实训练失败: ${error.message}`, 'error');
    } finally {
        this.hideLoading();
    }
},

    // 自定义确认对话框
    showConfirmDialog: function(title, message) {
        return new Promise((resolve) => {
            const dialog = document.createElement('div');
            dialog.className = 'confirm-dialog';
            dialog.innerHTML = `
                <div class="confirm-dialog-content">
                    <div class="confirm-dialog-header">
                        <h3><i class="fas fa-question-circle"></i> ${title}</h3>
                    </div>
                    <div class="confirm-dialog-body">
                        <p>${message}</p>
                    </div>
                    <div class="confirm-dialog-footer">
                        <button class="btn btn-secondary" id="confirm-cancel">取消</button>
                        <button class="btn btn-primary" id="confirm-ok">确定</button>
                    </div>
                </div>
            `;
            document.body.appendChild(dialog);
            setTimeout(() => dialog.classList.add('active'), 10);
            dialog.querySelector('#confirm-cancel').onclick = () => {
                dialog.classList.remove('active');
                setTimeout(() => {
                    document.body.removeChild(dialog);
                    resolve(false);
                }, 300);
            };
            dialog.querySelector('#confirm-ok').onclick = () => {
                dialog.classList.remove('active');
                setTimeout(() => {
                    document.body.removeChild(dialog);
                    resolve(true);
                }, 300);
            };
        });
    },

    // 显示训练详情
    showTrainingDetails: function(result) {
        let message = `训练完成！\n\n`;
        message += `设备ID: ${result.device_id}\n`;
        message += `目标特征: ${result.target_feature}\n`;
        message += `训练状态: ${result.training_success ? '成功' : '失败'}\n\n`;
        if (result.performance_metrics) {
            message += `性能指标:\n`;
            message += `  R²分数: ${result.performance_metrics.r2_score?.toFixed(4) || 'N/A'}\n`;
            message += `  RMSE: ${result.performance_metrics.rmse?.toFixed(4) || 'N/A'}\n`;
            message += `  MAE: ${result.performance_metrics.mae?.toFixed(4) || 'N/A'}\n`;
            message += `  MAPE: ${result.performance_metrics.mape?.toFixed(2) || 'N/A'}%\n`;
        }
        if (result.data_info) {
            message += `\n数据信息:\n`;
            message += `  训练样本: ${result.data_info.train_samples || 0}\n`;
            message += `  测试样本: ${result.data_info.test_samples || 0}\n`;
            message += `  特征数量: ${result.data_info.feature_count || 0}\n`;
        }
        alert(message);
    },

    // 格式化日期时间
    formatDateTime: function(dateString) {
        if (!dateString) return '-';
        try {
            const date = new Date(dateString);
            return date.toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        } catch (e) {
            return dateString;
        }
    },

    // 格式化训练时间
    formatTrainingTime: function(trainingTime) {
        if (!trainingTime) return '0s';
        let totalSeconds = 0;
        if (typeof trainingTime === 'number') {
            totalSeconds = trainingTime;
        } else if (typeof trainingTime === 'string') {
            totalSeconds = parseFloat(trainingTime) || 0;
        } else if (trainingTime && typeof trainingTime === 'object') {
            if (trainingTime.seconds !== undefined) totalSeconds = trainingTime.seconds || 0;
            else if (trainingTime.total_seconds !== undefined) totalSeconds = trainingTime.total_seconds || 0;
        }
        if (totalSeconds < 60) return `${Math.round(totalSeconds)}s`;
        if (totalSeconds < 3600) {
            const minutes = Math.floor(totalSeconds / 60);
            const seconds = Math.round(totalSeconds % 60);
            return seconds > 0 ? `${minutes}m${seconds}s` : `${minutes}m`;
        }
        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        return minutes > 0 ? `${hours}h${minutes}m` : `${hours}h`;
    },

    // 保存训练设置
    saveTrainingSettings: async function() {
         console.log('💾 保存训练设置...');
    const deviceId = this.state.selectedDevice;
    if (!deviceId) {
        this.showNotification('请先选择设备', 'error');
        return;
    }

    // 获取输出模式和步长
    const modeSelect = document.getElementById('output-mode');
    const outputMode = modeSelect ? modeSelect.value : 'single';
    const horizonInput = document.getElementById('forecast-horizon');
    let outputCount = horizonInput ? parseInt(horizonInput.value) : 1;
    if (isNaN(outputCount) || outputCount < 1) outputCount = 1;

    const settings = {
        device_id: deviceId,
        train_start_time: document.getElementById('train-start-time').value,
        train_interval_value: this.getIntervalValue(document.getElementById('train-interval').value),
        train_interval_unit: this.getIntervalUnit(document.getElementById('train-interval').value),
        train_end_time: document.getElementById('train-end-time').value || null,
        train_is_active: document.getElementById('training-stop-btn').style.display !== 'none',
        predict_start_time: document.getElementById('predict-start-time').value,
        predict_interval_value: this.getIntervalValue(document.getElementById('predict-interval').value),
        predict_interval_unit: this.getIntervalUnit(document.getElementById('predict-interval').value),
        predict_end_time: document.getElementById('predict-end-time').value || null,
        predict_is_active: document.getElementById('predict-stop-btn').style.display !== 'none',
        output_mode: outputMode,
        output_count: outputCount
    };
        console.log('📦 训练设置数据:', settings);
        const isEmptyOrNull = (value) => !value || value === '' || value === 'null' || value === 'undefined';
        if (isEmptyOrNull(settings.train_start_time)) {
            this.showNotification('请选择训练开始时间', 'error');
            return;
        }
        if (isEmptyOrNull(settings.predict_start_time)) {
            this.showNotification('请选择预测开始时间', 'error');
            return;
        }
        if (settings.train_end_time) {
            const trainStart = new Date(settings.train_start_time);
            const trainEnd = new Date(settings.train_end_time);
            if (trainEnd <= trainStart) {
                alert('错误：训练结束时间必须晚于开始时间！');
                return;
            }
        }
        if (settings.predict_end_time) {
            const predictStart = new Date(settings.predict_start_time);
            const predictEnd = new Date(settings.predict_end_time);
            if (predictEnd <= predictStart) {
                alert('错误：预测结束时间必须晚于开始时间！');
                return;
            }
        }
        try {
            this.showLoading('正在保存训练设置...');
            const toUTCString = (localDateTimeString) => {
                if (!localDateTimeString) return null;
                const localDate = new Date(localDateTimeString);
                return localDate.toISOString();
            };
            const requestData = {
                device_id: deviceId,
                train_start_time: toUTCString(settings.train_start_time),
                train_interval_value: settings.train_interval_value,
                train_interval_unit: settings.train_interval_unit,
                train_end_time: settings.train_end_time ? toUTCString(settings.train_end_time) : null,
                train_is_active: settings.train_is_active,
                predict_start_time: toUTCString(settings.predict_start_time),
                predict_interval_value: settings.predict_interval_value,
                predict_interval_unit: settings.predict_interval_unit,
                predict_end_time: settings.predict_end_time ? toUTCString(settings.predict_end_time) : null,
                predict_is_active: settings.predict_is_active,
                output_mode: settings.output_mode,
                output_count: settings.output_count
            };
            console.log('🚀 发送到后端的请求数据:', requestData);
            const response = await fetch(`http://localhost:8000/api/v1/model_training/save_settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });
            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ 后端错误响应:', errorText);
                let errorMessage = `HTTP ${response.status}`;
                try {
                    const errorData = JSON.parse(errorText);
                    errorMessage = errorData.detail || errorMessage;
                    if (errorMessage.includes('结束时间必须晚于开始时间') ||
                        errorMessage.includes('ck_valid_time_range') ||
                        errorMessage.includes('CheckViolation')) {
                        errorMessage = '时间设置错误：结束时间必须晚于开始时间';
                    }
                } catch (e) {
                    if (errorText.includes('end_time > start_time') || errorText.includes('ck_valid_time_range')) {
                        errorMessage = '时间设置错误：结束时间必须晚于开始时间';
                    } else {
                        errorMessage = errorText.substring(0, 200);
                    }
                }
                throw new Error(errorMessage);
            }
            const result = await response.json();
            console.log('✅ 保存成功:', result);
            this.showNotification(result.message || '训练设置保存成功！', 'success');
            document.getElementById('training-modal').classList.remove('active');
            this.state.selectedDevice = null;
            setTimeout(() => this.loadDeviceModels(), 2000);
        } catch (error) {
            console.error('❌ 保存训练设置失败:', error);
            let userMessage = error.message;
            if (userMessage.includes('结束时间必须晚于开始时间')) {
                userMessage = '时间设置错误：结束时间必须晚于开始时间';
                alert(userMessage);
            } else if (userMessage.includes('CheckViolation') || userMessage.includes('违反检查约束')) {
                userMessage = '时间设置错误：请检查开始时间和结束时间的顺序';
                alert(userMessage);
            } else if (userMessage.includes('HTTP')) {
                userMessage = '保存失败，请检查网络连接或联系管理员';
            }
            this.showNotification(`保存失败: ${userMessage}`, 'error');
        } finally {
            this.hideLoading();
        }
    },

    // 获取时间配置选项
    getTimeOptions: function() {
        return {
            trainIntervals: [
                { value: '1h', label: '每小时', minutes: 60 },
                { value: '6h', label: '每6小时', minutes: 360 },
                { value: '12h', label: '每12小时', minutes: 720 },
                { value: '24h', label: '每天', minutes: 1440 },
                { value: '168h', label: '每周', minutes: 10080 }
            ],
            predictIntervals: [
                { value: '5min', label: '每5分钟', minutes: 5 },
                { value: '15min', label: '每15分钟', minutes: 15 },
                { value: '30min', label: '每30分钟', minutes: 30 },
                { value: '1h', label: '每小时', minutes: 60 },
                { value: '2h', label: '每2小时', minutes: 120 }
            ]
        };
    },

    // 设置立即开始时间
    setNowTime: function(elementId) {
        const now = new Date();
        const nowStr = now.toISOString().slice(0, 16);
        document.getElementById(elementId).value = nowStr;
        return now;
    },

    // 设置默认结束时间
    setDefaultEndTime: function(startElementId, endElementId, offsetHours = 24) {
        const startInput = document.getElementById(startElementId);
        if (startInput.value) {
            const startTime = new Date(startInput.value);
            const endTime = new Date(startTime.getTime() + offsetHours * 60 * 60 * 1000);
            document.getElementById(endElementId).value = endTime.toISOString().slice(0, 16);
        }
    },

    // 格式化时间为本地时间字符串
    formatLocalTimeString: function(date) {
        if (!date) return '';
        const d = new Date(date);
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hours = String(d.getHours()).padStart(2, '0');
        const minutes = String(d.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day}T${hours}:${minutes}`;
    },

    // 获取设备默认配置
    async getDeviceConfig(deviceId) {
        try {
            const response = await fetch(`http://localhost:8000/api/v1/model_training/${deviceId}/config`);
            if (!response.ok) {
                console.warn('获取设备配置失败，使用默认配置');
                return this.getDefaultConfig();
            }
            return await response.json();
        } catch (error) {
            console.error('获取设备配置失败:', error);
            return this.getDefaultConfig();
        }
    },

    // 获取默认配置
    getDefaultConfig: function() {
        const now = new Date();
        const tomorrow = new Date(now.getTime() + 24 * 60 * 60 * 1000);
        const nextWeek = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
        return {
            train_start_time: this.formatLocalTimeString(now),
            train_end_time: this.formatLocalTimeString(tomorrow),
            predict_start_time: this.formatLocalTimeString(now),
            predict_end_time: this.formatLocalTimeString(nextWeek),
            train_interval: '12h',
            predict_interval: '5min'
        };
    },

    // 停止/启动训练计划
    async toggleScheduleStatus(scheduleId, deviceId, scheduleType) {
        try {
            this.showLoading('正在更新任务状态...');
            const response = await fetch(`http://localhost:8000/api/v1/model_training/schedule/${scheduleId}/toggle`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            const result = await response.json();
            this.showNotification(result.message, result.is_active ? 'success' : 'warning');
            setTimeout(() => this.loadDeviceModels(), 1000);
        } catch (error) {
            console.error('❌ 更新任务状态失败:', error);
            this.showNotification(`更新任务状态失败: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    },

    // 显示训练配置弹窗
// ==================== 修改后的 showTrainingConfig ====================
async showTrainingConfig(deviceId, deviceName, projectName, modelName) {
    console.log(`⚙️ 显示训练配置弹窗，设备ID: ${deviceId}`);
    this.state.selectedDevice = deviceId;
    document.getElementById('modal-project-name').textContent = projectName;
    document.getElementById('modal-device-name').textContent = deviceName;
    document.getElementById('modal-device-model').textContent = modelName;

    try {
        const existingSchedules = await this.getDeviceTrainingSchedules(deviceId);
        if (existingSchedules && existingSchedules.length > 0) {
            console.log('📋 找到已有配置:', existingSchedules);
            const trainSchedule = existingSchedules.find(s => s.schedule_type === 'train');
            const predictSchedule = existingSchedules.find(s => s.schedule_type === 'predict');

            // 处理训练计划
            if (trainSchedule) {
                document.getElementById('train-start-time').value = this.formatLocalTimeString(trainSchedule.start_time);
                document.getElementById('train-interval').value = this.convertIntervalToSelectValue(
                    trainSchedule.interval_value, trainSchedule.interval_unit, 'train');
                if (trainSchedule.end_time) document.getElementById('train-end-time').value = this.formatLocalTimeString(trainSchedule.end_time);
                this.updateScheduleButton('train', trainSchedule.is_active);
            } else {
                this.setNowTime('train-start-time');
                document.getElementById('train-interval').value = '12h';
                this.updateScheduleButton('train', false);
            }

            // 处理预测计划
            if (predictSchedule) {
                document.getElementById('predict-start-time').value = this.formatLocalTimeString(predictSchedule.start_time);
                document.getElementById('predict-interval').value = this.convertIntervalToSelectValue(
                    predictSchedule.interval_value, predictSchedule.interval_unit, 'predict');
                if (predictSchedule.end_time) document.getElementById('predict-end-time').value = this.formatLocalTimeString(predictSchedule.end_time);
                this.updateScheduleButton('predict', predictSchedule.is_active);

                // 设置输出模式和步长
                const modeSelect = document.getElementById('output-mode');
                const horizonInput = document.getElementById('forecast-horizon');
                if (modeSelect) {
                    modeSelect.value = predictSchedule.output_mode === 'multi' ? 'multi' : 'single';
                }
                if (horizonInput) {
                    horizonInput.value = predictSchedule.output_count ? predictSchedule.output_count : 1;
                }
                // 根据模式更新步长输入框的禁用状态
                this.updateForecastHorizonByMode();
            } else {
                this.setNowTime('predict-start-time');
                document.getElementById('predict-interval').value = '5min';
                this.updateScheduleButton('predict', false);

                // 没有预测计划时，默认单输出，步长1
                const modeSelect = document.getElementById('output-mode');
                if (modeSelect) modeSelect.value = 'single';
                const horizonInput = document.getElementById('forecast-horizon');
                if (horizonInput) horizonInput.value = 1;
                this.updateForecastHorizonByMode();
            }
        } else {
            console.log('📋 未找到已有配置，使用默认值');
            this.setNowTime('train-start-time');
            document.getElementById('train-interval').value = '12h';
            this.updateScheduleButton('train', false);
            this.setNowTime('predict-start-time');
            document.getElementById('predict-interval').value = '5min';
            this.updateScheduleButton('predict', false);

            // 默认单输出，步长1
            const modeSelect = document.getElementById('output-mode');
            if (modeSelect) modeSelect.value = 'single';
            const horizonInput = document.getElementById('forecast-horizon');
            if (horizonInput) horizonInput.value = 1;
            this.updateForecastHorizonByMode();
        }
    } catch (error) {
        console.error('加载配置失败，使用默认值:', error);
        this.setNowTime('train-start-time');
        document.getElementById('train-interval').value = '12h';
        this.updateScheduleButton('train', false);
        this.setNowTime('predict-start-time');
        document.getElementById('predict-interval').value = '5min';
        this.updateScheduleButton('predict', false);

        const modeSelect = document.getElementById('output-mode');
        if (modeSelect) modeSelect.value = 'single';
        const horizonInput = document.getElementById('forecast-horizon');
        if (horizonInput) horizonInput.value = 1;
        this.updateForecastHorizonByMode();
    }

    // 绑定输出模式切换事件（避免重复绑定）
    const modeSelect = document.getElementById('output-mode');
    if (modeSelect && !modeSelect._listenerAdded) {
        modeSelect.addEventListener('change', () => this.updateForecastHorizonByMode());
        modeSelect._listenerAdded = true;
    }

    document.getElementById('training-modal').classList.add('active');
},


    // 获取设备训练计划
    async getDeviceTrainingSchedules(deviceId) {
        try {
            const response = await fetch(`http://localhost:8000/api/v1/model_training/schedules/device/${deviceId}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('❌ 获取设备训练计划失败:', error);
            return null;
        }
    },

    // 转换间隔值为选择框值
    convertIntervalToSelectValue(intervalValue, intervalUnit, type) {
        if (type === 'train') {
            let hours = intervalValue;
            if (intervalUnit === 'minutes') hours = intervalValue / 60;
            else if (intervalUnit === 'days') hours = intervalValue * 24;
            const trainOptions = [1, 6, 12, 24, 168];
            const closest = trainOptions.reduce((prev, curr) => Math.abs(curr - hours) < Math.abs(prev - hours) ? curr : prev);
            return `${closest}h`;
        } else {
            let minutes = intervalValue;
            if (intervalUnit === 'hours') minutes = intervalValue * 60;
            else if (intervalUnit === 'days') minutes = intervalValue * 24 * 60;
            const predictOptions = [5, 15, 30, 60, 120];
            const closest = predictOptions.reduce((prev, curr) => Math.abs(curr - minutes) < Math.abs(prev - minutes) ? curr : prev);
            return `${closest}min`;
        }
    },

    // 绑定训练配置弹窗事件
    bindTrainingModalEvents: function() {
        const modal = document.getElementById('training-modal');
        if (!modal) return;
        const closeBtns = modal.querySelectorAll('.modal-close, #training-cancel');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                modal.classList.remove('active');
                this.state.selectedDevice = null;
            });
        });
        document.getElementById('training-save')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.saveTrainingSettings();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                e.preventDefault();
                modal.classList.remove('active');
                this.state.selectedDevice = null;
            }
        });
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                e.preventDefault();
                modal.classList.remove('active');
                this.state.selectedDevice = null;
            }
        });
    },

    // 保存训练配置（兼容旧名称）
    saveTrainingConfig: async function() {
        await this.saveTrainingSettings();
    },

    // 获取间隔值
    getIntervalValue: function(intervalString) {
        const match = intervalString.match(/(\d+)/);
        return match ? parseInt(match[1]) : 1;
    },

    // 获取间隔单位
    getIntervalUnit: function(intervalString) {
        if (intervalString.includes('min')) return 'minutes';
        if (intervalString.includes('h')) return 'hours';
        if (intervalString.includes('d')) return 'days';
        return 'hours';
    },

    // 显示通知
    showNotification: function(message, type = 'info', duration = null) {
    // 根据类型设置默认显示时长（毫秒）
    if (duration === null) {
        switch (type) {
            case 'error':
                duration = 8000;
                break;
            case 'warning':
                duration = 5000;
                break;
            default:
                duration = 4000;
        }
    }

    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
        <button class="notification-close">&times;</button>
    `;
    const container = document.getElementById('notifications') || this.createNotificationContainer();
    container.appendChild(notification);

    // 设置自动消失定时器
    let timeoutId = setTimeout(() => {
        if (notification.parentNode) {
            notification.classList.add('fade-out');
            setTimeout(() => {
                if (notification.parentNode) notification.parentNode.removeChild(notification);
            }, 300);
        }
    }, duration);

    // 手动关闭时取消自动消失定时器，并移除通知
    const closeBtn = notification.querySelector('.notification-close');
    closeBtn.addEventListener('click', () => {
        clearTimeout(timeoutId);
        notification.classList.add('fade-out');
        setTimeout(() => {
            if (notification.parentNode) notification.parentNode.removeChild(notification);
        }, 300);
    });
},

    // 创建通知容器
    createNotificationContainer: function() {
        const container = document.createElement('div');
        container.id = 'notifications';
        container.className = 'notifications-container';
        document.body.appendChild(container);
        return container;
    },

    // 显示加载状态
    showLoading: function(message = '正在处理...') {
        let loadingEl = document.getElementById('global-loading');
        if (!loadingEl) {
            loadingEl = document.createElement('div');
            loadingEl.id = 'global-loading';
            loadingEl.className = 'global-loading';
            loadingEl.innerHTML = `
                <div class="loading-overlay">
                    <div class="loading-content">
                        <i class="fas fa-spinner fa-spin"></i>
                        <div class="loading-message">${message}</div>
                    </div>
                </div>
            `;
            document.body.appendChild(loadingEl);
        }
        loadingEl.style.display = 'block';
    },

    // 隐藏加载状态
    hideLoading: function() {
        const loadingEl = document.getElementById('global-loading');
        if (loadingEl) loadingEl.style.display = 'none';
    },

    // 初始化
    async init() {
        console.log('🚀 初始化模型训练页面');
        if (typeof ModelTrainingAPI === 'undefined') {
            console.error('❌ ModelTrainingAPI未定义，无法初始化');
            this.showError('模型训练API模块未加载，请刷新页面');
            return;
        }
        await this.testAPI();
        TrainerConfigManager.init();
        await this.loadFilters();
        await this.loadDeviceModels();
        this.bindEvents();
        console.log('✅ 模型训练页面初始化完成');
    },

    // 开始任务
    async startSchedule(scheduleType) {
        console.log(`🚀 开始任务: scheduleType=${scheduleType}`);
        const deviceId = this.state.selectedDevice;
        if (!deviceId) {
            this.showNotification('请先选择设备', 'error');
            return;
        }
        try {
            this.updateScheduleButton(scheduleType, true);
            this.showLoading(`正在开始${scheduleType === 'train' ? '训练' : '预测'}任务...`);
            const response = await fetch(`http://localhost:8000/api/v1/model_training/schedule/start/${deviceId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ schedule_type: scheduleType })
            });
            if (!response.ok) {
                const errorText = await response.text();
                this.updateScheduleButton(scheduleType, false);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            const result = await response.json();
            console.log('✅ 开始任务成功:', result);
            this.showNotification(result.message, 'success');
            setTimeout(() => this.loadDeviceModels(), 2000);
        } catch (error) {
            console.error(`❌ 开始${scheduleType === 'train' ? '训练' : '预测'}任务失败:`, error);
            this.showNotification(`开始任务失败: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    },

    // 停止任务
    async stopSchedule(scheduleType) {
        console.log(`🛑 停止任务: scheduleType=${scheduleType}`);
        const deviceId = this.state.selectedDevice;
        if (!deviceId) {
            this.showNotification('请先选择设备', 'error');
            return;
        }
        try {
            this.updateScheduleButton(scheduleType, false);
            this.showLoading(`正在停止${scheduleType === 'train' ? '训练' : '预测'}任务...`);
            const response = await fetch(`http://localhost:8000/api/v1/model_training/schedule/stop/${deviceId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ schedule_type: scheduleType })
            });
            if (!response.ok) {
                const errorText = await response.text();
                this.updateScheduleButton(scheduleType, true);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            const result = await response.json();
            console.log('✅ 停止任务成功:', result);
            this.showNotification(result.message, 'warning');
            setTimeout(() => this.loadDeviceModels(), 2000);
        } catch (error) {
            console.error(`❌ 停止${scheduleType === 'train' ? '训练' : '预测'}任务失败:`, error);
            this.showNotification(`停止任务失败: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    },

    // 更新按钮状态
    updateScheduleButton: function(scheduleType, isActive) {
        const startBtnId = `${scheduleType === 'train' ? 'training' : 'predict'}-schedule-btn`;
        const stopBtnId = `${scheduleType === 'train' ? 'training' : 'predict'}-stop-btn`;
        const startBtn = document.getElementById(startBtnId);
        const stopBtn = document.getElementById(stopBtnId);
        if (startBtn && stopBtn) {
            if (isActive) {
                startBtn.style.display = 'none';
                stopBtn.style.display = 'inline-block';
            } else {
                startBtn.style.display = 'inline-block';
                stopBtn.style.display = 'none';
            }
        } else {
            console.error(`找不到按钮: ${startBtnId}, ${stopBtnId}`);
        }
    },

    // 测试API连通性
    async testAPI() {
        console.log('🔗 测试API连通性...');
        try {
            const response = await fetch('http://localhost:8000/health');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            console.log('✅ 后端服务健康检查通过');
        } catch (error) {
            console.error('❌ API测试失败:', error);
            this.showError(`后端连接失败: ${error.message}\n请确保后端服务运行在 http://localhost:8000`);
        }
    },

    // 显示错误信息
    showError(message) {
        const tableBody = document.getElementById('model-table-body');
        if (tableBody) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="8" class="error">
                        <div class="error-content">
                            <i class="fas fa-exclamation-triangle"></i>
                            <div class="error-message">${message}</div>
                            <button class="btn btn-primary" onclick="ModelTrainingManager.retry()">
                                <i class="fas fa-redo"></i> 重试
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }
    },

    // 重试
    async retry() {
        console.log('🔄 重新加载数据...');
        await this.loadDeviceModels();
    },

    // 加载筛选器
    async loadFilters() {
        console.log('📋 加载筛选器...');
        try {
            const result = await ModelTrainingAPI.getProjects();
            const projects = result.projects || result.data || result || [];
            const projectSelect = document.getElementById('filter-project');
            projectSelect.innerHTML = '<option value="">全部项目</option>';
            projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.id;
                option.textContent = `${project.name} (${project.code})`;
                projectSelect.appendChild(option);
            });
            console.log(`✅ 加载了 ${projects.length} 个项目到筛选器`);
        } catch (error) {
            console.error('❌ 加载筛选器失败:', error);
        }
    },

    // 加载设备模型数据
    async loadDeviceModels() {
        console.log('📋 加载设备模型数据...');
        const tableBody = document.getElementById('model-table-body');
        if (!tableBody) return;
        tableBody.innerHTML = `
            <tr class="loading-row">
                <td colspan="8" class="loading">
                    <i class="fas fa-spinner fa-spin"></i> 正在加载设备模型数据...
                </td>
            </tr>
        `;
        try {
            const result = await ModelTrainingAPI.getDevicesForTraining(
                this.state.filters,
                this.state.currentPage,
                this.state.pageSize
            );
            console.log('📦 设备模型数据响应:', result);
            const devices = result.devices || [];
            this.state.totalDevices = result.total || devices.length;
            console.log(`✅ 加载了 ${devices.length} 个设备模型，总计 ${this.state.totalDevices} 个`);
            this.renderDeviceModels(devices);
            this.updateStats(devices);
            this.calculateAndUpdateAvgAccuracy(devices); // 新增：计算平均精度
        } catch (error) {
            console.error('❌ 加载设备模型数据失败:', error);
            this.showError(`加载设备模型数据失败: ${error.message}`);
        }
    },

    // 渲染设备模型列表
    renderDeviceModels(devices) {
    const tableBody = document.getElementById('model-table-body');
    if (!tableBody) return;
    if (!devices || devices.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="8" class="empty-state">
                    <div class="empty-content">
                        <i class="fas fa-server"></i>
                        <div class="empty-message">暂无设备模型数据</div>
                        <button class="btn btn-primary" onclick="event.preventDefault(); ModelTrainingManager.loadDeviceModels()">
                            <i class="fas fa-redo"></i> 重新加载
                        </button>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    let html = '';
    devices.forEach(device => {
        const projectName = device.project?.name || '未知项目';
        const modelInfo = device.model_info || {};
        const modelName = modelInfo.name || '未配置';
        const versionInfo = device.version_info || {};
        const modelVersion = versionInfo.version || 'v1.0';
        let statusText = '';
        let statusClass = '';
        let statusIcon = '';
        switch (device.training_plan_status) {
            case 'active_plan':
                statusText = '训练计划进行中';
                statusClass = 'active-plan-badge';
                statusIcon = 'fas fa-play';
                break;
            case 'inactive_plan':
                statusText = '训练计划停止中';
                statusClass = 'inactive-plan-badge';
                statusIcon = 'fas fa-stop';
                break;
            default:
                statusText = '暂无训练计划';
                statusClass = 'failed-badge';
                statusIcon = 'fas fa-ban';
                break;
        }
        const lastTrainTime = device.last_train_run_at ? this.formatTime(device.last_train_run_at) : '未执行';
        html += `
            <tr>
                <td class="checkbox-cell"><input type="checkbox" class="device-checkbox" data-device-id="${device.id}"></td>
                <td>${projectName}</td>
                <td>${device.name}</td>
                <td>${modelName}</td>
                <td><span class="model-version">${modelVersion}</span></td>
                <td><span class="status-badge ${statusClass}"><i class="${statusIcon}"></i> ${statusText}</span></td>
                <td>${lastTrainTime}</td>
                <td>
                    <div class="model-actions">
                        <button class="btn-action btn-data-config" title="数据配置" type="button"
                                onclick="event.preventDefault(); ModelTrainingManager.showDataConfig(${device.id}, '${device.name}', '${projectName}')">
                            <i class="fas fa-database"></i>
                        </button>
                        <button class="btn-action btn-trainer-config" title="训练器配置" type="button"
                                onclick="event.preventDefault(); TrainerConfigManager.showTrainerConfig(${device.id}, '${device.name}', '${projectName}')">
                            <i class="fas fa-cogs"></i>
                        </button>
                        <button class="btn-action btn-real-train" title="真实训练" type="button"
                                onclick="event.preventDefault(); ModelTrainingManager.realTraining(${device.id}, '${device.name}')">
                            <i class="fas fa-brain"></i>
                        </button>
                        <button class="btn-action btn-train" title="训练设置" type="button"
                                onclick="event.preventDefault(); ModelTrainingManager.showTrainingConfig(${device.id}, '${device.name}', '${projectName}', '${modelName}')">
                            <i class="fas fa-cog"></i>
                        </button>
                        <button class="btn-action btn-metrics" title="查看参数" type="button"
                                onclick="event.preventDefault(); ModelTrainingManager.showMetrics(${device.id}, '${device.name}', '${projectName}', '${modelName}', '${modelVersion}')">
                            <i class="fas fa-chart-bar"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    });
    tableBody.innerHTML = html;

    // 重新绑定全选事件（每次渲染后重新绑定）
    this.bindSelectAll();
},

    // 更新统计信息
    updateStats(devices) {
    document.getElementById('total-models').textContent = devices.length;

    // 统计训练计划进行中（active_plan）的设备数
    const activePlanCount = devices.filter(d => d.training_plan_status === 'active_plan').length;
    document.getElementById('trained-models').textContent = activePlanCount; // 注意：这里字段名是“训练计划进行中”

    // 统计训练计划停止中（inactive_plan）的设备数
    const inactivePlanCount = devices.filter(d => d.training_plan_status === 'inactive_plan').length;
    document.getElementById('training-models').textContent = inactivePlanCount; // 注意：这里字段名是“训练计划停止中”
},

    // 格式化时间（用于表格显示）
    formatTime(dateString) {
        if (!dateString) return '-';
        try {
            const date = new Date(dateString);
            return date.toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return dateString;
        }
    },

    // 绑定事件
    bindEvents() {
        console.log('🔗 绑定事件...');
        document.getElementById('filter-project')?.addEventListener('change', (e) => {
            e.preventDefault();
            this.state.filters.projectId = e.target.value || null;
            this.state.currentPage = 1;
            this.loadDeviceModels();
        });
        document.getElementById('filter-status')?.addEventListener('change', (e) => {
            e.preventDefault();
            this.state.filters.planStatus = e.target.value || null;
            this.state.currentPage = 1;
            this.loadDeviceModels();
        });
        document.getElementById('filter-reset-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.resetFilters();
        });
        document.getElementById('start-training-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.startBatchTraining();
        });
        document.getElementById('refresh-models-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.loadDeviceModels();
        });
        this.bindTrainingModalEvents();
        this.bindScheduleButtons();
        this.bindMetricsModalEvents();
        this.bindDataConfigModalEvents();
        console.log('✅ 事件绑定完成');
    },

    // 重置筛选
    resetFilters() {
    document.getElementById('filter-project').value = '';
    document.getElementById('filter-status').value = '';
    this.state.filters = {
        projectId: null,
        deviceId: null,
        planStatus: null   // 清除计划状态筛选
    };
    this.state.currentPage = 1;
    this.loadDeviceModels();
},

    // 绑定模型参数弹窗事件
    bindMetricsModalEvents() {
        const modal = document.getElementById('metrics-modal');
        if (!modal) return;
        const closeBtns = modal.querySelectorAll('.modal-close, #metrics-close');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                modal.classList.remove('active');
            });
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                e.preventDefault();
                modal.classList.remove('active');
            }
        });
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                e.preventDefault();
                modal.classList.remove('active');
            }
        });
    },

    // 显示模型参数
    async showMetrics(deviceId, deviceName, projectName, modelName, modelVersion) {
        console.log(`📈 显示模型参数，设备ID: ${deviceId}`);
        try {
            const metrics = await this.getDeviceMetrics(deviceId);
            if (metrics && metrics.latest_evaluation) {
                this.populateRealMetrics(metrics);
            } else {
                this.populateMockMetrics(deviceId, deviceName, projectName, modelName, modelVersion);
            }
        } catch (error) {
            console.error('❌ 获取设备指标失败:', error);
            this.populateMockMetrics(deviceId, deviceName, projectName, modelName, modelVersion);
        }
        document.getElementById('metrics-modal').classList.add('active');
    },

    // 获取设备指标API
    async getDeviceMetrics(deviceId) {
        try {
            const response = await fetch(`http://localhost:8000/api/v1/model_evaluation/metrics/${deviceId}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
            return await response.json();
        } catch (error) {
            console.error('❌ 获取设备指标失败:', error);
            throw error;
        }
    },

    // 填充真实指标数据
    populateRealMetrics: function(metrics) {
        const evaluation = metrics.latest_evaluation;
        document.getElementById('metrics-project-name').textContent = metrics.project_name;
        document.getElementById('metrics-device-name').textContent = metrics.device_name;
        document.getElementById('metrics-model-version').textContent = `${metrics.model_name} ${metrics.model_version}`;
        document.getElementById('r2-score').textContent = evaluation.r_squared?.toFixed(4) || 'N/A';
        document.getElementById('rmse-score').textContent = evaluation.rmse?.toFixed(4) || 'N/A';
        document.getElementById('mae-score').textContent = evaluation.mae?.toFixed(4) || 'N/A';
        document.getElementById('training-time').textContent = this.formatTrainingTime(evaluation.training_time);
        document.getElementById('train-data-size').textContent = evaluation.training_data_size ? `${evaluation.training_data_size} 条` : 'N/A';
        document.getElementById('test-data-size').textContent = evaluation.test_data_size ? `${evaluation.test_data_size} 条` : 'N/A';
        document.getElementById('feature-count').textContent = evaluation.feature_count ? `${evaluation.feature_count} 个` : 'N/A';
        document.getElementById('last-update').textContent = metrics.last_train_run_at ? this.formatTime(metrics.last_train_run_at) : 'N/A';
        if (evaluation.r_squared !== undefined && evaluation.r_squared !== null) {
            this.addPerformanceRating(evaluation.r_squared);
        }
    },

    // 填充模拟指标数据
    populateMockMetrics: function(deviceId, deviceName, projectName, modelName, modelVersion) {
        document.getElementById('metrics-project-name').textContent = projectName;
        document.getElementById('metrics-device-name').textContent = deviceName;
        document.getElementById('metrics-model-version').textContent = `${modelName} ${modelVersion}`;
        const r2 = 0.85 + Math.random() * 0.1;
        document.getElementById('r2-score').textContent = r2.toFixed(4);
        document.getElementById('rmse-score').textContent = (0.1 + Math.random() * 0.05).toFixed(4);
        document.getElementById('mae-score').textContent = (0.08 + Math.random() * 0.04).toFixed(4);
        const mockTrainingTime = Math.floor(Math.random() * 1200) + 300;
        document.getElementById('training-time').textContent = this.formatTrainingTime(mockTrainingTime);
        document.getElementById('train-data-size').textContent = '14181 条';
        document.getElementById('test-data-size').textContent = '2836 条';
        document.getElementById('feature-count').textContent = '15 个';
        document.getElementById('last-update').textContent = '未执行';
        this.addPerformanceRating(r2);
    },

    // 添加性能评级
    addPerformanceRating(r2) {
        let rating = '', color = '';
        if (r2 >= 0.9) { rating = '优秀'; color = '#4CAF50'; }
        else if (r2 >= 0.8) { rating = '良好'; color = '#8BC34A'; }
        else if (r2 >= 0.7) { rating = '一般'; color = '#FFC107'; }
        else { rating = '较差'; color = '#F44336'; }
        const r2Element = document.getElementById('r2-score');
        if (r2Element) {
            r2Element.style.color = color;
            r2Element.innerHTML = `${r2.toFixed(4)} <span style="font-size: 14px; color: ${color};">(${rating})</span>`;
        }
    },

    // 开始批量训练
  async startBatchTraining() {
    const selectedDevices = this.getSelectedDevices();
    if (selectedDevices.length === 0) {
        this.showNotification('请先选择要训练的设备', 'warning');
        return;
    }
    if (!confirm(`确定要对 ${selectedDevices.length} 个设备执行批量训练吗？`)) return;

    try {
        this.showLoading('正在提交批量训练任务...');
        const result = await ModelTrainingAPI.batchTraining(selectedDevices);

        // 打印完整结果到控制台
        console.log('批量训练结果详情:', result);

        // 构建通知消息
        let notificationMsg = `批量训练提交完成：成功 ${result.success}，失败 ${result.failed}`;
        if (result.failed > 0) {
            const failedDevices = result.results.filter(r => r.status !== 'success');
            const failedSummary = failedDevices.map(r => `设备 ${r.device_id}: ${r.message}`).join('; ');
            notificationMsg += `。失败详情：${failedSummary}`;
            console.warn('失败设备详情:', failedDevices);
        }
        this.showNotification(notificationMsg, result.failed > 0 ? 'warning' : 'info');

        // 可选：如果失败数量较多，可以弹出一个详细对话框（这里保持简单）
        setTimeout(() => this.loadDeviceModels(), 3000);
    } catch (error) {
        console.error('批量训练请求失败:', error);
        this.showNotification(`批量训练失败: ${error.message}`, 'error');
    } finally {
        this.hideLoading();
    }
},
    // 绑定开始/停止按钮事件
    bindScheduleButtons: function() {
        document.getElementById('training-schedule-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.updateScheduleButton('train', true);
        });
        document.getElementById('training-stop-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.updateScheduleButton('train', false);
        });
        document.getElementById('predict-schedule-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.updateScheduleButton('predict', true);
        });
        document.getElementById('predict-stop-btn')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.updateScheduleButton('predict', false);
        });
    }
};

// 训练器配置管理器
const TrainerConfigManager = {
    state: {
        currentDeviceId: null,
        currentDeviceName: null,
        currentProjectName: null,
        trainerConfigs: []
    },

    init: function() {
        console.log('🔧 TrainerConfigManager 初始化');
        this.bindModalEvents();
    },

    showTrainerConfig: async function(deviceId, deviceName, projectName) {
        console.log(`⚙️ 显示训练器配置弹窗，设备ID: ${deviceId}`);
        this.state.currentDeviceId = deviceId;
        this.state.currentDeviceName = deviceName;
        this.state.currentProjectName = projectName;
        document.getElementById('trainer-config-device-name').textContent = deviceName;
        document.getElementById('trainer-config-project-name').textContent = projectName;
        try {
            await this.loadTrainerConfigs(deviceId);
            document.getElementById('trainer-config-modal').classList.add('active');
        } catch (error) {
            console.error('❌ 加载训练器配置失败:', error);
            this.showNotification('加载训练器配置失败', 'error');
        }
    },

    loadTrainerConfigs: async function(deviceId) {
        console.log(`📋 加载训练器配置，设备ID: ${deviceId}`);
        try {
            const configs = await this.getDeviceTrainerConfigs(deviceId);
            this.state.trainerConfigs = configs;
            this.renderTrainerConfigs(configs);
            return configs;
        } catch (error) {
            console.error('❌ 获取训练器配置失败:', error);
            throw error;
        }
    },

    getDeviceTrainerConfigs: async function(deviceId) {
        console.log(`🌐 调用训练器配置API，设备ID: ${deviceId}`);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/trainer_config/device/${deviceId}`);
            if (!response.ok) {
                if (response.status === 404) return [];
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error('❌ 获取训练器配置API失败:', error);
            throw error;
        }
    },

    renderTrainerConfigs: function(configs) {
        const tbody = document.getElementById('trainer-config-tbody');
        if (!tbody) {
            console.error('❌ 找不到训练器配置表格体');
            return;
        }
        if (!configs || configs.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="5" class="empty-state">
                        <div class="empty-content">
                            <i class="fas fa-cogs"></i>
                            <div class="empty-message">暂无训练器配置</div>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }
        let html = '';
        configs.forEach(config => {
            let statusBadge = '';
            if (config.is_primary && config.is_active) {
                statusBadge = `<span class="status-badge trained-badge" title="主训练器，启用中">
                    <i class="fas fa-crown"></i> 主训练器
                </span>`;
            } else if (config.is_primary && !config.is_active) {
                statusBadge = `<span class="status-badge failed-badge" title="主训练器，已禁用">
                    <i class="fas fa-crown"></i> 已禁用
                </span>`;
            } else if (!config.is_primary && config.is_active) {
                statusBadge = `<span class="status-badge training-badge" title="备用训练器，启用中">
                    <i class="fas fa-check-circle"></i> 备用
                </span>`;
            } else {
                statusBadge = `<span class="status-badge failed-badge" title="已禁用">
                    <i class="fas fa-ban"></i> 禁用
                </span>`;
            }
            const path = config.trainer_path || '未设置';
            const description = config.description ? `<div class="config-description">${config.description}</div>` : '';
            const trainerType = config.trainer_type || '未知';
            const updateTime = config.updated_at ? this.formatTime(config.updated_at) : '从未更新';
            const actionButton = config.is_primary ? '' :
                `<button class="btn btn-sm btn-primary set-primary-btn" data-config-id="${config.id}" title="设为主训练器">
                    <i class="fas fa-crown"></i> 设为主训练器
                </button>`;
            html += `
                <tr data-config-id="${config.id}">
                    <td>${statusBadge}</td>
                    <td>
                        <div class="config-path">${path}</div>
                        ${description}
                    </td>
                    <td>${trainerType}</td>
                    <td>${updateTime}</td>
                    <td>${actionButton}</td>
                </tr>
            `;
        });
        tbody.innerHTML = html;
        this.bindSetPrimaryButtons();
    },

    setPrimaryTrainer: async function(configId) {
        console.log(`👑 设置主训练器，配置ID: ${configId}`);
        try {
            this.showLoading('正在设置主训练器...');
            const response = await fetch(`http://localhost:8000/api/v1/trainer_config/set_primary/${configId}`, {
                method: 'POST'
            });
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
            const result = await response.json();
            console.log('✅ 设置主训练器成功:', result);
            await this.loadTrainerConfigs(this.state.currentDeviceId);
            this.showNotification('已成功设置主训练器', 'success');
        } catch (error) {
            console.error('❌ 设置主训练器失败:', error);
            this.showNotification(`设置主训练器失败: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    },

    bindSetPrimaryButtons: function() {
        const buttons = document.querySelectorAll('.set-primary-btn');
        buttons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const configId = e.target.closest('.set-primary-btn').getAttribute('data-config-id');
                this.setPrimaryTrainer(configId);
            });
        });
    },

    bindModalEvents: function() {
        const modal = document.getElementById('trainer-config-modal');
        if (!modal) {
            console.error('❌ 找不到训练器配置弹窗');
            return;
        }
        const closeBtns = modal.querySelectorAll('.modal-close, #trainer-config-close');
        closeBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                modal.classList.remove('active');
                this.clearState();
            });
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                e.preventDefault();
                modal.classList.remove('active');
                this.clearState();
            }
        });
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                e.preventDefault();
                modal.classList.remove('active');
                this.clearState();
            }
        });
        document.getElementById('add-trainer-config')?.addEventListener('click', async (e) => {
            e.preventDefault();
            await this.addTrainerConfig();   // 改为调用新函数
        });
    },
    // 新增方法：调用后端创建配置
    addTrainerConfig: async function() {
    const deviceId = this.state.currentDeviceId;
    if (!deviceId) {
        this.showNotification('请先选择设备', 'error');
        return;
    }

    try {
        this.showLoading('正在创建训练器配置...');
        const response = await fetch('http://localhost:8000/api/v1/trainer_config/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                device_id: deviceId,
                trainer_type: 'xgboost',
                is_primary: false,   // 用户可后续设置为主训练器
                description: '自动生成的训练器配置'
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText);
        }

        const result = await response.json();
        console.log('✅ 训练器配置创建成功:', result);
        this.showNotification('训练器配置及文件创建成功！', 'success');

        // 重新加载配置列表
        await this.loadTrainerConfigs(deviceId);
    } catch (error) {
        console.error('❌ 创建配置失败:', error);
        this.showNotification(`创建失败: ${error.message}`, 'error');
    } finally {
        this.hideLoading();
    }
},
    clearState: function() {
        this.state.currentDeviceId = null;
        this.state.currentDeviceName = null;
        this.state.currentProjectName = null;
        this.state.trainerConfigs = [];
    },

    formatTime: function(dateString) {
        if (!dateString) return '-';
        try {
            const date = new Date(dateString);
            return date.toLocaleString('zh-CN', {
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return dateString;
        }
    },

    // 显示通知（委托给 ModelTrainingManager）
showNotification: function(message, type = 'info', duration = null) {
    ModelTrainingManager.showNotification(message, type, duration);
},

    showLoading: function(message = '正在处理...') {
        ModelTrainingManager.showLoading(message);
    },

    hideLoading: function() {
        ModelTrainingManager.hideLoading();
    }
};

// 页面加载完成后初始化
window.addEventListener('DOMContentLoaded', function() {
    console.log('📄 DOM加载完成，准备初始化模型训练');
    const navbarContainer = document.getElementById('navbar-container');
    if (navbarContainer && typeof Navbar !== 'undefined') {
        Navbar.init(navbarContainer, 'model-training');
    }
    setTimeout(() => {
        ModelTrainingManager.init().catch(error => {
            console.error('❌ 模型训练初始化失败:', error);
        });
    }, 100);
});

// 全局可用
window.ModelTrainingManager = ModelTrainingManager;
console.log('🚀 模型训练模块已加载');