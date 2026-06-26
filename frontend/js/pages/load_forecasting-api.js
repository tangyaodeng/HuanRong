// load_forecasting-api.js
var LoadForecastingAPI = {
    getPredictions: async function() {
        try {
            // 将 load-forecasting 改为 load_forecasting
            const response = await fetch('/api/v1/load_forecasting/predictions');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('获取负荷预测失败:', error);
            throw error;
        }
    }
};