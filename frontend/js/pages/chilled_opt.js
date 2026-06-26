/**
 * 冷冻侧优化页面主逻辑 frontend/js/pages/chilled_opt.js
 * 版本：双图表独立版（查询模式 + 寻优模式）- 总功率版本
 * 重构：采用与 monitoring.js 相同的初始化与自动刷新模式，支持动态时间范围
 */

class ChilledOptPage {
    constructor() {
        this.api = window.ChilledOptAPI;
        this.updateInterval = null;          // 查询模式定时器（1分钟）
        this.optimUpdateInterval = null;     // 寻优模式定时器（1分钟）
        this.queryChart = null;               // 查询模式图表实例
        this.optimChart = null;                // 寻优模式图表实例

        this.modal = null;                     // 弹窗DOM
        this.modalOverlay = null;              // 遮罩层
        this.modalChart = null;                // 弹窗图表实例
        this.currentModalField = null;         // 当前选中字段
        this.currentModalUnit = '';            // 当前选中字段的单位

        this.iterationData = null;              // 缓存的最新迭代数据

        this.animationInterval = null;   // 动画定时器
        this.animationCurrentIndex = 0;  // 当前动画索引

        // 新增：当前图表的查询模式（实时/自定义）
        this.currentTimeRange = { hours: 1 };   // 默认实时模式：最近1小时
        this.optimStatusModal = null;
        this.optimStatusContent = null;

        // 初始化（同步）
        this.init();
    }

    // ==================== 初始化（同步，不等待异步数据） ====================
    init() {
        try {
            // 1. 初始化图表（同步）
            this.initQueryChart();
            this.initOptimChart();

            // 2. 绑定事件（同步）
            this.bindEvents();
            this.setDefaultTimeRange(1);    // 初始化输入框为最近1小时
            this.initModal();
            this.initOptimStatusModal();  
            // 3. 启动自动刷新定时器（同步）
            this.startAutoUpdate();          // 查询模式定时器
            this.startOptimAutoUpdate();     // 寻优模式定时器

            // 4. 立即加载一次所有数据（不等待）
            this.loadAllData();

            console.log('冷冻侧优化页面初始化完成（总功率版本，自动刷新已启动）');
        } catch (error) {
            console.error('初始化失败:', error);
            this.showMessage('页面初始化失败，请刷新重试', 'error');
        }
    }
    initOptimStatusModal() {
    this.optimStatusModal = document.getElementById('optim-status-modal');
    this.optimStatusContent = document.getElementById('optim-status-content');
    const closeBtn = document.getElementById('optim-status-close');
    if (closeBtn) closeBtn.addEventListener('click', () => this.closeOptimStatusModal());
    const overlay = document.getElementById('modal-overlay');
    if (overlay) {
        overlay.addEventListener('click', () => {
            if (this.optimStatusModal?.style.display === 'block') this.closeOptimStatusModal();
        });
    }
}

closeOptimStatusModal() {
    if (this.optimStatusModal) this.optimStatusModal.style.display = 'none';
    const overlay = document.getElementById('modal-overlay');
    if (overlay) overlay.style.display = 'none';
}

async showOptimStatusModal() {
    if (!this.optimStatusModal) return;
    
    // 先关闭可能打开的其他弹窗
    if (this.modal) this.modal.style.display = 'none';
    
    const overlay = document.getElementById('modal-overlay');
    if (overlay) overlay.style.display = 'block';
    this.optimStatusModal.style.display = 'block';
    this.optimStatusContent.innerHTML = '加载中...';

    try {
        const latest = await this.api.getLatestParameters();
        if (!latest) {
            this.optimStatusContent.innerHTML = '<p style="color:#6c757d;">暂无优化状态数据</p>';
            return;
        }

        const timestamp = latest.optimization_timestamp 
            ? new Date(latest.optimization_timestamp).toLocaleString('zh-CN') 
            : '--';
        const supplyApplied = latest.optimized_supply_temp_applied ? '✅ 是' : '❌ 否';
        const diffApplied = latest.optimized_temp_diff_applied ? '✅ 是' : '❌ 否';
        const failureReason = latest.failure_reasons || '无';

        // 转义HTML函数
        const escapeHtml = (str) => {
            if (!str) return '';
            return str.replace(/[&<>]/g, function(m) {
                if (m === '&') return '&amp;';
                if (m === '<') return '&lt;';
                if (m === '>') return '&gt;';
                return m;
            });
        };

        let failureHtml = '';
        if (failureReason !== '无' && failureReason.includes(';')) {
            const reasons = failureReason.split('; ');
            failureHtml = '<div style="max-height:500px; overflow-y:auto;">';
            reasons.forEach(reason => {
                failureHtml += `<div style="margin-bottom: 6px; line-height:1.4;">${escapeHtml(reason)}</div>`;
            });
            failureHtml += '</div>';
        } else {
            failureHtml = `<div>${escapeHtml(failureReason)}</div>`;
        }

        this.optimStatusContent.innerHTML = `
            <table style="width:100%; border-collapse: collapse;">
                <tr><td style="padding:8px 0; font-weight:600; width:40%;">优化时间戳</td><td>${escapeHtml(timestamp)}</td></tr>
                <tr><td style="padding:8px 0; font-weight:600;">供水温度优化可下发</td><td>${supplyApplied}</td></tr>
                <tr><td style="padding:8px 0; font-weight:600;">温差优化可下发</td><td>${diffApplied}</td></tr>
                <tr><td style="padding:8px 0; font-weight:600; vertical-align:top;">下发失败原因</td>
                    <td style="color:#dc3545;">${failureHtml}</td>
                </tr>
            </table>
        `;
    } catch (error) {
        console.error('获取优化状态失败:', error);
        this.optimStatusContent.innerHTML = '<p style="color:#dc3545;">获取状态失败，请稍后重试</p>';
    }
}
    // ==================== 加载所有数据（供定时器调用） ====================
    async loadAllData() {
        try {
            // 并行加载配置、优化数据、迭代数据
            await Promise.all([
                this.loadConfig(),
                this.loadOptimizationData(),
                this.loadIterationData()
            ]);
        } catch (error) {
            console.error('加载数据失败:', error);
            // 不弹出错误提示，避免频繁干扰
        }
    }

    // ==================== 查询模式图表 ====================
    initQueryChart() {
        const chartDom = document.getElementById('query-chart');
        if (!chartDom) {
            console.error('查询图表容器未找到');
            return;
        }
        if (typeof echarts === 'undefined') {
            console.error('ECharts未加载');
            return;
        }
        this.queryChart = echarts.init(chartDom);

        const option = {
            title: {
                text: '设备总功率优化趋势',
                left: 'center',
                textStyle: { fontSize: 14, fontWeight: 'bold' }
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross', label: { backgroundColor: '#6a7985' } },
                formatter: function(params) {
                    let result = params[0].axisValueLabel + '<br/>';
                    params.forEach(function(item) {
                        if (item.value && item.value[1] !== null) {
                            result += `${item.marker} ${item.seriesName}: ${item.value[1].toFixed(1)} kW<br/>`;
                        }
                    });
                    return result;
                }
            },
            legend: { data: ['当前设备总功率', '优化总功率'], top: 30, textStyle: { fontSize: 12 } },
            grid: { left: '3%', right: '3%', bottom: '3%', top: '15%', containLabel: true },
            xAxis: {
                type: 'time',
                boundaryGap: false,
                axisLabel: {
                    fontSize: 11,
                    formatter: function(value) {
                        const date = new Date(value);
                        return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
                    }
                }
            },
            yAxis: {
                type: 'value',
                name: '功率(kW)',
                position: 'left',
                axisLine: { show: true, lineStyle: { color: '#5470c6' } },
                axisLabel: { fontSize: 11 },
                nameTextStyle: { fontSize: 12 }
            },
            series: [
                { name: '当前设备总功率', type: 'line', smooth: true, lineStyle: { width: 3, color: '#5470c6' }, data: [] },
                { name: '优化总功率', type: 'line', smooth: true, lineStyle: { width: 3, color: '#91cc75' }, data: [] }
            ]
        };
        this.queryChart.setOption(option);
        window.addEventListener('resize', () => this.queryChart?.resize());
        console.log('查询图表初始化成功');
    }

    // 动态时间范围的图表更新
    async updateChartData() {
        if (!this.queryChart) {
            console.error('查询图表未初始化');
            return;
        }

        try {
            let startTime, endTime;

            // 根据 currentTimeRange 决定查询范围
            if (this.currentTimeRange.hours) {
                // 实时模式：动态计算
                endTime = new Date();
                startTime = new Date(endTime.getTime() - this.currentTimeRange.hours * 60 * 60 * 1000);
            } else if (this.currentTimeRange.startTime && this.currentTimeRange.endTime) {
                // 自定义模式：使用输入框的值
                startTime = new Date(this.currentTimeRange.startTime);
                endTime = new Date(this.currentTimeRange.endTime);
            } else {
                // 降级：使用默认最近1小时
                endTime = new Date();
                startTime = new Date(endTime.getTime() - 60 * 60 * 1000);
            }

            this.showLoading(true);

            const historyData = await this.api.getHistoryByUpdatedAt(startTime, endTime, 100);

            if (historyData.length === 0) {
                this.queryChart.setOption({ series: [{ data: [] }, { data: [] }] });
                this.showLoading(false);
                this.showMessage('该时间段内没有数据', 'info');
                return;
            }

            const currentData = [];
            const optimizedData = [];

            historyData.forEach(item => {
                const timestamp = new Date(item.updated_at);
                if (item.current_total_power != null) {
                    currentData.push([timestamp, item.current_total_power]);
                }
                if (item.optimized_total_power != null) {
                    optimizedData.push([timestamp, item.optimized_total_power]);
                }
            });

            if (currentData.length === 0 && optimizedData.length === 0) {
                this.showMessage('没有有效的数据点', 'info');
                this.queryChart.setOption({ series: [{ data: [] }, { data: [] }] });
                this.showLoading(false);
                return;
            }

            this.queryChart.setOption({
                series: [
                    { name: '当前设备总功率', data: currentData },
                    { name: '优化总功率', data: optimizedData }
                ]
            });

            this.showLoading(false);
        } catch (error) {
            console.error('更新查询图表数据失败:', error);
            this.showLoading(false);
            this.showMessage(`加载图表数据失败: ${error.message}`, 'error');
        }
    }

    // ==================== 寻优模式图表 ====================
    initOptimChart() {
        const chartDom = document.getElementById('optim-chart');
        if (!chartDom) {
            console.error('寻优图表容器未找到');
            return;
        }
        if (typeof echarts === 'undefined') {
            console.error('ECharts未加载');
            return;
        }
        this.optimChart = echarts.init(chartDom);
        console.log('寻优模式图表初始化成功');
    }

    async loadIterationData() {
        if (!this.optimChart) {
            console.error('寻优图表未初始化');
            return;
        }

        this.showLoading(true);

        try {
            const data = await this.api.getLatestIteration(); // 使用冷冻侧 API
            this.iterationData = data;

            if (!data || !data.combinations || data.combinations.length === 0) {
                this.showMessage('暂无迭代数据', 'info');
                this.renderOptimChart([]);
                document.getElementById('iteration-timestamp').textContent = '--';
                return;
            }

            const ts = data.timestamp ? new Date(data.timestamp).toLocaleString('zh-CN') : '--';
            document.getElementById('iteration-timestamp').textContent = ts;

            this.renderOptimChart(data.combinations);
        } catch (error) {
            console.error('加载迭代数据失败:', error);
            this.showMessage('加载迭代数据失败', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    renderOptimChart(combinations) {
        // 清除之前的动画
        if (this.animationInterval) {
            clearInterval(this.animationInterval);
            this.animationInterval = null;
        }

        if (combinations.length === 0) {
            this.optimChart.setOption({
                title: { text: '暂无迭代数据', left: 'center', top: 'center' },
                series: []
            }, { notMerge: true });
            return;
        }

        const indices = combinations.map(c => c.index);

        // 准备三条线的数据（总功率 + 主机总功率 + 冷冻泵总功率）
        const totalPowerData = combinations.map((c, idx) => [idx, c.total_power]);
        const hostPowerData = combinations.map((c, idx) => [idx, c.host_power]);       // 主机总功率
        const pumpPowerData = combinations.map((c, idx) => [idx, c.pump_power]);       // 冷冻泵总功率

        const tooltipFormatter = (params) => {
            if (!params || params.length === 0) return '';

            const dataIndex = params[0].dataIndex;
            const item = combinations[dataIndex];
            if (!item) return '';

            let result = `
                <div style="font-weight:bold; margin-bottom:4px;">组合 #${item.index}</div>
                <div>供水温度: ${item.actual_inlet_temp.toFixed(1)}℃</div>
                <div>回水温度: ${item.actual_return_temp.toFixed(1)}℃</div>
                <div>温差: ${item.delta_temp.toFixed(1)}℃</div>
                <div style="border-top:1px solid #ccc; margin:4px 0;"></div>
            `;

            // 遍历每个系列，添加带颜色标记的功率值
            params.forEach(series => {
                if (series.value && series.value[1] !== null) {
                    result += `${series.marker} ${series.seriesName}: ${series.value[1].toFixed(1)} kW<br/>`;
                }
            });

            result += `
                <div style="border-top:1px solid #ccc; margin-top:4px; padding-top:4px;">
                    节能: ${item.power_diff > 0 ? '+' : ''}${item.power_diff.toFixed(1)} kW (${item.power_diff_percent > 0 ? '+' : ''}${item.power_diff_percent.toFixed(1)}%)
                </div>
            `;
            return result;
        };

        const option = {
            title: {
                text: '迭代寻优过程 - 设备总功率分布',
                left: 'center',
                top: 0,
                textStyle: { fontSize: 14 }
            },
            tooltip: { trigger: 'axis', formatter: tooltipFormatter },
            legend: {
                data: ['总功率', '主机总功率', '冷冻泵总功率'],
                top: 30,
                textStyle: { fontSize: 11 }
            },
            grid: { left: '5%', right: '5%', bottom: '5%', top: '20%', containLabel: true },
            xAxis: {
                type: 'category',
                name: '组合序号',
                data: indices,
                axisLabel: { rotate: 45, interval: Math.floor(indices.length / 10) }
            },
            yAxis: { type: 'value', name: '功率 (kW)' },
            series: [
                {
                    name: '总功率',
                    type: 'line',
                    data: totalPowerData,
                    smooth: false,
                    lineStyle: { width: 2, color: '#5470c6' }, // 蓝色
                    symbol: 'none'
                },
                {
                    name: '主机总功率',
                    type: 'line',
                    data: hostPowerData,
                    smooth: false,
                    lineStyle: { width: 1.5, color: '#91cc75' }, // 翠绿
                    symbol: 'none'
                },
                {
                    name: '冷冻泵总功率',
                    type: 'line',
                    data: pumpPowerData,
                    smooth: false,
                    lineStyle: { width: 1.5, color: '#2e7d32' }, // 深绿
                    symbol: 'none'
                }
            ]
        };
        this.optimChart.setOption(option, { notMerge: true });
        // 移除自动启动动画，改为按钮触发
    }

    playAnimation() {
        if (!this.optimChart || !this.iterationData || !this.iterationData.combinations || this.iterationData.combinations.length === 0) {
            this.showMessage('暂无数据可播放动画', 'warning');
            return;
        }
        if (this.animationInterval) {
            clearInterval(this.animationInterval);
            this.animationInterval = null;
        }
        // 取消所有系列的高亮（共3个系列）
        for (let i = 0; i < 3; i++) {
            this.optimChart.dispatchAction({ type: 'downplay', seriesIndex: i });
        }
        this.startAnimationOnce(this.iterationData.combinations.length);
    }

    startAnimationOnce(dataLength) {
        let currentIndex = 0;
        const chart = this.optimChart;
        const intervalTime = 1000; // 1秒一个点

        for (let i = 0; i < 3; i++) {
            chart.dispatchAction({ type: 'downplay', seriesIndex: i });
        }

        this.animationInterval = setInterval(() => {
            for (let i = 0; i < 3; i++) {
                chart.dispatchAction({ type: 'downplay', seriesIndex: i });
            }
            // 高亮总功率系列（索引0）的当前点
            chart.dispatchAction({
                type: 'highlight',
                seriesIndex: 0,
                dataIndex: currentIndex
            });
            chart.dispatchAction({
                type: 'showTip',
                seriesIndex: 0,
                dataIndex: currentIndex
            });

            currentIndex++;
            if (currentIndex >= dataLength) {
                clearInterval(this.animationInterval);
                this.animationInterval = null;
                chart.dispatchAction({ type: 'downplay', seriesIndex: 0 });
                chart.dispatchAction({ type: 'hideTip' });
            }
        }, intervalTime);
    }

    // ==================== 定时更新（与 monitoring.js 一致） ====================
    startAutoUpdate() {
        if (this.updateInterval) clearInterval(this.updateInterval);
        this.updateInterval = setInterval(async () => {
            try {
                console.log('查询模式定时更新...');
                await this.loadOptimizationData();
                // updateChartData 在 loadOptimizationData 内部已被调用，无需重复
            } catch (err) {
                console.error('查询模式定时更新失败:', err);
            }
        }, 60000); // 1分钟
    }

    startOptimAutoUpdate() {
        if (this.optimUpdateInterval) clearInterval(this.optimUpdateInterval);
        this.optimUpdateInterval = setInterval(async () => {
            try {
                console.log('寻优模式定时更新...');
                await this.loadIterationData();
            } catch (err) {
                console.error('寻优模式定时更新失败:', err);
            }
        }, 60000); // 1分钟
    }

    destroy() {
        if (this.animationInterval) {
            clearInterval(this.animationInterval);
            this.animationInterval = null;
        }
        if (this.updateInterval) clearInterval(this.updateInterval);
        if (this.optimUpdateInterval) clearInterval(this.optimUpdateInterval);
        if (this.queryChart) this.queryChart.dispose();
        if (this.optimChart) this.optimChart.dispose();
    }

    // ==================== 历史弹窗相关 ====================
    initModal() {
        this.modal = document.getElementById('history-modal');
        this.modalOverlay = document.getElementById('modal-overlay');
        if (!this.modal || !this.modalOverlay) return;

        const chartDom = document.getElementById('modal-chart');
        if (chartDom) {
            this.modalChart = echarts.init(chartDom);
            const option = {
                tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
                legend: { data: ['当前值', '优化值'], top: 0 },
                grid: { left: '3%', right: '3%', bottom: '3%', top: '15%', containLabel: true },
                xAxis: { type: 'time', boundaryGap: false },
                yAxis: { type: 'value', name: '' },
                series: [
                    { name: '当前值', type: 'line', smooth: true, data: [] },
                    { name: '优化值', type: 'line', smooth: true, data: [] }
                ]
            };
            this.modalChart.setOption(option);
            window.addEventListener('resize', () => this.modalChart && this.modalChart.resize());
        }

        const closeBtn = document.getElementById('modal-close');
        if (closeBtn) closeBtn.addEventListener('click', () => this.closeModal());
        if (this.modalOverlay) this.modalOverlay.addEventListener('click', () => this.closeModal());

        const applyBtn = document.getElementById('modal-apply-time');
        if (applyBtn) applyBtn.addEventListener('click', () => this.loadModalChartData());

        const resetBtn = document.getElementById('modal-reset-time');
        if (resetBtn) resetBtn.addEventListener('click', () => {
            this.setModalDefaultTimeRange(1);
            this.loadModalChartData();
        });

        this.bindModalTriggers();
    }

    bindModalTriggers() {
        const rowMap = [
            { field: 'supply_temp', title: '冷冻水供水温度历史数据查询', unit: '℃' },
            { field: 'return_temp', title: '冷冻水回水温度历史数据查询', unit: '℃' },
            { field: 'temp_diff', title: '冷冻水温差历史数据查询', unit: '℃' },
            { field: 'total_power', title: '设备总功率历史数据查询', unit: 'kW' },
            { field: 'host_total_power', title: '主机总功率历史数据查询', unit: 'kW' },
            { field: 'chilled_pump_total_power', title: '冷冻泵总功率历史数据查询', unit: 'kW' }
        ];

        document.querySelectorAll('.comparison-check').forEach(el => {
            el.addEventListener('click', (e) => {
                const targetItem = e.target.closest('.comparison-item');
                if (!targetItem) return;

                const items = Array.from(document.querySelectorAll('.comparison-item'));
                const index = items.indexOf(targetItem);
                if (index === -1) return;

                const row = Math.floor(index / 4);
                if (row >= 0 && row < rowMap.length) {
                    this.openModal(rowMap[row].field, rowMap[row].title, rowMap[row].unit);
                } else {
                    console.warn('未知行索引:', row);
                }
            });
        });
    }

    openModal(field, title, unit) {
        if (!this.modal || !this.modalOverlay) return;

        this.currentModalField = field;
        this.currentModalUnit = unit;

        const titleEl = document.getElementById('modal-title');
        if (titleEl) titleEl.textContent = title;

        this.setModalDefaultTimeRange(1);

        if (this.modalChart) {
            this.modalChart.setOption({ yAxis: { name: unit } });
        }

        this.modal.style.display = 'block';
        this.modalOverlay.style.display = 'block';

        this.loadModalChartData();
    }

    closeModal() {
        if (this.modal) this.modal.style.display = 'none';
        if (this.modalOverlay) this.modalOverlay.style.display = 'none';
        this.currentModalField = null;
    }

    setModalDefaultTimeRange(hours = 1) {
        const now = new Date();
        const past = new Date(now.getTime() - hours * 60 * 60 * 1000);
        const formatDateTime = (date) => {
            const year = date.getFullYear();
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            const day = date.getDate().toString().padStart(2, '0');
            const hours = date.getHours().toString().padStart(2, '0');
            const minutes = date.getMinutes().toString().padStart(2, '0');
            return `${year}-${month}-${day}T${hours}:${minutes}`;
        };
        const startInput = document.getElementById('modal-start-time');
        const endInput = document.getElementById('modal-end-time');
        if (startInput) startInput.value = formatDateTime(past);
        if (endInput) endInput.value = formatDateTime(now);
    }

    async loadModalChartData() {
        if (!this.modalChart || !this.currentModalField) return;

        const startInput = document.getElementById('modal-start-time');
        const endInput = document.getElementById('modal-end-time');
        const startTime = startInput ? startInput.value : '';
        const endTime = endInput ? endInput.value : '';
        if (!startTime || !endTime) {
            this.setModalDefaultTimeRange(1);
            return this.loadModalChartData();
        }

        this.modalChart.showLoading();
        try {
            const data = await this.api.getDeviceHistory(
                this.currentModalField,
                new Date(startTime),
                new Date(endTime)
            );

            const currentData = data
                .map(item => [new Date(item.timestamp), item.current_value])
                .filter(item => item[1] !== null && item[1] !== undefined);

            const optimizedData = data
                .map(item => [new Date(item.timestamp), item.optimized_value])
                .filter(item => item[1] !== null && item[1] !== undefined);

            this.modalChart.setOption({
                series: [
                    { data: currentData },
                    { data: optimizedData }
                ]
            });
        } catch (error) {
            console.error('加载弹窗图表数据失败:', error);
            this.showMessage('加载数据失败', 'error');
        } finally {
            this.modalChart.hideLoading();
        }
    }

    // ==================== 配置加载与保存 ====================
    async loadConfig() {
        try {
            const config = await this.api.getConfig();
            this.fillConfigForm(config);
            console.log('配置加载成功:', config);
        } catch (error) {
            console.error('加载配置失败:', error);
            this.fillConfigForm({
                return_temp_lower_limit: 9.00,
                return_temp_upper_limit: 15.00,
                supply_temp_lower_limit: 7.00,
                supply_temp_upper_limit: 10.00,
                temp_diff_lower_limit: 4.00,
                temp_diff_upper_limit: 6.00
            });
        }
    }

    fillConfigForm(config) {
    const lowerLimit1 = document.getElementById('temp-lower-limit');
    const upperLimit1 = document.getElementById('temp-upper-limit-1');
    const lowerLimit2 = document.getElementById('temp-lower-limit-2');
    const upperLimit2 = document.getElementById('temp-upper-limit-2');
    const diffLower = document.getElementById('temp-diff-lower');
    const diffUpper = document.getElementById('temp-diff-upper');

    if (lowerLimit1) lowerLimit1.value = config.return_temp_lower_limit || 9.00;
    if (upperLimit1) upperLimit1.value = config.return_temp_upper_limit || 15.00;
    if (lowerLimit2) lowerLimit2.value = config.supply_temp_lower_limit || 7.00;
    if (upperLimit2) upperLimit2.value = config.supply_temp_upper_limit || 10.00;
    if (diffLower) diffLower.value = config.temp_diff_lower_limit || 4.00;
    if (diffUpper) diffUpper.value = config.temp_diff_upper_limit || 6.00;

    // ========== 新增：三个阈值字段 ==========
    const supplyThreshold = document.getElementById('supply-temp-threshold');
    const diffThreshold = document.getElementById('temp-diff-threshold');
    const savingThreshold = document.getElementById('energy-saving-threshold');

    if (supplyThreshold) supplyThreshold.value = config.supply_temp_threshold || 0.50;
    if (diffThreshold) diffThreshold.value = config.temp_diff_threshold || 0.80;
    if (savingThreshold) savingThreshold.value = config.energy_saving_threshold || 2.00;

    // 寻优周期字段（变量名一致）
    const optimizationCycle = document.getElementById('optimization-cycle');
    if (optimizationCycle) optimizationCycle.value = config.optimization_cycle_minutes || 5;
    // R²阈值字段（变量名一致）
    const r2Threshold = document.getElementById('r2-threshold');
    if (r2Threshold) r2Threshold.value = config.r2_threshold || 0.6;
}

    collectConfigForm() {
        const getValue = (id) => {
            const el = document.getElementById(id);
            return el ? parseFloat(el.value) : 0;
        };
        return {
            return_temp_lower_limit: getValue('temp-lower-limit'),
            return_temp_upper_limit: getValue('temp-upper-limit-1'),
            supply_temp_lower_limit: getValue('temp-lower-limit-2'),
            supply_temp_upper_limit: getValue('temp-upper-limit-2'),
            temp_diff_lower_limit: getValue('temp-diff-lower'),
            temp_diff_upper_limit: getValue('temp-diff-upper'),
            // 新增三个阈值字段
            supply_temp_threshold: getValue('supply-temp-threshold'),
            temp_diff_threshold: getValue('temp-diff-threshold'),
            energy_saving_threshold: getValue('energy-saving-threshold'),   // ← 添加逗号
            optimization_cycle_minutes: getValue('optimization-cycle'),
            r2_threshold: getValue('r2-threshold')
        };
    }

    async saveConfig() {
        try {
            const configData = this.collectConfigForm();

            if (configData.return_temp_upper_limit < configData.return_temp_lower_limit) {
                this.showMessage('回水温度上限必须大于或等于下限', 'error');
                return;
            }
            if (configData.supply_temp_upper_limit < configData.supply_temp_lower_limit) {
                this.showMessage('供水温度上限必须大于或等于下限', 'error');
                return;
            }
            if (configData.temp_diff_upper_limit < configData.temp_diff_lower_limit) {
                this.showMessage('温差上限必须大于或等于下限', 'error');
                return;
            }
            // 新增：阈值非负校验
            if (configData.supply_temp_threshold < 0) {
                this.showMessage('供水温度阈值不能为负数', 'error');
                return;
            }
            if (configData.temp_diff_threshold < 0) {
                this.showMessage('温差阈值不能为负数', 'error');
                return;
            }
            if (configData.energy_saving_threshold < 0) {
                this.showMessage('节能率阈值不能为负数', 'error');
                return;
            }
            if (configData.optimization_cycle_minutes < 1){
                this.showMessage('寻优周期必须大于等于1分钟', 'error');
                return;
            }
            // R²阈值字段（变量名一致）
            if (configData.r2_threshold < 0 || configData.r2_threshold > 1) {
                this.showMessage('R²阈值必须在0到1之间', 'error');
                return;
            }
            const saveButton = document.getElementById('save-params-btn');
            if (saveButton) {
                saveButton.disabled = true;
                saveButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';
            }

            await this.api.updateConfig(configData);
            this.showMessage('配置保存成功', 'success');
            await this.loadOptimizationData();

        } catch (error) {
            console.error('保存配置失败:', error);
            this.showMessage(`保存失败: ${error.message}`, 'error');
        } finally {
            const saveButton = document.getElementById('save-params-btn');
            if (saveButton) {
                saveButton.disabled = false;
                saveButton.innerHTML = '<i class="fas fa-save"></i> 保存配置';
            }
        }
    }

    // ==================== 右侧对比区与设备状态 ====================
    async loadOptimizationData() {
        try {
            const latestParams = await this.api.getLatestParameters();
            if (latestParams) {
                this.updateComparisonData(latestParams);
                this.updateDeviceStatus(latestParams.remarks);
                await this.updateChartData();  // 更新查询图表（使用动态时间范围）
            } else {
                this.showNoDataMessage();
                this.updateDeviceStatus('暂无设备状态信息');
            }
            console.log('优化数据加载成功');
        } catch (error) {
            console.error('加载优化数据失败:', error);
            this.showNoDataMessage();
            this.updateDeviceStatus('获取设备状态失败');
        }
    }

    updateComparisonData(params) {
        try {
            // 更新温度相关行（索引0-3供水，4-7回水，8-11温差）
            this.updateComparisonItem(0,  params.current_supply_temp,   params.optimized_supply_temp,   params.diff_supply_temp,   null, '℃');
            this.updateComparisonItem(4,  params.current_return_temp,   params.optimized_return_temp,   params.diff_return_temp,   null, '℃');
            this.updateComparisonItem(8,  params.current_temp_diff,     params.optimized_temp_diff,     params.diff_temp_diff,     null, '℃');

            // 更新总功率（索引12-15）
            this.updateComparisonItem(12, params.current_total_power,   params.optimized_total_power,   params.diff_total_power,   params.percent_total_power, 'kW');

            // 更新主机总功率（索引16-19）
            this.updateComparisonItem(16, params.current_host_total_power,   params.optimized_host_total_power,   params.diff_host_total_power,   params.percent_host_total_power, 'kW');

            // 更新冷冻泵总功率（索引20-23）
            this.updateComparisonItem(20, params.current_chilled_pump_total_power, params.optimized_chilled_pump_total_power, params.diff_chilled_pump_total_power, params.percent_chilled_pump_total_power, 'kW');

            this.updateSummaryInfo(params);
            this.updateTimestamp(params.updated_at);
        } catch (error) {
            console.error('更新对比数据失败:', error);
        }
    }

    updateComparisonItem(startIndex, currentValue, optimizedValue, diffValue, percentValue, unit) {
        const items = document.querySelectorAll('.comparison-item');
        const formatValue = (value) => {
            if (value === null || value === undefined) return '--';
            return value.toFixed(1);
        };

        // 当前值
        if (items[startIndex] && items[startIndex].querySelector('.comparison-value')) {
            items[startIndex].querySelector('.comparison-value').innerHTML =
                `${formatValue(currentValue)}<span class="comparison-unit">${unit}</span>`;
        }
        // 优化值
        if (items[startIndex + 1] && items[startIndex + 1].querySelector('.comparison-value')) {
            items[startIndex + 1].querySelector('.comparison-value').innerHTML =
                `${formatValue(optimizedValue)}<span class="comparison-unit">${unit}</span>`;
        }

        // 差值显示（节能为正，耗能为负）
        const isSaving = diffValue < 0;  // 节能（优化值 < 当前值）
        const absDiff = Math.abs(diffValue);
        const diffDisplay = isSaving ? `+${formatValue(absDiff)}` : `-${formatValue(absDiff)}`;

        const diffElement = items[startIndex + 2];
        if (diffElement && diffElement.querySelector('.comparison-value')) {
            diffElement.querySelector('.comparison-value').innerHTML =
                `${diffDisplay}<span class="comparison-unit">${unit}</span>`;
        }

        // 百分比显示（仅当存在 .comparison-note 元素且 percentValue 有效时）
        const noteElement = diffElement ? diffElement.querySelector('.comparison-note') : null;
        if (percentValue !== null && noteElement) {
            const absPercent = Math.abs(percentValue);
            const percentDisplay = isSaving ? `+${formatValue(absPercent)}%` : `-${formatValue(absPercent)}%`;
            noteElement.textContent = `(${percentDisplay})`;
        } else if (noteElement) {
            noteElement.textContent = '';  // 清空
        }

        // 颜色：节能 -> 红色 (positive-diff)，耗能 -> 绿色 (negative-diff)
        if (diffElement) {
            if (isSaving) {
                diffElement.classList.remove('negative-diff');
                diffElement.classList.add('positive-diff');
            } else if (diffValue > 0) {
                diffElement.classList.remove('positive-diff');
                diffElement.classList.add('negative-diff');
            }
        }
    }

    updateDeviceStatus(remarks) {
        try {
            const statusContainer = document.getElementById('device-status-content');
            if (!statusContainer) return;

            if (remarks) {
                const escapedRemarks = remarks
                    .replace(/&/g, '&amp;')
                    .replace(/</g, '&lt;')
                    .replace(/>/g, '&gt;')
                    .replace(/"/g, '&quot;')
                    .replace(/'/g, '&#039;');

                const parts = escapedRemarks.split(',');
                let htmlLines = [];
                let inDeviceStatusBlock = false;

                parts.forEach(part => {
                    let trimmed = part.trim();

                    if (trimmed.startsWith('数据时间:')) {
                        htmlLines.push(`<div style="color: #dc3545; font-weight: 600; margin-bottom: 8px;">${trimmed}</div>`);
                        return;
                    }

                    if (trimmed.startsWith('设备状态:')) {
                        const colonIndex = trimmed.indexOf(':');
                        const label = trimmed.substring(0, colonIndex + 1).trim();
                        const firstDevice = trimmed.substring(colonIndex + 1).trim();
                        htmlLines.push(`<div style="color: #28a745; font-weight: 500; margin-bottom: 4px;">${label}</div>`);
                        if (firstDevice) {
                            htmlLines.push(`<div style="color: #28a745; margin-left: 20px; margin-bottom: 3px;">${firstDevice}</div>`);
                        }
                        inDeviceStatusBlock = true;
                        return;
                    }

                    if (inDeviceStatusBlock && !trimmed.includes('数据超时') && !trimmed.includes('优化失败')) {
                        htmlLines.push(`<div style="color: #28a745; margin-left: 20px; margin-bottom: 3px;">${trimmed}</div>`);
                        return;
                    }

                    if (trimmed.includes('数据超时') || trimmed.includes('优化失败')) {
                        inDeviceStatusBlock = false;
                        htmlLines.push(`<div style="color: #ffc107; font-weight: 500; margin-top: 6px; margin-bottom: 5px;">⚠️ ${trimmed}</div>`);
                        return;
                    }

                    htmlLines.push(`<div style="margin-bottom: 3px;">${trimmed}</div>`);
                });

                statusContainer.innerHTML = htmlLines.join('');
                console.log('设备状态remarks解析完成:', remarks);
            } else {
                statusContainer.innerHTML = '<div style="color: #6c757d; font-style: italic; padding: 8px 0;">暂无设备状态信息</div>';
            }
        } catch (error) {
            console.error('更新设备状态失败:', error);
            statusContainer.innerHTML = '<div style="color: #dc3545; padding: 8px 0;">⚠️ 设备状态解析异常</div>';
        }
    }

    updateSummaryInfo(params) {
        const savingElem = document.getElementById('total-energy-saving');
        const percentElem = document.getElementById('energy-saving-percent');

        if (params.total_energy_saving !== null && params.total_energy_saving !== undefined) {
            const saving = params.total_energy_saving; // 节能为正，耗能为负
            const absSaving = Math.abs(saving);
            const sign = saving > 0 ? '+' : (saving < 0 ? '-' : '');
            if (savingElem) savingElem.textContent = `${sign}${absSaving.toFixed(1)} kW`;
            // 节能 -> 红色 (#dc3545)，耗能 -> 绿色 (#28a745)
            if (savingElem) {
                if (saving > 0) {
                    savingElem.style.color = '#dc3545';
                } else if (saving < 0) {
                    savingElem.style.color = '#28a745';
                } else {
                    savingElem.style.color = ''; // 恢复默认
                }
            }
        }
        if (params.energy_saving_percent !== null && params.energy_saving_percent !== undefined) {
            const percent = params.energy_saving_percent; // 节能为正，耗能为负
            const absPercent = Math.abs(percent);
            const sign = percent > 0 ? '+' : (percent < 0 ? '-' : '');
            if (percentElem) percentElem.textContent = `${sign}${absPercent.toFixed(1)}%`;
            if (percentElem) {
                if (percent > 0) {
                    percentElem.style.color = '#dc3545';
                } else if (percent < 0) {
                    percentElem.style.color = '#28a745';
                } else {
                    percentElem.style.color = '';
                }
            }
        }
    }

    updateTimestamp(timestamp) {
        const timeSpan = document.getElementById('update-time-text');
        if (timeSpan) {
            if (timestamp) {
                const date = new Date(timestamp);
                timeSpan.textContent = date.toLocaleString('zh-CN');
            } else {
                timeSpan.textContent = '--';
            }
        }
    }

    showNoDataMessage() {
        const savingElem = document.getElementById('total-energy-saving');
        const percentElem = document.getElementById('energy-saving-percent');
        if (savingElem) savingElem.textContent = '-- kW';
        if (percentElem) percentElem.textContent = '--%';
        this.updateTimestamp(null);
        const items = document.querySelectorAll('.comparison-item');
        items.forEach(item => {
            const labelElement = item.querySelector('.comparison-label');
            if (labelElement) {
                const valueElement = item.querySelector('.comparison-value');
                if (valueElement) {
                    valueElement.textContent = '--';
                }
            }
        });
    }

    // ==================== 通用工具方法 ====================
    bindEvents() {
        const saveBtn = document.getElementById('save-params-btn');
        if (saveBtn) saveBtn.addEventListener('click', () => this.saveConfig());
        const statusBtn = document.getElementById('optim-status-btn');
        if (statusBtn) statusBtn.addEventListener('click', () => this.showOptimStatusModal());
        const applyBtn = document.getElementById('apply-chart-time');
        if (applyBtn) {
            applyBtn.addEventListener('click', () => {
                const startInput = document.getElementById('chart-start-time');
                const endInput = document.getElementById('chart-end-time');
                if (!startInput || !endInput) return;
                const startTime = startInput.value;
                const endTime = endInput.value;
                if (!startTime || !endTime) {
                    this.showMessage('请选择开始时间和结束时间', 'warning');
                    return;
                }
                if (new Date(startTime) >= new Date(endTime)) {
                    this.showMessage('开始时间必须早于结束时间', 'error');
                    return;
                }
                // 设置为自定义模式
                this.currentTimeRange = {
                    startTime: startTime + ':00',
                    endTime: endTime + ':00'
                };
                this.updateChartData(); // 立即刷新
            });
        }

        const resetBtn = document.getElementById('reset-chart-time');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                // 重置为实时模式（最近1小时）
                this.currentTimeRange = { hours: 1 };
                this.updateChartData(); // 立即刷新
                // 同时更新输入框显示，让用户看到当前时间范围
                const now = new Date();
                const past = new Date(now.getTime() - 60 * 60 * 1000);
                const format = (date) => {
                    const y = date.getFullYear();
                    const m = String(date.getMonth() + 1).padStart(2, '0');
                    const d = String(date.getDate()).padStart(2, '0');
                    const h = String(date.getHours()).padStart(2, '0');
                    const mi = String(date.getMinutes()).padStart(2, '0');
                    return `${y}-${m}-${d}T${h}:${mi}`;
                };
                const startInput = document.getElementById('chart-start-time');
                const endInput = document.getElementById('chart-end-time');
                if (startInput) startInput.value = format(past);
                if (endInput) endInput.value = format(now);
            });
        }

        const animBtn = document.getElementById('play-optim-animation');
        if (animBtn) animBtn.addEventListener('click', () => this.playAnimation());

        // 其他非必要的事件（如 control-input 变化）可忽略或同样判空
        document.querySelectorAll('.control-input').forEach(input => {
            input.addEventListener('change', () => {});
        });
    }

    setDefaultTimeRange(hours = 1) {
        const now = new Date();
        const past = new Date(now.getTime() - hours * 60 * 60 * 1000);
        const formatDateTime = (date) => {
            const year = date.getFullYear();
            const month = (date.getMonth() + 1).toString().padStart(2, '0');
            const day = date.getDate().toString().padStart(2, '0');
            const hours = date.getHours().toString().padStart(2, '0');
            const minutes = date.getMinutes().toString().padStart(2, '0');
            return `${year}-${month}-${day}T${hours}:${minutes}`;
        };
        const startInput = document.getElementById('chart-start-time');
        const endInput = document.getElementById('chart-end-time');
        if (startInput) startInput.value = formatDateTime(past);
        if (endInput) endInput.value = formatDateTime(now);
    }

    showMessage(message, type = 'info') {
        const messageDiv = document.createElement('div');
        messageDiv.textContent = message;
        messageDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 4px;
            color: white;
            font-weight: 500;
            z-index: 9999;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            animation: slideIn 0.3s ease-out;
        `;
        if (type === 'success') {
            messageDiv.style.backgroundColor = '#28a745';
        } else if (type === 'warning') {
            messageDiv.style.backgroundColor = '#ffc107';
            messageDiv.style.color = '#212529';
        } else if (type === 'error') {
            messageDiv.style.backgroundColor = '#dc3545';
        } else {
            messageDiv.style.backgroundColor = '#17a2b8';
        }
        document.body.appendChild(messageDiv);
        setTimeout(() => {
            messageDiv.style.animation = 'slideOut 0.3s ease-in forwards';
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 300);
        }, 3000);
        if (!document.querySelector('#message-animations')) {
            const style = document.createElement('style');
            style.id = 'message-animations';
            style.textContent = `
                @keyframes slideIn {
                    from { transform: translateX(100%); opacity: 0; }
                    to { transform: translateX(0); opacity: 1; }
                }
                @keyframes slideOut {
                    from { transform: translateX(0); opacity: 1; }
                    to { transform: translateX(100%); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }
    }

    showLoading(show) {
        const loadingElement = document.getElementById('chart-loading');
        if (loadingElement) {
            loadingElement.style.display = show ? 'flex' : 'none';
        }
    }
}

// 页面加载完成后初始化（与 monitoring.js 一致）
document.addEventListener('DOMContentLoaded', function() {
    function checkECharts() {
        if (typeof echarts === 'undefined') {
            console.warn('ECharts未加载，等待100ms后重试...');
            setTimeout(checkECharts, 100);
            return;
        }
        console.log('ECharts已加载，开始初始化页面（总功率版本）');
        window.chilledOptPage = new ChilledOptPage();
    }
    checkECharts();
});