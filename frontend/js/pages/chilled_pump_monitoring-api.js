var MonitoringAPI = {
        /**
         * 获取实时预测数据
         * @param {Object} params - 查询参数（包括表名）
         * @returns {Promise} - 预测数据
         */
        getRealtimeData: async function(params = {}) {
            try {
                const queryParams = new URLSearchParams();

                // 添加查询参数
                if (params.start_time) queryParams.append('start_time', params.start_time);
                if (params.end_time) queryParams.append('end_time', params.end_time);
                if (params.limit) queryParams.append('limit', params.limit);
                if (params.table) queryParams.append('table_name', params.table);

                const response = await fetch(`/api/v1/monitoring/realtime-data?${queryParams.toString()}`, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP错误! 状态码: ${response.status}`);
                }

                return await response.json();
            } catch (error) {
                console.error('获取实时数据失败:', error);
                throw error;
            }
        },

        /**
         * 获取多个设备的最新数据
         * @param {Array} tableNames - 表名数组
         * @param {number} limit - 返回的数据条数限制
         * @returns {Promise} - 最新数据
         */
        getMultiLatestData: async function(tableNames = [], limit = 100) {
            try {
                const promises = tableNames.map(tableName =>
                    this.getRealtimeData({ limit, table: tableName })
                );

                const results = await Promise.all(promises);
                return results.reduce((acc, result, index) => {
                    acc[tableNames[index]] = result;
                    return acc;
                }, {});
            } catch (error) {
                console.error('获取多设备数据失败:', error);
                throw error;
            }
        },

        /**
         * 获取统计数据
         * @param {string} tableName - 表名（可选）
         * @returns {Promise} - 统计数据
         */
        getStats: async function(tableName = null) {
            try {
                let url = '/api/v1/monitoring/stats';
                if (tableName) {
                    url += `?table_name=${tableName}`;
                }

                const response = await fetch(url, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP错误! 状态码: ${response.status}`);
                }

                return await response.json();
            } catch (error) {
                console.error('获取统计信息失败:', error);
                throw error;
            }
        },

        /**
         * 获取系统状态
         * @returns {Promise} - 系统状态
         */
        getSystemStatus: async function() {
            try {
                const response = await fetch('/api/v1/monitoring/system-status', {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP错误! 状态码: ${response.status}`);
                }

                return await response.json();
            } catch (error) {
                console.error('获取系统状态失败:', error);
                throw error;
            }
        }
    };