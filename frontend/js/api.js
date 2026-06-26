// API通信模块
const API = {
    // API基础URL
    baseURL: 'http://localhost:8000/api',

    // 通用请求方法
    async request(endpoint, method = 'GET', data = null) {
        const url = `${this.baseURL}${endpoint}`;
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (data) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);

            if (!response.ok) {
                throw new Error(`HTTP错误: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error(`API请求失败 ${endpoint}:`, error);
            throw error;
        }
    },

    // 便捷方法
    async get(endpoint) {
        return this.request(endpoint, 'GET');
    },

    async post(endpoint, data) {
        return this.request(endpoint, 'POST', data);
    },

    async put(endpoint, data) {
        return this.request(endpoint, 'PUT', data);
    },

    async delete(endpoint) {
        return this.request(endpoint, 'DELETE');
    }
};
