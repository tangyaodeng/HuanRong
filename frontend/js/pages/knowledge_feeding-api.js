// knowledge_feeding-api.js
const KnowledgeFeedingAPI = {
    baseURL: '/api/v1/knowledge-feeding',

    // 获取文件列表（分页、筛选、搜索）
    async getFiles(params = {}) {
        const query = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseURL}/?${query}`);
        if (!response.ok) throw new Error('获取文件列表失败');
        return response.json();
    },

    // 获取统计信息
    async getStats() {
        const response = await fetch(`${this.baseURL}/stats`);
        if (!response.ok) throw new Error('获取统计失败');
        return response.json();
    },

    // 上传文件
    async uploadFile(formData) {
        const response = await fetch(`${this.baseURL}/upload`, {
            method: 'POST',
            body: formData, // 直接传递 FormData，不要设置 Content-Type
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '上传失败');
        }
        return response.json();
    },

    // 删除文件
    async deleteFile(fileId) {
        const response = await fetch(`${this.baseURL}/${fileId}`, {
            method: 'DELETE',
        });
        if (!response.ok) throw new Error('删除失败');
        return true;
    },

    // 重新处理文件（可选）
    async reprocessFile(fileId) {
        const response = await fetch(`${this.baseURL}/${fileId}/reprocess`, {
            method: 'POST',
        });
        if (!response.ok) throw new Error('重新处理失败');
        return response.json();
    }
};