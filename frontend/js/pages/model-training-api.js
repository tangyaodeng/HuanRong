//js/pages/model-training-api.js
// 模型训练页面API接口
console.log('🔧 model-training-api.js 开始加载');

// 创建模型训练API对象
window.ModelTrainingAPI = {
    // 获取设备列表（带模型信息）
    getDevicesForTraining: async function(filters = {}, page = 1, pageSize = 10) {
        console.log('📋 ModelTrainingAPI.getDevicesForTraining() 被调用', { filters, page, pageSize });

        // 构建查询参数
        const params = new URLSearchParams({
            page: page.toString(),
            page_size: pageSize.toString()
        });

        if (filters.projectId) params.append('project_id', filters.projectId);
        if (filters.status) params.append('status', filters.status);
         if (filters.planStatus) {
        // 前端值 -> 后端值映射
        const planStatusMap = {
            'training': 'active_plan',
            'trained': 'inactive_plan',
            'failed': 'no_plan'
        };
        const backendPlanStatus = planStatusMap[filters.planStatus];
        if (backendPlanStatus) {
            params.append('plan_status', backendPlanStatus);
        }
    }
        if (filters.search) params.append('search', filters.search);

        const url = `http://localhost:8000/api/v1/devices/?${params}`;
        console.log('🌐 请求设备URL:', url);

        try {
            const response = await fetch(url);
            console.log('📡 设备响应状态:', response.status, response.statusText);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('📦 设备响应数据:', data);

            // 处理设备数据，添加模型信息
            const processedDevices = await this.enrichDevicesWithModelInfo(data.devices || []);

            return {
                devices: processedDevices,
                total: data.total || 0,
                page: data.page || page,
                page_size: data.page_size || pageSize,
                total_pages: data.total_pages || 0
            };
        } catch (error) {
            console.error('❌ 获取设备列表失败:', error);
            return {
                devices: [],
                total: 0,
                page: page,
                page_size: pageSize,
                total_pages: 0
            };
        }
    },

    // 丰富设备数据，添加模型信息
    enrichDevicesWithModelInfo: async function(devices) {
        console.log('🔍 丰富设备数据，添加模型信息');

        // 如果没有设备，直接返回
        if (!devices || devices.length === 0) {
            return [];
        }

        try {
            // 获取所有设备模型
            const models = await this.getDeviceModels();
            const modelsMap = {};
            models.forEach(model => {
                modelsMap[model.id] = model;
            });

            // 获取所有设备模型版本
            const allVersions = [];
            for (const model of models) {
                try {
                    const versions = await this.getDeviceModelVersions(model.id);
                    versions.forEach(version => {
                        version.model_name = model.name;
                        allVersions.push(version);
                    });
                } catch (err) {
                    console.warn(`⚠️ 获取模型 ${model.id} 的版本失败:`, err);
                }
            }

            // 处理每个设备，添加模型信息
            return devices.map(device => {
                const enrichedDevice = { ...device };

                // 从 device_metadata 中获取模型信息
                const metadata = device.device_metadata || {};

                // 尝试从 metadata 中获取模型信息
                if (metadata.model_id) {
                    const model = modelsMap[metadata.model_id];
                    if (model) {
                        enrichedDevice.model_info = {
                            id: model.id,
                            name: model.name,
                            code: model.code,
                            description: model.description
                        };
                    }
                }

                // 尝试从 metadata 中获取版本信息
                if (metadata.model_version_id) {
                    // 查找对应的版本
                    const version = allVersions.find(v => v.id == metadata.model_version_id);
                    if (version) {
                        enrichedDevice.version_info = {
                            id: version.id,
                            version: version.version,
                            description: version.description,
                            model_name: version.model_name
                        };
                    }
                }

                // 如果没有明确的模型信息，尝试从 metadata 中解析
                if (!enrichedDevice.model_info && metadata.model) {
                    enrichedDevice.model_info = {
                        name: metadata.model,
                        code: metadata.model_code || metadata.model
                    };
                }

                if (!enrichedDevice.version_info && metadata.model_version) {
                    enrichedDevice.version_info = {
                        version: metadata.model_version,
                        description: metadata.model_version_description || ''
                    };
                }

                // 设置默认的模型和版本信息
                if (!enrichedDevice.model_info) {
                    enrichedDevice.model_info = {
                        name: '未配置',
                        code: 'unconfigured'
                    };
                }

                if (!enrichedDevice.version_info) {
                    enrichedDevice.version_info = {
                        version: 'v1.0',
                        description: '默认版本'
                    };
                }

                return enrichedDevice;
            });
        } catch (error) {
            console.error('❌ 丰富设备数据失败:', error);
            return devices;
        }
    },

    // 获取项目列表
    getProjects: async function() {
        console.log('📋 ModelTrainingAPI.getProjects() 被调用');
        try {
            const response = await fetch('http://localhost:8000/api/v1/projects/');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('❌ 获取项目列表失败:', error);
            return { projects: [] };
        }
    },

    // 获取设备模型列表
    getDeviceModels: async function() {
        console.log('📋 ModelTrainingAPI.getDeviceModels() 被调用');
        try {
            const response = await fetch('http://localhost:8000/api/v1/device_models/');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('❌ 获取设备模型列表失败:', error);
            return [];
        }
    },
    // 获取设备数据配置
    getDeviceDataConfig: async function(deviceId) {
        console.log(`📋 ModelTrainingAPI.getDeviceDataConfig() 被调用，设备ID: ${deviceId}`);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/data_config/device/${deviceId}`);
            if (!response.ok) {
                // 如果API不存在或设备没有配置，返回默认值
                return {
                    data_start_time: null,
                    data_end_time: null,
                    max_rows_limit: 300000,
                };
            }
            return await response.json();
        } catch (error) {
            console.error('❌ 获取设备数据配置失败:', error);
            return {
                data_start_time: null,
                data_end_time: null,
                max_rows_limit: 300000,
            };
        }
    },

    // 保存设备数据配置
    saveDeviceDataConfig: async function(deviceId, config) {
        console.log(`💾 ModelTrainingAPI.saveDeviceDataConfig() 被调用，设备ID: ${deviceId}`, config);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/data_config/device/${deviceId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(config)
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ 保存设备数据配置响应错误:', errorText);
                throw new Error(`HTTP ${response.status}: ${response.statusText} - ${errorText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('❌ 保存设备数据配置失败:', error);
            throw error;
        }
    },

    // 获取默认配置
    getDefaultDataConfig: async function() {
        console.log('📋 ModelTrainingAPI.getDefaultDataConfig() 被调用');
        try {
            const response = await fetch('http://localhost:8000/api/v1/data_config/defaults');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('❌ 获取默认配置失败:', error);
            return {
                DEFAULT_START_TIME: '2025-03-01T00:00:00',
                DEFAULT_END_TIME: '2025-11-30T23:59:59',
                MAX_ROWS_DEFAULT: 300000,
            };
        }
    },
    // 获取设备模型版本列表
    getDeviceModelVersions: async function(modelId) {
        console.log(`📋 ModelTrainingAPI.getDeviceModelVersions() 被调用，模型ID: ${modelId}`);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/device_models/${modelId}/versions`);
            if (!response.ok) {
                if (response.status === 404) {
                    console.warn(`⚠️ 设备模型版本API返回404，返回空数组`);
                    return [];
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`❌ 获取设备模型 ${modelId} 版本列表失败:`, error);
            return [];
        }
    },

    // 获取训练状态
    getTrainingStatus: async function(deviceId, modelId) {
        console.log(`📋 ModelTrainingAPI.getTrainingStatus() 被调用，设备ID: ${deviceId}, 模型ID: ${modelId}`);
        try {
            // 调用正确的API路径
            const response = await fetch(`http://localhost:8000/api/v1/model_training/device/${deviceId}`);

            if (!response.ok) {
                // 如果API不存在，返回默认状态
                return {
                    status: 'not_started',
                    last_train_time: null,
                    accuracy: null
                };
            }

            return await response.json();
        } catch (error) {
            console.error('❌ 获取训练状态失败:', error);
            return {
                status: 'not_started',
                last_train_time: null,
                accuracy: null
            };
        }
    },

    // 测试API连通性
    testConnection: async function() {
        console.log('🔗 ModelTrainingAPI.testConnection() 被调用');
        try {
            const response = await fetch('http://localhost:8000/health');
            const data = await response.json();
            console.log('✅ API连通性测试成功:', data);
            return data;
        } catch (error) {
            console.error('❌ API连通性测试失败:', error);
            throw error;
        }
    },

    // 真实训练模型
    realTraining: async function(deviceId, trainingConfig) {
        console.log('🚀 ModelTrainingAPI.realTraining() 被调用', { deviceId, trainingConfig });
        try {
            const url = `http://localhost:8000/api/v1/model_training/${deviceId}/real_train`;
            console.log('🌐 请求真实训练URL:', url);

            const response = await fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(trainingConfig || {
                    lookback_days: 30,
                    train_ratio: 0.8,
                    look_back: 24,
                    forecast_horizon: 1
                })
            });

            console.log('📡 真实训练响应状态:', response.status, response.statusText);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ 真实训练响应错误:', errorText);
                throw new Error(`HTTP ${response.status}: ${response.statusText} - ${errorText}`);
            }

            const result = await response.json();
            console.log('✅ 真实训练响应数据:', result);
            return result;
        } catch (error) {
            console.error('❌ 真实训练失败:', error);
            throw error;
        }
    },

    // 开始训练（带配置）
    startTrainingWithConfig: async function(trainingConfig) {
        console.log('🚀 ModelTrainingAPI.startTrainingWithConfig() 被调用', trainingConfig);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/model_training/${trainingConfig.device_id}/train_with_config`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    device_id: trainingConfig.device_id,
                    train_start_time: trainingConfig.train_start_time,
                    train_end_time: trainingConfig.train_end_time,
                    predict_start_time: trainingConfig.predict_start_time,
                    predict_end_time: trainingConfig.predict_end_time,
                    train_interval_hours: trainingConfig.train_interval_hours || 12,
                    predict_interval_minutes: trainingConfig.predict_interval_minutes || 5,
                    lookback_days: trainingConfig.lookback_days || 30,
                    train_ratio: trainingConfig.train_ratio || 0.8
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('❌ 开始训练失败:', error);
            throw error;
        }
    },
    //批量训练
    batchTraining: async function(deviceIds, trainingConfig = null) {
    const url = `http://localhost:8000/api/v1/model_training/batch/train`;
    const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            device_ids: deviceIds,
            training_config: trainingConfig || {
                lookback_days: 30,
                train_ratio: 0.8,
                look_back: 24,
                forecast_horizon: 1
            }
        })
    });
    if (!response.ok) throw new Error(await response.text());
    return await response.json();
},


};

console.log('✅ model-training-api.js 加载完成');