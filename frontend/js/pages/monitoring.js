//js/pages/monitoring.js
/**
     * 实时监控页面主逻辑 - 多图表版本  主机模型有2个，所以真实和预测各有两个表，是各自两个相加吗
     */

    var MultiChartMonitoring = (function() {
        'use strict';

        /**
         * MultiChartMonitoring 构造函数
         */
        function MultiChartMonitoring() {
            this.charts = {}; // 存储所有图表实例
            this.autoRefreshIntervals = {}; // 存储所有自动刷新间隔
            this.isAutoRefresh = true;
            this.refreshInterval = 5000; // 5秒刷新一次
            this.defaultTimeRange = { hours: 24 }; // 默认显示最近24小时
            this.deviceIdMap = null;//存储图表索引:设备id映射
            this.chartConfigs = {
                'chart-1': {
                    category: 'host',                      // 固定标识
                    enabled: true,            // ← 新增：标记为不启用
                    title: '主机总功率预测',
                    yAxisName: 'kW',
                    chartId: 'real-time-chart-1',
                    containerId: 'chart-container-1'
                },
                'chart-2': {
                    category: 'cooling_tower',
                    title: '冷却塔总功率预测',
                    yAxisName: 'kW',
                    chartId: 'real-time-chart-2',
                    containerId: 'chart-container-2'
                },
                'chart-3': {
                    category: 'cooling_pump',
                    title: '冷却泵总功率预测',
                    yAxisName: 'kW',
                    chartId: 'real-time-chart-3',
                    containerId: 'chart-container-3'
                },
                'chart-4': {
                    category: 'chilled_pump',
                    title: '冷冻泵总功率预测',
                    yAxisName: 'kW',
                    chartId: 'real-time-chart-4',
                    containerId: 'chart-container-4'
                }
            };

            this.init();
        }
        // 构建设备ID映射
MultiChartMonitoring.prototype.buildDeviceIdMap = async function() {
    try {
        const response = await fetch('http://localhost:8000/api/v1/devices/');
        if (!response.ok) throw new Error('获取设备列表失败');
        const data = await response.json();
        const devices = data.devices || [];

        const map = {};
        devices.forEach(device => {
            const name = device.name;
            // 根据设备名称关键词匹配图表索引（可根据实际设备名称调整）
            if (name.includes('主机')) map['1'] = device.id;
            else if (name.includes('冷却塔')) map['2'] = device.id;
            else if (name.includes('冷却泵')) map['3'] = device.id;
            else if (name.includes('冷冻泵')) map['4'] = device.id;
        });
        this.deviceIdMap = map;
        console.log('设备ID映射构建完成:', this.deviceIdMap);
    } catch (error) {
        console.error('构建设备ID映射失败:', error);
    }
};

// 确保映射已构建
MultiChartMonitoring.prototype.ensureDeviceIdMap = async function() {
    if (!this.deviceIdMap) {
        await this.buildDeviceIdMap();
    }
};

// 获取设备评价指标
MultiChartMonitoring.prototype.getDeviceMetrics = async function(deviceId) {
    try {
        const response = await fetch(`http://localhost:8000/api/v1/model_evaluation/metrics/${deviceId}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('获取设备指标失败:', error);
        throw error;
    }
};

// 填充指标到模态框（复用 model-training.js 的逻辑）
MultiChartMonitoring.prototype.populateMetricsModal = function(metrics) {
    const evaluation = metrics.latest_evaluation;
    if (!evaluation) {
        document.getElementById('r2-score').textContent = '无数据';
        document.getElementById('rmse-score').textContent = '无数据';
        document.getElementById('mae-score').textContent = '无数据';
        document.getElementById('training-time').textContent = '无数据';
        document.getElementById('train-data-size').textContent = '无数据';
        document.getElementById('test-data-size').textContent = '无数据';
        document.getElementById('feature-count').textContent = '无数据';
        document.getElementById('last-update').textContent = '无数据';
        return;
    }

    // 基本信息
    document.getElementById('metrics-project-name').textContent = metrics.project_name || '-';
    document.getElementById('metrics-device-name').textContent = metrics.device_name || '-';
    document.getElementById('metrics-model-version').textContent = `${metrics.model_name || ''} ${metrics.model_version || ''}`.trim() || '-';

    // 主要指标
    document.getElementById('r2-score').textContent = evaluation.r_squared?.toFixed(4) || 'N/A';
    document.getElementById('rmse-score').textContent = evaluation.rmse?.toFixed(4) || 'N/A';
    document.getElementById('mae-score').textContent = evaluation.mae?.toFixed(4) || 'N/A';

    // 训练时间格式化
    let trainingTime = evaluation.training_time;
    if (trainingTime && typeof trainingTime === 'number') {
        if (trainingTime < 60) trainingTime = `${Math.round(trainingTime)}s`;
        else if (trainingTime < 3600) trainingTime = `${Math.floor(trainingTime/60)}m ${Math.round(trainingTime%60)}s`;
        else trainingTime = `${Math.floor(trainingTime/3600)}h ${Math.floor((trainingTime%3600)/60)}m`;
    } else {
        trainingTime = '-';
    }
    document.getElementById('training-time').textContent = trainingTime;

    // 详细指标
    document.getElementById('train-data-size').textContent = evaluation.training_data_size ? `${evaluation.training_data_size} 条` : '-';
    document.getElementById('test-data-size').textContent = evaluation.test_data_size ? `${evaluation.test_data_size} 条` : '-';
    document.getElementById('feature-count').textContent = evaluation.feature_count ? `${evaluation.feature_count} 个` : '-';
    document.getElementById('last-update').textContent = evaluation.created_at ? new Date(evaluation.created_at).toLocaleString() : '-';

    // 添加性能评级（新增）
    if (evaluation.r_squared !== undefined && evaluation.r_squared !== null) {
        this.addPerformanceRating(evaluation.r_squared);
    }
};
MultiChartMonitoring.prototype.addPerformanceRating = function(r2) {
    let rating = '', color = '';

    if (r2 >= 0.9) {
        rating = '优秀';
        color = '#4CAF50';
    } else if (r2 >= 0.8) {
        rating = '良好';
        color = '#8BC34A';
    } else if (r2 >= 0.7) {
        rating = '一般';
        color = '#FFC107';
    } else {
        rating = '较差';
        color = '#F44336';
    }

    const r2Element = document.getElementById('r2-score');
    if (r2Element) {
        r2Element.style.color = color;
        r2Element.innerHTML = `${r2.toFixed(4)} <span style="font-size: 14px; color: ${color};">(${rating})</span>`;
    }
};

// 显示评价弹窗
MultiChartMonitoring.prototype.showMetricsForChart = async function(chartKey) {
    await this.ensureDeviceIdMap();
    const chartNum = chartKey.split('-')[1];
    const deviceId = this.deviceIdMap[chartNum];
    if (!deviceId) {
        this.showError(`未找到图表 ${chartNum} 对应的设备ID`);
        return;
    }

    try {
        this.showLoadingOverlay(); // 显示加载中
        const metrics = await this.getDeviceMetrics(deviceId);
        this.populateMetricsModal(metrics);
        document.getElementById('metrics-modal').classList.add('active');
    } catch (error) {
        console.error('获取指标失败:', error);
        this.showError('获取模型评价指标失败');
    } finally {
        this.hideLoadingOverlay(); // 隐藏加载
    }
};

// 绑定模态框关闭事件
MultiChartMonitoring.prototype.bindMetricsModalEvents = function() {
    const modal = document.getElementById('metrics-modal');
    if (!modal) return;

    const closeModal = () => modal.classList.remove('active');
    modal.querySelectorAll('.modal-close, #metrics-close').forEach(btn => btn.addEventListener('click', closeModal));
    modal.addEventListener('click', (e) => { if (e.target === modal) closeModal(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && modal.classList.contains('active')) closeModal(); });
};
// 显示全局加载遮罩
MultiChartMonitoring.prototype.showLoadingOverlay = function() {
    let loadingEl = document.getElementById('global-loading');
    if (!loadingEl) {
        loadingEl = document.createElement('div');
        loadingEl.id = 'global-loading';
        loadingEl.className = 'global-loading';
        loadingEl.innerHTML = `
            <div class="loading-overlay">
                <div class="loading-content">
                    <i class="fas fa-spinner fa-spin"></i>
                    <div class="loading-message">加载中...</div>
                </div>
            </div>
        `;
        document.body.appendChild(loadingEl);
    }
    loadingEl.style.display = 'block';
};

// 隐藏全局加载遮罩
MultiChartMonitoring.prototype.hideLoadingOverlay = function() {
    const loadingEl = document.getElementById('global-loading');
    if (loadingEl) {
        loadingEl.style.display = 'none';
    }
};
         // 在 MultiChartMonitoring 内部或外部添加此函数
        function formatLocalDateTime(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            const seconds = String(date.getSeconds()).padStart(2, '0');
            return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
        }
        /**
         * 初始化所有图表
         */
        MultiChartMonitoring.prototype.init = function() {
            // 初始化前两个图表
            for (const chartKey in this.chartConfigs) {
                // 跳过 enabled 为 false 的图表
                if (this.chartConfigs[chartKey].enabled === false) continue;
                this.initChart(chartKey);
            }

            this.bindGlobalEvents();
            this.loadAllChartsData();

            // 启动自动刷新
            if (this.isAutoRefresh) {
                this.startAutoRefreshForAll();
            }

            // 初始化时间输入框
            this.initTimeInputs();
            this.bindMetricsModalEvents();  // 绑定模态框关闭事件

        };

        /**
         * 初始化单个图表
         */
        MultiChartMonitoring.prototype.initChart = function(chartKey) {
            const config = this.chartConfigs[chartKey];
            const chartId = config.chartId;
            const chartDom = document.getElementById(chartId);

            if (!chartDom) {
                console.error(`图表容器不存在: ${chartId}`);
                return;
            }

            // 初始化ECharts实例
            const chartInstance = echarts.init(chartDom);

            // 基础配置 - 修改y轴标签颜色为#111
            const option = {
                tooltip: {
                    trigger: 'axis',
                    formatter: function(params) {
                        let timeValue;
                        if (params && params.length > 0 && params[0].value) {
                            timeValue = params[0].value[0];
                        } else {
                            timeValue = new Date();
                        }

                        let date;
                        if (typeof timeValue === 'number') {
                            date = new Date(timeValue);
                        } else if (typeof timeValue === 'string') {
                            date = new Date(timeValue);
                        } else if (timeValue instanceof Date) {
                            date = timeValue;
                        } else {
                            date = new Date();
                        }

                        if (isNaN(date.getTime())) {
                            date = new Date();
                        }

                        const year = date.getFullYear();
                        const month = (date.getMonth() + 1);
                        const day = date.getDate();
                        const hours = date.getHours().toString().padStart(2, '0');
                        const minutes = date.getMinutes().toString().padStart(2, '0');
                        const seconds = date.getSeconds().toString().padStart(2, '0');

                        const timeStr = `${year}年${month}月${day}日 ${hours}:${minutes}:${seconds}`;

                        let result = '<div style="font-weight: bold; margin-bottom: 5px;">' + timeStr + '</div>';

                        let actualValue = null;
                        let predictedValue = null;
                        let actualSeriesName = '';
                        let predictedSeriesName = '';

                        params.forEach(function(param) {
                            if (param.seriesName.includes('实际') || param.seriesName === '实际值') {
                                actualValue = param.value[1];
                                actualSeriesName = param.seriesName;
                            } else if (param.seriesName.includes('预测') || param.seriesName === '预测值') {
                                predictedValue = param.value[1];
                                predictedSeriesName = param.seriesName;
                            }
                        });

                        if (actualValue !== null) {
                            const unit = config.yAxisName;
                            result += '<div style="display: flex; align-items: center; margin: 2px 0;">' +
                                '<span style="color: #28a745; margin-right: 8px;">●</span>' +
                                '<span style="flex: 1;">' + actualSeriesName + '</span>' +
                                '<span style="font-weight: bold;">' + actualValue + ' ' + unit + '</span>' +
                                '</div>';
                        }

                        if (predictedValue !== null) {
                            const unit = config.yAxisName;
                            result += '<div style="display: flex; align-items: center; margin: 2px 0;">' +
                                '<span style="color: #007bff; margin-right: 8px;">◆</span>' +
                                '<span style="flex: 1;">' + predictedSeriesName + '</span>' +
                                '<span style="font-weight: bold;">' + predictedValue + ' ' + unit + '</span>' +
                                '</div>';
                        }

                        if (actualValue !== null && predictedValue !== null && actualValue !== 0) {
                            const errorPercent = Math.abs((actualValue - predictedValue) / actualValue * 100).toFixed(1);
                            result += '<div style="display: flex; align-items: center; margin: 2px 0; padding-top: 5px; border-top: 1px solid #eee;">' +
                                '<span style="color: #dc3545; margin-right: 8px;">⚠</span>' +
                                '<span style="flex: 1;">误差</span>' +
                                '<span style="font-weight: bold; color: ' + (errorPercent > 10 ? '#dc3545' : '#28a745') + ';">' + errorPercent + '%</span>' +
                                '</div>';
                        }

                        return result;
                    },
                    backgroundColor: 'rgba(255, 255, 255, 0.95)',
                    borderColor: '#e9ecef',
                    borderWidth: 1
                },
                legend: {
                    data: ['实际值', '预测值'],
                    top: 5,
                    right: 10,
                    textStyle: {
                        fontSize: 12
                    }
                },
                grid: {
                    left: '3%',
                    right: '4%',
                    bottom: '3%',
                    top: '15%',
                    containLabel: true
                },
                xAxis: {
                    type: 'time',
                    boundaryGap: false,
                    axisLabel: {
                        formatter: function(value) {
                            const date = new Date(value);
                            const hours = date.getHours().toString().padStart(2, '0');
                            const minutes = date.getMinutes().toString().padStart(2, '0');
                            return `${hours}:${minutes}`;
                        },
                        color: '#111'
                    },
                    axisLine: {
                        lineStyle: {
                            color: '#e9ecef'
                        }
                    },
                    splitLine: {
                        show: true,
                        lineStyle: {
                            color: '#f8f9fa',
                            type: 'dashed'
                        }
                    }
                },
                yAxis: {
                    type: 'value',
                    name: config.yAxisName,
                    nameLocation: 'end',
                    nameTextStyle: {
                        padding: [0, 0, 0, 10],
                        fontSize: 12
                    },
                    axisLabel: {
                        color: '#111' // 设置y轴标签颜色为#111
                    },
                    axisLine: {
                        show: true,
                        lineStyle: {
                            color: '#e9ecef'
                        }
                    },
                    splitLine: {
                        show: true,
                        lineStyle: {
                            color: '#f8f9fa',
                            type: 'dashed'
                        }
                    }
                },
                series: [
                    {
                        name: '实际值',
                        type: 'line',
                        smooth: true,
                        showSymbol: false,
                        data: [],
                        itemStyle: {
                            color: '#28a745'
                        },
                        lineStyle: {
                            width: 2
                        },
                        areaStyle: {
                            color: {
                                type: 'linear',
                                x: 0,
                                y: 0,
                                x2: 0,
                                y2: 1,
                                colorStops: [{
                                    offset: 0,
                                    color: 'rgba(40, 167, 69, 0.2)'
                                }, {
                                    offset: 1,
                                    color: 'rgba(40, 167, 69, 0.02)'
                                }]
                            }
                        }
                    },
                    {
                        name: '预测值',
                        type: 'line',
                        smooth: true,
                        showSymbol: false,
                        data: [],
                        itemStyle: {
                            color: '#007bff'
                        },
                        lineStyle: {
                            width: 2,
                            type: 'dashed'
                        }
                    }
                ]
            };

            chartInstance.setOption(option);

            // 存储图表实例
            this.charts[chartKey] = {
                instance: chartInstance,
                config: config,
                currentTimeRange: { hours: 24 },
                data: []
            };

            // 绑定图表特定事件
            this.bindChartEvents(chartKey);
        };

        /**
         * 初始化时间输入框
         */
        MultiChartMonitoring.prototype.initTimeInputs = function() {
            const now = new Date();
            const endTime = this.formatDateTimeLocal(now);

            for (const chartKey in this.charts) {
                const chart = this.charts[chartKey];
                const startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);

                const chartNum = chartKey.split('-')[1];
                const startInput = document.querySelector(`.start-time[data-chart="${chartNum}"]`);
                const endInput = document.querySelector(`.end-time[data-chart="${chartNum}"]`);

                if (startInput && endInput) {
                    startInput.value = this.formatDateTimeLocal(startTime);
                    endInput.value = endTime;
                }
            }
        };

        /**
         * 格式化时间为datetime-local格式
         */
        MultiChartMonitoring.prototype.formatDateTimeLocal = function(date) {
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            const hours = String(date.getHours()).padStart(2, '0');
            const minutes = String(date.getMinutes()).padStart(2, '0');
            return `${year}-${month}-${day}T${hours}:${minutes}`;
        };

        /**
         * 绑定全局事件
         */
        MultiChartMonitoring.prototype.bindGlobalEvents = function() {
            const self = this;

            // 刷新全部按钮
            document.getElementById('refresh-all-btn')?.addEventListener('click', function() {
                self.loadAllChartsData();
            });

            // 监听窗口大小变化
            window.addEventListener('resize', function() {
                for (const chartKey in self.charts) {
                    if (self.charts[chartKey].instance) {
                        self.charts[chartKey].instance.resize();
                    }
                }
            });
        };

        /**
         * 绑定单个图表的事件
         */
        MultiChartMonitoring.prototype.bindChartEvents = function(chartKey) {
            const self = this;
            const chartNum = chartKey.split('-')[1];

            // 应用时间按钮
            const applyBtn = document.querySelector(`.apply-time-btn[data-chart="${chartNum}"]`);
            if (applyBtn) {
                applyBtn.addEventListener('click', function() {
                    const startInput = document.querySelector(`.start-time[data-chart="${chartNum}"]`);
                    const endInput = document.querySelector(`.end-time[data-chart="${chartNum}"]`);

                    if (!startInput.value || !endInput.value) {
                        self.showError('请选择开始时间和结束时间');
                        return;
                    }

                    if (new Date(startInput.value) >= new Date(endInput.value)) {
                        self.showError('开始时间必须早于结束时间');
                        return;
                    }

                    self.setChartTimeRange(chartKey, {
                        startTime: startInput.value + ':00',
                        endTime: endInput.value + ':00'
                    });
                });
            }

            // 重置时间按钮
            const resetBtn = document.querySelector(`.reset-time-btn[data-chart="${chartNum}"]`);
            if (resetBtn) {
                resetBtn.addEventListener('click', function() {
                    // 重置为最近24小时
                    const now = new Date();
                    const startTime = new Date(now.getTime() - 1 * 60 * 60 * 1000);

                    const startInput = document.querySelector(`.start-time[data-chart="${chartNum}"]`);
                    const endInput = document.querySelector(`.end-time[data-chart="${chartNum}"]`);

                    if (startInput && endInput) {
                        startInput.value = self.formatDateTimeLocal(startTime);
                        endInput.value = self.formatDateTimeLocal(now);
                    }

                    self.setChartTimeRange(chartKey, { hours: 1 });
                });
            }
            // 新增：评价按钮事件
            const metricsBtn = document.querySelector(`.metrics-btn[data-chart="${chartNum}"]`);
            if (metricsBtn) {
                metricsBtn.addEventListener('click', () => {
                    this.showMetricsForChart(chartKey);
                });
            }

            // 全屏按钮
            const fullscreenBtn = document.querySelector(`.fullscreen-btn[data-chart="${chartNum}"]`);
            if (fullscreenBtn) {
                fullscreenBtn.addEventListener('click', function() {
                    self.toggleChartFullscreen(chartKey);
                });
            }
        };

        /**
         * 设置图表时间范围
         */
        MultiChartMonitoring.prototype.setChartTimeRange = function(chartKey, range) {
            const chart = this.charts[chartKey];
            if (!chart) return;

            chart.currentTimeRange = range;
            this.refreshChartData(chartKey);
        };

        /**
         * 加载所有图表数据
         */
        MultiChartMonitoring.prototype.loadAllChartsData = function() {
            for (const chartKey in this.charts) {
                // 额外保险：如果配置被禁用就直接跳过
                if (this.chartConfigs[chartKey]?.enabled === false) continue;

                const chart = this.charts[chartKey];
                if (chart.currentTimeRange && chart.currentTimeRange.hours) {
                    this.refreshChartData(chartKey);
                } else {
                    console.log(`图表 ${chartKey} 为自定义模式，跳过自动刷新`);
                }
            }
        };

        /**
         * 刷新单个图表数据
         */
        MultiChartMonitoring.prototype.refreshChartData = async function(chartKey) {
    const chart = this.charts[chartKey];
    if (!chart) return;

    try {
        this.showChartLoading(chartKey);

        const timeRange = chart.currentTimeRange || this.defaultTimeRange;
        let queryParams = {
            limit: 200,
            category: chart.config.category   // ✅ 始终传递 category
        };

        if (timeRange.hours) {
            const endTime = new Date();
            const startTime = new Date(endTime.getTime() - timeRange.hours * 60 * 60 * 1000);
            queryParams.start_time = formatLocalDateTime(startTime);
            queryParams.end_time = formatLocalDateTime(endTime);
        } else if (timeRange.startTime && timeRange.endTime) {
            // ✅ 使用 timeRange 对象中的 startTime/endTime
            queryParams.start_time = timeRange.startTime.replace('T', ' ');
            queryParams.end_time = timeRange.endTime.replace('T', ' ');
        }

        console.log(`刷新图表 ${chartKey}，查询参数:`, queryParams);
        const data = await MonitoringAPI.getRealtimeData(queryParams);

        if (data && data.data) {
            data.data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
            this.updateChart(chartKey, data);
            this.updateChartStats(chartKey, data);
        }
    } catch (error) {
        console.error(`刷新图表 ${chartKey} 数据失败:`, error);
        this.showError(`获取数据失败: ${error.message}`);
    } finally {
        this.hideChartLoading(chartKey);
    }
};

        /**
         * 更新图表数据
         */
        MultiChartMonitoring.prototype.updateChart = function(chartKey, data) {
            const chart = this.charts[chartKey];
            if (!chart || !chart.instance || !data || !data.data) return;

            chart.data = data.data;

            const actualData = [];
            const predictedData = [];

            chart.data.forEach(function(item) {
                const timestamp = new Date(item.timestamp);

                if (item.actual_value !== null && !isNaN(item.actual_value)) {
                    actualData.push([timestamp, item.actual_value]);
                }

                if (item.predicted_value !== null && !isNaN(item.predicted_value)) {
                    predictedData.push([timestamp, item.predicted_value]);
                }
            });

            chart.instance.setOption({
                series: [
                    { data: actualData },
                    { data: predictedData }
                ]
            });
        };

        /**
         * 更新图表统计信息
         */
        MultiChartMonitoring.prototype.updateChartStats = function(chartKey, data) {
            // 这里可以添加图表特定的统计信息更新逻辑
            if (data.stats) {
                console.log(`图表 ${chartKey} 统计信息:`, data.stats);
            }
        };



        /**
         * 显示图表加载状态
         */
        MultiChartMonitoring.prototype.showChartLoading = function(chartKey) {
            const loadingEl = document.getElementById(`chart-loading-${chartKey.split('-')[1]}`);
            if (loadingEl) {
                loadingEl.style.display = 'flex';
            }
        };

        /**
         * 隐藏图表加载状态
         */
        MultiChartMonitoring.prototype.hideChartLoading = function(chartKey) {
            const loadingEl = document.getElementById(`chart-loading-${chartKey.split('-')[1]}`);
            if (loadingEl) {
                loadingEl.style.display = 'none';
            }
        };

        /**
         * 启动所有图表的自动刷新
         */
        MultiChartMonitoring.prototype.startAutoRefreshForAll = function() {
            const self = this;
            if (this.globalRefreshInterval) {
                clearInterval(this.globalRefreshInterval);
            }

            this.globalRefreshInterval = setInterval(function() {
                self.loadAllChartsData();
            }, this.refreshInterval);
        };

        /**
         * 停止所有自动刷新
         */
        MultiChartMonitoring.prototype.stopAutoRefreshForAll = function() {
            if (this.globalRefreshInterval) {
                clearInterval(this.globalRefreshInterval);
                this.globalRefreshInterval = null;
            }
        };

        /**
         * 切换图表全屏
         */
        MultiChartMonitoring.prototype.toggleChartFullscreen = function(chartKey) {
            const chart = this.charts[chartKey];
            if (!chart) return;

            const chartDom = document.getElementById(chart.config.chartId);
            if (!chartDom) return;

            if (!document.fullscreenElement) {
                if (chartDom.requestFullscreen) {
                    chartDom.requestFullscreen();
                }
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                }
            }
        };

        /**
         * 显示错误信息
         */
        MultiChartMonitoring.prototype.showError = function(message) {
            console.error(message);
            const warningElement = document.getElementById('data-warning');
            if (warningElement) {
                warningElement.textContent = '错误: ' + message;
                warningElement.style.display = 'block';
                warningElement.style.backgroundColor = '#f8d7da';
                warningElement.style.color = '#721c24';
                warningElement.style.borderColor = '#f5c6cb';

                setTimeout(() => {
                    warningElement.style.display = 'none';
                }, 5000);
            }
        };

        /**
         * 销毁实例
         */
        MultiChartMonitoring.prototype.destroy = function() {
            this.stopAutoRefreshForAll();

            for (const chartKey in this.charts) {
                if (this.charts[chartKey].instance) {
                    this.charts[chartKey].instance.dispose();
                }
            }
            this.charts = {};
        };

        return MultiChartMonitoring;
    })();

    // 页面加载完成后初始化
    document.addEventListener('DOMContentLoaded', function() {
        // 初始化导航栏
        const navbarContainer = document.getElementById('navbar-container');
        if (navbarContainer && typeof Navbar !== 'undefined') {
            Navbar.init(navbarContainer, 'monitoring');
        }

        // 初始化多图表监控
        window.multiChartMonitoring = new MultiChartMonitoring();

        // 退出页面时清理
        window.addEventListener('beforeunload', function() {
            if (window.multiChartMonitoring) {
                window.multiChartMonitoring.destroy();
            }
        });
    });