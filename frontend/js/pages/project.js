/**
 * 项目管理页面逻辑 js/pages/project.js
 */
const ProjectManager = {
    init() {
        this.currentPage = 1;
        this.pageSize = 10;
        this.totalProjects = 0;
        this.currentProjectId = null;

        this.loadProjects();
        this.bindEvents();
    },

    async loadProjects() {
        const tableBody = document.getElementById('project-table-body');
        tableBody.innerHTML = '<tr><td colspan="7" class="loading">正在加载项目数据...</td></tr>';

        try {
            // 从API获取项目数据
            const result = await API.getProjects(this.getFilters(), this.currentPage, this.pageSize);

            // 调试输出
            console.log('API响应:', result);

            if (!result) {
                throw new Error('API返回空数据');
            }

            // 处理不同的响应格式
            let projects = [];
            if (Array.isArray(result)) {
                projects = result;
                this.totalProjects = result.length;
            } else if (result.projects) {
                projects = result.projects;
                this.totalProjects = result.total || projects.length;
            } else {
                projects = result.data || [];
                this.totalProjects = result.total || projects.length;
            }

            this.renderProjects(projects);
            this.updatePagination();

            // 更新概览卡片 - 使用正确的属性名
            if (result.overview) {
                this.updateOverviewCards(result.overview);
            } else {
                // 如果没有概览数据，只更新总数
                this.updateOverviewCards({ total_projects: this.totalProjects });
            }

        } catch (error) {
            console.error('加载项目失败:', error);
            tableBody.innerHTML = `<tr><td colspan="7" class="error">
                加载项目数据失败: ${error.message}<br>
                请检查：<br>
                1. 后端服务是否运行 (http://localhost:8000)<br>
                2. API路径是否正确 (/api/v1)<br>
                3. 控制台查看详细错误
            </td></tr>`;
        }
    },

    getFilters() {
        return {
            status: document.getElementById('status-filter').value,
            search: document.getElementById('search-input').value
        };
    },

    renderProjects(projects) {
        const tableBody = document.getElementById('project-table-body');

        if (!projects || projects.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="empty-state">
                        <i class="fas fa-project-diagram"></i>
                        <div>暂无项目数据</div>
                        <button class="btn btn-primary" onclick="ProjectManager.showProjectModal()">创建第一个项目</button>
                    </td>
                </tr>
            `;
            return;
        }

        let html = '';
        projects.forEach(project => {
            const statusClass = `status-${project.status}`;
            const statusText = this.getStatusText(project.status);

            html += `
                <tr data-project-id="${project.id}">
                    <td>
                        <strong>${project.name}</strong>
                        ${project.description ? `<div class="text-muted">${project.description}</div>` : ''}
                        ${project.tags && project.tags.length > 0 ?
                            `<div class="tag-list">${this.renderTags(project.tags)}</div>` : ''}
                    </td>
                    <td><code>${project.code}</code></td>
                    <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    <td><strong>${project.device_count || 0}</strong></td>
                    <td>${Utils.formatTime(project.created_at, 'YYYY-MM-DD')}</td>
                    <td>${Utils.formatTime(project.updated_at, 'YYYY-MM-DD HH:mm')}</td>
                    <td>
                        <div class="action-buttons">
                            <button class="btn-action btn-view" onclick="ProjectManager.viewProject(${project.id})">
                                <i class="fas fa-eye"></i>
                            </button>
                            <button class="btn-action btn-edit" onclick="ProjectManager.editProject(${project.id})">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn-action btn-devices" onclick="ProjectManager.viewProjectDevices(${project.id})" title="查看设备">
                                <i class="fas fa-server"></i>
                            </button>
                            <button class="btn-action btn-delete" onclick="ProjectManager.deleteProject(${project.id})">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        });

        tableBody.innerHTML = html;
    },

    renderTags(tags) {
        if (!tags) return '';
        const tagArray = Array.isArray(tags) ? tags : tags.split(',');
        return tagArray.map(tag => `<span class="tag">${tag.trim()}</span>`).join('');
    },

    getStatusText(status) {
        const statusMap = { active: '使用中', inactive: '未使用'};
        return statusMap[status] || status;
    },

    updatePagination() {
        const totalPages = Math.ceil(this.totalProjects / this.pageSize);
        document.getElementById('current-page').textContent = this.currentPage;
        document.getElementById('total-pages').textContent = totalPages;
        document.getElementById('prev-page').disabled = this.currentPage <= 1;
        document.getElementById('next-page').disabled = this.currentPage >= totalPages;
    },

    updateOverviewCards(overview) {
        // 修改这里：使用正确的属性名
        document.getElementById('total-projects').textContent = overview.total_projects || overview.total || 0;
        document.getElementById('active-projects').textContent = overview.active_projects || overview.active || 0;
        document.getElementById('total-devices').textContent = overview.total_devices || 0;
    },

    bindEvents() {
        // 创建项目按钮
        document.getElementById('create-project-btn').addEventListener('click', () => {
            this.showProjectModal();
        });

        // 筛选按钮
        document.getElementById('apply-filters').addEventListener('click', () => {
            this.currentPage = 1;
            this.loadProjects();
        });

        document.getElementById('reset-filters').addEventListener('click', () => {
            document.getElementById('status-filter').value = '';
            document.getElementById('search-input').value = '';
            this.currentPage = 1;
            this.loadProjects();
        });

        // 搜索
        document.getElementById('search-btn').addEventListener('click', () => {
            this.currentPage = 1;
            this.loadProjects();
        });

        document.getElementById('search-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.currentPage = 1;
                this.loadProjects();
            }
        });

        // 分页
        document.getElementById('prev-page').addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadProjects();
            }
        });

        document.getElementById('next-page').addEventListener('click', () => {
            const totalPages = Math.ceil(this.totalProjects / this.pageSize);
            if (this.currentPage < totalPages) {
                this.currentPage++;
                this.loadProjects();
            }
        });

        // 每页数量变化
        document.getElementById('page-size').addEventListener('change', (e) => {
            this.pageSize = parseInt(e.target.value);
            this.currentPage = 1;
            this.loadProjects();
        });

        // 模态框事件
        this.bindModalEvents();
    },

    bindModalEvents() {
        const modal = document.getElementById('project-modal');

        modal.querySelector('.modal-close').addEventListener('click', () => {
            modal.classList.remove('active');
        });

        document.getElementById('modal-cancel').addEventListener('click', () => {
            modal.classList.remove('active');
        });

        document.getElementById('modal-save').addEventListener('click', () => {
            this.saveProject();
        });
    },

    async showProjectModal(projectId = null) {
        const modal = document.getElementById('project-modal');
        const title = document.getElementById('modal-title');
        const form = document.getElementById('project-form');

        form.reset();

        if (projectId) {
            title.textContent = '编辑项目';
            this.currentProjectId = projectId;

            try {
                const project = await API.getProject(projectId);
                console.log('编辑项目数据:', project);

                document.getElementById('project-name').value = project.name;
                document.getElementById('project-code').value = project.code;
                document.getElementById('project-description').value = project.description || '';
                document.getElementById('project-status').value = project.status || 'active';

                // 处理标签：数组转字符串
                if (project.tags && Array.isArray(project.tags)) {
                    document.getElementById('project-tags').value = project.tags.join(', ');
                } else {
                    document.getElementById('project-tags').value = project.tags || '';
                }

            } catch (error) {
                console.error('加载项目数据失败:', error);
                Utils.showError('加载项目数据失败: ' + error.message);
                return;
            }
        } else {
            title.textContent = '创建新项目';
            this.currentProjectId = null;
        }

        modal.classList.add('active');
    },

    async saveProject() {
        const form = document.getElementById('project-form');
        if (!form.checkValidity()) {
            form.reportValidity();
            return;
        }

        const projectData = {
            name: document.getElementById('project-name').value,
            code: document.getElementById('project-code').value,
            description: document.getElementById('project-description').value || null,
            status: document.getElementById('project-status').value,
            tags: document.getElementById('project-tags').value
        };

        console.log('保存项目数据:', projectData);

        try {
            if (this.currentProjectId) {
                await API.updateProject(this.currentProjectId, projectData);
                Utils.showSuccess('项目更新成功');
            } else {
                await API.createProject(projectData);
                Utils.showSuccess('项目创建成功');
            }

            document.getElementById('project-modal').classList.remove('active');
            this.loadProjects();

        } catch (error) {
            console.error('保存项目失败:', error);
            Utils.showError('保存项目失败: ' + error.message);
        }
    },

    async viewProject(projectId) {
        // 显示项目详情模态框
        await this.showProjectModal(projectId);
    },

    async editProject(projectId) {
        await this.showProjectModal(projectId);
    },

    async deleteProject(projectId) {
        // 如果 Utils.confirm 不存在，使用原生的 confirm
        let confirmed = false;

        if (Utils.confirm && typeof Utils.confirm === 'function') {
            confirmed = await Utils.confirm(
                '确定要删除这个项目吗？此操作将删除项目下的所有设备和数据，且不可恢复！',
                '删除项目'
            );
        } else {
            // 备用方案：使用原生的 confirm
            confirmed = window.confirm('确定要删除这个项目吗？\n\n此操作将删除项目下的所有设备和数据，且不可恢复！');
        }

        if (!confirmed) {
            return;
        }

        try {
            await API.deleteProject(projectId);

            // 如果 Utils.showSuccess 存在就使用，否则用 alert
            if (Utils.showSuccess && typeof Utils.showSuccess === 'function') {
                Utils.showSuccess('项目删除成功');
            } else {
                alert('✓ 项目删除成功');
            }

            this.loadProjects();
        } catch (error) {
            console.error('删除项目失败:', error);

            // 如果 Utils.showError 存在就使用，否则用 alert
            if (Utils.showError && typeof Utils.showError === 'function') {
                Utils.showError('删除项目失败: ' + error.message);
            } else {
                alert('✗ 删除项目失败: ' + error.message);
            }
        }
    },

    viewProjectDevices(projectId) {
        // 跳转到设备管理页面并自动筛选该项目
        sessionStorage.setItem('filterProjectId', projectId);
        window.location.href = 'device.html';
    }
};