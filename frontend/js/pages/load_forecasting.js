(function () {
    'use strict';

    var chartInstances = {};

    document.addEventListener('DOMContentLoaded', async function () {
        if (typeof Navbar !== 'undefined') {
            Navbar.init(document.getElementById('navbar-container'), 'load_forecasting');
        }

        showLoading();

        try {
            var data = await LoadForecastingAPI.getPredictions();
            updatePageInfo(data);
            initCharts(data);
            initDailyPlanModal(data);
        } catch (error) {
            showError('获取预测数据失败: ' + error.message);
        } finally {
            hideLoading();
        }

        window.addEventListener('resize', function () {
            Object.values(chartInstances).forEach(function(chart) {
                if (chart) chart.resize();
            });
        });
    });

    function showLoading() {
        var el = document.getElementById('global-loading');
        if (el) el.style.display = 'flex';
    }

    function hideLoading() {
        var el = document.getElementById('global-loading');
        if (el) el.style.display = 'none';
    }

    function showError(msg) {
        console.error(msg);
        var warn = document.getElementById('data-warning');
        if (warn) {
            warn.textContent = msg;
            warn.style.display = 'block';
        }
    }

    function updatePageInfo(data) {
        var baseDateEl = document.getElementById('base-date');
        if (baseDateEl && data.forecast_start) {
            baseDateEl.textContent = data.forecast_start.split(' ')[0];
        }

        if (data.daily && data.daily.length > 0) {
            var todayTotal = data.daily[0].total;
            var todayEl = document.getElementById('today-total-load');
            if (todayEl) todayEl.textContent = todayTotal.toLocaleString() + ' kW';
        }

        if (data.hourly && data.hourly.length > 0) {
            var maxVal = -1, maxIdx = 0;
            data.hourly.forEach(function(item, idx) {
                if (item.value > maxVal) {
                    maxVal = item.value;
                    maxIdx = idx;
                }
            });
            var peakTime = data.hourly[maxIdx].timestamp.slice(11, 16) + ' - ' +
                           data.hourly[Math.min(maxIdx+1, data.hourly.length-1)].timestamp.slice(11, 16);
            var peakEl = document.getElementById('peak-hour');
            if (peakEl) peakEl.textContent = peakTime;
        }
    }

    function createBarChart(containerId, xData, barData, barName, barColor) {
        var dom = document.getElementById(containerId);
        if (!dom) return null;
        var chart = echarts.init(dom);
        chart.setOption({
            tooltip: { trigger: 'axis' },
            legend: { data: [barName], bottom: 0 },
            grid: { left: '3%', right: '4%', bottom: '12%', top: '15%', containLabel: true },
            xAxis: { type: 'category', data: xData, axisLabel: { rotate: 0 } },
            yAxis: { type: 'value', name: barName + ' (kW)', splitLine: { lineStyle: { type: 'dashed' } } },
            series: [{
                name: barName, type: 'bar', data: barData,
                itemStyle: { color: barColor, borderRadius: [4,4,0,0] }, barMaxWidth: 20
            }]
        });
        return chart;
    }

    function initCharts(data) {
        // 图表1：未来三天逐时
        var hourlyX = data.hourly.map(function(item) {
            return item.timestamp.slice(5, 16);
        });
        var hourlyBar = data.hourly.map(function(item) { return item.value; });
        chartInstances['chart1'] = createBarChart(
            'chart-1', hourlyX, hourlyBar, '冷量负荷', '#3498db'
        );

        // 图表2：未来一周逐日
        var dailyX = [];
        var dailyBar = [];
        if (data.daily.length > 0) {
            var firstDate = new Date(data.daily[0].date + 'T00:00:00');
            for (var i = 0; i < 7; i++) {
                var d = new Date(firstDate);
                d.setDate(d.getDate() + i);
                var dateStr = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
                var found = data.daily.find(function(item) { return item.date === dateStr; });
                dailyX.push(dateStr.slice(5));
                dailyBar.push(found ? found.total : 0);
            }
        }
        chartInstances['chart2'] = createBarChart(
            'chart-2', dailyX, dailyBar, '日总冷量', '#2ecc71'
        );

        // 图表3：未来一月逐周
        var weeklyX = [];
        var weeklyBar = [];
        if (data.weekly.length > 0) {
            for (var w = 0; w < 5; w++) {
                if (w < data.weekly.length) {
                    weeklyX.push(data.weekly[w].week);
                    weeklyBar.push(data.weekly[w].total);
                } else {
                    weeklyX.push('第'+(w+1)+'周');
                    weeklyBar.push(0);
                }
            }
        } else {
            for (var i=1; i<=5; i++) { weeklyX.push('第'+i+'周'); weeklyBar.push(0); }
        }
        chartInstances['chart3'] = createBarChart(
            'chart-3', weeklyX, weeklyBar, '周总冷量', '#9b59b6'
        );

        // 图表4：未来一年逐月
        var monthlyX = [];
        var monthlyBar = [];
        if (data.monthly.length > 0) {
            for (var m = 0; m < 12; m++) {
                if (m < data.monthly.length) {
                    monthlyX.push(data.monthly[m].month);
                    monthlyBar.push(data.monthly[m].total);
                } else {
                    monthlyX.push('M'+(m+1));
                    monthlyBar.push(0);
                }
            }
        } else {
            for (var i=1; i<=12; i++) { monthlyX.push(i+'月'); monthlyBar.push(0); }
        }
        chartInstances['chart4'] = createBarChart(
            'chart-4', monthlyX, monthlyBar, '月总冷量', '#1abc9c'
        );
    }

    function initDailyPlanModal(data) {
        var modal = document.getElementById('daily-plan-modal');
        var openBtn = document.getElementById('daily-plan-btn');
        var closeBtn = document.getElementById('modal-close-btn');
        var tbody = document.getElementById('plan-table-body');

        var planRows = data.hourly.slice(0, 24);
        var html = '';
        planRows.forEach(function(item) {
            var ts = new Date(item.timestamp);
            var hourStr = String(ts.getHours()).padStart(2,'0') + ':00';
            var temp = (20 + Math.sin(Math.PI*(ts.getHours()-6)/12)*10).toFixed(1);
            var weather = '晴';
            var humidity = 60;
            var wind = '南风';
            var loadClass = item.value > 500 ? 'load-high' : (item.value > 300 ? 'load-mid' : 'load-low');
            html += '<tr>' +
                '<td>' + hourStr + '</td>' +
                '<td>' + temp + '</td>' +
                '<td>' + humidity + '</td>' +
                '<td><span class="weather-icon">☀️</span> ' + weather + '</td>' +
                '<td>' + wind + '</td>' +
                '<td class="' + loadClass + '">' + item.value.toFixed(0) + '</td>' +
                '</tr>';
        });
        tbody.innerHTML = html;

        openBtn.addEventListener('click', function() {
            modal.classList.add('active');
        });
        closeBtn.addEventListener('click', function() {
            modal.classList.remove('active');
        });
        modal.addEventListener('click', function(e) {
            if (e.target === modal) modal.classList.remove('active');
        });
    }
})();