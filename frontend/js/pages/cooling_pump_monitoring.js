/**
     * 实时监控页面主逻辑 - 多图表版本
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

            this.chartConfigs = {
                'chart-1': {
                    tableName: 'pre-dev-zlz-plc-ai215',
                    title: 'PLC AI215 - 1#冷却泵功率预测',
                    yAxisName: 'kW',
                    chartId: 'real-time-chart-1',
                    containerId: 'chart-container-1'
                },
                'chart-2': {
                    tableName: 'pre-dev-zlz-plc-ai223',
                    title: 'PLC AI223 - 2#冷却泵功率预测',
                    yAxisName: 'kW',
                    chartId: 'real-time-chart-2',
                    containerId: 'chart-container-2'
                },
            };

            this.init();
        }

        /**
         * 初始化所有图表
         */
        MultiChartMonitoring.prototype.init = function() {
            // 初始化前两个图表
            for (const chartKey in this.chartConfigs) {
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
                            const month = date.getMonth() + 1;
                            const day = date.getDate();
                            const hours = date.getHours().toString().padStart(2, '0');
                            const minutes = date.getMinutes().toString().padStart(2, '0');
                            return `${month}/${day} ${hours}:${minutes}`;
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
                    const startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);

                    const startInput = document.querySelector(`.start-time[data-chart="${chartNum}"]`);
                    const endInput = document.querySelector(`.end-time[data-chart="${chartNum}"]`);

                    if (startInput && endInput) {
                        startInput.value = self.formatDateTimeLocal(startTime);
                        endInput.value = self.formatDateTimeLocal(now);
                    }

                    self.setChartTimeRange(chartKey, { hours: 24 });
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
                this.refreshChartData(chartKey);
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
                let queryParams = {};

                if (timeRange.hours) {
                    const endTime = new Date();
                    const startTime = new Date(endTime.getTime() - timeRange.hours * 60 * 60 * 1000);

                    queryParams = {
                        start_time: startTime.toISOString().replace('T', ' ').split('.')[0],
                        end_time: endTime.toISOString().replace('T', ' ').split('.')[0],
                        limit: 200,
                        table: chart.config.tableName
                    };
                } else if (timeRange.startTime && timeRange.endTime) {
                    queryParams = {
                        start_time: timeRange.startTime,
                        end_time: timeRange.endTime,
                        limit: 200,
                        table: chart.config.tableName
                    };
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