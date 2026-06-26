// 主应用程序
document.addEventListener('DOMContentLoaded', function() {
    // 全局变量
    let currentProjectId = null;
    let autoRefreshInterval = null;
    let loadChart = null;
    let predictionChart = null;

    // 初始化应用
    function initApp() {
        updateTime();
        setInterval(updateTime, 1000);

        loadProjects();
        loadOverview();
        loadDeviceStatus();

        initCharts();
        setupEventListeners();

        // 启动自动刷新
        startAutoRefresh();
    }

    // 更新时间显示
    function updateTime() {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('zh-CN', { hour12: false });
        document.getElementById('current-time').textContent = timeStr;
    }

    // 加载项目列表
    async function loadProjects() {
        try {
            const projects = await API.getProjects();
            const select = document.getElementById('project-select');

            // 清空选项（保留第一个）
            select.innerHTML = '<option value="">选择项目...</option>';

            projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.id;
                option.textContent = project.name;
                select.appendChild(option);
            });

            // 如果有项目，选择第一个
            if (projects.length > 0) {
                select.value = projects[0].id;
                currentProjectId = projects[0].id;
                onProjectChange();
            }
        } catch (error) {
            console.error('加载项目失败:', error);
            showError('加载项目失败: ' + error.message);
        }
    }

    // 项目选择变化
    function onProjectChange() {
        const select = document.getElementById('project-select');
        currentProjectId = select.value;

        if (currentProjectId) {
            loadOverview();
            loadDeviceStatus();
            updateDeviceSelectors();
            loadChartsData();
        }
    }

    // 加载概览数据
    async function loadOverview() {
        if (!currentProjectId) return;

        try {
            const overview = await API.getProjectOverview(currentProjectId);

            document.getElementById('project-count').textContent = overview.totalProjects || 0;
            document.getElementById('device-count').textContent = overview.totalDevices || 0;
            document.getElementById('running-devices').textContent = overview.runningDevices || 0;
            document.getElementById('feature-count').textContent = overview.totalFeatures || 0;
        } catch (error) {
            console.error('加载概览数据失败:', error);
        }
    }

    // 加载设备状态
    async function loadDeviceStatus() {
        if (!currentProjectId) return;

        const container = document.getElementById('device-status-cards');
        container.innerHTML = '<div class="loading">正在加载设备状态...</div>';

        try {
            const devices = await API.getProjectDevices(currentProjectId);

            if (devices.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-server"></i>
                        <h3>暂无设备</h3>
                        <p>请先添加设备到当前项目</p>
                    </div>
                `;
                return;
            }

            let html = '';
            devices.forEach(device => {
                const statusClass = `status-${device.status}`;
                const loadClass = getLoadClass(device.currentLoad);

                html += `
                    <div class="device-card">
                        <div class="device-status ${statusClass}"></div>
                        <div class="device-info">
                            <div class="device-name">${device.name}</div>
                            <div class="device-meta">
                                ${device.type} • ${device.location || '未知位置'}
                            </div>
                        </div>
                        <div class="device-load ${loadClass}">
                            ${device.currentLoad || 0}%
                        </div>
                    </div>
                `;
            });

            container.innerHTML = html;
        } catch (error) {
            console.error('加载设备状态失败:', error);
            container.innerHTML = '<div class="alert alert-error">加载设备状态失败</div>';
        }
    }

    // 获取负荷等级对应的CSS类
    function getLoadClass(load) {
        if (load >= 90) return 'load-critical';
        if (load >= 70) return 'load-high';
        return 'load-normal';
    }

    // 更新设备选择器
    async function updateDeviceSelectors() {
        if (!currentProjectId) return;

        try {
            const devices = await API.getProjectDevices(currentProjectId);
            const loadSelect = document.getElementById('load-device-select');
            const predSelect = document.getElementById('prediction-device-select');

            // 清空选项
            loadSelect.innerHTML = '<option value="">选择设备...</option>';
            predSelect.innerHTML = '<option value="">选择设备...</option>';

            devices.forEach(device => {
                const option1 = document.createElement('option');
                option1.value = device.id;
                option1.textContent = device.name;
                loadSelect.appendChild(option1.cloneNode(true));

                const option2 = option1.cloneNode(true);
                predSelect.appendChild(option2);
            });

            // 默认选择第一个设备
            if (devices.length > 0) {
                loadSelect.value = devices[0].id;
                predSelect.value = devices[0].id;
            }
        } catch (error) {
            console.error('更新设备选择器失败:', error);
        }
    }

    // 初始化图表
    function initCharts() {
        loadChart = echarts.init(document.getElementById('load-chart'));
        predictionChart = echarts.init(document.getElementById('prediction-chart'));

        // 设置默认图表选项
        loadChart.setOption(Charts.getLoadChartOption());
        predictionChart.setOption(Charts.getPredictionChartOption());

        // 窗口大小变化时重绘图表
        window.addEventListener('resize', function() {
            loadChart.resize();
            predictionChart.resize();
        });
    }

    // 加载图表数据
    async function loadChartsData() {
        if (!currentProjectId) return;

        const loadDeviceId = document.getElementById('load-device-select').value;
        const predDeviceId = document.getElementById('prediction-device-select').value;

        if (loadDeviceId) {
            await loadDeviceLoadData(loadDeviceId);
        }

        if (predDeviceId) {
            await loadPredictionData(predDeviceId);
        }
    }

    // 加载设备负荷数据
    async function loadDeviceLoadData(deviceId) {
        try {
            const range = document.querySelector('.btn-time.active').dataset.range;
            const data = await API.getDeviceLoadData(deviceId, range);

            loadChart.setOption(Charts.updateLoadChartData(data));
        } catch (error) {
            console.error('加载负荷数据失败:', error);
            showError('加载负荷数据失败');
        }
    }

    // 加载预测数据
    async function loadPredictionData(deviceId) {
        try {
            const data = await API.getPredictionData(deviceId);

            predictionChart.setOption(Charts.updatePredictionChartData(data));
        } catch (error) {
            console.error('加载预测数据失败:', error);
            showError('加载预测数据失败');
        }
    }

    // 设置事件监听器
    function setupEventListeners() {
        // 项目选择变化
        document.getElementById('project-select').addEventListener('change', onProjectChange);

        // 导航菜单点击
        document.querySelectorAll('.nav-item:not(.disabled)').forEach(item => {
            item.addEventListener('click', function() {
                const page = this.dataset.page;
                navigateToPage(page);
            });
        });

        // 时间范围按钮
        document.querySelectorAll('.btn-time').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.btn-time').forEach(b => b.classList.remove('active'));
                this.classList.add('active');

                if (currentProjectId) {
                    loadChartsData();
                }
            });
        });

        // 刷新按钮
        document.getElementById('refresh-btn').addEventListener('click', function() {
            refreshAllData();
        });

        // 设备选择变化
        document.getElementById('load-device-select').addEventListener('change', function() {
            if (this.value && currentProjectId) {
                loadDeviceLoadData(this.value);
            }
        });

        document.getElementById('prediction-device-select').addEventListener('change', function() {
            if (this.value && currentProjectId) {
                loadPredictionData(this.value);
            }
        });

        // 自动刷新开关
        document.getElementById('auto-refresh').addEventListener('change', function() {
            if (this.checked) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        });
    }

    // 导航到页面
    function navigateToPage(page) {
        // 更新导航状态
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        event.target.closest('.nav-item').classList.add('active');

        // 隐藏所有页面，显示目标页面
        if (page === 'dashboard') {
            document.querySelector('.main-content').style.display = 'block';
            document.getElementById('page-container').style.display = 'none';
        } else {
            document.querySelector('.main-content').style.display = 'none';
            document.getElementById('page-container').style.display = 'block';

            // 加载对应页面内容
            loadPageContent(page);
        }
    }

    // 加载页面内容
    async function loadPageContent(page) {
        const container = document.getElementById('page-container');

        switch(page) {
            case 'projects':
                container.innerHTML = await loadProjectsPage();
                break;
            case 'devices':
                container.innerHTML = await loadDevicesPage();
                break;
            case 'features':
                container.innerHTML = await loadFeaturesPage();
                break;
            case 'data-sources':
                container.innerHTML = await loadDataSourcesPage();
                break;
            default:
                container.innerHTML = '<h2>功能开发中...</h2>';
        }
    }

    // 刷新所有数据
    function refreshAllData() {
        if (!currentProjectId) return;

        loadOverview();
        loadDeviceStatus();
        loadChartsData();

        // 显示刷新提示
        showSuccess('数据已刷新');
    }

    // 开始自动刷新
    function startAutoRefresh() {
        stopAutoRefresh(); // 先停止之前的定时器

        autoRefreshInterval = setInterval(() => {
            if (currentProjectId && document.getElementById('auto-refresh').checked) {
                refreshAllData();
            }
        }, 30000); // 30秒刷新一次
    }

    // 停止自动刷新
    function stopAutoRefresh() {
        if (autoRefreshInterval) {
            clearInterval(autoRefreshInterval);
            autoRefreshInterval = null;
        }
    }

    // 显示成功消息
    function showSuccess(message) {
        showNotification(message, 'success');
    }

    // 显示错误消息
    function showError(message) {
        showNotification(message, 'error');
    }

    // 显示通知
    function showNotification(message, type) {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
            <span>${message}</span>
        `;

        // 添加到页面
        document.body.appendChild(notification);

        // 3秒后移除
        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }

    // 页面加载函数占位符
    async function loadProjectsPage() {
        return '<h2>项目管理页面</h2><p>功能开发中...</p>';
    }

    async function loadDevicesPage() {
        return '<h2>设备管理页面</h2><p>功能开发中...</p>';
    }

    async function loadFeaturesPage() {
        return '<h2>特征配置页面</h2><p>功能开发中...</p>';
    }

    async function loadDataSourcesPage() {
        return '<h2>数据源配置页面</h2><p>功能开发中...</p>';
    }

    // 添加通知样式
    const style = document.createElement('style');
    style.textContent = `
        .notification {
            position: fixed;
            top: 80px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 4px;
            color: white;
            display: flex;
            align-items: center;
            gap: 10px;
            z-index: 3000;
            animation: slideIn 0.3s ease;
            min-width: 300px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        .notification-success {
            background-color: #27ae60;
        }

        .notification-error {
            background-color: #e74c3c;
        }

        .fade-out {
            animation: fadeOut 0.3s ease forwards;
        }

        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @keyframes fadeOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);

    // 初始化应用
    initApp();
});