/**
 * API封装模块 - 项目管理 js/pages/project-api.js
 */
const API = {
    // API基础配置
    baseURL: 'http://localhost:8000/api/v1',

    // 通用请求方法
    async request(endpoint, method = 'GET', data = null) {
        const url = `${this.baseURL}${endpoint}`;
        const config = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };

        if (data && (method === 'POST' || method === 'PUT')) {
            config.body = JSON.stringify(data);
        }

        try {
            console.log(`API请求: ${method} ${url}`, data || '');
            const response = await fetch(url, config);

            // 处理HTTP错误状态
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP ${response.status}: ${errorText || response.statusText}`);
            }

            // 处理204 No Content响应（DELETE操作）
            if (response.status === 204) {
                return null;
            }

            const result = await response.json();
            console.log(`API响应: ${method} ${url}`, result);
            return result;

        } catch (error) {
            console.error(`API请求失败: ${method} ${url}`, error);
            throw error;
        }
    },

    // ==================== 项目管理API ====================

    /**
     * 获取项目列表（支持分页、搜索、筛选）
     * @param {Object} filters - 筛选条件 {status, search}
     * @param {number} page - 页码，默认1
     * @param {number} pageSize - 每页数量，默认10
     * @returns {Promise} 项目列表和分页信息
     */
    async getProjects(filters = {}, page = 1, pageSize = 10) {
        const queryParams = new URLSearchParams({
            page: page.toString(),
            page_size: pageSize.toString(),
        });

        // 添加筛选参数
        if (filters.status) queryParams.append('status', filters.status);
        if (filters.search) queryParams.append('search', filters.search);

        return this.request(`/projects?${queryParams.toString()}`);
    },

    /**
     * 获取项目统计信息
     * @returns {Promise} 统计信息 {total_projects, active_projects, total_devices}
     */
    async getProjectStats() {
        return this.request('/projects/stats');
    },

    /**
     * 获取单个项目详情
     * @param {number|string} projectId - 项目ID或UUID
     * @returns {Promise} 项目详情
     */
    async getProject(projectId) {
        // 判断是数字ID还是UUID
        if (isNaN(projectId)) {
            return this.request(`/projects/uuid/${projectId}`);
        }
        return this.request(`/projects/${projectId}`);
    },

    /**
     * 创建新项目
     * @param {Object} projectData - 项目数据 {name, code, description, status, tags}
     * @returns {Promise} 创建的项目
     */
    async createProject(projectData) {
        // 转换标签格式：字符串转数组
        const data = {
            ...projectData,
            tags: projectData.tags ?
                projectData.tags.split(',').map(tag => tag.trim()).filter(tag => tag) :
                []
        };
        return this.request('/projects', 'POST', data);
    },

    /**
     * 更新项目
     * @param {number} projectId - 项目ID
     * @param {Object} projectData - 更新的项目数据
     * @returns {Promise} 更新后的项目
     */
    async updateProject(projectId, projectData) {
        // 转换标签格式
        const data = {
            ...projectData,
            tags: projectData.tags ?
                projectData.tags.split(',').map(tag => tag.trim()).filter(tag => tag) :
                []
        };

        return this.request(`/projects/${projectId}`, 'PUT', data);
    },

    /**
     * 删除项目
     * @param {number} projectId - 项目ID
     * @returns {Promise} 无内容
     */
    async deleteProject(projectId) {
        return this.request(`/projects/${projectId}`, 'DELETE');
    },

    /**
     * 获取项目的设备列表
     * @param {number} projectId - 项目ID
     * @returns {Promise} 设备列表
     */
    async getProjectDevices(projectId) {
        return this.request(`/projects/${projectId}/devices`);
    }
};

// 添加到全局对象 - 确保这行存在
if (typeof window !== 'undefined') {
    window.API = API;  // 注意：不是 window.ProjectAPI
}