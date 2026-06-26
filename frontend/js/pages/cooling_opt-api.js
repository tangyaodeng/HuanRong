/**
 * 冷却侧优化API接口 frontend/js/pages/cooling_opt-api.js
 */

class CoolingOptAPI {
    constructor() {
        this.baseURL = '/api/v1/cooling_opt_config';
    }

    /**
     * 获取冷却侧优化配置
     * @returns {Promise<Object>} 配置数据
     */
    async getConfig() {
        try {
            const response = await fetch(`${this.baseURL}/config`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('获取配置失败:', error);
            throw error;
        }
    }

    /**
     * 更新冷却侧优化配置
     * @param {Object} configData - 配置数据
     * @returns {Promise<Object>} 更新后的配置
     */
    async updateConfig(configData) {
        try {
            const response = await fetch(`${this.baseURL}/config`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(configData)
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('更新配置失败:', error);
            throw error;
        }
    }

    /**
     * 获取优化参数列表
     * @param {Object} options - 查询选项
     * @returns {Promise<Object>} 参数列表
     */
    async getParameters(options = {}) {
        try {
            const { skip = 0, limit = 100, applied = null, start_date = null, end_date = null } = options;
            let url = `${this.baseURL}/parameters?skip=${skip}&limit=${limit}`;

            if (applied !== null) {
                url += `&applied=${applied}`;
            }

            if (start_date) {
                // 确保日期格式正确
                const startDateStr = typeof start_date === 'string' ? start_date : start_date.toISOString();
                url += `&start_date=${encodeURIComponent(startDateStr)}`;
            }

            if (end_date) {
                // 确保日期格式正确
                const endDateStr = typeof end_date === 'string' ? end_date : end_date.toISOString();
                url += `&end_date=${encodeURIComponent(endDateStr)}`;
            }

            console.log('请求URL:', url); // 调试用
            const response = await fetch(url);
            if (!response.ok) {
                const errorText = await response.text();
                console.error('API错误响应:', errorText);
                throw new Error(`HTTP error! status: ${response.status}, response: ${errorText}`);
            }
            return await response.json();
        } catch (error) {
            console.error('获取参数列表失败:', error);
            throw error;
        }
    }

    /**
     * 获取最新的优化参数
     * @returns {Promise<Object>} 最新的优化参数
     */
    async getLatestParameters() {
        try {
            const response = await fetch(`${this.baseURL}/parameters/latest`);
            if (!response.ok) {
                if (response.status === 404) {
                    // 没有优化参数时返回null
                    return null;
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('获取最新参数失败:', error);
            return null;
        }
    }

    /**
     * 获取优化统计信息
     * @param {number} days - 统计天数
     * @returns {Promise<Object>} 统计信息
     */
    async getOptimizationStats(days = 30) {
        try {
            const response = await fetch(`${this.baseURL}/parameters/stats?days=${days}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('获取统计信息失败:', error);
            throw error;
        }
    }

    /**
     * 获取历史优化数据用于图表
     * @param {Date} startTime - 开始时间
     * @param {Date} endTime - 结束时间
     * @returns {Promise<Array>} 历史数据
     */
    async getHistoryData(startTime, endTime) {
        try {
            // 确保传入正确的日期格式
            const startDateStr = startTime.toISOString();
            const endDateStr = endTime.toISOString();

            console.log('获取历史数据，时间范围:', startDateStr, '至', endDateStr);

            // 直接调用后端的历史数据接口
            const response = await fetch(
                `${this.baseURL}/parameters/history?start_date=${encodeURIComponent(startDateStr)}&end_date=${encodeURIComponent(endDateStr)}&limit=100`
            );

            if (!response.ok) {
                const errorText = await response.text();
                console.error('获取历史数据API错误:', errorText);
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            // 转换数据格式为图表需要的格式
            return data.map(param => ({
                timestamp: param.optimization_timestamp,
                current_total_power: param.current_total_power,
                optimized_total_power: param.optimized_total_power,
                diff_total_power: param.diff_total_power,
                updated_at: param.updated_at
            }));
        } catch (error) {
            console.error('获取历史数据失败:', error);
            return [];
        }
    }

/**
 * 获取历史优化数据（按updated_at排序）
 * @param {Date} startTime - 开始时间
 * @param {Date} endTime - 结束时间
 * @param {number} limit - 限制数量
 * @returns {Promise<Array>} 历史数据
 */
async getHistoryByUpdatedAt(startTime, endTime, limit = 100) {
    try {
        // 格式化时间，确保格式正确
        const formatDateForAPI = (date) => {
            return date.toISOString().split('.')[0] + 'Z'; // 格式: 2026-02-08T09:00:00Z
        };

        const startDateStr = formatDateForAPI(startTime);
        const endDateStr = formatDateForAPI(endTime);

        console.log('获取历史数据，时间范围:', startDateStr, '至', endDateStr);

        // 通过getParameters接口获取数据
        const params = await this.getParameters({
            start_date: startDateStr,
            end_date: endDateStr,
            limit: limit
        });

        if (params && params.parameters && params.parameters.length > 0) {
            // 按updated_at排序（最新的在前）
            const sortedParams = params.parameters.sort((a, b) => {
                return new Date(b.updated_at) - new Date(a.updated_at);
            });

            // 转换数据格式
            return sortedParams.map(param => ({
                timestamp: param.optimization_timestamp,
                updated_at: param.updated_at,
                current_total_power: param.current_total_power,
                optimized_total_power: param.optimized_total_power,
                diff_total_power: param.diff_total_power,
                remarks: param.remarks
            }));
        }

        console.log('没有获取到历史数据');
        return [];
    } catch (error) {
        console.error('按updated_at获取历史数据失败:', error);
        return [];
    }
}
/**
 * 获取指定设备字段的历史数据
 * @param {string} field - 字段标识，如 'total_power', 'host3_power'
 * @param {Date} startTime - 开始时间
 * @param {Date} endTime - 结束时间
 * @param {number} limit - 返回记录数上限
 * @returns {Promise<Array>} 历史数据数组 [{timestamp, current_value, optimized_value}]
 */
async getDeviceHistory(field, startTime, endTime, limit = 100) {
    try {
        const formatDateForAPI = (date) => {
            return date.toISOString().split('.')[0] + 'Z'; // 格式: 2026-02-26T12:00:00Z
        };
        const startStr = formatDateForAPI(startTime);
        const endStr = formatDateForAPI(endTime);
        const url = `${this.baseURL}/parameters/history/field?field=${encodeURIComponent(field)}&start_date=${encodeURIComponent(startStr)}&end_date=${encodeURIComponent(endStr)}&limit=${limit}`;
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('获取设备历史数据失败:', error);
        return [];
    }
}
/**
 * 获取最近一次优化迭代的全部组合数据（从Redis）
 * @returns {Promise<Object>} 包含 timestamp 和 combinations 数组
 */
async getLatestIteration() {
    try {
        const response = await fetch(`${this.baseURL}/iteration/latest`);
        if (!response.ok) {
            if (response.status === 404) {
                return null; // 无数据
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('获取迭代数据失败:', error);
        return null;
    }
}
}

// 创建全局实例
window.CoolingOptAPI = new CoolingOptAPI();