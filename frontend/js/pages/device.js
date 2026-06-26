/**
 * 设备管理页面逻辑 - 精简版（移除了特征配置） js/pages/device.js
 */

const DeviceManager = {
    // 状态
    state: {
        currentPage: 1,
        pageSize: 10,
        totalDevices: 0,
        selectedDevices: new Set(),
        filters: {
            projectId: null,
            model: null,
            status: null,
            search: null
        }
    },

    // 初始化
    async init() {
        console.log('🚀 初始化设备管理页面');

        // 检查API是否可用
        if (typeof API === 'undefined') {
            console.error('❌ API未定义，无法初始化');
            this.showError('API模块未加载，请刷新页面');
            return;
        }

        // 测试API连通性
        await this.testAPI();

        // 加载数据
        await this.loadFilters();
        await this.loadDevices();

        // 绑定事件
        this.bindEvents();

        // 检查是否有项目筛选
        const filterProjectId = sessionStorage.getItem('filterProjectId');
        if (filterProjectId) {
            document.getElementById('project-filter').value = filterProjectId;
            this.state.filters.projectId = filterProjectId;
            this.state.currentPage = 1;
            await this.loadDevices();
            sessionStorage.removeItem('filterProjectId');
        }

        console.log('✅ 设备管理页面初始化完成');
    },

    // 测试API连通性
    async testAPI() {
        console.log('🔗 测试API连通性...');
        try {
            const response = await fetch('http://localhost:8000/health');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            console.log('✅ 后端服务健康检查通过');

            // 测试设备API
            try {
                const devices = await API.getDevices({}, 1, 1);
                console.log('✅ 设备API测试通过');
            } catch (error) {
                console.warn('⚠️ 设备API可能存在问题:', error.message);
            }
        } catch (error) {
            console.error('❌ API测试失败:', error);
            this.showError(`后端连接失败: ${error.message}\n请确保后端服务运行在 http://localhost:8000`);
        }
    },

    // 显示错误信息
    showError(message) {
        const tableBody = document.getElementById('device-table-body');
        if (tableBody) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="11" class="error">
                        <div class="error-content">
                            <i class="fas fa-exclamation-triangle"></i>
                            <div class="error-message">${message}</div>
                            <button class="btn btn-primary" onclick="DeviceManager.retry()">
                                <i class="fas fa-redo"></i> 重试
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }
    },

    // 重试
    async retry() {
        console.log('🔄 重新加载数据...');
        await this.loadDevices();
    },

    // 加载筛选器
    async loadFilters() {
        console.log('📋 加载筛选器...');

        try {
            // 加载项目
            const result = await API.getProjects();
            const projects = result.projects || result.data || result || [];

            const projectSelect = document.getElementById('project-filter');
            const deviceProjectSelect = document.getElementById('device-project');

            // 清空选项
            projectSelect.innerHTML = '<option value="">全部项目</option>';
            deviceProjectSelect.innerHTML = '<option value="">请选择项目</option>';

            // 添加项目选项
            projects.forEach(project => {
                const option1 = document.createElement('option');
                option1.value = project.id;
                option1.textContent = `${project.name} (${project.code})`;
                projectSelect.appendChild(option1);

                const option2 = document.createElement('option');
                option2.value = project.id;
                option2.textContent = `${project.name} (${project.code})`;
                deviceProjectSelect.appendChild(option2);
            });

            console.log(`✅ 加载了 ${projects.length} 个项目到筛选器`);

            // 从后端加载设备模型到筛选器
            await this.loadDeviceModels();
             // 新增：检查是否有从项目页面跳转过来的项目筛选
            const filterProjectId = sessionStorage.getItem('filterProjectId');
            if (filterProjectId) {
                // 在筛选器和添加设备弹窗中都设置默认选中
                if (projectSelect.querySelector(`option[value="${filterProjectId}"]`)) {
                    projectSelect.value = filterProjectId;
                }
                if (deviceProjectSelect.querySelector(`option[value="${filterProjectId}"]`)) {
                    deviceProjectSelect.value = filterProjectId;
                    // 存储到状态中，供后续使用
                    this.state.defaultProjectId = filterProjectId;
                }
                console.log(`✅ 已设置默认项目ID: ${filterProjectId}`);
            }
            // 从后端加载设备模型到筛选器
            await this.loadDeviceModels();
        } catch (error) {
            console.error('❌ 加载筛选器失败:', error);
            Utils.showError('加载筛选器失败: ' + error.message);
        }
    },

    // 从后端加载设备模型
    async loadDeviceModels() {
        console.log('📋 加载设备模型...');

        try {
            const deviceModels = await API.getDeviceModels();

            const modelFilter = document.getElementById('model-filter');
            const deviceModelSelect = document.getElementById('device-model');

            if (modelFilter) {
                modelFilter.innerHTML = '<option value="">全部模型</option>';
                deviceModels.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.code || model.id;
                    option.textContent = model.name;
                    if (model.description) {
                        option.title = model.description;
                    }
                    modelFilter.appendChild(option);
                });
            }

            if (deviceModelSelect) {
                deviceModelSelect.innerHTML = '<option value="">请选择设备模型</option>';
                deviceModels.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.code || model.id;
                    option.textContent = model.name;
                    if (model.description) {
                        option.title = model.description;
                    }
                    deviceModelSelect.appendChild(option);
                });
            }

            console.log(`✅ 加载了 ${deviceModels.length} 个设备模型`);

        } catch (error) {
            console.error('❌ 加载设备模型失败:', error);
            // 不显示错误，因为可能后端API还在开发中
        }
    },

    // 加载设备数据
    async loadDevices() {
        const tableBody = document.getElementById('device-table-body');
        if (!tableBody) return;

        // 显示加载状态
        tableBody.innerHTML = `
            <tr>
                <td colspan="11" class="loading">
                    <i class="fas fa-spinner fa-spin"></i> 正在加载设备数据...
                </td>
            </tr>
        `;

        console.log('📋 加载设备数据...');
        console.log('📊 参数:', {
            page: this.state.currentPage,
            pageSize: this.state.pageSize,
            filters: this.state.filters
        });

        try {
            const result = await API.getDevices(
                this.state.filters,
                this.state.currentPage,
                this.state.pageSize
            );

            console.log('📦 设备数据响应:', result);

            // 处理响应数据
            let devices = [];
            if (Array.isArray(result)) {
                devices = result;
                this.state.totalDevices = result.length;
            } else if (result.devices) {
                devices = result.devices;
                this.state.totalDevices = result.total || devices.length;
            } else if (result.data) {
                devices = result.data;
                this.state.totalDevices = result.total || devices.length;
            } else {
                devices = [];
                this.state.totalDevices = 0;
            }

            console.log(`✅ 加载了 ${devices.length} 个设备，总计 ${this.state.totalDevices} 个`);

            // 渲染设备列表
            this.renderDevices(devices);

            // 更新分页
            this.updatePagination();

        } catch (error) {
            console.error('❌ 加载设备数据失败:', error);
            this.showError(`加载设备数据失败: ${error.message}`);
        }
    },

    // 渲染设备列表
    renderDevices(devices) {
        const tableBody = document.getElementById('device-table-body');
        if (!tableBody) return;

        if (!devices || devices.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="11" class="empty-state">
                        <div class="empty-content">
                            <i class="fas fa-server"></i>
                            <div class="empty-message">暂无设备数据</div>
                            <button class="btn btn-primary" onclick="DeviceManager.showAddModal()">
                                <i class="fas fa-plus"></i> 添加第一个设备
                            </button>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        let html = '';
        devices.forEach(device => {
    const isSelected = this.state.selectedDevices.has(device.id);
    const statusText = device.status === 'active' ? '运行中' : '已停止';
    const statusClass = device.status === 'active' ? 'status-active' : 'status-inactive';

    // 优先使用model_version_info，然后是device_metadata，最后是默认值
    const modelVersionInfo = device.model_version_info;
    const modelName = device.model?.name || device.device_metadata?.model || '未配置';
    const modelVersion = modelVersionInfo?.version ||
                        device.model_version?.version ||
                        device.device_metadata?.model_version ||
                        '默认';

    html += `
        <tr data-device-id="${device.id}">
            <td>
                <input type="checkbox" class="device-checkbox"
                       ${isSelected ? 'checked' : ''}
                       onclick="DeviceManager.toggleSelection(${device.id})">
            </td>
            <td>${device.id}</td>  <!-- 新增：显示设备ID -->
            <td>
                <div class="device-info">
                    <strong>${device.name}</strong>
                    ${device.description ? `<div class="text-muted">${device.description}</div>` : ''}
                </div>
            </td>
            <td><code>${device.identifier}</code></td>
            <td>
                <span class="model-name">${modelName}</span>
                ${device.device_metadata?.model_code ?
                    `<div class="text-muted"><small>${device.device_metadata.model_code}</small></div>` : ''}
            </td>
            <td>
                <span class="badge badge-version">${modelVersion}</span>
                ${modelVersionInfo?.description ?
                    `<div class="text-muted"><small>${modelVersionInfo.description}</small></div>` : ''}
            </td>
            <td>${device.project?.name || '未知项目'}</td>
            <td><span class="status-badge ${statusClass}">${statusText}</span></td>
            <td>${device.location || '-'}</td>
            <td>${Utils.formatTime(device.updated_at, 'YYYY-MM-DD HH:mm')}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn-action btn-view" onclick="DeviceManager.viewDevice(${device.id})" title="查看">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-action btn-edit" onclick="DeviceManager.editDevice(${device.id})" title="编辑">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn-action btn-data" onclick="DeviceManager.viewDeviceData(${device.id})" title="查看数据">
                        <i class="fas fa-chart-line"></i>
                    </button>
                    <button class="btn-action btn-delete" onclick="DeviceManager.deleteDevice(${device.id})" title="删除">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        </tr>
    `;
});

        tableBody.innerHTML = html;
    },


    // 切换设备选择
    toggleSelection(deviceId) {
        if (this.state.selectedDevices.has(deviceId)) {
            this.state.selectedDevices.delete(deviceId);
        } else {
            this.state.selectedDevices.add(deviceId);
        }
        console.log(`📌 选中设备: ${Array.from(this.state.selectedDevices).join(', ')}`);
    },

    // 更新分页
    updatePagination() {
        const totalPages = Math.max(1, Math.ceil(this.state.totalDevices / this.state.pageSize));
        const currentPage = Math.min(this.state.currentPage, totalPages);

        // 更新页码显示
        document.getElementById('current-page').textContent = currentPage;
        document.getElementById('total-pages').textContent = totalPages;

        // 更新按钮状态
        document.getElementById('prev-page').disabled = currentPage <= 1;
        document.getElementById('next-page').disabled = currentPage >= totalPages;

        console.log(`📄 分页: 第 ${currentPage} 页/共 ${totalPages} 页`);
    },

    // 绑定事件
    bindEvents() {
        console.log('🔗 绑定事件...');

        // 筛选按钮
        document.getElementById('apply-filters')?.addEventListener('click', () => {
            this.applyFilters();
        });

        document.getElementById('reset-filters')?.addEventListener('click', () => {
            this.resetFilters();
        });

        // 搜索框回车事件
        document.getElementById('search-input')?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.applyFilters();
            }
        });

        // 分页按钮
        document.getElementById('prev-page')?.addEventListener('click', () => {
            this.prevPage();
        });

        document.getElementById('next-page')?.addEventListener('click', () => {
            this.nextPage();
        });

        // 每页数量
        document.getElementById('page-size')?.addEventListener('change', (e) => {
            this.changePageSize(parseInt(e.target.value));
        });

        // 添加设备按钮
        document.getElementById('add-device-btn')?.addEventListener('click', () => {
            this.showAddModal();
        });

        // 批量操作按钮
        document.getElementById('batch-operate-btn')?.addEventListener('click', () => {
            this.showBatchModal();
        });

        // 全选/全不选
        document.getElementById('select-all')?.addEventListener('change', (e) => {
            this.toggleSelectAll(e.target.checked);
        });

        // 模型筛选器变化
        document.getElementById('model-filter')?.addEventListener('change', () => {
            this.applyFilters();
        });

        // 绑定批量操作弹窗事件
        this.bindBatchModalEvents();

        console.log('✅ 事件绑定完成');
    },

    // 绑定批量操作弹窗事件
    bindBatchModalEvents() {
        console.log('🔗 绑定批量操作弹窗事件...');

        const modal = document.getElementById('batch-modal');
        if (!modal) {
            console.warn('⚠️ 批量操作弹窗未找到');
            return;
        }

        // 关闭按钮 (x)
        const closeBtn = modal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.onclick = () => {
                modal.classList.remove('active');
            };
        }

        // 取消按钮
        const cancelBtn = document.getElementById('batch-cancel');
        if (cancelBtn) {
            cancelBtn.onclick = () => {
                modal.classList.remove('active');
            };
        }

        // 操作选择变化
        const actionSelect = document.getElementById('batch-action');
        if (actionSelect) {
            actionSelect.addEventListener('change', (e) => {
                this.updateBatchActionForm(e.target.value);
            });
        }

        // 确认执行按钮
        const confirmBtn = document.getElementById('batch-confirm');
        if (confirmBtn) {
            confirmBtn.onclick = () => {
                this.executeBatchAction();
            };
        }

        // ESC键关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                modal.classList.remove('active');
            }
        });

        // 点击模态框外部关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });

        console.log('✅ 批量操作弹窗事件绑定完成');
    },

    // 更新批量操作表单
    updateBatchActionForm(action) {
        const actionForm = document.getElementById('batch-action-form');
        const confirmBtn = document.getElementById('batch-confirm');

        if (!actionForm || !confirmBtn) return;

        // 首先确保按钮样式固定为 btn btn-primary
        confirmBtn.className = 'btn btn-primary';
        confirmBtn.textContent = '确认';

        if (action) {
            confirmBtn.disabled = false;
            actionForm.style.display = 'block';

            // 根据操作类型显示不同的表单
            let formContent = '';

            switch(action) {
                case 'enable':
                    formContent = `
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle"></i>
                            <div>
                                <strong>请注意：点击"确认"后操作将立即执行</strong>
                                <p>此操作将启用选中的 ${this.state.selectedDevices.size} 个设备，使其变为运行状态。</p>
                            </div>
                        </div>
                    `;
                    break;

                case 'disable':
                    formContent = `
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle"></i>
                            <div>
                                <strong>请注意：点击"确认"后操作将立即执行</strong>
                                <p>此操作将禁用选中的 ${this.state.selectedDevices.size} 个设备，使其变为停止状态。</p>
                            </div>
                        </div>
                    `;
                    break;

                case 'change-project':
                    formContent = `
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle"></i>
                            <div>
                                <strong>请注意：点击"确认"后操作将立即执行</strong>
                                <p>请选择新项目，此操作将变更选中的 ${this.state.selectedDevices.size} 个设备到新项目。</p>
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="new-project" class="form-label required">新项目</label>
                            <select id="new-project" class="form-select" required>
                                <option value="">请选择项目</option>
                            </select>
                        </div>
                    `;
                    // 动态加载项目选项
                    this.loadProjectOptionsForBatch();
                    break;

                case 'change-model':
                    formContent = `
                        <div class="alert alert-warning">
                            <i class="fas fa-exclamation-triangle"></i>
                            <div>
                                <strong>请注意：点击"确认"后操作将立即执行</strong>
                                <p>请选择新的设备模型和版本，此操作将更新选中的 ${this.state.selectedDevices.size} 个设备的模型。</p>
                            </div>
                        </div>
                        <div class="form-group">
                            <label for="new-model" class="form-label required">新设备模型</label>
                            <select id="new-model" class="form-select" required>
                                <option value="">请选择设备模型</option>
                                <!-- 设备模型将通过JavaScript动态添加 -->
                            </select>
                        </div>
                        <div class="form-group">
                            <label for="new-model-version" class="form-label required">新模型版本</label>
                            <select id="new-model-version" class="form-select" required>
                                <option value="">请先选择设备模型</option>
                            </select>
                        </div>
                    `;
                    // 动态加载设备模型
                    this.loadDeviceModelsForBatch();
                    break;

                case 'delete':
                    formContent = `
                        <div class="alert alert-danger">
                            <i class="fas fa-exclamation-circle"></i>
                            <div>
                                <strong>警告：此操作不可恢复！点击"确认"后操作将立即执行</strong>
                                <p>将永久删除选中的 ${this.state.selectedDevices.size} 个设备及其所有相关数据。</p>
                                <p>请勾选确认框后点击确认按钮执行删除操作。</p>
                            </div>
                        </div>
                        <div class="form-group">
                            <label class="checkbox">
                                <input type="checkbox" id="confirm-delete" required>
                                <span>我确认要删除这些设备，并了解此操作不可撤销</span>
                            </label>
                        </div>
                    `;
                    break;

                default:
                    formContent = `<p>请选择一个操作</p>`;
                    confirmBtn.disabled = true;
            }

            actionForm.innerHTML = formContent;

            // 绑定动态表单的事件
            if (action === 'change-model') {
                const newModelSelect = document.getElementById('new-model');
                if (newModelSelect) {
                    newModelSelect.addEventListener('change', () => {
                        this.updateBatchModelVersions();
                    });
                }
            }
        } else {
            confirmBtn.disabled = true;
            actionForm.style.display = 'none';
            actionForm.innerHTML = '';
        }
    },

    // 为批量操作加载设备模型
    async loadDeviceModelsForBatch() {
        const select = document.getElementById('new-model');
        if (!select) return;

        try {
            const deviceModels = await API.getDeviceModels();

            select.innerHTML = '<option value="">请选择设备模型</option>';

            deviceModels.forEach(model => {
                const option = document.createElement('option');
                option.value = model.code || model.id;
                option.textContent = model.name;
                if (model.description) {
                    option.title = model.description;
                }
                select.appendChild(option);
            });

            console.log(`✅ 为批量操作加载了 ${deviceModels.length} 个设备模型`);

        } catch (error) {
            console.error('❌ 加载设备模型失败:', error);
            select.innerHTML = '<option value="">加载失败，请重试</option>';
        }
    },


    // 更新批量操作的模型版本
    async updateBatchModelVersions() {
    const modelSelect = document.getElementById('new-model');
    const versionSelect = document.getElementById('new-model-version');

    if (!modelSelect || !versionSelect) return;

    const modelCode = modelSelect.value;

    if (!modelCode) {
        versionSelect.innerHTML = '<option value="">请先选择设备模型</option>';
        return;
    }

    console.log(`📋 批量操作：加载设备模型版本，模型: ${modelCode}`);

    try {
        // 首先需要获取模型ID
        const deviceModels = await API.getDeviceModels();
        const model = deviceModels.find(m => (m.code || m.id) === modelCode);

        if (!model) {
            throw new Error('未找到设备模型');
        }

        const versions = await API.getDeviceModelVersions(model.id);

        versionSelect.innerHTML = '<option value="">请选择模型版本</option>';

        versions.forEach(version => {
            const option = document.createElement('option');
            option.value = version.version;
            option.textContent = `${version.version} - ${version.description || version.name || '未命名版本'}`;

            // 设置 data 属性，便于获取ID和类型
            option.dataset.id = version.id;
            option.dataset.modelType = version.model_type || 'xgboost';

            versionSelect.appendChild(option);
        });

        console.log(`✅ 批量操作：加载了 ${versions.length} 个模型版本`);

    } catch (error) {
        console.error('❌ 批量操作：加载模型版本失败:', error);
        versionSelect.innerHTML = '<option value="">加载失败，请重试</option>';
    }
},

    // 为批量操作加载项目选项
    async loadProjectOptionsForBatch() {
        const select = document.getElementById('new-project');
        if (!select) return;

        try {
            const result = await API.getProjects();
            const projects = result.projects || result.data || result || [];

            // 清空选项（保留第一个空选项）
            select.innerHTML = '<option value="">请选择项目</option>';

            // 添加项目选项
            projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.id;
                option.textContent = `${project.name} (${project.code})`;
                select.appendChild(option);
            });

        } catch (error) {
            console.error('❌ 加载项目选项失败:', error);
        }
    },

    // 全选/全不选
    toggleSelectAll(checked) {
        const checkboxes = document.querySelectorAll('.device-checkbox');
        const tableBody = document.getElementById('device-table-body');

        checkboxes.forEach(checkbox => {
            checkbox.checked = checked;
            const deviceId = checkbox.closest('tr')?.dataset.deviceId;
            if (deviceId) {
                if (checked) {
                    this.state.selectedDevices.add(parseInt(deviceId));
                } else {
                    this.state.selectedDevices.delete(parseInt(deviceId));
                }
            }
        });

        console.log(`📌 ${checked ? '全选' : '全不选'}, 选中设备: ${Array.from(this.state.selectedDevices).join(', ')}`);
    },

    // 应用筛选
    applyFilters() {
        console.log('🔍 应用筛选...');

        // 获取筛选值
        this.state.filters = {
            projectId: document.getElementById('project-filter').value || null,
            model: document.getElementById('model-filter').value || null,
            status: document.getElementById('status-filter').value || null,
            search: document.getElementById('search-input')?.value || null
        };

        // 重置页码并重新加载
        this.state.currentPage = 1;
        this.loadDevices();
    },

    // 重置筛选
    resetFilters() {
        console.log('🔄 重置筛选...');

        document.getElementById('project-filter').value = '';
        document.getElementById('model-filter').value = '';
        document.getElementById('status-filter').value = '';
        const searchInput = document.getElementById('search-input');
        if (searchInput) searchInput.value = '';

        this.state.filters = {
            projectId: null,
            model: null,
            status: null,
            search: null
        };

        this.state.currentPage = 1;
        this.loadDevices();
    },

    // 上一页
    prevPage() {
        if (this.state.currentPage > 1) {
            this.state.currentPage--;
            this.loadDevices();
        }
    },

    // 下一页
    nextPage() {
        const totalPages = Math.ceil(this.state.totalDevices / this.state.pageSize);
        if (this.state.currentPage < totalPages) {
            this.state.currentPage++;
            this.loadDevices();
        }
    },

    // 改变每页数量
    changePageSize(size) {
        this.state.pageSize = size;
        this.state.currentPage = 1;
        this.loadDevices();
    },

    // 查看设备
    async viewDevice(deviceId) {
        console.log(`👁️ 查看设备 ${deviceId}`);
        try {
            const device = await API.getDevice(deviceId);
            this.showDeviceModal(device, true);
        } catch (error) {
            console.error('❌ 查看设备失败:', error);
            Utils.showError('查看设备失败: ' + error.message);
        }
    },

    // 编辑设备
    async editDevice(deviceId) {
        console.log(`✏️ 编辑设备 ${deviceId}`);
        try {
            const device = await API.getDevice(deviceId);
            this.showDeviceModal(device, false);
        } catch (error) {
            console.error('❌ 编辑设备失败:', error);
            Utils.showError('编辑设备失败: ' + error.message);
        }
    },

    // 查看设备数据
    viewDeviceData(deviceId) {
        console.log(`📊 查看设备 ${deviceId} 数据`);
        Utils.showInfo('功能开发中，将跳转到数据可视化页面');
    },

    // 删除设备
    async deleteDevice(deviceId) {
        console.log(`🗑️ 删除设备 ${deviceId}`);

        let confirmed = false;
        if (Utils.confirm && typeof Utils.confirm === 'function') {
            confirmed = await Utils.confirm(
                '确定要删除这个设备吗？此操作将删除该设备的所有数据，且不可恢复！',
                '删除设备'
            );
        } else {
            confirmed = window.confirm('确定要删除这个设备吗？\n\n此操作将删除该设备的所有数据，且不可恢复！');
        }

        if (!confirmed) {
            return;
        }

        try {
            await API.deleteDevice(deviceId);
            Utils.showSuccess('设备删除成功');
            this.loadDevices();
        } catch (error) {
            console.error('❌ 删除设备失败:', error);
            Utils.showError('删除设备失败: ' + error.message);
        }
    },

    // 显示批量操作弹窗
    showBatchModal() {
        const selectedCount = this.state.selectedDevices.size;
        if (selectedCount === 0) {
            Utils.showWarning('请先选择要操作的设备');
            return;
        }

        console.log(`📦 显示批量操作弹窗，已选择 ${selectedCount} 个设备`);

        const modal = document.getElementById('batch-modal');
        const selectedCountEl = document.getElementById('selected-count');
        const confirmBtn = document.getElementById('batch-confirm');
        const actionSelect = document.getElementById('batch-action');
        const actionForm = document.getElementById('batch-action-form');

        if (selectedCountEl) selectedCountEl.textContent = selectedCount;
        if (confirmBtn) {
            confirmBtn.disabled = true;
            confirmBtn.textContent = '确认';
            confirmBtn.className = 'btn btn-primary';
        }
        if (actionSelect) actionSelect.value = '';
        if (actionForm) {
            actionForm.style.display = 'none';
            actionForm.innerHTML = '';
        }

        modal.classList.add('active');
    },

    // 执行批量操作
    async executeBatchAction() {
        const action = document.getElementById('batch-action').value;
        const selectedDevices = Array.from(this.state.selectedDevices);

        if (!action || selectedDevices.length === 0) {
            Utils.showError('请选择操作和要操作的设备');
            return;
        }

        console.log(`🔄 执行批量操作: ${action}, 设备: ${selectedDevices}`);

        // 对于删除操作，检查确认复选框
        if (action === 'delete') {
            const confirmCheckbox = document.getElementById('confirm-delete');
            if (!confirmCheckbox || !confirmCheckbox.checked) {
                Utils.showError('请确认删除操作');
                return;
            }
        }

        // 对于变更项目和变更模型操作，检查必要字段
        if (action === 'change-project') {
            const newProject = document.getElementById('new-project').value;
            if (!newProject) {
                Utils.showError('请选择新项目');
                return;
            }
        }

        if (action === 'change-model') {
            const newModel = document.getElementById('new-model').value;
            const newVersion = document.getElementById('new-model-version').value;
            if (!newModel || !newVersion) {
                Utils.showError('请选择新的设备模型和版本');
                return;
            }
        }

        // 执行操作
        try {
            let successCount = 0;
            let failedDevices = [];

            for (const deviceId of selectedDevices) {
                try {
                    let result;

                    switch(action) {
                        case 'enable':
                            result = await API.updateDevice(deviceId, { status: 'active' });
                            break;
                        case 'disable':
                            result = await API.updateDevice(deviceId, { status: 'inactive' });
                            break;
                        case 'change-project':
                            const newProject = document.getElementById('new-project').value;
                            result = await API.updateDevice(deviceId, { project_id: parseInt(newProject) });
                            break;
                        case 'change-model':
                            const newModel = document.getElementById('new-model').value;
                            const newVersion = document.getElementById('new-model-version').value;

                            // 尝试获取模型版本ID
                            let modelVersionId = null;
                            let modelType = 'xgboost';

                            try {
                                const newModelVersionSelect = document.getElementById('new-model-version');
                                const selectedOption = newModelVersionSelect?.options[newModelVersionSelect.selectedIndex];

                                if (selectedOption && selectedOption.dataset.id) {
                                    modelVersionId = parseInt(selectedOption.dataset.id);
                                    modelType = selectedOption.dataset.modelType || 'xgboost';
                                }
                            } catch (error) {
                                console.warn('获取模型版本ID失败:', error);
                            }

                            const updateData = {
                                device_metadata: {
                                    model: newModel,
                                    model_version: newVersion
                                }
                            };

                            // 如果获取到model_version_id，添加到更新数据中
                            if (modelVersionId) {
                                updateData.model_version_id = modelVersionId;
                                updateData.model_type = modelType;
                                updateData.device_metadata.model_version_id = modelVersionId;
                                updateData.device_metadata.model_type = modelType;
                            }

                            result = await API.updateDevice(deviceId, updateData);
                            break;
                        case 'delete':
                            result = await API.deleteDevice(deviceId);
                            break;
                    }

                    if (result && (result.id || result.success !== false)) {
                        successCount++;
                    } else {
                        failedDevices.push(deviceId);
                    }
                } catch (error) {
                    console.error(`❌ 设备 ${deviceId} 操作失败:`, error);
                    failedDevices.push(deviceId);
                }
            }

            // 关闭弹窗并显示结果
            document.getElementById('batch-modal').classList.remove('active');

            if (failedDevices.length === 0) {
                Utils.showSuccess(`批量操作完成：成功 ${successCount} 个设备`);
            } else {
                Utils.showWarning(`批量操作完成：成功 ${successCount} 个，失败 ${failedDevices.length} 个`);
            }

            // 清空选中状态并刷新数据
            this.state.selectedDevices.clear();

            // 重置全选复选框状态
            const selectAllCheckbox = document.getElementById('select-all');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = false;
            }

            // 同时更新表格中的复选框状态
            document.querySelectorAll('.device-checkbox').forEach(checkbox => {
                checkbox.checked = false;
            });

            this.loadDevices();

        } catch (error) {
            console.error('❌ 批量操作失败:', error);
            Utils.showError('批量操作失败: ' + error.message);
        }
    },

    // 显示添加设备弹窗
    showAddModal() {
    console.log('➕ 显示添加设备弹窗');

    // 先打开弹窗
    this.showDeviceModal(null, false);

    // 延迟一点时间确保DOM已经渲染完成
    setTimeout(() => {
        // 检查是否有默认项目ID
        if (this.state.defaultProjectId) {
            const projectSelect = document.getElementById('device-project');
            if (projectSelect && projectSelect.querySelector(`option[value="${this.state.defaultProjectId}"]`)) {
                projectSelect.value = this.state.defaultProjectId;
                console.log(`✅ 已为添加设备弹窗设置默认项目ID: ${this.state.defaultProjectId}`);
            }
        }
    }, 100);
},

    // 显示设备弹窗
async showDeviceModal(device = null, isViewOnly = false) {
    console.log(`📱 显示设备弹窗: ${device ? (isViewOnly ? '查看' : '编辑') : '添加'}`);

    const modal = document.getElementById('device-modal');
    const title = document.getElementById('modal-title');
    const form = document.getElementById('device-form');

    // 设置标题
    if (device) {
        title.textContent = isViewOnly ? '查看设备' : '编辑设备';

        // 填充数据
        document.getElementById('device-name').value = device.name;
        document.getElementById('device-identifier').value = device.identifier;
        document.getElementById('device-project').value = device.project_id;
        document.getElementById('device-status').value = device.status || 'active';
        document.getElementById('device-location').value = device.location || '';
        document.getElementById('device-description').value = device.description || '';

        // 填充模型信息 - 优先使用model_version_info
        const modelVersionInfo = device.model_version_info;
        const modelVersion = modelVersionInfo?.version ||
                            device.model_version?.version ||
                            device.device_metadata?.model_version ||
                            '';

        // 先设置模型值
        document.getElementById('device-model').value = device.device_metadata?.model || '';
        document.getElementById('device-model-version').value = modelVersion;

        // 更新特征详情标签页中的信息
        document.getElementById('current-device-model').textContent = device.device_metadata?.model || '未选择';
        document.getElementById('current-model-version').textContent = modelVersion || '默认';

        // 存储设备ID
        modal.dataset.deviceId = device.id;

        // 如果设备有模型，动态加载该模型的版本选项
        if (device.device_metadata?.model) {
            await this.updateModelVersionsForDevice(device.device_metadata.model, modelVersion);
        } else if (device.model_version_id && device.model_version) {
            // 如果设备有model_version_id，但device_metadata中没有model信息
            // 需要从model_version反向查找模型信息
            try {
                const versionId = device.model_version_id;
                // 这里需要一个新的API方法来根据版本ID获取模型信息
                // 或者我们可以在updateModelVersionsForDevice中处理这种情况
                await this.loadModelVersionInfo(versionId);
            } catch (error) {
                console.warn('无法加载模型版本信息:', error);
            }
        }
    } else {
        title.textContent = '添加设备';
        form.reset();

        // 重置特征详情标签页中的信息
        document.getElementById('current-device-model').textContent = '未选择';
        document.getElementById('current-model-version').textContent = '默认';

        modal.dataset.deviceId = '';
    }

    // 设置表单状态
    const inputs = form.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        input.disabled = isViewOnly;
    });

    // 设置保存按钮文本
    const saveBtn = document.getElementById('modal-save');
    if (saveBtn) {
        saveBtn.style.display = isViewOnly ? 'none' : 'block';
        saveBtn.textContent = device ? '更新设备' : '创建设备';
    }

    // 绑定标签页切换
    this.bindTabEvents();

    // 显示弹窗
    modal.classList.add('active');

    // 绑定弹窗事件
    this.bindModalEvents();
},
    // 根据模型版本ID加载模型信息
async loadModelVersionInfo(versionId) {
    const modelSelect = document.getElementById('device-model');
    const versionSelect = document.getElementById('device-model-version');

    if (!modelSelect || !versionSelect) return;

    try {
        // 这里需要一个新的API方法来根据版本ID获取详细信息
        // 由于没有这个API，我们暂时使用现有的方法
        // 首先获取所有设备模型
        const deviceModels = await API.getDeviceModels();

        // 遍历所有模型，找到包含该版本ID的模型
        for (const model of deviceModels) {
            try {
                const versions = await API.getDeviceModelVersions(model.id);
                const foundVersion = versions.find(v => v.id === versionId);

                if (foundVersion) {
                    // 设置模型选择
                    modelSelect.value = model.code || model.id;

                    // 更新版本下拉框
                    versionSelect.innerHTML = '<option value="">请选择模型版本</option>';

                    versions.forEach(version => {
                        const option = document.createElement('option');
                        option.value = version.version;
                        option.textContent = `${version.version} - ${version.description || version.name || '未命名版本'}`;

                        // 设置 data 属性
                        option.dataset.id = version.id;
                        option.dataset.modelType = version.model_type || 'xgboost';

                        if (version.id === versionId) {
                            option.selected = true;
                        }

                        versionSelect.appendChild(option);
                    });

                    console.log(`✅ 根据版本ID ${versionId} 加载了模型 ${model.name} 的信息`);
                    return;
                }
            } catch (error) {
                continue; // 继续尝试下一个模型
            }
        }

        console.warn(`⚠️ 未找到版本ID: ${versionId} 对应的模型`);
    } catch (error) {
        console.error('❌ 加载模型版本信息失败:', error);
    }
},
// 为设备动态加载模型版本选项
async updateModelVersionsForDevice(modelCode, selectedVersion) {
    const versionSelect = document.getElementById('device-model-version');

    if (!modelCode) {
        versionSelect.innerHTML = '<option value="">请选择模型版本</option>';
        return;
    }

    console.log(`📋 加载设备模型版本，模型: ${modelCode}`);

    try {
        // 首先需要获取模型ID
        const deviceModels = await API.getDeviceModels();
        const model = deviceModels.find(m => (m.code || m.id) === modelCode);

        if (!model) {
            console.warn(`⚠️ 未找到设备模型: ${modelCode}`);
            versionSelect.innerHTML = '<option value="">模型不存在</option>';
            return;
        }

        const versions = await API.getDeviceModelVersions(model.id);

        versionSelect.innerHTML = '<option value="">请选择模型版本</option>';

        versions.forEach(version => {
            const option = document.createElement('option');
            option.value = version.version;
            option.textContent = `${version.version} - ${version.description || version.name || '未命名版本'}`;

            // 关键修改：设置 data 属性，便于获取ID和类型
            option.dataset.id = version.id;
            option.dataset.modelType = version.model_type || 'xgboost';

            // 如果版本匹配，则选中
            if (version.version === selectedVersion) {
                option.selected = true;
            }

            versionSelect.appendChild(option);
        });

        console.log(`✅ 加载了 ${versions.length} 个模型版本`);

    } catch (error) {
        console.error('❌ 加载模型版本失败:', error);
        versionSelect.innerHTML = '<option value="">加载失败，请重试</option>';
    }
},

// 修改 bindTabEvents 函数，在点击特征详情标签页时加载特征列表
bindTabEvents() {
    const tabLinks = document.querySelectorAll('.tab-link');
    const tabContents = document.querySelectorAll('.tab-content');

    tabLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            const tabId = e.target.dataset.tab;

            // 移除所有激活状态
            tabLinks.forEach(l => l.classList.remove('active'));
            tabContents.forEach(c => c.classList.remove('active'));

            // 添加当前激活状态
            e.target.classList.add('active');
            document.getElementById(`tab-${tabId}`).classList.add('active');

            // 如果是特征详情标签页，更新信息并加载特征列表
            if (tabId === 'features') {
                const model = document.getElementById('device-model').value;
                const version = document.getElementById('device-model-version').value;
                document.getElementById('current-device-model').textContent = model || '未选择';
                document.getElementById('current-model-version').textContent = version || '默认';

                // 加载特征列表
                this.loadFeaturesList();
            }
        });
    });
},

    // 绑定弹窗事件 - 简化版
    bindModalEvents() {
        const modal = document.getElementById('device-modal');
        if (!modal) return;
        // 模型选择变化时更新版本下拉框
        const modelSelect = document.getElementById('device-model');
        if (modelSelect) {
            // 移除之前的事件监听器，避免重复绑定
            modelSelect.removeEventListener('change', this.handleModelChange);
            // 添加新的事件监听器
            this.handleModelChange = () => {
                this.updateModelDependencies();
            };
            modelSelect.addEventListener('change', this.handleModelChange);
        }

        // 当版本变化时，更新特征详情标签页中的信息
        const versionSelect = document.getElementById('device-model-version');
        if (versionSelect) {
            versionSelect.addEventListener('change', () => {
                // 如果当前在特征详情标签页，更新信息
                const activeTab = document.querySelector('.tab-link.active');
                if (activeTab && activeTab.dataset.tab === 'features') {
                    const model = document.getElementById('device-model').value;
                    const version = document.getElementById('device-model-version').value;
                    document.getElementById('current-device-model').textContent = model || '未选择';
                    document.getElementById('current-model-version').textContent = version || '默认';
                }
            });
        }
        // 关闭按钮
        const closeBtn = modal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.onclick = () => {
                modal.classList.remove('active');
            };
        }

        // 取消按钮
        const cancelBtn = document.getElementById('modal-cancel');
        if (cancelBtn) {
            cancelBtn.onclick = () => {
                modal.classList.remove('active');
            };
        }

        // 保存按钮
        const saveBtn = document.getElementById('modal-save');
        if (saveBtn) {
            saveBtn.onclick = () => {
                this.saveDevice();
            };
        }

        // 模型选择变化时更新版本下拉框
        document.getElementById('device-model')?.addEventListener('change', () => {
            this.updateModelDependencies();
        });

        // 当版本变化时，更新特征详情标签页中的信息
        document.getElementById('device-model-version')?.addEventListener('change', () => {
            // 如果当前在特征详情标签页，更新信息
            const activeTab = document.querySelector('.tab-link.active');
            if (activeTab && activeTab.dataset.tab === 'features') {
                const model = document.getElementById('device-model').value;
                const version = document.getElementById('device-model-version').value;
                document.getElementById('current-device-model').textContent = model || '未选择';
                document.getElementById('current-model-version').textContent = version || '默认';
            }
        });

        // ESC键关闭
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('active')) {
                modal.classList.remove('active');
            }
        });

        // 点击模态框外部关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    },

// 更新模型依赖
async updateModelDependencies() {
    const modelCode = document.getElementById('device-model').value;

    if (!modelCode) {
        const versionSelect = document.getElementById('device-model-version');
        versionSelect.innerHTML = '<option value="">请选择模型版本</option>';
        return;
    }

    console.log(`📋 加载设备模型版本，模型: ${modelCode}`);

    try {
        // 首先需要获取模型ID
        const deviceModels = await API.getDeviceModels();
        const model = deviceModels.find(m => (m.code || m.id) === modelCode);

        if (!model) {
            throw new Error('未找到设备模型');
        }

        const versions = await API.getDeviceModelVersions(model.id);

        const versionSelect = document.getElementById('device-model-version');
        versionSelect.innerHTML = '<option value="">请选择模型版本</option>';

        versions.forEach(version => {
            const option = document.createElement('option');
            option.value = version.version;
            option.textContent = `${version.version} - ${version.description || version.name || '未命名版本'}`;

            // 关键修改：设置 data 属性
            option.dataset.id = version.id;
            option.dataset.modelType = version.model_type || 'xgboost';

            versionSelect.appendChild(option);
        });

        console.log(`✅ 加载了 ${versions.length} 个模型版本`);

    } catch (error) {
        console.error('❌ 加载模型版本失败:', error);
        const versionSelect = document.getElementById('device-model-version');
        versionSelect.innerHTML = '<option value="">加载失败，请重试</option>';
    }
},
// 加载特征列表
async loadFeaturesList() {
    const container = document.getElementById('feature-list-container');
    const model = document.getElementById('device-model').value;
    const version = document.getElementById('device-model-version').value;

    if (!model || !version) {
        container.innerHTML = `
            <div class="no-features">
                <i class="fas fa-info-circle"></i>
                <p>请先选择设备模型和版本</p>
            </div>
        `;
        return;
    }

    try {
        container.innerHTML = `
            <div class="loading">
                <i class="fas fa-spinner fa-spin"></i> 正在加载特征数据...
            </div>
        `;

        // 1. 首先获取设备模型ID
        const deviceModels = await API.getDeviceModels();
        const selectedModel = deviceModels.find(m => (m.code || m.id) === model);

        if (!selectedModel) {
            throw new Error('未找到设备模型');
        }

        // 2. 获取该模型的所有版本
        const versions = await API.getDeviceModelVersions(selectedModel.id);
        const selectedVersion = versions.find(v => v.version === version);

        if (!selectedVersion) {
            throw new Error('未找到模型版本');
        }

        // 3. 获取该版本关联的特征列表
        const features = await this.getFeaturesByVersion(selectedVersion.id);

        if (features.length === 0) {
            container.innerHTML = `
                <div class="no-features">
                    <i class="fas fa-info-circle"></i>
                    <p>该设备模型版本尚未配置特征</p>
                </div>
            `;
            return;
        }

        // 4. 计算统计信息
        const requiredCount = features.filter(f => f.is_required).length;
        const numericCount = features.filter(f => f.data_type === 'number').length;
        const stringCount = features.filter(f => f.data_type === 'string').length;

        // 5. 渲染特征列表
        let html = `
            <div class="feature-list-header">
                <h5><i class="fas fa-sliders-h"></i> 特征列表</h5>
                <small>共 ${features.length} 个特征</small>
            </div>

            <div class="feature-stats">
                <div class="stat-item">
                    <span>必填:</span>
                    <span class="stat-value">${requiredCount}</span>
                </div>
                <div class="stat-item">
                    <span>数值型:</span>
                    <span class="stat-value">${numericCount}</span>
                </div>
                <div class="stat-item">
                    <span>字符型:</span>
                    <span class="stat-value">${stringCount}</span>
                </div>
            </div>

            <div class="features-grid">
        `;

        features.forEach(feature => {
            // 简化单位显示
            let unitDisplay = feature.unit ? feature.unit : '';
            if (unitDisplay && unitDisplay.length > 6) {
                unitDisplay = unitDisplay.substring(0, 6) + '...';
            }

            // 简化描述显示
            let description = feature.description || '';
            if (description && description.length > 60) {
                description = description.substring(0, 60) + '...';
            }

            html += `
                <div class="feature-card">
                    <div class="feature-card-header">
                        <div class="feature-name">
                            ${feature.name}
                            ${feature.is_required ? '<span class="feature-category">必填</span>' : ''}
                        </div>
                        <div class="feature-code" title="${feature.code}">${feature.code}</div>
                    </div>
                    <div class="feature-card-body">
                        <div class="feature-detail">
                            <span class="detail-label">类型:</span>
                            <span class="detail-value">
                                ${feature.data_type}
                                ${unitDisplay ? ` (${unitDisplay})` : ''}
                            </span>
                        </div>
                        <div class="feature-detail">
                            <span class="detail-label">默认值:</span>
                            <span class="detail-value" title="${feature.default_value || '无'}">
                                ${feature.default_value ? (feature.default_value.length > 12 ?
                                    feature.default_value.substring(0, 12) + '...' :
                                    feature.default_value) : '无'}
                            </span>
                        </div>
                        ${description ? `
                        <div class="feature-desc" title="${feature.description}">
                            ${description}
                        </div>` : ''}
                    </div>
                </div>
            `;
        });

        html += `</div>`;

        container.innerHTML = html;

    } catch (error) {
        console.error('❌ 加载特征列表失败:', error);
        container.innerHTML = `
            <div class="error">
                <i class="fas fa-exclamation-triangle"></i>
                <p>加载特征列表失败</p>
                <button class="btn btn-primary" onclick="DeviceManager.loadFeaturesList()">
                    <i class="fas fa-redo"></i> 重新加载
                </button>
            </div>
        `;
    }
},

// 获取设备版本关联的特征
async getFeaturesByVersion(versionId) {
    console.log(`📋 获取版本 ${versionId} 关联的特征`);

    try {
        // 使用 API 模块中的方法，而不是直接调用 fetch
        return await API.getFeaturesByVersion(versionId);
    } catch (error) {
        console.error('❌ 获取特征列表失败:', error);
        return [];
    }
},
// 保存设备
async saveDevice() {
    console.log('💾 保存设备...');

    const form = document.getElementById('device-form');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    // 收集数据
    const deviceData = {
        name: document.getElementById('device-name').value,
        identifier: document.getElementById('device-identifier').value,
        description: document.getElementById('device-description').value || null,
        status: document.getElementById('device-status').value,
        location: document.getElementById('device-location').value || null,
        device_metadata: {
            model: document.getElementById('device-model').value,
            model_version: document.getElementById('device-model-version').value
        }
    };

    // 获取模型版本ID - 关键修改：从select的data属性中获取
    const modelSelect = document.getElementById('device-model');
    const versionSelect = document.getElementById('device-model-version');

    const modelCode = modelSelect?.value;
    const versionValue = versionSelect?.value;

    // 从选中的option中获取data-id属性
    const selectedOption = versionSelect?.options[versionSelect.selectedIndex];
    let modelVersionId = null;
    let modelType = 'xgboost';

    if (selectedOption && selectedOption.dataset.id) {
        modelVersionId = parseInt(selectedOption.dataset.id);
        modelType = selectedOption.dataset.modelType || 'xgboost';
        console.log(`✅ 从选项属性获取到模型版本ID: ${modelVersionId}, 类型: ${modelType}`);
    }

    if (modelCode && versionValue) {
        // 如果通过data属性没有获取到ID，尝试通过API查询
        if (!modelVersionId) {
            try {
                const deviceModels = await API.getDeviceModels();
                const selectedModel = deviceModels.find(m => (m.code || m.id) === modelCode);

                if (selectedModel) {
                    console.log(`✅ 找到设备模型: ${selectedModel.name} (ID: ${selectedModel.id})`);

                    const versions = await API.getDeviceModelVersions(selectedModel.id);
                    const selectedVersion = versions.find(v => v.version === versionValue);

                    if (selectedVersion) {
                        modelVersionId = selectedVersion.id;
                        modelType = selectedVersion.model_type || 'xgboost';
                        console.log(`✅ 通过API查询到模型版本ID: ${modelVersionId}, 类型: ${modelType}`);
                    }
                }
            } catch (error) {
                console.error('通过API查询模型版本信息失败:', error);
            }
        }
    }

    // 如果获取到了模型版本ID，添加到设备数据中
    if (modelVersionId) {
        deviceData.model_version_id = modelVersionId;
        deviceData.model_type = modelType;
        deviceData.device_metadata.model_version_id = modelVersionId;
        deviceData.device_metadata.model_type = modelType;
    } else {
        console.warn('⚠️ 未获取到模型版本ID，将不会设置model_version_id');
    }

    console.log('📦 保存的设备数据:', deviceData);

    try {
        const modal = document.getElementById('device-modal');
        const deviceId = modal.dataset.deviceId;

        if (deviceId) {
            // 更新设备
            console.log(`🔄 更新设备 ${deviceId}`);
            await API.updateDevice(deviceId, deviceData);
            Utils.showSuccess('设备更新成功');
        } else {
            // 创建设备
            console.log('➕ 创建设备');
            const projectId = document.getElementById('device-project').value;
            if (!projectId) {
                Utils.showError('请选择所属项目');
                return;
            }

            const createData = {
                ...deviceData,
                project_id: parseInt(projectId)
            };

            await API.createDevice(createData);
            Utils.showSuccess('设备创建成功');
        }

        // 关闭弹窗并刷新
        modal.classList.remove('active');
        this.loadDevices();

    } catch (error) {
        console.error('❌ 保存设备失败:', error);
        Utils.showError('保存设备失败: ' + error.message);
    }
}
};

// 页面加载完成后初始化
window.addEventListener('DOMContentLoaded', function() {
    console.log('📄 DOM加载完成，准备初始化设备管理');

    // 延迟初始化，确保所有资源加载完成
    setTimeout(() => {
        DeviceManager.init().catch(error => {
            console.error('❌ 设备管理初始化失败:', error);
        });
    }, 100);
});

// 全局可用
window.DeviceManager = DeviceManager;

console.log('🚀 设备管理模块已加载');