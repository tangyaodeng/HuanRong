
        // 修改后的 JavaScript 代码
        const FeaturesPage = (function() {
            // 状态管理
            const state = {
                currentTab: 'device-models',
                editingModel: null,
                editingVersion: null,
                editingFeature: null,
                selectedFeatures: [],
                deviceModels: [],
                modelVersions: [],
                features: [],
                projects: []
            };

            // 初始化函数
            function init() {
                console.log('🚀 初始化配置管理页面');
                initEventListeners(); // 只需要调用这一个函数
                initTabNavigation();
                loadInitialData();

                // 默认显示设备模型tab
                switchTab('device-models');

                console.log('✅ 配置管理页面初始化完成');
            }

            // 初始化事件监听器
            function initEventListeners() {
                console.log('🔗 绑定事件监听器...');

                // 外层Tab切换按钮（主页面）- 修复：只绑定一次
                const outerTabLinks = document.querySelectorAll('.tab-link:not(.inner-tab-link)');
                outerTabLinks.forEach(button => {
                    // 先移除可能存在的旧监听器
                    button.replaceWith(button.cloneNode(true));
                });

                // 重新获取并绑定
                document.querySelectorAll('.tab-link:not(.inner-tab-link)').forEach(button => {
                    button.addEventListener('click', function(e) {
                        const tabId = this.dataset.tab;
                        if (tabId) { // 确保是外层标签页
                            e.stopPropagation();
                            switchTab(tabId);
                        }
                    });
                });
                // 设备模型代码输入验证
                document.getElementById('model-code')?.addEventListener('input', function(e) {
                    autoFormatCodeField(e.target);
                });

                document.getElementById('model-code')?.addEventListener('blur', function(e) {
                    autoFormatCodeField(e.target);
                });

                // 模型版本号输入验证
                document.getElementById('version-number')?.addEventListener('input', function(e) {
                    autoFormatCodeField(e.target);
                });

                document.getElementById('version-number')?.addEventListener('blur', function(e) {
                    autoFormatCodeField(e.target);
                });
                // 特征代码输入验证 - 添加 input 事件监听，实时处理
                document.getElementById('feature-code')?.addEventListener('input', function(e) {
                    // 实时处理输入
                    const value = e.target.value;
                    if (value) {
                        // 去除头尾空格
                        let processedValue = value.trim();

                        // 将连续空格替换为下划线
                        processedValue = processedValue.replace(/\s+/g, '_');

                        // 转为小写
                        processedValue = processedValue.toLowerCase();

                        // 如果处理后的值与原值不同，更新输入框
                        if (processedValue !== value) {
                            const cursorPos = e.target.selectionStart;
                            e.target.value = processedValue;

                            // 恢复光标位置
                            e.target.setSelectionRange(cursorPos, cursorPos);

                            // 重新验证
                            setTimeout(() => validateFeatureCode(e.target), 0);
                        } else {
                            validateFeatureCode(e.target);
                        }
                    } else {
                        validateFeatureCode(e.target);
                    }
                });

                document.getElementById('feature-code')?.addEventListener('blur', function(e) {
                    validateFeatureCode(e.target);
                });
                // 内层Tab切换按钮（模态框内） - 通过事件委托
                document.addEventListener('click', function(e) {
                    const innerTabLink = e.target.closest('.inner-tab-link');
                    if (innerTabLink && !e.defaultPrevented) {
                        e.preventDefault();
                        e.stopPropagation();

                        const tabId = innerTabLink.dataset.innerTab;
                        switchInnerTab(tabId);
                    }
                });

                // 弹窗关闭按钮
                document.querySelectorAll('.modal-close').forEach(closeBtn => {
                    closeBtn.addEventListener('click', function() {
                        this.closest('.modal').classList.remove('active');
                    });
                });

                // 设备模型相关
                document.getElementById('add-model-btn')?.addEventListener('click', showAddModelModal);
                document.getElementById('model-cancel')?.addEventListener('click', hideModelModal);
                document.getElementById('model-save')?.addEventListener('click', saveDeviceModel);

                // 模型版本相关
                document.getElementById('add-version-btn')?.addEventListener('click', showAddVersionModal);
                document.getElementById('version-cancel')?.addEventListener('click', hideVersionModal);
                document.getElementById('version-save')?.addEventListener('click', saveModelVersion);

                // 特征相关
                document.getElementById('add-feature-btn')?.addEventListener('click', showAddFeatureModal);
                document.getElementById('feature-cancel')?.addEventListener('click', hideFeatureModal);
                document.getElementById('feature-save')?.addEventListener('click', saveFeature);

                // 筛选器
                document.getElementById('model-type-filter')?.addEventListener('change', filterDeviceModels);
                document.getElementById('model-status-filter')?.addEventListener('change', filterDeviceModels);
                document.getElementById('version-model-filter')?.addEventListener('change', filterModelVersions);
                document.getElementById('version-status-filter')?.addEventListener('change', filterModelVersions);
                document.getElementById('feature-data-type-filter')?.addEventListener('change', filterFeatures);
                document.getElementById('feature-required-filter')?.addEventListener('change', filterFeatures);

                // 特征代码输入验证
                document.getElementById('feature-code')?.addEventListener('input', function(e) {
                    validateFeatureCode(e.target);
                });

                document.getElementById('feature-code')?.addEventListener('blur', function(e) {
                    validateFeatureCode(e.target);
                });

                // ESC键关闭所有弹窗
                document.addEventListener('keydown', function(event) {
                    if (event.key === 'Escape') {
                        document.querySelectorAll('.modal.active').forEach(modal => {
                            modal.classList.remove('active');
                        });
                    }
                });

                // 特征搜索功能
                const featureSearch = document.getElementById('feature-search');
                if (featureSearch) {
                    featureSearch.addEventListener('input', function(e) {
                        searchFeatures(e.target.value);
                    });
                }
                console.log('✅ 事件监听器绑定完成');
            }

            // 初始化Tab导航
            function initTabNavigation() {
                // 获取URL中的tab参数
                const urlParams = new URLSearchParams(window.location.search);
                const tabParam = urlParams.get('tab');
                if (tabParam && ['device-models', 'model-versions', 'features'].includes(tabParam)) {
                    state.currentTab = tabParam;
                }
            }

            // 加载初始数据
            async function loadInitialData() {
                console.log('📋 加载初始数据...');

                try {
                    // 并行加载数据
                    const [modelsData, versionsData, featuresData, projectsData] = await Promise.all([
                        FeaturesAPI.DeviceModelAPI.getDeviceModels(),
                        FeaturesAPI.ModelVersionAPI.getModelVersions(),
                        FeaturesAPI.FeatureAPI.getFeatures(),
                        FeaturesAPI.ProjectAPI.getProjects()
                    ]);

                    state.deviceModels = Array.isArray(modelsData) ? modelsData : (modelsData?.device_models || []);
                    state.modelVersions = Array.isArray(versionsData) ? versionsData : (versionsData?.versions || []);
                    state.features = Array.isArray(featuresData) ? featuresData : (featuresData?.features || []);
                    state.projects = Array.isArray(projectsData) ? projectsData : (projectsData?.projects || []);

                    console.log(`✅ 加载了 ${state.deviceModels.length} 个设备模型`);
                    console.log(`✅ 加载了 ${state.modelVersions.length} 个模型版本`);
                    console.log(`✅ 加载了 ${state.features.length} 个特征`);
                    console.log(`✅ 加载了 ${state.projects.length} 个项目`);

                    // 更新筛选器选项
                    updateFilterOptions();

                    // 加载当前tab的数据
                    loadCurrentTabData();

                } catch (error) {
                    console.error('❌ 加载初始数据失败:', error);
                    showNotification('加载数据失败: ' + error.message, 'error');
                }
            }

            // 更新筛选器选项
            function updateFilterOptions() {
                // 更新模型筛选器（版本页面使用）
                const versionModelFilter = document.getElementById('version-model-filter');
                if (versionModelFilter) {
                    const currentValue = versionModelFilter.value;
                    versionModelFilter.innerHTML = '<option value="">全部模型</option>';

                    state.deviceModels.forEach(model => {
                        const option = document.createElement('option');
                        option.value = model.id;
                        option.textContent = `${model.name} (${model.code})`;
                        versionModelFilter.appendChild(option);
                    });

                    if (currentValue) {
                        versionModelFilter.value = currentValue;
                    }
                }
            }

            // 切换Tab
            function switchTab(tabId) {
                // 更新UI
                document.querySelectorAll('.tab-link').forEach(button => {
                    button.classList.toggle('active', button.dataset.tab === tabId);
                });

                document.querySelectorAll('.tab-content').forEach(content => {
                    content.classList.toggle('active', content.id === `tab-${tabId}`);
                });

                // 更新URL
                const url = new URL(window.location);
                url.searchParams.set('tab', tabId);
                window.history.pushState({}, '', url);

                state.currentTab = tabId;
                loadCurrentTabData();
            }
            // 通用代码字段格式化函数
            function autoFormatCodeField(inputElement) {
                const value = inputElement.value;
                if (!value) return;

                let processedValue = value.trim();
                processedValue = processedValue.replace(/\s+/g, '_');
                processedValue = processedValue.toLowerCase();

                if (processedValue !== value) {
                    const cursorPos = inputElement.selectionStart;
                    inputElement.value = processedValue;
                    inputElement.setSelectionRange(cursorPos, cursorPos);
                }
            }
            // 切换内层Tab
            function switchInnerTab(tabId) {
                // 只在模态框内切换
                const modal = document.querySelector('.modal.active');
                if (!modal) return;

                // 切换标签页按钮
                modal.querySelectorAll('.inner-tab-link').forEach(button => {
                    button.classList.toggle('active', button.dataset.innerTab === tabId);
                });

                // 切换标签页内容
                modal.querySelectorAll('.inner-tab-content').forEach(content => {
                    content.classList.toggle('active', content.id === `inner-tab-${tabId}`);
                });

                // 如果是特征配置标签页，加载特征
                if (tabId === 'version-features') {
                    setTimeout(() => {
                        loadAvailableFeatures();
                    }, 100);
                }
            }

            // 加载当前Tab的数据
            function loadCurrentTabData() {
                switch(state.currentTab) {
                    case 'device-models':
                        renderDeviceModelsTable();
                        break;
                    case 'model-versions':
                        renderModelVersionsTable();
                        break;
                    case 'features':
                        renderFeaturesTable();
                        break;
                }
            }

            // ========== 设备模型管理 ==========

            // 渲染设备模型表格
            function renderDeviceModelsTable() {
                const tableBody = document.getElementById('device-models-table-body');
                if (!tableBody) return;

                if (!state.deviceModels || state.deviceModels.length === 0) {
                    tableBody.innerHTML = `
                        <tr>
                            <td colspan="8" class="empty-state">
                                <div class="empty-content">
                                    <i class="fas fa-microchip"></i>
                                    <div class="empty-message">暂无设备模型数据</div>
                                    <button class="btn btn-primary" onclick="window.FeaturesPage.showAddModelModal()">
                                        <i class="fas fa-plus"></i> 添加第一个设备模型
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                    return;
                }

                let html = '';
                state.deviceModels.forEach(model => {
                    const versionCount = state.modelVersions.filter(v => v.model_id === model.id).length;
                    const isPredefined = model.is_predefined;

                    html += `
                        <tr data-device-model-id="${model.id}">
                            <td>
                                <div class="device-model-info">
                                    <strong>${model.name}</strong>
                                    ${isPredefined ? '<span class="feature-category">预定义</span>' : ''}
                                </div>
                            </td>
                            <td><code>${model.code}</code></td>
                            <td>${isPredefined ? '预定义模型' : '自定义模型'}</td>
                            <td>${model.description || '-'}</td>
                            <td>${versionCount}</td>
                            <td>
                                <span class="status-badge ${model.is_active ? 'status-active' : 'status-inactive'}">
                                    ${model.is_active ? '启用' : '禁用'}
                                </span>
                            </td>
                            <td>${formatDateTime(model.created_at)}</td>
                            <td>
                                <div class="action-buttons">
                                    <button class="btn-action btn-view" title="查看版本"
                                            onclick="window.FeaturesPage.viewModelVersions(${model.id})">
                                        <i class="fas fa-eye"></i>
                                    </button>
                                    <button class="btn-action btn-edit" title="编辑"
                                            onclick="window.FeaturesPage.editDeviceModel(${model.id})">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    ${!isPredefined ? `
                                        <button class="btn-action btn-delete" title="删除"
                                                onclick="window.FeaturesPage.deleteDeviceModel(${model.id})">
                                            <i class="fas fa-trash"></i>
                                        </button>
                                    ` : ''}
                                </div>
                            </td>
                        </tr>
                    `;
                });

                tableBody.innerHTML = html;
            }

            // 筛选设备模型
            function filterDeviceModels() {
                const typeFilter = document.getElementById('model-type-filter').value;
                const statusFilter = document.getElementById('model-status-filter').value;

                let filteredModels = [...state.deviceModels];

                if (typeFilter === 'predefined') {
                    filteredModels = filteredModels.filter(model => model.is_predefined);
                } else if (typeFilter === 'custom') {
                    filteredModels = filteredModels.filter(model => !model.is_predefined);
                }

                if (statusFilter === 'active') {
                    filteredModels = filteredModels.filter(model => model.is_active);
                } else if (statusFilter === 'inactive') {
                    filteredModels = filteredModels.filter(model => !model.is_active);
                }

                // 临时更新显示
                const tableBody = document.getElementById('device-models-table-body');
                if (!tableBody || filteredModels.length === 0) {
                    tableBody.innerHTML = `
                        <tr>
                            <td colspan="8" class="empty-state">
                                <div class="empty-content">
                                    <i class="fas fa-microchip"></i>
                                    <div class="empty-message">没有找到匹配的设备模型</div>
                                </div>
                            </td>
                        </tr>
                    `;
                    return;
                }

                // 重新渲染
                const originalModels = [...state.deviceModels];
                state.deviceModels = filteredModels;
                renderDeviceModelsTable();
                state.deviceModels = originalModels;
            }

            // 显示添加设备模型弹窗
            function showAddModelModal() {
                state.editingModel = null;
                const modal = document.getElementById('device-model-modal');
                const form = document.getElementById('device-model-form');

                form.reset();
                modal.classList.add('active');
            }

            // 编辑设备模型
            function editDeviceModel(modelId) {
                const model = state.deviceModels.find(m => m.id === modelId);
                if (!model) {
                    showNotification('设备模型未找到', 'error');
                    return;
                }

                state.editingModel = model;
                const modal = document.getElementById('device-model-modal');
                const form = document.getElementById('device-model-form');

                // 填充表单
                document.getElementById('model-name').value = model.name;
                document.getElementById('model-code').value = model.code;
                document.getElementById('model-description').value = model.description || '';
                document.getElementById('model-is-predefined').checked = model.is_predefined;
                document.getElementById('model-is-active').checked = model.is_active;

                modal.classList.add('active');
            }

            // 保存设备模型
            async function saveDeviceModel() {
                try {
                    const form = document.getElementById('device-model-form');
                    if (!form.checkValidity()) {
                        form.reportValidity();
                        return;
                    }

                    const modelData = {
                        name: document.getElementById('model-name').value.trim(),
                        code: document.getElementById('model-code').value.trim(),
                        description: document.getElementById('model-description').value.trim(),
                        is_predefined: document.getElementById('model-is-predefined').checked,
                        is_active: document.getElementById('model-is-active').checked
                    };

                    if (state.editingModel) {
                        // 更新现有模型
                        await FeaturesAPI.DeviceModelAPI.updateDeviceModel(state.editingModel.id, modelData);
                        showNotification('设备模型更新成功', 'success');
                    } else {
                        // 创建新模型
                        await FeaturesAPI.DeviceModelAPI.createDeviceModel(modelData);
                        showNotification('设备模型创建成功', 'success');
                    }

                    // 重新加载数据
                    await loadInitialData();
                    hideModelModal();

                } catch (error) {
                    console.error('❌ 保存设备模型失败:', error);
                    showNotification('保存失败: ' + error.message, 'error');
                }
            }

            // 删除设备模型
            function deleteDeviceModel(modelId) {
                const model = state.deviceModels.find(m => m.id === modelId);
                if (!model) return;

                if (!confirm(`确定要删除设备模型 "${model.name}" 吗？此操作将同时删除所有关联的模型版本，且不可恢复！`)) {
                    return;
                }

                try {
                    // 调用API删除
                    FeaturesAPI.DeviceModelAPI.deleteDeviceModel(modelId).then(() => {
                        showNotification('设备模型删除成功', 'success');
                        loadInitialData();
                    }).catch(error => {
                        console.error('❌ 删除设备模型失败:', error);
                        // 修复：检查400错误并显示特定提示
                        if (error.message.includes("status: 400")) {
                            showNotification('删除失败: 存在关联的模型版本，请先删除相关版本', 'error');
                        } else {
                            showNotification('删除失败: ' + error.message, 'error');
                        }
                    });
                } catch (error) {
                    console.error('❌ 删除设备模型失败:', error);
                    showNotification('删除失败: ' + error.message, 'error');
                }
            }

            // 查看模型版本
            function viewModelVersions(modelId) {
                switchTab('model-versions');

                // 设置筛选器
                setTimeout(() => {
                    const filter = document.getElementById('version-model-filter');
                    if (filter) {
                        filter.value = modelId;
                        filterModelVersions();
                    }
                }, 100);
            }

            // 隐藏设备模型弹窗
            function hideModelModal() {
                document.getElementById('device-model-modal').classList.remove('active');
            }

            // ========== 模型版本管理 ==========

            // 渲染模型版本表格
            function renderModelVersionsTable() {
                const tableBody = document.getElementById('model-versions-table-body');
                if (!tableBody) return;

                if (!state.modelVersions || state.modelVersions.length === 0) {
                    tableBody.innerHTML = `
                        <tr>
                            <td colspan="7" class="empty-state">
                                <div class="empty-content">
                                    <i class="fas fa-code-branch"></i>
                                    <div class="empty-message">暂无模型版本数据</div>
                                    <button class="btn btn-primary" onclick="window.FeaturesPage.showAddVersionModal()">
                                        <i class="fas fa-plus"></i> 添加第一个模型版本
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                    return;
                }

                let html = '';
                state.modelVersions.forEach(version => {
                    const model = state.deviceModels.find(m => m.id === version.model_id);
                    const featureCount = version.feature_count || 0;

                    html += `
                        <tr data-model-version-id="${version.id}">
                            <td><strong>${version.version}</strong></td>
                            <td>${model ? model.name : '未知模型'}</td>
                            <td>${featureCount}</td>
                            <td>${version.description || '-'}</td>
                            <td>
                                <span class="status-badge ${version.is_active ? 'status-active' : 'status-inactive'}">
                                    ${version.is_active ? '启用' : '禁用'}
                                </span>
                            </td>
                            <td>${formatDateTime(version.created_at)}</td>
                            <td>
                                <div class="action-buttons">
                                    <button class="btn-action btn-edit" title="编辑"
                                            onclick="window.FeaturesPage.editModelVersion(${version.id})">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    <button class="btn-action btn-delete" title="删除"
                                            onclick="window.FeaturesPage.deleteModelVersion(${version.id})">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                });

                tableBody.innerHTML = html;
            }

            // 筛选模型版本
            function filterModelVersions() {
                const modelFilter = document.getElementById('version-model-filter').value;
                const statusFilter = document.getElementById('version-status-filter').value;

                let filteredVersions = [...state.modelVersions];

                if (modelFilter) {
                    filteredVersions = filteredVersions.filter(version => version.model_id == modelFilter);
                }

                if (statusFilter === 'active') {
                    filteredVersions = filteredVersions.filter(version => version.is_active);
                } else if (statusFilter === 'inactive') {
                    filteredVersions = filteredVersions.filter(version => !version.is_active);
                }

                // 临时更新显示
                const tableBody = document.getElementById('model-versions-table-body');
                if (!tableBody || filteredVersions.length === 0) {
                    tableBody.innerHTML = `
                        <tr>
                            <td colspan="7" class="empty-state">
                                <div class="empty-content">
                                    <i class="fas fa-code-branch"></i>
                                    <div class="empty-message">没有找到匹配的模型版本</div>
                                </div>
                            </td>
                        </tr>
                    `;
                    return;
                }

                // 重新渲染
                const originalVersions = [...state.modelVersions];
                state.modelVersions = filteredVersions;
                renderModelVersionsTable();
                state.modelVersions = originalVersions;
            }

            // 显示添加版本弹窗
function showAddVersionModal() {
    state.editingVersion = null;
    const modal = document.getElementById('model-version-modal');

    // 重置表单
    const form = document.getElementById('model-version-form');
    form.reset();

    // 清空已选特征
    state.selectedFeatures = [];

    // 重置UI
    updateSelectedFeaturesList(); // 这行会调用 updateStatusFeatureSelector()
    updateSelectedFeaturesCount();

    // 加载可用特征
    loadAvailableFeatures();

    // 更新模型下拉选项
    populateModelDropdown();

    // 重置内层标签页到基础信息
    setTimeout(() => {
        switchInnerTab('version-basic');
    }, 50);

    modal.classList.add('active');
}


        // 编辑模型版本 - 修改加载特征部分
async function editModelVersion(versionId) {
    const version = state.modelVersions.find(v => v.id === versionId);
    if (!version) {
        showNotification('模型版本未找到', 'error');
        return;
    }

    state.editingVersion = version;
    const modal = document.getElementById('model-version-modal');

    // 清空已选特征，重新加载
    state.selectedFeatures = [];

    try {
        console.log(`🔍 开始加载版本 ${versionId} 的特征...`);

        // 尝试使用新的API端点获取详细特征信息
        const detailedResponse = await fetch(`http://localhost:8000/api/v1/features/version/${versionId}/features/detailed`);

        if (detailedResponse.ok) {
            const detailedFeatures = await detailedResponse.json();
            console.log('✅ 从详细特征API获取到特征:', detailedFeatures);

            if (detailedFeatures && detailedFeatures.length > 0) {
                // 转换数据结构
                state.selectedFeatures = detailedFeatures.map((detailedFeature) => {
                    return {
                        feature_id: detailedFeature.feature_id,
                        feature: detailedFeature.feature || {
                            id: detailedFeature.feature_id,
                            name: detailedFeature.feature?.name || '未知特征',
                            code: detailedFeature.feature?.code || '未知代码',
                            data_type: detailedFeature.feature?.data_type || '未知类型',
                            unit: detailedFeature.feature?.unit || '',
                            description: detailedFeature.feature?.description || '',
                            is_required: detailedFeature.feature?.is_required || false,
                            default_value: detailedFeature.feature?.default_value || '',
                            validation_rules: detailedFeature.feature?.validation_rules || {}
                        },
                        display_order: detailedFeature.display_order || 0,
                        is_output: detailedFeature.is_output || false,
                        is_primary_output: detailedFeature.is_primary_output || false, // 修复：确保获取主输出标记
                        is_status: detailedFeature.is_status || false
                    };
                });

                // 调试信息
                console.log(`✅ 设置了 ${state.selectedFeatures.length} 个已选特征`);
                state.selectedFeatures.forEach((f, i) => {
                    console.log(`特征 ${i+1}: ${f.feature.name}, is_primary_output: ${f.is_primary_output}`);
                });
            } else {
                console.log('⚠️ 该版本没有配置特征');
            }
        } else {
            console.error('❌ 详细特征API响应失败:', detailedResponse.status);
            // 如果详细API不可用，给出提示
            showNotification('无法加载特征详细信息', 'error');
        }
    } catch (error) {
        console.error('❌ 加载版本特征失败:', error);
        showNotification('加载特征失败: ' + error.message, 'error');
    }

    // 更新UI
    updateSelectedFeaturesList();
    updateSelectedFeaturesCount();

    // 加载可用特征
    loadAvailableFeatures();

    // 更新模型下拉选项
    populateModelDropdown();

    // 填充表单字段
    setTimeout(() => {
        const modelSelect = document.getElementById('version-model-id');
        if (modelSelect) {
            modelSelect.value = version.model_id;
        }

        document.getElementById('version-number').value = version.version;
        document.getElementById('version-description').value = version.description || '';
        document.getElementById('version-is-active').checked = version.is_active;

        // 重置内层标签页到基础信息
        switchInnerTab('version-basic');
    }, 100);

    modal.classList.add('active');
}

// 保存模型版本
async function saveModelVersion() {
    try {
        // 手动验证必填字段
        const modelId = document.getElementById('version-model-id').value;
        let versionNumber = document.getElementById('version-number').value;

        // 处理版本号中的空格
        versionNumber = versionNumber.trim().replace(/\s+/g, '_');

        // 更新输入框的值
        document.getElementById('version-number').value = versionNumber;

        if (!modelId) {
            showNotification('请选择所属模型', 'warning');
            return;
        }

        if (!versionNumber) {
            showNotification('请输入版本号', 'warning');
            return;
        }

        if (!state.selectedFeatures || state.selectedFeatures.length === 0) {
            showNotification('请至少添加一个特征', 'warning');
            return;
        }

        // 准备版本基础数据
        const versionData = {
            model_id: parseInt(modelId),
            version: versionNumber, // 使用处理后的版本号
            description: document.getElementById('version-description').value.trim(),
            is_active: document.getElementById('version-is-active').checked
        };

        console.log('📤 准备保存版本数据:', versionData);
        console.log('📤 已选特征数量:', state.selectedFeatures.length);

        let savedVersion;

        // 1. 先保存版本基本信息
        if (state.editingVersion) {
            console.log('🔄 更新现有版本:', state.editingVersion.id);

            // 先更新版本基础信息
            savedVersion = await FeaturesAPI.ModelVersionAPI.updateModelVersion(
                state.editingVersion.id,
                versionData
            );
            console.log('✅ 版本基础信息更新成功:', savedVersion);

        } else {
            console.log('🆕 创建新版本');

            // 创建新版本
            savedVersion = await FeaturesAPI.ModelVersionAPI.createModelVersion(versionData);
            console.log('✅ 新版本创建成功:', savedVersion);
        }

        // 获取版本ID
        const versionId = state.editingVersion ? state.editingVersion.id : (savedVersion.id || savedVersion.version_id);

        if (!versionId) {
            throw new Error('无法获取版本ID');
        }

        console.log(`📝 开始更新版本 ${versionId} 的特征...`);

        // 检查输出特征数量（至少一个）
        const outputFeatures = state.selectedFeatures.filter(f => f.is_output);
        if (outputFeatures.length === 0) {
            showNotification('请至少设置一个输出特征', 'warning');
            return;
        }

        // 检查主输出特征数量（必须有且只有一个）
        const primaryOutputFeatures = state.selectedFeatures.filter(f => f.is_primary_output);
        if (primaryOutputFeatures.length !== 1) {
            showNotification('必须设置且只能设置一个主输出特征', 'warning');
            return;
        }

        // 检查主输出特征必须是输出特征
        const invalidPrimaryOutput = primaryOutputFeatures[0];
        if (!invalidPrimaryOutput.is_output) {
            showNotification('主输出特征必须是输出特征', 'warning');
            return;
        }
        // 检查同一个特征不能同时是输出和状态
        const conflictFeature = state.selectedFeatures.find(f => f.is_output && f.is_status);
        if (conflictFeature) {
            showNotification('同一个特征不能同时设置为输出特征和状态特征', 'warning');
            return;
        }

        // 准备特征关联数据
        const featuresData = state.selectedFeatures.map((featureData, index) => {
            // 统一处理特征ID
            let featureId;
            if (featureData.feature_id) {
                featureId = featureData.feature_id;
            } else if (featureData.id) {
                featureId = featureData.id;
            } else if (featureData.feature && featureData.feature.id) {
                featureId = featureData.feature.id;
            }

            if (!featureId) {
                console.error('❌ 无法获取特征ID:', featureData);
                throw new Error('无效的特征数据');
            }

            return {
                feature_id: featureId,
                display_order: index,
                is_output: featureData.is_output || false,
                is_primary_output: featureData.is_primary_output || false, // 新增：主输出特征标记
                is_status: featureData.is_status || false // 新增：状态特征标记
            };
        });

        console.log('📤 准备保存的特征数据:', featuresData);
        console.log('📤 特征数量:', featuresData.length);

        // 3. 更新特征关联（使用特征API）
        try {
            console.log('🔄 调用特征更新API...');

            const response = await fetch(`http://localhost:8000/api/v1/features/update_version_features/${versionId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(featuresData),
                credentials: 'include'
            });

            console.log(`📥 特征API响应状态: ${response.status} ${response.statusText}`);

            if (!response.ok) {
                let errorDetail;
                try {
                    const errorData = await response.json();
                    errorDetail = errorData.detail || JSON.stringify(errorData);
                } catch (e) {
                    errorDetail = await response.text();
                }
                console.error('❌ 特征更新API错误详情:', errorDetail);
                throw new Error(`特征更新失败: ${response.status} ${response.statusText} - ${errorDetail}`);
            }

            const featureResult = await response.json();
            console.log('✅ 特征关联更新成功:', featureResult);

        } catch (featureError) {
            console.error('❌ 特征更新失败:', featureError);

            // 尝试备选方案：如果特征API失败，尝试使用设备模型版本的特征API
            try {
                console.log('🔄 尝试备选方案：使用设备模型版本特征API');

                const fallbackResponse = await fetch(`http://localhost:8000/api/v1/device_models/versions/${versionId}/features`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({ features: featuresData }),
                    credentials: 'include'
                });

                if (fallbackResponse.ok) {
                    console.log('✅ 备选方案成功');
                } else {
                    throw new Error(`备选方案失败: ${fallbackResponse.status}`);
                }
            } catch (fallbackError) {
                console.error('❌ 所有特征更新方法都失败:', fallbackError);
                // 抛出原始错误，不覆盖
                throw featureError;
            }
        }

        // 显示成功消息
        showNotification(state.editingVersion ? '模型版本更新成功' : '模型版本创建成功', 'success');

        // 重新加载数据
        await reloadDataAfterSave();

    } catch (error) {
        console.error('❌ 保存模型版本失败:', error);
        showNotification('保存失败: ' + error.message, 'error');
    }
}

            // 重新加载数据辅助函数
            async function reloadDataAfterSave() {
                console.log('🔄 重新加载数据...');

                try {
                    // 重新加载所有数据
                    await loadInitialData();

                    // 刷新当前页面
                    loadCurrentTabData();

                    // 关闭模态框
                    hideVersionModal();

                    console.log('✅ 数据重新加载完成');
                } catch (reloadError) {
                    console.error('❌ 重新加载数据失败:', reloadError);
                    // 即使重新加载失败，也关闭模态框
                    hideVersionModal();
                    showNotification('保存成功，但刷新数据失败', 'warning');
                }
            }

            // 删除模型版本
            function deleteModelVersion(versionId) {
                const version = state.modelVersions.find(v => v.id === versionId);
                if (!version) return;

                const model = state.deviceModels.find(m => m.id === version.model_id);

                if (!confirm(`确定要删除模型版本 "${model?.name || '未知模型'} - ${version.version}" 吗？\n\n此操作不可恢复！`)) {
                    return;
                }

                try {
                    // 调用API删除
                    FeaturesAPI.ModelVersionAPI.deleteModelVersion(versionId).then(() => {
                        showNotification('模型版本删除成功', 'success');
                        loadInitialData();
                    }).catch(error => {
                        console.error('❌ 删除模型版本失败:', error);
                        showNotification('删除失败: ' + error.message, 'error');
                    });

                } catch (error) {
                    console.error('❌ 删除模型版本失败:', error);
                    showNotification('删除失败: ' + error.message, 'error');
                }
            }

            // 隐藏模型版本弹窗
            function hideVersionModal() {
                document.getElementById('model-version-modal').classList.remove('active');
            }

            // ========== 特征管理 ==========

            // 渲染特征表格
            function renderFeaturesTable() {
                const tableBody = document.getElementById('features-table-body');
                if (!tableBody) return;

                if (!state.features || state.features.length === 0) {
                    tableBody.innerHTML = `<tr><td colspan="10" class="empty-state"><div class="empty-content"><i class="fas fa-sliders-h"></i><div class="empty-message">暂无特征数据</div><button class="btn btn-primary" onclick="window.FeaturesPage.showAddFeatureModal()"><i class="fas fa-plus"></i> 添加第一个特征</button></div></td></tr>`;
                    return;
                }

                let html = '';
                state.features.forEach(feature => {
                    // 确保有验证规则字段，如果没有则用空对象
                    const validationRules = feature.validation_rules || {};

                    html += `<tr data-feature-id="${feature.id}">
                        <td>${feature.name}</td>
                        <td><code>${feature.code}</code></td>
                        <td><span class="badge">${feature.data_type}</span></td>
                        <td>${feature.unit || '-'}</td>
                        <td>${feature.default_value || '-'}</td>
                        <td>${feature.is_required ? '<span class="status-badge status-active">必需</span>' : '可选'}</td>
                        <td>${feature.description || '-'}</td>
                        <td>${JSON.stringify(validationRules)}</td>
                        <td>${formatDateTime(feature.created_at)}</td>
                        <td><div class="action-buttons">
                            <button class="btn-action btn-edit" title="编辑" onclick="window.FeaturesPage.editFeature(${feature.id})"><i class="fas fa-edit"></i></button>
                            <button class="btn-action btn-delete" title="删除" onclick="window.FeaturesPage.deleteFeature(${feature.id})"><i class="fas fa-trash"></i></button>
                        </div></td>
                    </tr>`;
                });
                tableBody.innerHTML = html;
            }

            // 筛选特征
            function filterFeatures() {
                const dataTypeFilter = document.getElementById('feature-data-type-filter').value;
                const requiredFilter = document.getElementById('feature-required-filter').value;

                let filteredFeatures = [...state.features];

                if (dataTypeFilter) {
                    filteredFeatures = filteredFeatures.filter(feature => feature.data_type === dataTypeFilter);
                }

                if (requiredFilter === 'true') {
                    filteredFeatures = filteredFeatures.filter(feature => feature.is_required);
                } else if (requiredFilter === 'false') {
                    filteredFeatures = filteredFeatures.filter(feature => !feature.is_required);
                }

                // 临时更新显示
                const tableBody = document.getElementById('features-table-body');
                if (!tableBody || filteredFeatures.length === 0) {
                    tableBody.innerHTML = `
                        <tr>
                            <td colspan="9" class="empty-state">
                                <div class="empty-content">
                                    <i class="fas fa-sliders-h"></i>
                                    <div class="empty-message">没有找到匹配的特征</div>
                                </div>
                            </td>
                        </tr>
                    `;
                    return;
                }

                // 重新渲染
                const originalFeatures = [...state.features];
                state.features = filteredFeatures;
                renderFeaturesTable();
                state.features = originalFeatures;
            }

            // 显示添加特征弹窗
            function showAddFeatureModal() {
                state.editingFeature = null;
                const modal = document.getElementById('feature-modal');
                const form = document.getElementById('feature-form');

                form.reset();

                // 重置验证状态
                const codeInput = document.getElementById('feature-code');
                codeInput.classList.remove('valid', 'invalid');
                document.getElementById('code-validation-error').style.display = 'none';
                document.getElementById('code-validation-hint').style.display = 'block';

                // 设置默认值
                document.getElementById('feature-data-type').value = 'number';
                document.getElementById('feature-is-required').checked = false;

                modal.classList.add('active');
            }

            // 编辑特征
            function editFeature(featureId) {
                const feature = state.features.find(f => f.id === featureId);
                if (!feature) {
                    showNotification('特征未找到', 'error');
                    return;
                }

                state.editingFeature = feature;
                const modal = document.getElementById('feature-modal');
                const form = document.getElementById('feature-form');

                // 填充表单
                document.getElementById('feature-name').value = feature.name;
                document.getElementById('feature-code').value = feature.code;
                document.getElementById('feature-data-type').value = feature.data_type;
                document.getElementById('feature-unit').value = feature.unit || '';
                document.getElementById('feature-default-value').value = feature.default_value || '';
                document.getElementById('feature-is-required').checked = feature.is_required;
                document.getElementById('feature-description').value = feature.description || '';

                // 验证特征代码（应该通过）
                setTimeout(() => {
                    validateFeatureCode(document.getElementById('feature-code'));
                }, 100);

                modal.classList.add('active');
            }

            // 保存特征
            async function saveFeature() {
                try {
                    const form = document.getElementById('feature-form');

                    // 首先获取并处理特征代码
                    const codeInput = document.getElementById('feature-code');

                    // 在保存时也应用相同的格式化
                    autoFormatCodeField(codeInput);

                    // 现在验证处理后的代码
                    if (!validateFeatureCode(codeInput)) {
                        showNotification('特征代码格式不正确，请按照提示修改', 'warning');
                        codeInput.focus();
                        return;
                    }

                    // 验证其他必填字段
                    const nameInput = document.getElementById('feature-name');
                    const dataTypeSelect = document.getElementById('feature-data-type');

                    if (!nameInput.value.trim()) {
                        showNotification('请输入特征名称', 'warning');
                        nameInput.focus();
                        return;
                    }

                    if (!dataTypeSelect.value) {
                        showNotification('请选择数据类型', 'warning');
                        dataTypeSelect.focus();
                        return;
                    }

                    // 准备数据，但先进行清理
                    const featureData = {
                        name: nameInput.value.trim(),
                        code: codeInput.value, // 使用处理后的特征代码
                        data_type: dataTypeSelect.value,
                        unit: document.getElementById('feature-unit').value.trim() || null,
                        default_value: document.getElementById('feature-default-value').value.trim() || null,
                        is_required: document.getElementById('feature-is-required').checked,
                        description: document.getElementById('feature-description').value.trim() || null,
                        validation_rules: {}  // 添加默认的空验证规则对象
                    };

                    console.log('📤 准备创建特征数据:', JSON.stringify(featureData, null, 2));

                    // 检查是否已存在同名特征（前端检查）
                    const existingFeature = state.features.find(f =>
                        f.code.toLowerCase() === featureData.code.toLowerCase()
                    );

                    if (existingFeature && (!state.editingFeature || state.editingFeature.id !== existingFeature.id)) {
                        showNotification(`特征代码 "${featureData.code}" 已存在，请使用其他代码`, 'warning');
                        return;
                    }

                    let result;
                    if (state.editingFeature) {
                        // 更新现有特征
                        result = await FeaturesAPI.FeatureAPI.updateFeature(state.editingFeature.id, featureData);
                        showNotification('特征更新成功', 'success');
                    } else {
                        // 创建新特征
                        result = await FeaturesAPI.FeatureAPI.createFeature(featureData);
                        showNotification('特征创建成功', 'success');
                    }

                    console.log('✅ 保存成功:', result);

                    // 重新加载数据
                    await loadInitialData();
                    hideFeatureModal();

                } catch (error) {
                    console.error('❌ 保存特征失败:', error);

                    // 更友好的错误提示
                    let errorMessage = '保存失败';
                    if (error.message.includes('422')) {
                        errorMessage = '数据格式不正确，请检查特征代码和数据类型';
                    } else if (error.message.includes('400')) {
                        errorMessage = '特征代码可能已存在，请修改后重试';
                    } else if (error.message.includes('500')) {
                        errorMessage = '服务器错误，请稍后重试';
                    }

                    showNotification(`${errorMessage}: ${error.message}`, 'error');
                }
            }

            // 删除特征
            function deleteFeature(featureId) {
                const feature = state.features.find(f => f.id === featureId);
                if (!feature) return;

                if (!confirm(`确定要删除特征 "${feature.name}" 吗？\n\n此操作将影响所有使用此特征的设备模型版本，且不可恢复！`)) {
                    return;
                }

                try {
                    // 调用API删除
                    FeaturesAPI.FeatureAPI.deleteFeature(featureId).then(() => {
                        showNotification('特征删除成功', 'success');
                        loadInitialData();
                    }).catch(error => {
                        console.error('❌ 删除特征失败:', error);
                        showNotification('删除失败: ' + error.message, 'error');
                    });

                } catch (error) {
                    console.error('❌ 删除特征失败:', error);
                    showNotification('删除失败: ' + error.message, 'error');
                }
            }

            // 隐藏特征弹窗
            function hideFeatureModal() {
                document.getElementById('feature-modal').classList.remove('active');
            }

            // ========== 辅助函数 ==========

// 特征代码验证函数
function validateFeatureCode(inputElement) {
    const value = inputElement.value;
    const validationError = document.getElementById('code-validation-error');
    const validationHint = document.getElementById('code-validation-hint');
    const errorText = document.getElementById('code-error-text');

    // 清除之前的样式
    inputElement.classList.remove('valid', 'invalid');

    if (!value) {
        validationError.style.display = 'none';
        validationHint.style.display = 'block';
        return true;
    }

    // 自动处理：去除头尾空格
    let processedValue = value.trim();

    // 自动处理：将中间的连续空格（一个或多个）替换为单个下划线
    processedValue = processedValue.replace(/\s+/g, '_');

    // 自动处理：将所有大写字母转为小写
    processedValue = processedValue.toLowerCase();

    // 如果处理后的值与原始值不同，更新输入框
    if (processedValue !== value) {
        inputElement.value = processedValue;

        // 获取文本选区，确保光标位置正确
        const selectionStart = inputElement.selectionStart;
        const selectionEnd = inputElement.selectionEnd;

        // 设置光标到文本末尾
        inputElement.focus();
        inputElement.setSelectionRange(selectionStart, selectionEnd);

        // 显示提示信息
        validationHint.style.display = 'none';
        validationError.style.display = 'block';
        errorText.textContent = '已自动处理：头尾空格已去除，连续空格已替换为下划线，大写字母已转为小写';
        inputElement.classList.add('valid'); // 添加有效样式，因为是自动修复

        // 延迟验证，确保输入框值已更新
        setTimeout(() => validateFeatureCode(inputElement), 10);
        return true;
    }

    // 检测中文下划线（全角）
    if (/＿/.test(value)) {
        inputElement.classList.add('invalid');
        validationError.style.display = 'block';
        validationHint.style.display = 'none';
        errorText.textContent = '请使用英文下划线 (_)，而不是中文下划线 (＿)';
        return false;
    }

    // 检测中文字符
    if (/[\u4e00-\u9fa5]/.test(value)) {
        inputElement.classList.add('invalid');
        validationError.style.display = 'block';
        validationHint.style.display = 'none';
        errorText.textContent = '不能包含中文字符，请使用小写英文字母';
        return false;
    }

    // 检测特殊字符（除了字母、数字、下划线）
    if (!/^[a-zA-Z0-9_]+$/.test(value)) {
        inputElement.classList.add('invalid');
        validationError.style.display = 'block';
        validationHint.style.display = 'none';

        // 找出具体的非法字符
        const illegalChars = value.match(/[^a-zA-Z0-9_]/g);
        if (illegalChars) {
            const uniqueChars = [...new Set(illegalChars)];
            const charList = uniqueChars.map(c => {
                if (c === ' ') return '空格';
                if (c === '-') return '连字符 (-)';
                if (c === '.') return '点 (.)';
                return `"${c}"`;
            }).join('、');

            errorText.textContent = `包含非法字符：${charList}`;
        }
        return false;
    }

    // 验证通过
    inputElement.classList.add('valid');
    validationError.style.display = 'none';
    validationHint.style.display = 'block';
    return true;
}

            // 特征搜索功能
            function searchFeatures(keyword) {
                const availableFeaturesList = document.getElementById('available-features-list');
                if (!availableFeaturesList) return;

                const items = availableFeaturesList.querySelectorAll('.feature-item');

                items.forEach(item => {
                    const featureName = item.querySelector('.feature-name').textContent.toLowerCase();
                    const featureCode = item.querySelector('.feature-code').textContent.toLowerCase();
                    const searchTerm = keyword.toLowerCase();

                    if (featureName.includes(searchTerm) || featureCode.includes(searchTerm)) {
                        item.style.display = 'flex';
                    } else {
                        item.style.display = 'none';
                    }
                });
            }

            // 填充模型下拉选项
            function populateModelDropdown() {
                const dropdown = document.getElementById('version-model-id');
                if (!dropdown) return;

                const currentValue = dropdown.value;
                dropdown.innerHTML = '<option value="">请选择设备模型</option>';

                state.deviceModels.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.id;
                    option.textContent = `${model.name} (${model.code})`;
                    option.disabled = !model.is_active;
                    dropdown.appendChild(option);
                });

                if (currentValue) {
                    dropdown.value = currentValue;
                }
            }

            // 加载可用特征
            function loadAvailableFeatures() {
    const container = document.getElementById('available-features-list');
    if (!container) return;

    // 显示加载状态
    container.innerHTML = '<div class="loading">正在加载特征...</div>';

    if (!state.features || state.features.length === 0) {
        container.innerHTML = '<div class="empty-state">特征数据正在加载中...</div>';
        return;
    }

    const selectedFeatureIds = state.selectedFeatures?.map(f => f.feature_id || f.id) || [];
    let availableFeatures = state.features.filter(f => !selectedFeatureIds.includes(f.id));

    // ★ 关键修复：先获取搜索关键字，直接过滤数据源
    const searchInput = document.getElementById('feature-search');
    const keyword = searchInput ? searchInput.value.trim().toLowerCase() : '';

    if (keyword) {
        availableFeatures = availableFeatures.filter(f =>
            f.name.toLowerCase().includes(keyword) ||
            f.code.toLowerCase().includes(keyword)
        );
    }

    if (availableFeatures.length === 0) {
        container.innerHTML = keyword
            ? '<div class="empty-state">未找到匹配的特征</div>'
            : '<div class="empty-state">所有特征都已添加到该版本</div>';
        return;
    }

    // 按特征名称排序
    availableFeatures.sort((a, b) => a.name.localeCompare(b.name));

    let html = '';
    availableFeatures.forEach(feature => {
        html += `
            <div class="feature-item" data-id="${feature.id}">
                <div class="feature-info">
                    <div class="feature-name">${feature.name}</div>
                    <div class="feature-details">
                        <span class="feature-code">${feature.code}</span>
                        <span class="feature-badge">${feature.data_type}</span>
                        ${feature.unit ? `<span class="feature-unit">${feature.unit}</span>` : ''}
                        ${feature.is_required ? '<span class="required-badge">必填</span>' : ''}
                    </div>
                    <div class="feature-description">${feature.description || '暂无描述'}</div>
                </div>
                <button class="btn-action btn-add" title="添加到此版本"
                        onclick="window.FeaturesPage.selectFeature(${feature.id})">
                    <i class="fas fa-plus"></i>
                </button>
            </div>
        `;
    });

    container.innerHTML = html;
    // 不再需要额外调用 searchFeatures，因为数据源已过滤
}

            // 选择特征
function selectFeature(featureId) {
    const feature = state.features.find(f => f.id === featureId);
    if (!feature || !state.selectedFeatures) return;

    // 检查是否已选择
    const alreadySelected = state.selectedFeatures.some(f =>
        f.feature_id === featureId || f.id === featureId
    );

    if (!alreadySelected) {
        state.selectedFeatures.push({
            feature_id: featureId,
            feature: feature,
            display_order: state.selectedFeatures.length,
            is_output: false,  // 默认不是输出特征
            is_status: false   // 新增：默认不是状态特征
        });

        updateSelectedFeaturesList();
        updateSelectedFeaturesCount();
        loadAvailableFeatures();
    }
}

// 更新已选特征列表的显示
function updateSelectedFeaturesList() {
    const container = document.getElementById('selected-features-list');
    const outputSelector = document.getElementById('output-features-selector');
    const primaryOutputSelector = document.getElementById('primary-output-feature-selector');
    const statusSelector = document.getElementById('status-feature-selector');

    if (!container) return;

    if (!state.selectedFeatures || state.selectedFeatures.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-sliders-h"></i>
                <div class="empty-message">暂无特征，从左侧添加</div>
            </div>
        `;

        // 清空选择器
        [outputSelector, primaryOutputSelector, statusSelector].forEach(selector => {
            if (selector) {
                selector.innerHTML = `
                    <div class="empty-state">
                        <i class="fas fa-exclamation-circle"></i>
                        <div class="empty-message">请先添加特征到已选列表</div>
                    </div>
                `;
            }
        });
        return;
    }

    let html = '';
    state.selectedFeatures.forEach((featureData, index) => {
        const feature = featureData.feature || featureData;
        const featureId = feature.id || feature.feature_id;
        const featureName = feature.name || '未知特征';
        const featureCode = feature.code || '未知代码';
        const dataType = feature.data_type || '未知类型';
        const unit = feature.unit || '';
        const description = feature.description || '';
        const isOutput = featureData.is_output || false;
        const isPrimaryOutput = featureData.is_primary_output || false;
        const isStatus = featureData.is_status || false;

        html += `
            <div class="feature-item selected" data-id="${featureId}">
                <div class="feature-order">${index + 1}</div>
                <div class="feature-info">
                    <div class="feature-name">
                        ${featureName}
                        ${isOutput ? '<span class="output-badge"><i class="fas fa-bullseye"></i> 输出特征</span>' : ''}
                        ${isPrimaryOutput ? '<span class="primary-output-badge" style="background: linear-gradient(135deg, #FF9800, #FFB74D);"><i class="fas fa-star"></i> 主输出</span>' : ''}
                        ${isStatus ? '<span class="status-badge" style="background: linear-gradient(135deg, #2196F3, #64B5F6);"><i class="fas fa-toggle-on"></i> 状态特征</span>' : ''}
                    </div>
                    <div class="feature-details">
                        <span class="feature-code">${featureCode}</span>
                        <span class="feature-badge">${dataType}</span>
                        ${unit ? `<span class="feature-unit">${unit}</span>` : ''}
                    </div>
                    ${description ? `<div class="feature-description">${description}</div>` : ''}
                </div>
                <div class="feature-actions">
                    <button class="btn-action btn-remove" title="移除"
                            onclick="window.FeaturesPage.removeSelectedFeature(${featureId})">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;

    // 更新所有选择器 - 修复：添加主输出特征选择器更新
    updateOutputFeaturesSelector();
    updatePrimaryOutputFeatureSelector(); // 添加这行
    updateStatusFeatureSelector();
}


// 更新输出特征选择器（多选）
function updateOutputFeaturesSelector() {
    const outputSelector = document.getElementById('output-features-selector');
    if (!outputSelector) return;

    if (!state.selectedFeatures || state.selectedFeatures.length === 0) {
        outputSelector.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-circle"></i>
                <div class="empty-message">请先添加特征到已选列表</div>
            </div>
        `;
        return;
    }

    let html = '';
    state.selectedFeatures.forEach((featureData) => {
        const feature = featureData.feature || featureData;
        // 修复：确保正确获取特征ID
        const featureId = featureData.feature_id || feature.id;
        const featureName = feature.name || '未知特征';
        const featureCode = feature.code || '未知代码';
        const isOutput = featureData.is_output || false;

        html += `
            <div class="output-feature-option">
                <label class="checkbox">
                    <input type="checkbox"
                           value="${featureId}"
                           ${isOutput ? 'checked' : ''}
                           onchange="window.FeaturesPage.toggleOutputFeature(${featureId}, this.checked)">
                    <span class="checkbox-label">
                        <strong>${featureName}</strong>
                        <code>${featureCode}</code>
                    </span>
                </label>
            </div>
        `;
    });

    outputSelector.innerHTML = html;
}

// 切换输出特征状态
function toggleOutputFeature(featureId, isOutput) {
    if (!state.selectedFeatures) return;

    const featureIndex = state.selectedFeatures.findIndex(f =>
        f.feature_id === featureId || f.id === featureId
    );

    if (featureIndex > -1) {
        // 设置输出特征
        state.selectedFeatures[featureIndex].is_output = isOutput;

        // 如果取消输出特征，也取消主输出标记
        if (!isOutput) {
            state.selectedFeatures[featureIndex].is_primary_output = false;
        }

        // 更新显示
        updateSelectedFeaturesList();
    }
}
// 更新状态特征选择器
function updateStatusFeatureSelector() {
    const statusSelector = document.getElementById('status-feature-selector');
    if (!statusSelector) {
        console.error('❌ 状态特征选择器元素未找到');
        return;
    }

    // 如果没有已选特征，显示空状态
    if (!state.selectedFeatures || state.selectedFeatures.length === 0) {
        statusSelector.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-circle"></i>
                <div class="empty-message">请先添加特征到已选列表</div>
            </div>
        `;
        return;
    }

    let html = '';
    state.selectedFeatures.forEach((featureData) => {
        const feature = featureData.feature || featureData;
        const featureId = featureData.feature_id || feature.id;
        const featureName = feature.name || '未知特征';
        const featureCode = feature.code || '未知代码';
        const isStatus = featureData.is_status || false;

        html += `
            <div class="status-feature-option">
                <label class="checkbox">
                    <input type="checkbox"
                           value="${featureId}"
                           ${isStatus ? 'checked' : ''}
                           onchange="window.FeaturesPage.toggleStatusFeature(${featureId}, this.checked)">
                    <span class="checkbox-label">
                        <strong>${featureName}</strong>
                        <code>${featureCode}</code>
                    </span>
                </label>
            </div>
        `;
    });

    statusSelector.innerHTML = html;
    console.log('✅ 状态特征选择器更新完成');
}
function toggleStatusFeature(featureId, isChecked) {
    if (!state.selectedFeatures) return;

    const featureIndex = state.selectedFeatures.findIndex(f =>
        f.feature_id === featureId || f.id === featureId
    );

    if (featureIndex > -1) {
        state.selectedFeatures[featureIndex].is_status = isChecked;
        updateSelectedFeaturesList(); // 更新列表显示（刷新标记）
    }
}
// 更新主输出特征选择器
function updatePrimaryOutputFeatureSelector() {
    const primarySelector = document.getElementById('primary-output-feature-selector');
    if (!primarySelector) {
        console.error('❌ 主输出特征选择器元素未找到');
        return;
    }

    // 筛选出输出特征
    const outputFeatures = state.selectedFeatures?.filter(f => f.is_output) || [];

    console.log('🔄 更新主输出特征选择器');
    console.log('📊 所有已选特征:', state.selectedFeatures);
    console.log('🎯 输出特征:', outputFeatures);
    console.log('🏆 主输出特征:', outputFeatures.find(f => f.is_primary_output));

    if (outputFeatures.length === 0) {
        console.log('⚠️ 没有输出特征，显示空状态');
        primarySelector.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-exclamation-circle"></i>
                <div class="empty-message">请先设置至少一个输出特征</div>
            </div>
        `;
        return;
    }

    // 找出当前的主输出特征
    const currentPrimaryFeature = outputFeatures.find(f => f.is_primary_output);
    console.log('✅ 当前主输出特征:', currentPrimaryFeature);

    let html = '';
    outputFeatures.forEach((featureData) => {
        const feature = featureData.feature || featureData;
        // 修复：确保正确获取特征ID
        const featureId = featureData.feature_id || feature.id;
        const featureName = feature.name || '未知特征';
        const featureCode = feature.code || '未知代码';

        // 检查是否是主输出特征
        const isPrimaryOutput = featureData.is_primary_output || false;
        console.log(`特征 ${featureName} (ID: ${featureId}) 是否主输出: ${isPrimaryOutput}`);

        const isSelected = currentPrimaryFeature &&
                         (currentPrimaryFeature.feature_id === featureId ||
                          currentPrimaryFeature.id === featureId);

        console.log(`特征 ${featureName} 是否被选中: ${isSelected}`);

        html += `
            <div class="primary-output-option">
                <label class="radio">
                    <input type="radio"
                           name="primary-output"
                           value="${featureId}"
                           ${isSelected ? 'checked' : ''}
                           onchange="window.FeaturesPage.setPrimaryOutputFeature(${featureId})">
                    <span class="radio-label">
                        <strong>${featureName}</strong>
                        <code>${featureCode}</code>
                    </span>
                </label>
            </div>
        `;
    });

    primarySelector.innerHTML = html;
    console.log('✅ 主输出特征选择器更新完成，HTML长度:', html.length);
}

// 设置主输出特征
function setPrimaryOutputFeature(featureId) {
    if (!state.selectedFeatures) return;

    // 先清除所有特征的主输出标记
    state.selectedFeatures.forEach(featureData => {
        featureData.is_primary_output = false;
    });

    // 设置选中的特征为主输出
    const featureIndex = state.selectedFeatures.findIndex(f =>
        (f.feature_id === featureId) || (f.id === featureId) ||
        (f.feature && f.feature.id === featureId)
    );

    if (featureIndex > -1) {
        // 确保该特征是输出特征
        state.selectedFeatures[featureIndex].is_output = true;
        state.selectedFeatures[featureIndex].is_primary_output = true;
        updateSelectedFeaturesList();
    }
}



// 在 removeSelectedFeature 函数中，添加状态特征的处理
function removeSelectedFeature(featureId) {
    if (!state.selectedFeatures) return;

    const index = state.selectedFeatures.findIndex(f =>
        f.feature_id === featureId || f.id === featureId
    );

    if (index > -1) {
        // 如果移除的是输出特征，需要清除输出特征标记
        const isOutputFeature = state.selectedFeatures[index].is_output;
        const isStatusFeature = state.selectedFeatures[index].is_status; // 新增：检查是否是状态特征
        state.selectedFeatures.splice(index, 1);

        // 重新计算显示顺序
        updateDisplayOrders();
        updateSelectedFeaturesList();
        updateSelectedFeaturesCount();
        loadAvailableFeatures();

        if (isOutputFeature) {
            // 如果还有特征，自动选择第一个特征作为输出特征
            if (state.selectedFeatures.length > 0) {
                state.selectedFeatures[0].is_output = true;
                updateSelectedFeaturesList();
            }
        }

        if (isStatusFeature) {
            // 如果移除了状态特征，清除状态特征标记
            // 状态特征不自动选择新的，因为它是可选的
        }
    }
}
            // 更新输出特征选择器
            function updateOutputFeatureSelector() {
                const outputSelector = document.getElementById('output-feature-selector');
                if (!outputSelector || !state.selectedFeatures || state.selectedFeatures.length === 0) return;

                let html = '';
                let hasOutputFeature = false;

                // 先找出当前选中的输出特征
                const currentOutputFeature = state.selectedFeatures.find(f => f.is_output);

                // 创建单选按钮组
                state.selectedFeatures.forEach((featureData, index) => {
                    const feature = featureData.feature || featureData;
                    const featureId = feature.id || feature.feature_id;
                    const featureName = feature.name || '未知特征';
                    const featureCode = feature.code || '未知代码';
                    const isSelected = currentOutputFeature &&
                                     (currentOutputFeature.feature_id === featureId ||
                                      currentOutputFeature.id === featureId);

                    if (isSelected) hasOutputFeature = true;

                    html += `
                        <div class="output-feature-option">
                            <label class="radio">
                                <input type="radio"
                                       name="output-feature"
                                       value="${featureId}"
                                       ${isSelected ? 'checked' : ''}
                                       onchange="window.FeaturesPage.setOutputFeature(${featureId})">
                                <span class="radio-label">
                                    <strong>${featureName}</strong>
                                    <code>${featureCode}</code>
                                </span>
                            </label>
                        </div>
                    `;
                });

                // 添加"无输出特征"选项
                html += `
                    <div class="output-feature-option">
                        <label class="radio">
                            <input type="radio"
                                   name="output-feature"
                                   value=""
                                   ${!hasOutputFeature ? 'checked' : ''}
                                   onchange="window.FeaturesPage.clearOutputFeature()">
                            <span class="radio-label">
                                <em>不设置输出特征</em>
                            </span>
                        </label>
                    </div>
                `;

                outputSelector.innerHTML = html;
            }

            // 设置输出特征
            function setOutputFeature(featureId) {
                if (!state.selectedFeatures) return;

                // 先清除所有特征的输出标记
                state.selectedFeatures.forEach(featureData => {
                    featureData.is_output = false;
                });

                // 设置选中的特征为输出特征
                const featureIndex = state.selectedFeatures.findIndex(f =>
                    f.feature_id === featureId || f.id === featureId
                );

                if (featureIndex > -1) {
                    state.selectedFeatures[featureIndex].is_output = true;
                    updateSelectedFeaturesList();
                }
            }

            // 清除输出特征
            function clearOutputFeature() {
                if (!state.selectedFeatures) return;

                state.selectedFeatures.forEach(featureData => {
                    featureData.is_output = false;
                });

                updateSelectedFeaturesList();
            }

            // 更新已选特征数量
            function updateSelectedFeaturesCount() {
                const countElement = document.getElementById('selected-features-count');
                if (countElement && state.selectedFeatures) {
                    countElement.textContent = `(${state.selectedFeatures.length})`;
                }
            }

            // 移除已选特征
            function removeSelectedFeature(featureId) {
                if (!state.selectedFeatures) return;

                const index = state.selectedFeatures.findIndex(f =>
                    f.feature_id === featureId || f.id === featureId
                );

                if (index > -1) {
                    // 如果移除的是输出特征，需要清除输出特征标记
                    const isOutputFeature = state.selectedFeatures[index].is_output;
                    state.selectedFeatures.splice(index, 1);

                    // 重新计算显示顺序
                    updateDisplayOrders();
                    updateSelectedFeaturesList();
                    updateSelectedFeaturesCount();
                    loadAvailableFeatures();

                    if (isOutputFeature) {
                        // 如果还有特征，自动选择第一个特征作为输出特征（可选）
                        if (state.selectedFeatures.length > 0) {
                            state.selectedFeatures[0].is_output = true;
                            updateSelectedFeaturesList();
                        }
                    }
                }
            }

            // 更新显示顺序
            function updateDisplayOrders() {
                state.selectedFeatures.forEach((feature, index) => {
                    feature.display_order = index;
                });
            }

            // 格式化日期时间
            function formatDateTime(dateTime) {
                if (!dateTime) return '-';

                const date = new Date(dateTime);
                return date.toLocaleString('zh-CN', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }

            // 显示通知
            function showNotification(message, type = 'info') {
                alert(`${type === 'error' ? '❌ ' : type === 'success' ? '✅ ' : 'ℹ️ '}${message}`);
            }

            // 公开的方法
            return {
                init,

                // 设备模型
                showAddModelModal,
                editDeviceModel,
                deleteDeviceModel,
                viewModelVersions,

                // 模型版本
                showAddVersionModal,
                editModelVersion,
                deleteModelVersion,
                selectFeature,
                removeSelectedFeature,
                // 特征
                showAddFeatureModal,
                editFeature,
                deleteFeature,
                setOutputFeature,
                clearOutputFeature,

                // 特征搜索
                searchFeatures,
                 // 输出特征相关
                toggleOutputFeature,
                setPrimaryOutputFeature,

                // 状态特征相关
                 toggleStatusFeature,
            };
        })();

        // 全局导出
        if (typeof window !== 'undefined') {
            window.FeaturesPage = FeaturesPage;
        }
