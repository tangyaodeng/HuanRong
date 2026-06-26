// 工具函数模块 js/utils.js
const Utils = {
    // 格式化时间
    formatTime(timestamp, format = 'HH:mm') {
        if (!timestamp) return '-';
        const date = new Date(timestamp);
        const pad = (n) => n.toString().padStart(2, '0');

        const formats = {
            'HH:mm': `${pad(date.getHours())}:${pad(date.getMinutes())}`,
            'MM-DD HH:mm': `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`,
            'YYYY-MM-DD HH:mm': `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`,
            'YYYY-MM-DD': `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
        };

        return formats[format] || date.toLocaleString();
    },

    // 显示成功消息
    showSuccess(message) {
        this.showNotification(message, 'success');
    },

    // 显示错误消息
    showError(message) {
        this.showNotification(message, 'error');
    },

    // 显示警告消息
    showWarning(message) {
        this.showNotification(message, 'warning');
    },

    // 显示信息消息
    showInfo(message) {
        this.showNotification(message, 'info');
    },

    // 显示通知
    showNotification(message, type = 'info') {
        // 移除现有的通知
        const existing = document.querySelector('.notification');
        if (existing) existing.remove();

        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;

        // 根据类型设置图标
        let icon = 'fa-info-circle';
        if (type === 'success') icon = 'fa-check-circle';
        if (type === 'error') icon = 'fa-exclamation-circle';
        if (type === 'warning') icon = 'fa-exclamation-triangle';

        notification.innerHTML = `
            <div class="notification-content">
                <i class="fas ${icon}"></i>
                <span>${message}</span>
            </div>
            <button class="notification-close">&times;</button>
        `;

        // 添加到页面
        document.body.appendChild(notification);

        // 显示通知
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        // 绑定关闭事件
        notification.querySelector('.notification-close').addEventListener('click', () => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        });

        // 自动关闭（3秒后）
        setTimeout(() => {
            if (notification.parentNode) {
                notification.classList.remove('show');
                setTimeout(() => notification.remove(), 300);
            }
        }, 3000);
    },

    // 确认对话框
    confirm(message, title = '确认操作') {
        return new Promise((resolve) => {
            // 创建遮罩层
            const overlay = document.createElement('div');
            overlay.className = 'modal-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0,0,0,0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
            `;

            // 创建对话框
            const dialog = document.createElement('div');
            dialog.className = 'confirm-dialog';
            dialog.style.cssText = `
                background: white;
                padding: 24px;
                border-radius: 8px;
                min-width: 350px;
                max-width: 500px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            `;

            dialog.innerHTML = `
                <h3 style="margin: 0 0 15px 0; color: #333; font-size: 18px;">${title}</h3>
                <p style="margin: 0 0 25px 0; color: #666; line-height: 1.5;">${message}</p>
                <div style="display: flex; justify-content: flex-end; gap: 12px;">
                    <button class="btn-cancel" style="
                        padding: 8px 20px;
                        background: #f0f0f0;
                        border: 1px solid #ddd;
                        border-radius: 4px;
                        cursor: pointer;
                        color: #333;
                        font-size: 14px;
                        transition: background 0.2s;
                    ">取消</button>
                    <button class="btn-confirm" style="
                        padding: 8px 20px;
                        background: #dc3545;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-size: 14px;
                        transition: background 0.2s;
                    ">确认删除</button>
                </div>
            `;

            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            // 绑定事件
            const cancelBtn = dialog.querySelector('.btn-cancel');
            const confirmBtn = dialog.querySelector('.btn-confirm');

            const close = (result) => {
                overlay.remove();
                resolve(result);
            };

            cancelBtn.addEventListener('click', () => close(false));
            cancelBtn.addEventListener('mouseenter', () => {
                cancelBtn.style.background = '#e0e0e0';
            });
            cancelBtn.addEventListener('mouseleave', () => {
                cancelBtn.style.background = '#f0f0f0';
            });

            confirmBtn.addEventListener('click', () => close(true));
            confirmBtn.addEventListener('mouseenter', () => {
                confirmBtn.style.background = '#c82333';
            });
            confirmBtn.addEventListener('mouseleave', () => {
                confirmBtn.style.background = '#dc3545';
            });

            // ESC键关闭
            const handleEsc = (e) => {
                if (e.key === 'Escape') close(false);
            };
            document.addEventListener('keydown', handleEsc);

            // 点击遮罩层关闭
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) close(false);
            });

            // 移除事件监听器
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) close(false);
            });
        });
    },

    // 格式化数值
    formatNumber(num, decimals = 2) {
        if (num === null || num === undefined) return '0';
        return Number(num).toFixed(decimals);
    },

    // 防抖函数
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // 节流函数
    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    // 深拷贝
    deepCopy(obj) {
        return JSON.parse(JSON.stringify(obj));
    },

    // 生成随机ID
    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    },

    // 验证邮箱格式
    isValidEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    },

    // 下载文件
    downloadFile(filename, content, type = 'text/plain') {
        const blob = new Blob([content], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    },

    // 复制到剪贴板
    async copyToClipboard(text) {
        try {
            await navigator.clipboard.writeText(text);
            this.showSuccess('已复制到剪贴板');
        } catch (err) {
            // 备用方案
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            this.showSuccess('已复制到剪贴板');
        }
    },

    // 验证手机号格式
    isValidPhone(phone) {
        const re = /^1[3-9]\d{9}$/;
        return re.test(phone);
    },

    // 获取URL参数
    getUrlParam(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    },

    // 设置URL参数
    setUrlParam(name, value) {
        const url = new URL(window.location);
        url.searchParams.set(name, value);
        window.history.pushState({}, '', url);
    },

    // 移除URL参数
    removeUrlParam(name) {
        const url = new URL(window.location);
        url.searchParams.delete(name);
        window.history.pushState({}, '', url);
    }
};

// 添加到全局对象
if (typeof window !== 'undefined') {
    window.Utils = Utils;
}

