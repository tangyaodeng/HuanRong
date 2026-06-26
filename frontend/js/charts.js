// 图表管理模块
const Charts = {
    // 获取负荷曲线图配置
    getLoadChartOption() {
        return {
            title: {
                text: '设备负荷实时曲线',
                left: 'center',
                textStyle: {
                    fontSize: 14,
                    fontWeight: 'normal'
                }
            },
            tooltip: {
                trigger: 'axis',
                formatter: function(params) {
                    let result = `${params[0].axisValueLabel}<br/>`;
                    params.forEach(param => {
                        result += `${param.marker} ${param.seriesName}: ${param.value}%<br/>`;
                    });
                    return result;
                }
            },
            legend: {
                data: ['负荷率'],
                top: 30
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
                    formatter: '{HH}:{mm}'
                }
            },
            yAxis: {
                type: 'value',
                min: 0,
                max: 100,
                axisLabel: {
                    formatter: '{value}%'
                },
                splitLine: {
                    lineStyle: {
                        type: 'dashed'
                    }
                }
            },
            series: [
                {
                    name: '负荷率',
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    sampling: 'average',
                    itemStyle: {
                        color: '#5470c6'
                    },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            {
                                offset: 0,
                                color: 'rgba(84, 112, 198, 0.3)'
                            },
                            {
                                offset: 1,
                                color: 'rgba(84, 112, 198, 0.1)'
                            }
                        ])
                    },
                    data: []
                }
            ]
        };
    },

    // 获取预测对比图配置
    getPredictionChartOption() {
        return {
            title: {
                text: '预测 vs 实际对比',
                left: 'center',
                textStyle: {
                    fontSize: 14,
                    fontWeight: 'normal'
                }
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'cross'
                }
            },
            legend: {
                data: ['实际值', '预测值'],
                top: 30
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
                boundaryGap: false
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    formatter: '{value}%'
                },
                splitLine: {
                    lineStyle: {
                        type: 'dashed'
                    }
                }
            },
            series: [
                {
                    name: '实际值',
                    type: 'line',
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 6,
                    itemStyle: {
                        color: '#91cc75'
                    },
                    data: []
                },
                {
                    name: '预测值',
                    type: 'line',
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 6,
                    lineStyle: {
                        type: 'dashed'
                    },
                    itemStyle: {
                        color: '#fac858'
                    },
                    data: []
                }
            ]
        };
    },

    // 更新负荷图表数据
    updateLoadChartData(data) {
        return {
            xAxis: {
                data: data.timestamps || []
            },
            series: [{
                data: data.loadValues || []
            }]
        };
    },

    // 更新预测图表数据
    updatePredictionChartData(data) {
        return {
            xAxis: {
                data: data.timestamps || []
            },
            series: [
                {
                    data: data.actualValues || []
                },
                {
                    data: data.predictedValues || []
                }
            ]
        };
    }
};