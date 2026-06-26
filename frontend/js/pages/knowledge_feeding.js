// knowledge_feeding.js
const KnowledgeFeedingManager = {
    // 状态管理
    currentPage: 1,
    pageSize: 10,
    pollingTimer: null,
    selectedIds: new Set(),
    filters: {
        status: '',
        search: '',
    },

    // 初始化
    async init() {
        this.bindEvents();
        await this.loadStats();
        await this.loadFiles();
        this.startPolling();
    },

    // 自动轮询：有待处理/索引中文件时每5秒刷新
    startPolling() {
        this.stopPolling();
        this.pollingTimer = setInterval(async () => {
            const el = document.getElementById('processing-files');
            if (el && parseInt(el.textContent) > 0) {
                await this.loadStats();
                await this.loadFiles();
            }
        }, 5000);
    },

    stopPolling() {
        if (this.pollingTimer) {
            clearInterval(this.pollingTimer);
            this.pollingTimer = null;
        }
    },

    // 绑定事件
    bindEvents() {
        // 上传按钮
        document.getElementById('upload-file-btn').addEventListener('click', () => {
            this.openUploadModal();
        });

        // 模态框关闭
        document.querySelector('#upload-modal .modal-close').addEventListener('click', () => {
            this.closeUploadModal();
        });
        document.getElementById('modal-cancel').addEventListener('click', () => {
            this.closeUploadModal();
        });

        // 上传提交
        document.getElementById('modal-upload').addEventListener('click', () => {
            this.handleUpload();
        });

        // 搜索和筛选
        document.getElementById('apply-filters').addEventListener('click', () => {
            this.filters.status = document.getElementById('status-filter').value;
            this.filters.search = document.getElementById('search-input').value.trim();
            this.currentPage = 1;
            this.loadFiles();
        });

        document.getElementById('reset-filters').addEventListener('click', () => {
            document.getElementById('status-filter').value = '';
            document.getElementById('search-input').value = '';
            this.filters.status = '';
            this.filters.search = '';
            this.currentPage = 1;
            this.loadFiles();
        });

        // 分页
        document.getElementById('prev-page').addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadFiles();
            }
        });
        document.getElementById('next-page').addEventListener('click', () => {
            this.currentPage++;
            this.loadFiles();
        });
        document.getElementById('page-size').addEventListener('change', (e) => {
            this.pageSize = parseInt(e.target.value);
            this.currentPage = 1;
            this.loadFiles();
        });

        // 全选 / 取消全选
        document.getElementById('select-all').addEventListener('change', (e) => {
            const checked = e.target.checked;
            document.querySelectorAll('#knowledge-table-body input[type="checkbox"].row-checkbox').forEach(cb => {
                cb.checked = checked;
                const id = parseInt(cb.dataset.id);
                if (checked) {
                    this.selectedIds.add(id);
                } else {
                    this.selectedIds.delete(id);
                }
            });
            this.updateBatchUI();
        });

        // 批量删除按钮
        document.getElementById('batch-delete-btn').addEventListener('click', () => {
            this.confirmBatchDelete();
        });

        // 表格操作（事件委托）
        document.getElementById('knowledge-table-body').addEventListener('click', (e) => {
            // 复选框变化
            if (e.target.classList.contains('row-checkbox')) {
                const id = parseInt(e.target.dataset.id);
                if (e.target.checked) {
                    this.selectedIds.add(id);
                } else {
                    this.selectedIds.delete(id);
                }
                // 更新全选状态
                const allCbs = document.querySelectorAll('#knowledge-table-body input[type="checkbox"].row-checkbox');
                document.getElementById('select-all').checked =
                    allCbs.length > 0 && this.selectedIds.size === allCbs.length;
                this.updateBatchUI();
                return;
            }

            const target = e.target.closest('button');
            if (!target) return;
            const fileId = target.dataset.id;
            if (target.classList.contains('btn-delete')) {
                this.confirmDelete(fileId);
            } else if (target.classList.contains('btn-reprocess')) {
                this.reprocessFile(fileId);
            }
        });
    },

    // 加载统计卡片
    async loadStats() {
        try {
            const stats = await KnowledgeFeedingAPI.getStats();
            document.getElementById('total-files').textContent = stats.total || 0;
            document.getElementById('completed-files').textContent = stats.completed || 0;
            document.getElementById('processing-files').textContent = (stats.indexing || 0) + (stats.pending || 0);
        } catch (error) {
            console.error('加载统计失败:', error);
        }
    },

    // 加载文件列表
    async loadFiles() {
        const tbody = document.getElementById('knowledge-table-body');
        tbody.innerHTML = '<tr><td colspan="7" class="loading">加载中...</td></tr>';

        try {
            const params = {
                page: this.currentPage,
                page_size: this.pageSize,
                status: this.filters.status,
                search: this.filters.search,
            };
            const data = await KnowledgeFeedingAPI.getFiles(params);

            // 更新分页
            document.getElementById('current-page').textContent = data.page;
            document.getElementById('total-pages').textContent = data.total_pages;
            document.getElementById('prev-page').disabled = data.page <= 1;
            document.getElementById('next-page').disabled = data.page >= data.total_pages;

            // 渲染表格
            if (data.items.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center">暂无数据</td></tr>';
                this.selectedIds.clear();
                this.updateBatchUI();
                return;
            }

            // 清除不在当前页的选中项
            const currentIds = new Set(data.items.map(f => f.id));
            let needClear = false;
            for (const id of this.selectedIds) {
                if (!currentIds.has(id)) { needClear = true; break; }
            }
            if (needClear) this.selectedIds.clear();

            tbody.innerHTML = data.items.map(file => `
                <tr>
                    <td><input type="checkbox" class="row-checkbox" data-id="${file.id}" ${this.selectedIds.has(file.id) ? 'checked' : ''}></td>
                    <td title="${this.escapeHtml(file.original_name)}">
                        <i class="fas fa-file-alt"></i> ${this.escapeHtml(file.original_name)}
                    </td>
                    <td>${this.formatFileSize(file.file_size)}</td>
                    <td><span class="status-badge status-${file.status}">${this.statusLabel(file.status)}</span></td>
                    <td>${this.formatDateTime(file.created_at)}</td>
                    <td>${this.formatDateTime(file.updated_at)}</td>
                    <td class="actions">
                        <button class="btn btn-sm btn-info btn-reprocess" data-id="${file.id}" title="重新索引">
                            <i class="fas fa-redo"></i>
                        </button>
                        <button class="btn btn-sm btn-danger btn-delete" data-id="${file.id}" title="删除">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                </tr>
            `).join('');

            // 更新全选状态
            document.getElementById('select-all').checked = false;
            this.updateBatchUI();
        } catch (error) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-danger">加载失败: ${error.message}</td></tr>`;
        }
    },

    // 打开上传模态框
    openUploadModal() {
        document.getElementById('upload-form').reset();
        document.getElementById('upload-modal').style.display = 'block';
    },

    // 关闭上传模态框
    closeUploadModal() {
        document.getElementById('upload-modal').style.display = 'none';
    },

    // 处理上传
    async handleUpload() {
        const fileInput = document.getElementById('file-input');
        const files = fileInput.files;
        if (files.length === 0) {
            alert('请选择文件');
            return;
        }

        const allowed = ['.txt', '.md', '.docx', '.xlsx', '.pptx', '.pdf'];
        for (const file of files) {
            const ext = '.' + file.name.split('.').pop().toLowerCase();
            if (!allowed.includes(ext)) {
                alert(`不支持的文件格式: ${file.name}\n仅支持 ${allowed.join(', ')} 文件`);
                return;
            }
        }

        const description = document.getElementById('file-description').value.trim();
        const formData = new FormData();
        for (const file of files) {
            formData.append('files', file);
        }
        formData.append('description', description);

        const uploadBtn = document.getElementById('modal-upload');
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> 上传中 (${files.length}个文件)...`;

        try {
            await KnowledgeFeedingAPI.uploadFile(formData);
            this.closeUploadModal();
            await this.loadStats();
            await this.loadFiles();
            this.startPolling();
            alert(`${files.length} 个文件上传成功，已加入处理队列`);
        } catch (error) {
            alert('上传失败: ' + error.message);
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '开始上传';
        }
    },

    // 确认删除
    confirmDelete(fileId) {
        if (confirm('确定要删除该文件吗？此操作不可恢复。')) {
            this.deleteFile(fileId);
        }
    },

    // 执行删除
    async deleteFile(fileId) {
        try {
            await KnowledgeFeedingAPI.deleteFile(fileId);
            this.selectedIds.delete(fileId);
            this.loadStats();
            this.loadFiles();
        } catch (error) {
            alert('删除失败: ' + error.message);
        }
    },

    // 更新批量操作 UI
    updateBatchUI() {
        const btn = document.getElementById('batch-delete-btn');
        const countEl = document.getElementById('selected-count');
        countEl.textContent = this.selectedIds.size;
        btn.style.display = this.selectedIds.size > 0 ? '' : 'none';
    },

    // 确认批量删除
    confirmBatchDelete() {
        if (this.selectedIds.size === 0) return;
        if (confirm(`确定要删除选中的 ${this.selectedIds.size} 个文件吗？此操作不可恢复。`)) {
            this.batchDelete();
        }
    },

    // 执行批量删除
    async batchDelete() {
        const ids = Array.from(this.selectedIds);
        let success = 0, fail = 0;
        for (const id of ids) {
            try {
                await KnowledgeFeedingAPI.deleteFile(id);
                this.selectedIds.delete(id);
                success++;
            } catch (error) {
                fail++;
            }
        }
        this.loadStats();
        this.loadFiles();
        if (fail > 0) {
            alert(`删除完成：${success} 个成功，${fail} 个失败`);
        }
    },

    // 重新处理
    async reprocessFile(fileId) {
        try {
            await KnowledgeFeedingAPI.reprocessFile(fileId);
            this.loadFiles();
        } catch (error) {
            alert('操作失败: ' + error.message);
        }
    },

    // 工具方法
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    formatFileSize(bytes) {
        if (!bytes) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        let i = 0;
        while (bytes >= 1024 && i < units.length - 1) {
            bytes /= 1024;
            i++;
        }
        return bytes.toFixed(1) + ' ' + units[i];
    },

    formatDateTime(isoString) {
        if (!isoString) return '';
        const date = new Date(isoString);
        return date.toLocaleString('zh-CN', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit'
        });
    },

    statusLabel(status) {
        const map = {
            'pending': '待处理',
            'indexing': '索引中',
            'completed': '已完成',
            'failed': '失败'
        };
        return map[status] || status;
    }
};