// 设备API模块 - 最小测试版 js/pages/device-api.js
console.log('🔧 device-api.js 开始加载');

// 创建全局API对象
window.API = {
    // 测试函数
    test: function() {
        console.log('✅ API.test() 被调用');
        return 'API 工作正常';
    },

    // 获取项目列表
    getProjects: async function() {
        console.log('📋 API.getProjects() 被调用');
        try {
            const response = await fetch('http://localhost:8000/api/v1/projects/');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('❌ 获取项目列表失败:', error);
            return { projects: [] }; // 返回空数组避免错误
        }
    },

    // 获取设备列表
    getDevices: async function(filters = {}, page = 1, pageSize = 10) {
        console.log('📋 API.getDevices() 被调用', { filters, page, pageSize });

        // 构建查询参数
        const params = new URLSearchParams({
            page: page.toString(),
            page_size: pageSize.toString()
        });

        if (filters.projectId) params.append('project_id', filters.projectId);
        if (filters.status) params.append('status', filters.status);
        if (filters.search) params.append('search', filters.search);

        const url = `http://localhost:8000/api/v1/devices/?${params}`;
        console.log('🌐 请求URL:', url);

        try {
            const response = await fetch(url);
            console.log('📡 响应状态:', response.status, response.statusText);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('📦 响应数据:', data);
            return data;
        } catch (error) {
            console.error('❌ 获取设备列表失败:', error);
            // 返回模拟数据用于测试
            return {
                devices: [],
                total: 0,
                page: page,
                page_size: pageSize,
                total_pages: 0
            };
        }
    },

    // 获取设备详情
    getDevice: async function(deviceId) {
        console.log('📋 API.getDevice() 被调用', deviceId);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/devices/${deviceId}`);
            return await response.json();
        } catch (error) {
            console.error('❌ 获取设备详情失败:', error);
            return null;
        }
    },

// 更新设备
updateDevice: async function(deviceId, deviceData) {
    console.log('✏️ API.updateDevice() 被调用', deviceId, deviceData);
    try {
        // 构建更新数据
        let updateData = { ...deviceData };

        // 如果包含device_metadata并且有model和model_version，尝试获取model_version_id
        if (updateData.device_metadata && updateData.device_metadata.model && updateData.device_metadata.model_version) {
            try {
                // 1. 获取设备模型列表，找到对应的模型
                const deviceModels = await this.getDeviceModels();
                const selectedModel = deviceModels.find(m => (m.code || m.id) === updateData.device_metadata.model);

                if (selectedModel) {
                    // 2. 获取该模型的版本列表
                    const versions = await this.getDeviceModelVersions(selectedModel.id);
                    const selectedVersion = versions.find(v => v.version === updateData.device_metadata.model_version);

                    if (selectedVersion) {
                        // 3. 添加model_version_id到更新数据
                        updateData.model_version_id = selectedVersion.id;

                        // 4. 根据模型类型设置model_type
                        if (selectedVersion.model_type) {
                            updateData.model_type = selectedVersion.model_type;
                        } else {
                            // 从device_metadata中获取或使用默认值
                            updateData.model_type = updateData.device_metadata.model_type || 'xgboost';
                        }

                        console.log(`✅ 找到模型版本ID: ${selectedVersion.id}, 类型: ${updateData.model_type}`);
                    }
                }
            } catch (error) {
                console.warn('⚠️ 获取模型版本信息失败，但仍继续更新:', error);
                // 即使获取失败，也继续更新其他字段
            }
        }

        const response = await fetch(`http://localhost:8000/api/v1/devices/${deviceId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(updateData)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        console.error('❌ 更新设备失败:', error);
        throw error;
    }
},

// 创建设备
createDevice: async function(deviceData) {
    console.log('➕ API.createDevice() 被调用', deviceData);
    try {
        // 构建创建设备的数据
        let createData = { ...deviceData };

        // 如果包含device_metadata并且有model和model_version，尝试获取model_version_id
        if (createData.device_metadata && createData.device_metadata.model && createData.device_metadata.model_version) {
            try {
                // 1. 获取设备模型列表，找到对应的模型
                const deviceModels = await this.getDeviceModels();
                const selectedModel = deviceModels.find(m => (m.code || m.id) === createData.device_metadata.model);

                if (selectedModel) {
                    // 2. 获取该模型的版本列表
                    const versions = await this.getDeviceModelVersions(selectedModel.id);
                    const selectedVersion = versions.find(v => v.version === createData.device_metadata.model_version);

                    if (selectedVersion) {
                        // 3. 添加model_version_id到创建数据
                        createData.model_version_id = selectedVersion.id;

                        // 4. 根据模型类型设置model_type
                        if (selectedVersion.model_type) {
                            createData.model_type = selectedVersion.model_type;
                        } else {
                            // 从device_metadata中获取或使用默认值
                            createData.model_type = createData.device_metadata.model_type || 'xgboost';
                        }

                        console.log(`✅ 找到模型版本ID: ${selectedVersion.id}, 类型: ${createData.model_type}`);
                    }
                }
            } catch (error) {
                console.warn('⚠️ 获取模型版本信息失败，但仍继续创建:', error);
                // 即使获取失败，也继续创建设备
            }
        }

        const response = await fetch('http://localhost:8000/api/v1/devices/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(createData)
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    } catch (error) {
        console.error('❌ 创建设备失败:', error);
        throw error;
    }
},

    // 删除设备
    deleteDevice: async function(deviceId) {
        console.log('🗑️ API.deleteDevice() 被调用', deviceId);
        try {
            const response = await fetch(`http://localhost:8000/api/v1/devices/${deviceId}`, {
                method: 'DELETE'
            });
            return response.ok ? { success: true } : { success: false };
        } catch (error) {
            console.error('❌ 删除设备失败:', error);
            throw error;
        }
    },

    // 获取设备模型列表
    getDeviceModels: async function() {
        console.log('📋 API.getDeviceModels() 被调用');
        try {
            const response = await fetch('http://localhost:8000/api/v1/device_models/');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('❌ 获取设备模型列表失败:', error);
            // 返回空数组避免错误
            return [];
        }
    },

    // 获取设备模型版本列表
    getDeviceModelVersions: async function(modelId) {
        console.log(`📋 API.getDeviceModelVersions() 被调用，模型ID: ${modelId}`);
        try {
            // 修复：使用正确的后端路由路径
            // 注意：根据后端代码，设备模型版本的路由是 /device_models/{model_id}/versions
            // 而不是 /device-models/{model_id}/versions
            const response = await fetch(`http://localhost:8000/api/v1/device_models/${modelId}/versions`);
            if (!response.ok) {
                // 如果返回404，可能是因为后端路由还没完全正确设置
                // 先返回空数组，让前端能继续工作
                if (response.status === 404) {
                    console.warn(`⚠️ 设备模型版本API返回404，返回空数组`);
                    return [];
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error(`❌ 获取设备模型 ${modelId} 版本列表失败:`, error);
            // 返回模拟数据，让前端能继续开发
            console.log('📦 返回模拟数据用于开发');
            return [
                {
                    "id": 1,
                    "version": "v1.0",
                    "description": "基础版本",
                    "is_active": true
                },
                {
                    "id": 2,
                    "version": "v1.1",
                    "description": "优化版本",
                    "is_active": true
                },
                {
                    "id": 3,
                    "version": "v2.0",
                    "description": "最新版本",
                    "is_active": true
                }
            ];
        }
    },
// 获取设备模型版本的特征列表
getFeaturesByVersion: async function(versionId) {
    console.log(`📋 API.getFeaturesByVersion() 被调用，版本ID: ${versionId}`);
    try {
        const response = await fetch(`http://localhost:8000/api/v1/features/by_version/${versionId}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`❌ 获取版本特征失败:`, error);
        // 返回空数组
        return [];
    }
},

// 获取设备的特征值
getDeviceFeatures: async function(deviceId) {
    console.log(`📋 API.getDeviceFeatures() 被调用，设备ID: ${deviceId}`);
    try {
        const response = await fetch(`http://localhost:8000/api/v1/features/by_device/${deviceId}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`❌ 获取设备特征失败:`, error);
        return [];
    }
},
    // 测试API连通性
    testConnection: async function() {
        console.log('🔗 API.testConnection() 被调用');
        try {
            const response = await fetch('http://localhost:8000/health');
            const data = await response.json();
            console.log('✅ API连通性测试成功:', data);
            return data;
        } catch (error) {
            console.error('❌ API连通性测试失败:', error);
            throw error;
        }
    }
};

// 工具函数
window.Utils = {
    showSuccess: function(message) {
        alert('✅ ' + message);
    },

    showError: function(message) {
        alert('❌ ' + message);
    },

    formatTime: function(dateString) {
        if (!dateString) return '-';
        try {
            const date = new Date(dateString);
            return date.toLocaleString('zh-CN');
        } catch (e) {
            return dateString;
        }
    }
};

// 测试函数
window.testAPI = function() {
    console.log('🧪 测试API...');
    console.log('API对象:', window.API);
    console.log('API.test():', window.API.test());

    // 测试获取健康状态
    fetch('http://localhost:8000/health')
        .then(response => response.json())
        .then(data => console.log('健康检查:', data))
        .catch(error => console.error('健康检查失败:', error));

    // 测试获取设备列表
    window.API.getDevices({}, 1, 5)
        .then(data => console.log('设备列表:', data))
        .catch(error => console.error('设备列表失败:', error));
};

console.log('✅ device-api.js 加载完成');
console.log('📌 测试命令: testAPI()');