// js/pages/config.js
const ConfigPage = (function() {
    // 私有变量
    let currentDataSourceId = null;
    let currentDatabase = null;
    let currentProjectId = null;
    let currentDeviceId = null;
    let editingDataSourceId = null;
    let dataSources = [];
    let projects = [];
    let devices = [];
    let deviceFeatures = [];
    let tableMappings = {};
    let usedFeatures = [];
    let creatingDataSourceId = null;
    let creatingDatabase = null;
    // DOM 元素
    const elements = {
        // 按钮
        addDataSourceBtn: document.getElementById('add-data-source-btn'),
        refreshDataSourcesBtn: document.getElementById('refresh-data-sources-btn'),
        refreshTablesBtn: document.getElementById('refresh-tables-btn'),
        saveMappingBtn: document.getElementById('save-mapping-btn'),

        // 选择器
        selectDataSource: document.getElementById('select-data-source'),
        selectDatabase: document.getElementById('select-database'),
        selectProject: document.getElementById('select-project'),
        selectDevice: document.getElementById('select-device'),

        // 容器
        dataSourceList: document.getElementById('data-source-list'),
        tableFeatureMapping: document.getElementById('table-feature-mapping'),

        // 模态框
        dataSourceModal: document.getElementById('data-source-modal'),
        deleteConfirmModal: document.getElementById('delete-confirm-modal'),

        // 表单
        dataSourceForm: document.getElementById('data-source-form'),

        // 模态框按钮
        dsCancel: document.getElementById('ds-cancel'),
        dsSave: document.getElementById('ds-save'),
        testConnectionBtn: document.getElementById('test-connection-btn'),
        deleteCancel: document.getElementById('delete-cancel'),
        deleteConfirm: document.getElementById('delete-confirm')
    };

    // 初始化函数
    function init() {
    console.log('🚀 初始化数据源配置页面');

    // 初始化事件监听器
    initEventListeners();

    // 加载数据源
    loadDataSources();

    // 更新UI状态
    updateUI();

    // 绑定模态框关闭事件
    bindModalEvents();

    console.log('✅ 数据源配置页面初始化完成');
}

    // 初始化事件监听器
    function initEventListeners() {
        console.log('🔗 绑定事件监听器...');

            // 绑定创建表模态框事件
        if (document.getElementById('create-table-cancel')) {
            document.getElementById('create-table-cancel').addEventListener('click', closeAllModals);
        }
        if (document.getElementById('create-table-confirm')) {
            document.getElementById('create-table-confirm').addEventListener('click', createTable);
        }
        // 添加数据源按钮
        if (elements.addDataSourceBtn) {
            elements.addDataSourceBtn.addEventListener('click', showDataSourceModal);
        }

        // 刷新数据源列表
        if (elements.refreshDataSourcesBtn) {
            elements.refreshDataSourcesBtn.addEventListener('click', loadDataSources);
        }

        // 数据源选择变化
        if (elements.selectDataSource) {
            elements.selectDataSource.addEventListener('change', handleDataSourceChange);
        }

        // 数据库选择变化
        if (elements.selectDatabase) {
            elements.selectDatabase.addEventListener('change', handleDatabaseChange);
        }

        // 项目选择变化
        if (elements.selectProject) {
            elements.selectProject.addEventListener('change', handleProjectChange);
        }

        // 设备选择变化
        if (elements.selectDevice) {
            elements.selectDevice.addEventListener('change', handleDeviceChange);
        }

        // 刷新表列表按钮
        if (elements.refreshTablesBtn) {
            elements.refreshTablesBtn.addEventListener('click', () => {
                if (currentDataSourceId && currentDatabase) {
                    loadDatabaseTables(currentDataSourceId, currentDatabase);
                }
            });
        }

        // 保存映射配置
        if (elements.saveMappingBtn) {
            elements.saveMappingBtn.addEventListener('click', saveMappingConfig);
        }
        console.log('✅ 事件监听器绑定完成');
    }

    // 绑定模态框关闭事件
    function bindModalEvents() {
    console.log('🔧 绑定模态框事件...');

    // ESC键关闭所有弹窗
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeAllModals();
        }
    });

    // 点击模态框外部关闭
    document.querySelectorAll('.modal').forEach(modal => {
        if (modal) {
            modal.addEventListener('click', function(event) {
                if (event.target === this || event.target.classList.contains('modal-close')) {
                    closeAllModals();
                }
            });
        }
    });

    // 模态框关闭按钮（专门处理X按钮）
    document.querySelectorAll('.modal-close').forEach(btn => {
        if (btn) {
            btn.addEventListener('click', function(event) {
                event.stopPropagation();
                closeAllModals();
            });
        }
    });

    // 取消按钮
    if (elements.dsCancel) {
        elements.dsCancel.addEventListener('click', function(event) {
            event.stopPropagation();
            closeAllModals();
        });
    }
    if (elements.deleteCancel) {
        elements.deleteCancel.addEventListener('click', function(event) {
            event.stopPropagation();
            closeAllModals();
        });
    }

    // 保存数据源按钮
    if (elements.dsSave) {
        elements.dsSave.addEventListener('click', function(event) {
            event.stopPropagation();
            saveDataSource();
        });
    }

    // 测试连接按钮
    if (elements.testConnectionBtn) {
        elements.testConnectionBtn.addEventListener('click', function(event) {
            event.stopPropagation();
            testConnection();
        });
    }

    // 删除确认按钮
    if (elements.deleteConfirm) {
        elements.deleteConfirm.addEventListener('click', function(event) {
            event.stopPropagation();
            confirmDelete();
        });
    }

    console.log('✅ 模态框事件绑定完成');
}

    // 加载数据源列表
    async function loadDataSources() {
        try {
            showLoading(elements.dataSourceList, '正在加载数据源...');

            // 从API获取数据源
            const response = await fetch(API.DATA_SOURCES);
            if (!response.ok) throw new Error('数据源加载失败');

            dataSources = await response.json();

            // 确保所有数据源都有正确的字段名
            dataSources.forEach(ds => {
                // 如果后端返回的是 database 字段，转换为 database_name
                if (ds.database && !ds.database_name) {
                    ds.database_name = ds.database;
                }
                // 初始化连接状态
                ds.connection_status = 'unknown';
            });

            renderDataSourceList();
            updateDataSourceSelect();
            loadSavedMappings();
            showNotification('数据源列表已更新', 'success');

        } catch (error) {
            console.error('❌ 加载数据源失败:', error);
            showError(elements.dataSourceList, '加载数据源失败: ' + error.message);
            showNotification('加载数据源失败', 'error');
        }
    }

    // 加载已保存的映射配置
    function loadSavedMappings() {
        try {
            const savedData = localStorage.getItem('feature_table_mappings');
            if (savedData) {
                tableMappings = JSON.parse(savedData);
                console.log('✅ 加载已保存的映射配置:', tableMappings);
            }
        } catch (error) {
            console.error('❌ 加载映射配置失败:', error);
            tableMappings = {};
        }
    }

    // 渲染数据源列表
    function renderDataSourceList() {
        if (!dataSources || dataSources.length === 0) {
            elements.dataSourceList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-database fa-3x"></i>
                    <h3>暂无数据源配置</h3>
                    <p>点击右上角按钮添加MySQL数据源</p>
                </div>
            `;
            return;
        }

        const html = dataSources.map(ds => {
            // 使用正确的数据库名称字段
            const dbName = ds.database_name || ds.database || '未设置';
            const mappedTables = countMappedTables(ds.id, dbName);

            // 格式化时间
            const createdAt = ds.created_at ? new Date(ds.created_at).toLocaleString('zh-CN') : '未知';
            const updatedAt = ds.updated_at ? new Date(ds.updated_at).toLocaleString('zh-CN') : '未知';

            // 动态测试连接状态
            const status = ds.connection_status || ds.status || 'unknown';
            const statusText = status === 'connected' ? '已连接' :
                             status === 'disconnected' ? '未连接' : '未知';

            return `
                <div class="data-source-card" data-id="${ds.id}">
                    <div class="data-source-card-header">
                        <div class="data-source-card-title">
                            <i class="fas fa-database"></i>
                            ${ds.name}
                            <span class="status-badge ${status === 'connected' ? 'connected-badge' :
                                                status === 'disconnected' ? 'disconnected-badge' :
                                                'unknown-badge'}">
                                <i class="fas fa-circle" style="font-size: 0.7em;"></i>
                                ${statusText}
                            </span>
                        </div>
                        <div class="data-source-actions">
                            <button class="btn-action" onclick="ConfigPage.testDataSource(${ds.id})" title="测试连接">
                                <i class="fas fa-vial"></i>
                            </button>
                            <button class="btn-action btn-create-table" onclick="ConfigPage.showCreateTableModal(${ds.id})" title="创建特征表">
                                <i class="fas fa-plus-circle"></i>
                            </button>
                            <button class="btn-action btn-edit" onclick="ConfigPage.editDataSource(${ds.id})" title="编辑">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="btn-action btn-delete" onclick="ConfigPage.deleteDataSource(${ds.id})" title="删除">
                                <i class="fas fa-trash"></i>
                            </button>
                        </div>
                    </div>
                    <div class="data-source-card-meta">
                        <div class="connection-info">
                            <div class="connection-info-item">
                                <span class="connection-info-label">主机:</span>
                                <span class="connection-info-value">${ds.host}:${ds.port}</span>
                            </div>
                            <div class="connection-info-item">
                                <span class="connection-info-label">数据库:</span>
                                <span class="connection-info-value">${dbName}</span>
                            </div>
                            <div class="connection-info-item">
                                <span class="connection-info-label">用户:</span>
                                <span class="connection-info-value">${ds.username}</span>
                            </div>
                            <div class="connection-info-item">
                                <span class="connection-info-label">字符集:</span>
                                <span class="connection-info-value">${ds.charset || 'utf8mb4'}</span>
                            </div>
                            <div class="connection-info-item">
                                <span class="connection-info-label">超时:</span>
                                <span class="connection-info-value">${ds.timeout || 10}秒</span>
                            </div>
                            <div class="connection-info-item">
                                <span class="connection-info-label">映射表数:</span>
                                <span class="connection-info-value">${mappedTables} 个表</span>
                            </div>
                            <div class="connection-info-item">
                                <span class="connection-info-label">创建时间:</span>
                                <span class="connection-info-value">${createdAt}</span>
                            </div>
                            <div class="connection-info-item">
                                <span class="connection-info-label">更新时间:</span>
                                <span class="connection-info-value">${updatedAt}</span>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        elements.dataSourceList.innerHTML = html;
    }
    // 添加显示创建表模态框函数
function showCreateTableModal(dataSourceId) {
    const dataSource = dataSources.find(ds => ds.id === dataSourceId);
    if (!dataSource) {
        showNotification('数据源不存在', 'error');
        return;
    }

    const dbName = dataSource.database_name || dataSource.database || '';
    if (!dbName) {
        showNotification('数据源没有配置数据库名称', 'error');
        return;
    }

    creatingDataSourceId = dataSourceId;
    creatingDatabase = dbName;

    // 清空表单
    document.getElementById('new-table-name').value = '';
    document.getElementById('create-table-result').style.display = 'none';
    document.getElementById('create-table-result').className = 'alert';

    // 加载现有表列表
    loadExistingTables(dataSourceId, dbName);

    // 更新预览
    updateTableStructurePreview('');

    // 显示模态框
    document.getElementById('create-table-modal').classList.add('active');
}

// 加载现有表列表
async function loadExistingTables(dataSourceId, database) {
    try {
        const tablesList = document.getElementById('existing-tables-list');
        tablesList.innerHTML = '<div class="loading">加载表列表中...</div>';

        // 调用API获取表列表
        const response = await fetch(API.TABLES(dataSourceId, database));
        if (!response.ok) {
            throw new Error('加载表列表失败');
        }

        const tables = await response.json();

        if (!tables || tables.length === 0) {
            tablesList.innerHTML = '<div class="empty-state">数据库中没有表</div>';
            return;
        }

        // 渲染表列表
        const html = tables.map(table => {
            return `
                <div class="table-item">
                    <i class="fas fa-table"></i>
                    <span class="table-name">${table}</span>
                    <span class="table-type">${getTableDescription(table)}</span>
                </div>
            `;
        }).join('');

        tablesList.innerHTML = html;

    } catch (error) {
        console.error('❌ 加载表列表失败:', error);
        document.getElementById('existing-tables-list').innerHTML =
            `<div class="alert alert-error">加载表列表失败: ${error.message}</div>`;
    }
}

// 更新表结构预览
function updateTableStructurePreview(tableName) {
    const previewCode = document.querySelector('.table-structure-preview code');
    if (previewCode) {
        const safeTableName = tableName || '新表名';
        previewCode.textContent = `CREATE TABLE \`${safeTableName}\` (
  \`UpdateDateTime\` datetime DEFAULT NULL,
  \`PointValue\` float DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci`;
    }
}

// 创建表函数
async function createTable() {
      const tableName = document.getElementById('new-table-name').value.trim();
    const resultDiv = document.getElementById('create-table-result');

    // 验证表名
    if (!tableName) {
        showErrorInModal('请输入表名', resultDiv);
        return;
    }

    // 改进的表名验证规则（更宽松，兼容MySQL规则）
    const tableNameRegex = /^[a-zA-Z_][a-zA-Z0-9_$#@\-]*$/;
    if (!tableNameRegex.test(tableName)) {
        showErrorInModal('表名规则：<br>' +
            '1. 必须以字母或下划线开头<br>' +
            '2. 只能包含字母、数字、下划线(_)、短横线(-)、美元符号($)、井号(#)、at符号(@)<br>' +
            '3. 不能包含空格和其他特殊字符', resultDiv);
        return;
    }

    // 检查是否MySQL保留关键字（可选）
    const reservedKeywords = [
        'select', 'insert', 'update', 'delete', 'create', 'drop', 'table',
        'database', 'alter', 'index', 'view', 'procedure', 'function',
        'trigger', 'event', 'temporary', 'if', 'exists', 'like', 'where',
        'and', 'or', 'not', 'null', 'default', 'auto_increment', 'primary',
        'key', 'unique', 'index', 'foreign', 'references', 'constraint'
    ];

    const lowerTableName = tableName.toLowerCase();
    if (reservedKeywords.some(keyword => lowerTableName === keyword)) {
        showErrorInModal(`表名 "${tableName}" 是MySQL保留关键字，请使用其他名称`, resultDiv);
        return;
    }

    if (tableName.length > 64) {
        showErrorInModal('表名不能超过64个字符', resultDiv);
        return;
    }

    // 检查表名是否太短或太长
    if (tableName.length < 2) {
        showErrorInModal('表名至少需要2个字符', resultDiv);
        return;
    }

    // 不允许纯数字表名
    if (/^\d+$/.test(tableName)) {
        showErrorInModal('表名不能是纯数字', resultDiv);
        return;
    }

    // 检查连续的短横线或下划线
    if (/[-_]{2,}/.test(tableName)) {
        showErrorInModal('表名不能包含连续的短横线或下划线', resultDiv);
        return;
    }

    // 检查开头或结尾的特殊字符
    if (/^[-_$#@]|[-_]$/.test(tableName)) {
        showErrorInModal('表名不能以特殊字符开头或结尾（除了下划线）', resultDiv);
        return;
    }

    try {
        // 显示加载状态
        const confirmBtn = document.getElementById('create-table-confirm');
        const originalHtml = confirmBtn.innerHTML;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 创建中...';
        confirmBtn.disabled = true;

        // 调用API创建表
        const response = await fetch(API.CREATE_TABLE(creatingDataSourceId, creatingDatabase), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                table_name: tableName
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: '创建表失败' }));
            throw new Error(errorData.detail || '创建表失败');
        }

        const result = await response.json();

        if (result.status === 'success') {
            resultDiv.className = 'alert alert-success';
            resultDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${result.message}`;
            resultDiv.style.display = 'block';

            // 重新加载表列表
            await loadExistingTables(creatingDataSourceId, creatingDatabase);

            // 清空输入框
            document.getElementById('new-table-name').value = '';
            updateTableStructurePreview('');

            // 显示成功通知
            showNotification(`表 "${tableName}" 创建成功`, 'success');

            // 2秒后关闭模态框
            setTimeout(() => {
                closeAllModals();
                // 如果当前正在查看这个数据源的表列表，刷新一下
                if (currentDataSourceId === creatingDataSourceId && currentDatabase === creatingDatabase) {
                    loadDatabaseTables(currentDataSourceId, currentDatabase);
                }
            }, 2000);

        } else {
            throw new Error(result.message || '创建表失败');
        }

    } catch (error) {
        console.error('❌ 创建表失败:', error);
        showErrorInModal(`创建表失败: ${error.message}`, resultDiv);
    } finally {
        // 恢复按钮状态
        const confirmBtn = document.getElementById('create-table-confirm');
        if (confirmBtn) {
            confirmBtn.innerHTML = '<i class="fas fa-plus"></i> 创建表';
            confirmBtn.disabled = false;
        }
    }
}
// 添加表名建议函数
function suggestTableName() {
    const input = document.getElementById('new-table-name');
    const dataSource = dataSources.find(ds => ds.id === creatingDataSourceId);

    if (!dataSource || !input.value) return;

    // 自动转换建议
    let suggested = input.value
        // 替换空格为下划线
        .replace(/\s+/g, '_')
        // 替换中文标点为英文
        .replace(/，/g, '_')
        .replace(/；/g, '_')
        .replace(/：/g, '_')
        .replace(/。/g, '_')
        // 移除非法字符
        .replace(/[^a-zA-Z0-9_\-$#@]/g, '')
        // 确保以字母或下划线开头
        .replace(/^[^a-zA-Z_]+/, '');

    // 如果修改后有变化，显示建议
    if (suggested !== input.value && suggested.length > 0) {
        const suggestion = `建议表名: <code>${suggested}</code>`;
        const helpDiv = document.querySelector('.form-help');
        if (helpDiv) {
            const existingSuggestion = helpDiv.querySelector('.suggestion');
            if (existingSuggestion) {
                existingSuggestion.innerHTML = suggestion;
            } else {
                const suggestionDiv = document.createElement('div');
                suggestionDiv.className = 'suggestion';
                suggestionDiv.innerHTML = suggestion;
                helpDiv.appendChild(suggestionDiv);
            }
        }
    }
}

// 在输入框添加事件监听
const tableNameInput = document.getElementById('new-table-name');
if (tableNameInput) {
    tableNameInput.addEventListener('input', function() {
        updateTableStructurePreview(this.value);
        suggestTableName();
    });
}
// 添加实时验证函数
function validateTableNameInRealTime(tableName) {
    const inputElement = document.getElementById('new-table-name');
    const statusElement = document.querySelector('.input-status');
    const confirmBtn = document.getElementById('create-table-confirm');

    if (!tableName) {
        inputElement.classList.remove('valid-table-name', 'invalid-table-name');
        statusElement.innerHTML = '';
        statusElement.className = 'input-status';
        confirmBtn.disabled = true;
        return false;
    }

    // 基本规则验证
    const tableNameRegex = /^[a-zA-Z_][a-zA-Z0-9_$#@\-]*$/;

    let isValid = true;
    let message = '';

    // 检查长度
    if (tableName.length < 2) {
        isValid = false;
        message = '太短';
    } else if (tableName.length > 64) {
        isValid = false;
        message = '太长';
    }

    // 检查格式
    else if (!tableNameRegex.test(tableName)) {
        isValid = false;
        message = '格式错误';
    }

    // 检查纯数字
    else if (/^\d+$/.test(tableName)) {
        isValid = false;
        message = '不能纯数字';
    }

    // 检查连续特殊字符
    else if (/[-_]{2,}/.test(tableName)) {
        isValid = false;
        message = '连续特殊字符';
    }

    // 检查开头结尾
    else if (/^[-_$#@]|[-_]$/.test(tableName)) {
        isValid = false;
        message = '首尾字符无效';
    }

    // 检查保留字（部分常见）
    const reservedKeywords = ['select', 'table', 'database', 'update', 'delete', 'insert'];
    if (reservedKeywords.includes(tableName.toLowerCase())) {
        isValid = false;
        message = '保留关键字';
    }

    // 更新UI状态
    if (isValid) {
        inputElement.classList.add('valid-table-name');
        inputElement.classList.remove('invalid-table-name');
        statusElement.innerHTML = '<i class="fas fa-check-circle"></i>';
        statusElement.className = 'input-status valid';
        confirmBtn.disabled = false;
    } else {
        inputElement.classList.add('invalid-table-name');
        inputElement.classList.remove('valid-table-name');
        statusElement.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        statusElement.className = 'input-status invalid';
        confirmBtn.disabled = true;
    }

    return isValid;
}

// 更新输入事件监听
if (tableNameInput) {
    tableNameInput.addEventListener('input', function() {
        updateTableStructurePreview(this.value);
        suggestTableName();
        validateTableNameInRealTime(this.value);
    });

    // 添加焦点事件
    tableNameInput.addEventListener('focus', function() {
        if (this.value) {
            validateTableNameInRealTime(this.value);
        }
    });
}
// 在模态框中显示错误
function showErrorInModal(message, resultDiv) {
    resultDiv.className = 'alert alert-error';
    resultDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    resultDiv.style.display = 'block';

    // 滚动到错误信息位置
    resultDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

    // 计算已映射的表数量
    function countMappedTables(dataSourceId, database) {
        const key = `${dataSourceId}_${database}`;
        if (tableMappings[key] && tableMappings[key].tables) {
            return Object.keys(tableMappings[key].tables).length;
        }
        return 0;
    }

    // 更新数据源选择器
    function updateDataSourceSelect() {
        if (!elements.selectDataSource) return;

        const currentValue = elements.selectDataSource.value;
        elements.selectDataSource.innerHTML = '<option value="">请选择数据源</option>' +
            dataSources.map(ds => {
                const dbName = ds.database_name || ds.database || '';
                return `
                    <option value="${ds.id}" ${ds.id == currentValue ? 'selected' : ''}>
                        ${ds.name} (${dbName})
                    </option>
                `;
            }).join('');
    }

    // 显示数据源模态框
    function showDataSourceModal() {
        editingDataSourceId = null;
        const modal = document.getElementById('data-source-modal');
        const form = document.getElementById('data-source-form');

        form.reset();
        document.getElementById('ds-host').value = 'localhost';
        document.getElementById('ds-port').value = '3306';
        document.getElementById('ds-charset').value = 'utf8mb4';
        document.getElementById('ds-timeout').value = '10';
        document.getElementById('test-result').textContent = '';
        document.getElementById('test-result').className = 'test-result';

        modal.classList.add('active');
    }

    // 关闭所有模态框
    // 修改 closeAllModals 函数，确保它能正常工作
function closeAllModals() {
    console.log('🔒 关闭所有模态框');

    // 确保移除所有模态框的 active 类
    document.querySelectorAll('.modal').forEach(modal => {
        if (modal) {
            modal.classList.remove('active');
        }
    });

    // 重置表单状态
    if (document.getElementById('data-source-form')) {
        document.getElementById('data-source-form').reset();
    }

    // 清除编辑状态
    editingDataSourceId = null;
}
    // 测试连接
    async function testConnection() {
        const testResult = document.getElementById('test-result');
        testResult.textContent = '正在测试连接...';
        testResult.className = 'test-result testing';

        try {
            // 从表单获取配置
            const host = document.getElementById('ds-host').value.trim();
            const port = document.getElementById('ds-port').value;
            const database = document.getElementById('ds-database').value.trim() || '';
            const username = document.getElementById('ds-username').value.trim();
            const password = document.getElementById('ds-password').value;
            const charset = document.getElementById('ds-charset').value;
            const timeout = document.getElementById('ds-timeout').value;

            // 验证必要字段
            if (!host) throw new Error('主机地址不能为空');
            if (!database) throw new Error('数据库名不能为空');
            if (!username) throw new Error('用户名不能为空');

            // 调用API测试连接
            const response = await fetch(API.TEST_CONNECTION, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    host,
                    port: parseInt(port),
                    database_name: database,
                    username,
                    password,
                    charset,
                    timeout: parseInt(timeout)
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: '服务器错误' }));
                let errorMessage;
                if (Array.isArray(errorData.detail)) {
                    errorMessage = errorData.detail.map(err => err.msg).join(', ');
                } else {
                    errorMessage = errorData.detail || response.statusText;
                }
                throw new Error(`连接测试失败: ${errorMessage}`);
            }

            const result = await response.json();
            if (result.status === 'success') {
                testResult.textContent = '✓ 连接成功';
                testResult.className = 'test-result success';
                showNotification('数据库连接测试成功', 'success');
            } else {
                testResult.textContent = '✗ 连接失败';
                testResult.className = 'test-result error';
                showNotification('连接测试失败: ' + result.message, 'error');
            }
        } catch (error) {
            console.error('❌ 测试连接失败:', error);
            testResult.textContent = '✗ 连接失败';
            testResult.className = 'test-result error';
            showNotification('测试连接失败: ' + error.message, 'error');
        }
    }

    // 保存数据源
    async function saveDataSource() {
        try {
            const form = document.getElementById('data-source-form');
            if (!form.checkValidity()) {
                form.reportValidity();
                return;
            }

            const dsData = {
                name: document.getElementById('ds-name').value.trim(),
                host: document.getElementById('ds-host').value.trim(),
                port: parseInt(document.getElementById('ds-port').value),
                database_name: document.getElementById('ds-database').value.trim() || '',
                username: document.getElementById('ds-username').value.trim(),
                password: document.getElementById('ds-password').value || "",
                charset: document.getElementById('ds-charset').value,
                timeout: parseInt(document.getElementById('ds-timeout').value),
                is_active: document.getElementById('ds-is-active') ? document.getElementById('ds-is-active').checked : true,
            };

            // 验证 port 和 timeout
            if (isNaN(dsData.port) || dsData.port <= 0) {
                throw new Error('端口必须是正整数（例如：3306）');
            }
            if (isNaN(dsData.timeout) || dsData.timeout < 0) {
                throw new Error('超时必须是非负整数（例如：30）');
            }

            let response;
            if (editingDataSourceId) {
                response = await fetch(API.DATA_SOURCE(editingDataSourceId), {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dsData)
                });
            } else {
                response = await fetch(API.DATA_SOURCES, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(dsData)
                });
            }

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`数据源保存失败: ${errorText}`);
            }

            const savedDataSource = await response.json();

            // 更新前端数据
            if (editingDataSourceId) {
                const index = dataSources.findIndex(ds => ds.id === editingDataSourceId);
                if (index !== -1) {
                    dataSources[index] = savedDataSource;
                }
            } else {
                dataSources.push(savedDataSource);
            }

            showNotification('数据源保存成功', 'success');
            closeAllModals();
            loadDataSources();

        } catch (error) {
            console.error('❌ 保存数据源失败:', error);
            showNotification('保存失败: ' + error.message, 'error');
        }
    }

    // 数据源选择变化
    async function handleDataSourceChange() {
        const dsId = parseInt(elements.selectDataSource.value);
        if (!dsId) {
            elements.selectDatabase.disabled = true;
            elements.selectDatabase.innerHTML = '<option value="">请先选择数据源</option>';
            elements.selectProject.disabled = true;
            elements.selectProject.innerHTML = '<option value="">请先选择数据源</option>';
            elements.selectDevice.disabled = true;
            elements.selectDevice.innerHTML = '<option value="">请先选择项目</option>';
            elements.refreshTablesBtn.disabled = true;
            elements.saveMappingBtn.disabled = true;
            showTableMappingMessage('请先选择数据源');
            return;
        }

        currentDataSourceId = dsId;
        const dataSource = dataSources.find(ds => ds.id === dsId);
        if (!dataSource) return;

        // 直接设置数据库选择器
        elements.selectDatabase.disabled = false;
        const dbName = dataSource.database_name || dataSource.database || '';
        elements.selectDatabase.innerHTML = `<option value="${dbName}" selected>${dbName}</option>`;
        elements.refreshTablesBtn.disabled = false;

        // 清除项目和设备选择
        elements.selectProject.disabled = false;
        elements.selectProject.innerHTML = '<option value="">请选择项目</option>';
        elements.selectDevice.disabled = true;
        elements.selectDevice.innerHTML = '<option value="">请先选择项目</option>';

        // 触发数据库选择变化
        await handleDatabaseChange();
    }

    // 数据库选择变化
    async function handleDatabaseChange() {
        const database = elements.selectDatabase.value;
        if (!database || !currentDataSourceId) {
            elements.refreshTablesBtn.disabled = true;
            elements.saveMappingBtn.disabled = true;
            showTableMappingMessage('请先选择数据库');
            return;
        }

        currentDatabase = database;

        // 加载项目列表
        await loadProjects();

        // 加载表列表
        await loadDatabaseTables(currentDataSourceId, database);
    }

    // 加载项目列表
    async function loadProjects() {
        try {
            showLoading(elements.selectProject, '加载项目中...');

            // 调用后端API获取项目列表
            const response = await fetch(API.MAPPING_PROJECT(currentDataSourceId, currentDatabase));
            if (!response.ok) throw new Error('项目列表加载失败');

            projects = await response.json();

            // 渲染项目选择器
            renderProjectSelect();
            elements.selectProject.disabled = false;

        } catch (error) {
            console.error('❌ 加载项目列表失败:', error);
            elements.selectProject.innerHTML = '<option value="">加载失败，请重试</option>';
            showNotification('加载项目列表失败: ' + error.message, 'error');
        }
    }

    // 渲染项目选择器
    function renderProjectSelect() {
        if (!elements.selectProject) return;

        const currentValue = elements.selectProject.value;
        elements.selectProject.innerHTML = '<option value="">请选择项目</option>' +
            projects.map(project => {
                return `
                    <option value="${project.id}" ${project.id == currentValue ? 'selected' : ''}>
                        ${project.name} (${project.code})
                    </option>
                `;
            }).join('');
    }

// 项目选择变化
async function handleProjectChange() {
    const projectId = parseInt(elements.selectProject.value);
    if (!projectId) {
        elements.selectDevice.disabled = true;
        elements.selectDevice.innerHTML = '<option value="">请先选择项目</option>';
        currentProjectId = null;
        currentDeviceId = null;
        deviceFeatures = [];
        return;
    }

    currentProjectId = projectId;

    // 清除当前选择的设备
    currentDeviceId = null;
    deviceFeatures = [];

    // 显示选择的项目信息
    const selectedProject = projects.find(p => p.id === projectId);
    if (selectedProject) {
        console.log(`📋 选择的项目: ${selectedProject.name} (${selectedProject.device_count} 个设备)`);
    }

    // 加载设备
    await loadDevices(projectId);
}
    // 加载设备列表
   async function loadDevices(projectId) {
    try {
        console.log(`🔄 加载项目 ${projectId} 的设备列表...`);

        showLoading(elements.selectDevice, '加载设备中...');

        // 调用后端API获取设备列表
        const response = await fetch(API.MAPPING_DEVICE(projectId));

        if (!response.ok) {
            const errorText = await response.text();
            console.error(`❌ 设备列表加载失败: ${response.status} ${response.statusText}`, errorText);
            throw new Error(`设备列表加载失败: ${response.status} ${response.statusText}`);
        }

        devices = await response.json();
        console.log(`✅ 加载了 ${devices.length} 个设备`, devices);

        // 渲染设备选择器
        renderDeviceSelect();
        elements.selectDevice.disabled = false;

        // 如果只有一个设备，自动选择它
        if (devices.length === 1) {
            elements.selectDevice.value = devices[0].id;
            await handleDeviceChange();
        }

        showNotification(`加载了 ${devices.length} 个设备`, 'success');

    } catch (error) {
        console.error('❌ 加载设备列表失败:', error);
        devices = [];
        renderDeviceSelect();
        elements.selectDevice.innerHTML = '<option value="">加载失败，请重试</option>';
        showNotification('加载设备列表失败: ' + error.message, 'error');
    }
}

    // 渲染设备选择器
// 修改 renderDeviceSelect 函数，添加模型状态提示
function renderDeviceSelect() {
    if (!elements.selectDevice) return;

    const currentValue = elements.selectDevice.value;
    elements.selectDevice.disabled = false;
    elements.selectDevice.innerHTML = '<option value="">请选择设备</option>' +
        devices.map(device => {
            const modelInfo = device.model_name ? ` (${device.model_name} v${device.model_version?.version || '?'})` : '';
            const modelStatus = checkDeviceModelStatus(device);
            const statusClass = modelStatus === '正常' ? 'model-ok' : 'model-warning';

            return `
                <option value="${device.id}" ${device.id == currentValue ? 'selected' : ''}
                        data-status="${modelStatus}"
                        class="${statusClass}">
                    ${device.name}${modelInfo} ${modelStatus !== '正常' ? `[${modelStatus}]` : ''}
                </option>
            `;
        }).join('');

    // 添加CSS样式
    if (!document.querySelector('#device-select-styles')) {
        const style = document.createElement('style');
        style.id = 'device-select-styles';
        style.textContent = `
            option.model-warning {
                color: #dc3545;
                font-style: italic;
            }
            option.model-ok {
                color: #28a745;
            }
        `;
        document.head.appendChild(style);
    }
}
// 设备选择变化
// 修改 handleDeviceChange 函数
async function handleDeviceChange() {
    const deviceId = parseInt(elements.selectDevice.value);
    if (!deviceId) {
        currentDeviceId = null;
        deviceFeatures = [];
        return;
    }

    currentDeviceId = deviceId;

    // 并行加载设备特征和设备映射
    await Promise.all([
        loadDeviceFeatures(deviceId),
        loadDeviceFeatureMappings(deviceId)
    ]);

    // 重新加载表映射界面
    if (currentDataSourceId && currentDatabase) {
        loadDatabaseTables(currentDataSourceId, currentDatabase);
    }
}
    // 加载设备特征
    // 修改 loadDeviceFeatures 函数
async function loadDeviceFeatures(deviceId) {
    try {
        console.log(`🔍 开始加载设备 ${deviceId} 的特征...`);

        // 调用后端API获取设备特征
        const response = await fetch(API.MAPPING_DEVICE_FEATURES(deviceId));
        if (!response.ok) {
            const errorText = await response.text();
            console.error(`❌ API响应失败: ${response.status} ${response.statusText}`, errorText);
            throw new Error(`设备特征加载失败: ${response.status} ${response.statusText}`);
        }

        deviceFeatures = await response.json();
        console.log(`✅ 加载了设备 ${deviceId} 的 ${deviceFeatures.length} 个特征`, deviceFeatures);

        // 记录设备信息以便调试
        const currentDevice = devices.find(d => d.id === deviceId);
        if (currentDevice) {
            console.log(`📊 设备调试信息:`, {
                deviceId: currentDevice.id,
                deviceName: currentDevice.name,
                modelVersionId: currentDevice.model_version_id,
                hasModel: !!currentDevice.model_version_id,
                featuresCount: deviceFeatures.length
            });

            // 如果设备没有模型版本或特征，显示提醒
            if (!currentDevice.model_version_id) {
                showNotification(`设备 "${currentDevice.name}" 未绑定设备模型，请先绑定模型`, 'warning');
            } else if (deviceFeatures.length === 0) {
                showNotification(`设备 "${currentDevice.name}" 的模型版本没有配置特征，请先在设备模型中配置特征`, 'warning');
            }
        }

    } catch (error) {
        console.error('❌ 加载设备特征失败:', error);
        deviceFeatures = [];
        showNotification('加载设备特征失败: ' + error.message, 'error');
    }
}

    // 加载数据库表
// 在 loadDatabaseTables 函数中，修改数据处理部分
// 在 loadDatabaseTables 函数中添加调试信息
// 修改 loadDatabaseTables 函数
async function loadDatabaseTables(dataSourceId, database) {
    showLoading(elements.tableFeatureMapping, '正在加载特征表列表...');
    elements.refreshTablesBtn.disabled = true;

    try {
        console.log(`🔍 调用API: ${API.MYSQL_FEATURE_TABLES(dataSourceId, database)}`);

        // 同时加载表列表和设备映射
        const [tablesResponse, mappingsResponse] = await Promise.all([
            fetch(API.MYSQL_FEATURE_TABLES(dataSourceId, database)),
            currentDeviceId ? fetch(API.FEATURE_MAPPINGS(currentDeviceId)) : Promise.resolve(null)
        ]);

        if (!tablesResponse.ok) {
            const errorText = await tablesResponse.text();
            console.error('API错误响应:', errorText);
            throw new Error(errorText || '表列表加载失败');
        }

        const data = await tablesResponse.json();
        console.log('API返回数据:', data);

        // 验证数据结构
        if (!data) {
            throw new Error('API返回空数据');
        }

        // 安全地获取tables数组
        let tables = [];
        if (data && data.tables && Array.isArray(data.tables)) {
            tables = data.tables;
            console.log(`✅ 从data.tables获取到 ${tables.length} 个表`);
        } else if (Array.isArray(data)) {
            tables = data;
            console.log(`✅ 从data数组获取到 ${tables.length} 个表`);
        } else {
            console.warn('数据格式不符合预期:', data);
            tables = [];
        }

        // 获取设备映射数据
        let deviceMappings = [];
        if (mappingsResponse && mappingsResponse.ok) {
            deviceMappings = await mappingsResponse.json();
            console.log('✅ 获取设备映射数据:', deviceMappings);
        }

        // 过滤掉无效的表数据
        const validTables = tables.filter(table => {
            if (table == null) {
                console.warn('过滤掉 null 表数据');
                return false;
            }

            // 检查是否有有效的表名
            if (typeof table === 'string') {
                const result = table.trim().length > 0;
                if (!result) console.warn('过滤掉空字符串表名:', table);
                return result;
            }

            if (typeof table === 'object') {
                const name = table.table_name || table.name || table;
                const result = String(name).trim().length > 0;
                if (!result) console.warn('过滤掉无有效表名的对象:', table);
                return result;
            }

            console.warn('过滤掉非预期类型表数据:', typeof table, table);
            return false;
        });

        console.log(`📊 有效表数量: ${validTables.length}`);
        console.log('有效表列表:', validTables);

        if (validTables.length === 0) {
            elements.tableFeatureMapping.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle"></i>
                    该数据库中没有找到有效的特征表。请确认数据库名称是否正确。
                </div>
            `;
            return;
        }

        // 传递有效的表格数据和设备映射给渲染函数
        renderTableFeatureMapping(validTables, dataSourceId, database, deviceMappings);

        elements.refreshTablesBtn.disabled = false;
        elements.saveMappingBtn.disabled = false;

    } catch (error) {
        console.error('❌ 加载表列表失败:', error);
        console.error('错误堆栈:', error.stack);
        showError(elements.tableFeatureMapping, '加载表列表失败: ' + error.message);
    }
}

// 修改 renderTableFeatureMapping 函数
function renderTableFeatureMapping(tables, dataSourceId, database, deviceMappings = []) {
    console.log('🔍 开始渲染表映射界面');
    console.log('传入的表数据:', tables);
    console.log('设备ID:', currentDeviceId);
    console.log('设备特征数量:', deviceFeatures.length);
    console.log('设备映射数据:', deviceMappings);

    // 检查是否选择了设备和项目
    if (!currentDeviceId) {
        showTableMappingMessage('请先选择项目和设备');
        return;
    }

    // 获取当前设备信息
    const currentDevice = devices.find(d => d.id === currentDeviceId);
    if (!currentDevice) {
        showTableMappingMessage('设备信息加载失败，请重新选择设备');
        return;
    }

    // 检查设备是否有模型版本
    if (!currentDevice.model_version_id) {
        showTableMappingMessage(`
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle"></i>
                <strong>设备未绑定模型：</strong>
                设备 "${currentDevice.name}" 没有绑定设备模型，无法获取特征。<br>
                请先在设备管理页面为设备绑定模型版本。
            </div>
        `);
        return;
    }

    // 获取设备特征
    if (deviceFeatures.length === 0) {
        showTableMappingMessage(`
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-triangle"></i>
                <strong>设备特征为空：</strong>
                设备 "${currentDevice.name}" 的模型版本没有配置特征。<br>
                请先在设备模型管理中为模型版本配置特征。
            </div>
        `);
        return;
    }

    // 将设备映射转换为便于查找的格式
    const deviceMappingsMap = {};
    if (deviceMappings && Array.isArray(deviceMappings)) {
        deviceMappings.forEach(mapping => {
            if (mapping && mapping.feature && mapping.feature.id) {
                deviceMappingsMap[mapping.feature.id] = {
                    table_name: mapping.table_name,
                    is_active: mapping.is_active !== false,
                    column_name: mapping.column_name || 'PointValue',
                    timestamp_column: mapping.timestamp_column || 'UpdateDateTime'
                };
            }
        });
    }

    let html = `
        <div class="feature-mapping-header">
            <div>设备特征</div>
            <div>映射特征表</div>
            <div>是否启用</div>
        </div>
    `;

    // 按类别分组特征
    const groupedFeatures = groupFeaturesByCategory(deviceFeatures);

    // 遍历所有类别
    Object.keys(groupedFeatures).forEach(category => {
        const categoryFeatures = groupedFeatures[category];

        // 添加类别标题
        html += `
            <div class="category-header">
                <h4>${category}</h4>
                <span class="category-count">${categoryFeatures.length} 个特征</span>
            </div>
        `;

        // 遍历该类别下的所有特征
        categoryFeatures.forEach(feature => {
            try {
                // 从设备映射中获取已保存的映射
                const savedMapping = deviceMappingsMap[feature.id] || {};
                const savedTable = savedMapping.table_name || null;
                const isEnabled = savedMapping.is_active !== false; // 默认为 true

                // 显示特征详细信息
                const featureInfo = `
                    <div class="feature-info">
                        <div class="feature-name">${feature.name}</div>
                        <div class="feature-details">
                            <span class="feature-code">${feature.code}</span>
                            ${feature.unit ? `<span class="feature-unit">${feature.unit}</span>` : ''}
                            ${feature.is_required ? '<span class="feature-required">必填</span>' : ''}
                            ${savedTable ? `
                                <span class="mapping-status" style="margin-left: 10px; color: #28a745;">
                                    <i class="fas fa-check-circle"></i> 已映射: ${savedTable}
                                </span>
                            ` : ''}
                        </div>
                    </div>
                `;

                // 生成表选项
                let tableOptions = '<option value="">-- 请选择特征表 --</option>';
                tables.forEach(tableObj => {
                    let tableName = '';
                    if (typeof tableObj === 'string') {
                        tableName = tableObj.trim();
                    } else if (typeof tableObj === 'object' && tableObj !== null) {
                        tableName = (tableObj.table_name || tableObj.name || '').toString().trim();
                    }
                    if (tableName) {
                        // 判断选中状态：优先使用设备级映射，否则使用特征的默认表名
                        let selected = false;
                        if (savedTable) {
                            selected = savedTable === tableName;
                        } else if (feature.table_name) {
                            selected = feature.table_name === tableName;
                        }
                        const selectedAttr = selected ? 'selected' : '';
                        tableOptions += `<option value="${tableName}" ${selectedAttr}>${tableName}</option>`;
                    }
                });

                html += `
                    <div class="feature-mapping-row" data-feature-id="${feature.id}">
                        <div class="feature-column">
                            ${featureInfo}
                        </div>
                        <div class="table-column">
                            <select class="table-select" data-feature-id="${feature.id}">
                                ${tableOptions}
                            </select>
                        </div>
                        <div class="enable-column">
                            <label class="switch">
                                <input type="checkbox" ${isEnabled ? 'checked' : ''} data-feature-id="${feature.id}">
                                <span class="slider"></span>
                            </label>
                            <span class="enable-text">${isEnabled ? '启用' : '禁用'}</span>
                        </div>
                    </div>
                `;
            } catch (featureError) {
                console.error('处理特征时出错:', featureError, feature);
            }
        });
    });

    // 添加说明和提示
    html += `
        <div class="mapping-info-section">
            <div class="alert alert-info">
                <i class="fas fa-lightbulb"></i>
                <strong>映射规则说明：</strong>
                <ul>
                    <li>每个设备特征只能映射到一个特征表</li>
                    <li>一个特征表可以被多个设备的不同特征映射</li>
                    <li>特征表包含两个字段：UpdateDateTime (时间戳) 和 PointValue (特征值)</li>
                    <li>启用状态控制该特征表是否参与数据同步和预测</li>
                </ul>
            </div>

            <div class="mapping-stats">
                <div class="stat-card">
                    <div class="stat-title">设备信息</div>
                    <div class="stat-content">
                        <p><strong>设备名称：</strong>${currentDevice.name}</p>
                        <p><strong>设备标识：</strong>${currentDevice.identifier}</p>
                        <p><strong>模型版本：</strong>${currentDevice.model_version?.version || '未绑定模型'}</p>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-title">特征统计</div>
                    <div class="stat-content">
                        <p><strong>总特征数：</strong>${deviceFeatures.length}</p>
                        <p><strong>已映射：</strong><span id="mapped-count">${Object.keys(deviceMappingsMap).length}</span></p>
                        <p><strong>待映射：</strong><span id="unmapped-count">${deviceFeatures.length - Object.keys(deviceMappingsMap).length}</span></p>
                    </div>
                </div>

                <div class="stat-card">
                    <div class="stat-title">验证状态</div>
                    <div class="stat-content">
                        <p><strong>必填特征：</strong>${deviceFeatures.filter(f => f.is_required).length}</p>
                        <p><strong>已映射必填：</strong><span id="mapped-required-count">0</span></p>
                        <p><strong>状态：</strong><span id="validation-status">未验证</span></p>
                    </div>
                </div>
            </div>
        </div>
    `;

    elements.tableFeatureMapping.innerHTML = html;

    // 初始化映射统计
    updateMappingStats();

    // 绑定表选择变化事件
    bindTableSelectEvents();

    // 绑定启用开关变化事件
    bindEnableSwitchEvents();
}// 按类别分组特征
function groupFeaturesByCategory(features) {
    return features.reduce((groups, feature) => {
        const category = feature.category || '其他参数';
        if (!groups[category]) {
            groups[category] = [];
        }
        groups[category].push(feature);
        return groups;
    }, {});
}

// 获取类别CSS类
function getCategoryClass(category) {
    const categoryMap = {
        '电气参数': 'category-electric',
        '环境参数': 'category-env',
        '机械参数': 'category-mechanical',
        '流体参数': 'category-fluid',
        '其他参数': 'category-other'
    };
    return categoryMap[category] || 'category-other';
}

// 获取数据类型CSS类
function getDataTypeClass(dataType) {
    const dataTypeMap = {
        'number': 'type-number',
        'string': 'type-string',
        'boolean': 'type-boolean',
        'array': 'type-array'
    };
    return dataTypeMap[dataType] || 'type-other';
}

// 绑定表选择事件
function bindTableSelectEvents() {
    const tableSelects = elements.tableFeatureMapping.querySelectorAll('.table-select');
    tableSelects.forEach(select => {
        select.addEventListener('change', function() {
            updateMappingStats();
            validateMappingRules();
        });
    });
}
// 绑定启用开关事件
function bindEnableSwitchEvents() {
    const switches = elements.tableFeatureMapping.querySelectorAll('.switch input[type="checkbox"]');
    switches.forEach(switchEl => {
        switchEl.addEventListener('change', function() {
            const featureId = this.dataset.featureId;
            const enableText = this.closest('.enable-column').querySelector('.enable-text');
            enableText.textContent = this.checked ? '启用' : '禁用';
            updateMappingStats();
        });
    });
}
// 更新映射统计
function updateMappingStats() {
    const tableSelects = elements.tableFeatureMapping.querySelectorAll('.table-select');
    const switches = elements.tableFeatureMapping.querySelectorAll('.switch input[type="checkbox"]');

    let mappedCount = 0;
    let enabledCount = 0;
    const usedTables = new Set();
    const featureTableMap = new Map();

    tableSelects.forEach(select => {
        if (select.value) {
            mappedCount++;
            usedTables.add(select.value);

            const featureId = select.dataset.featureId;
            featureTableMap.set(featureId, select.value);
        }
    });

    switches.forEach(switchEl => {
        if (switchEl.checked) {
            enabledCount++;
        }
    });

    // 计算必填特征映射情况
    const requiredFeatures = deviceFeatures.filter(f => f.is_required);
    let mappedRequiredCount = 0;
    requiredFeatures.forEach(feature => {
        if (featureTableMap.has(feature.id.toString())) {
            mappedRequiredCount++;
        }
    });

    // 检查表被多个特征使用的情况
    const tableUsage = {};
    featureTableMap.forEach((table, featureId) => {
        if (!tableUsage[table]) {
            tableUsage[table] = [];
        }
        tableUsage[table].push(featureId);
    });

    // 验证映射规则
    const validationResult = validateMappingRules();

    // 更新统计显示
    const mappedCountElement = document.getElementById('mapped-count');
    const unmappedCountElement = document.getElementById('unmapped-count');
    const mappedRequiredCountElement = document.getElementById('mapped-required-count');
    const validationElement = document.getElementById('validation-status');

    if (mappedCountElement) {
        mappedCountElement.textContent = mappedCount;
        mappedCountElement.className = mappedCount > 0 ? 'text-success' : 'text-muted';
    }

    if (unmappedCountElement) {
        const unmapped = deviceFeatures.length - mappedCount;
        unmappedCountElement.textContent = unmapped;
        unmappedCountElement.className = unmapped > 0 ? 'text-warning' : 'text-success';
    }

    if (mappedRequiredCountElement) {
        mappedRequiredCountElement.textContent = mappedRequiredCount;
        mappedRequiredCountElement.className =
            mappedRequiredCount === requiredFeatures.length ? 'text-success' : 'text-danger';
    }

    if (validationElement) {
        if (validationResult.errors.length > 0) {
            validationElement.textContent = '有错误';
            validationElement.className = 'text-danger';
        } else if (validationResult.warnings.length > 0) {
            validationElement.textContent = '有警告';
            validationElement.className = 'text-warning';
        } else {
            validationElement.textContent = '有效';
            validationElement.className = 'text-success';
        }
    }

    // 更新保存按钮状态
    elements.saveMappingBtn.disabled = !validationResult.valid;
}


// 验证映射规则
function validateMappingRules() {
    const tableSelects = elements.tableFeatureMapping.querySelectorAll('.table-select');
    const featureTableMap = new Map();
    const errors = [];
    const warnings = [];

    // 收集映射关系
    tableSelects.forEach(select => {
        if (select.value) {
            const featureId = select.dataset.featureId;
            const tableName = select.value;
            featureTableMap.set(featureId, tableName);
        }
    });

    // 验证规则1：检查必填特征是否已配置
    deviceFeatures.forEach(feature => {
        if (feature.is_required && !featureTableMap.has(feature.id.toString())) {
            errors.push(`必填特征"${feature.name}"未配置特征表`);
        }
    });

    // 验证规则2：检查特征表被多个特征使用的情况（这是允许的，但给出提示）
    const tableFeatureMap = {};
    featureTableMap.forEach((tableName, featureId) => {
        if (!tableFeatureMap[tableName]) {
            tableFeatureMap[tableName] = [];
        }
        tableFeatureMap[tableName].push(featureId);
    });

    Object.keys(tableFeatureMap).forEach(tableName => {
        const featureIds = tableFeatureMap[tableName];
        if (featureIds.length > 1) {
            const featureNames = featureIds.map(fid => {
                const feature = deviceFeatures.find(f => f.id.toString() === fid);
                return feature ? feature.name : '未知特征';
            });
            warnings.push(`特征表"${tableName}"被多个特征使用: ${featureNames.join(', ')}`);
        }
    });

    return {
        valid: errors.length === 0,
        errors: errors,
        warnings: warnings,
        featureTableMap: featureTableMap,
        tableFeatureMap: tableFeatureMap
    };
}

// 修改保存映射配置函数
async function saveMappingConfig() {
    try {
        console.log('🔍 开始保存映射配置...');

        if (!currentDataSourceId || !currentDatabase) {
            showNotification('请先选择数据源和数据库', 'warning');
            return;
        }

        if (!currentDeviceId) {
            showNotification('请先选择设备', 'warning');
            return;
        }

        const rows = elements.tableFeatureMapping.querySelectorAll('.feature-mapping-row');
        const mappings = [];

        // 收集特征映射
        rows.forEach(row => {
            const featureId = row.dataset.featureId;
            const select = row.querySelector('.table-select');
            const switchEl = row.querySelector('.switch input[type="checkbox"]');

            if (select && select.value) {
                const tableName = select.value;
                const isEnabled = switchEl ? switchEl.checked : true;

                // 查找特征信息
                const feature = deviceFeatures.find(f => f.id === parseInt(featureId));
                if (!feature) {
                    console.warn(`未找到特征ID ${featureId} 的信息`);
                    return;
                }

                mappings.push({
                    data_source_id: currentDataSourceId,
                    database_name: currentDatabase,
                    device_id: currentDeviceId,
                    feature_id: parseInt(featureId),
                    table_name: tableName,
                    column_name: 'PointValue',  // 默认列名
                    timestamp_column: 'UpdateDateTime',  // 默认时间戳列名
                    is_active: isEnabled,
                    sync_frequency: 15  // 默认15分钟同步一次
                });
            }
        });

        if (mappings.length === 0) {
            showNotification('请至少为一个特征选择特征表', 'warning');
            return;
        }

        console.log('📤 准备发送映射数据:', mappings);

        // 修改：使用单个保存接口而不是批量接口
        const savePromises = mappings.map(async (mapping) => {
            try {
                const response = await fetch(API.FEATURE_MAPPINGS_SAVE, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(mapping)
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({ detail: '服务器错误' }));
                    throw new Error(errorData.detail || '保存失败');
                }

                return await response.json();
            } catch (error) {
                console.error(`❌ 保存特征 ${mapping.feature_id} 失败:`, error);
                throw error;
            }
        });

        // 显示保存中的提示
        showNotification('正在保存映射配置...', 'info');
        elements.saveMappingBtn.disabled = true;
        elements.saveMappingBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 保存中...';

        // 并行保存所有映射
        const results = await Promise.allSettled(savePromises);

        const successCount = results.filter(r => r.status === 'fulfilled').length;
        const failedCount = results.filter(r => r.status === 'rejected').length;

        if (successCount > 0) {
            showNotification(`成功保存 ${successCount} 个特征映射`, 'success');

            // 更新本地存储
            const mappingKey = `${currentDataSourceId}_${currentDatabase}_${currentDeviceId}`;
            if (!tableMappings[mappingKey]) {
                tableMappings[mappingKey] = { features: {} };
            }

            mappings.forEach(mapping => {
                tableMappings[mappingKey].features[mapping.feature_id] = {
                    table_name: mapping.table_name,
                    enabled: mapping.is_active,
                    timestamp: new Date().toISOString()
                };
            });

            localStorage.setItem('feature_table_mappings', JSON.stringify(tableMappings));

            // 重新加载设备映射以显示最新状态
            await loadDeviceFeatureMappings(currentDeviceId);
        }

        if (failedCount > 0) {
            showNotification(`有 ${failedCount} 个特征映射保存失败`, 'error');
        }

    } catch (error) {
        console.error('❌ 保存映射配置失败:', error);
        showNotification('保存失败: ' + error.message, 'error');
    } finally {
        // 恢复按钮状态
        elements.saveMappingBtn.disabled = false;
        elements.saveMappingBtn.innerHTML = '<i class="fas fa-save"></i> 保存映射配置';
    }
}
// 新增：加载设备的特征映射
// 修改 loadDeviceFeatureMappings 函数
async function loadDeviceFeatureMappings(deviceId) {
    try {
        const response = await fetch(API.FEATURE_MAPPINGS(deviceId));
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: '服务器错误' }));
            throw new Error(errorData.detail || '加载映射失败');
        }

        const mappings = await response.json();
        console.log('✅ 加载的设备特征映射:', mappings);

        // 将映射数据存储到全局变量，供后续使用
        window.currentDeviceMappings = mappings;

        return mappings;

    } catch (error) {
        console.error('❌ 加载特征映射失败:', error);
        return [];
    }
}

// 新增：在界面上更新映射状态
// 修改 updateMappingsOnUI 函数
function updateMappingsOnUI(mappings) {
    // 清空之前的映射状态
    document.querySelectorAll('.mapping-status').forEach(el => el.remove());

    if (!mappings || !Array.isArray(mappings)) {
        console.warn('无效的映射数据:', mappings);
        return;
    }

    mappings.forEach(mapping => {
        if (!mapping || !mapping.feature || !mapping.feature.id) {
            console.warn('跳过无效的映射:', mapping);
            return;
        }

        const row = document.querySelector(`[data-feature-id="${mapping.feature.id}"]`);
        if (row) {
            try {
                // 添加映射状态标签
                const statusDiv = document.createElement('div');
                statusDiv.className = 'mapping-status';
                statusDiv.innerHTML = `
                    <span class="badge badge-success" style="margin-left: 10px;">
                        <i class="fas fa-check-circle"></i> 已映射: ${mapping.table_name || '未知表'}
                    </span>
                `;
                row.querySelector('.feature-column').appendChild(statusDiv);

                // 更新选择器和开关状态
                const select = row.querySelector('.table-select');
                const switchEl = row.querySelector('.switch input[type="checkbox"]');

                if (select && mapping.table_name) {
                    select.value = mapping.table_name;
                }
                if (switchEl) {
                    switchEl.checked = mapping.is_active !== false; // 默认为 true
                    const enableText = row.querySelector('.enable-text');
                    if (enableText) {
                        enableText.textContent = switchEl.checked ? '启用' : '禁用';
                    }
                }
            } catch (error) {
                console.error('更新映射状态时出错:', error);
            }
        }
    });

    // 更新统计
    updateMappingStats();
}
// 辅助函数：获取项目名称
function getProjectName(projectId) {
    const project = projects.find(p => p.id === projectId);
    return project ? project.name : '未知项目';
}

// 获取表描述信息
function getTableDescription(tableName) {
    // 确保 tableName 是字符串
    if (tableName == null) return '';

    const tableStr = String(tableName).toLowerCase();

    if (tableStr.includes('forecast_')) {
        if (tableStr.includes('host1')) return '主机1';
        if (tableStr.includes('host2')) return '主机2';
        if (tableStr.includes('machine1')) return '机器1';
        if (tableStr.includes('machine2')) return '机器2';
        if (tableStr.includes('room1')) return '房间1';
        return '预测数据';
    }

    if (tableStr.includes('historical_')) {
        if (tableStr.includes('2023')) return '2023年历史';
        if (tableStr.includes('2024')) return '2024年历史';
        return '历史数据';
    }

    return '特征数据表';
}

    // 显示表映射消息
// 修改 showTableMappingMessage 函数
function showTableMappingMessage(message) {
    elements.tableFeatureMapping.innerHTML = `
        <div class="alert alert-info">
            <i class="fas fa-info-circle"></i>
            ${message}
        </div>
    `;
}
// 添加一个检查设备模型状态的函数
function checkDeviceModelStatus(device) {
    if (!device) return '设备不存在';
    if (!device.model_version_id) return '未绑定模型';
    if (!device.model_name) return '模型信息不完整';
    return '正常';
}
    // 保存映射配置
// 修改保存映射配置函数
async function saveMappingConfig() {
    try {
        if (!currentDataSourceId || !currentDatabase) {
            showNotification('请先选择数据源和数据库', 'warning');
            return;
        }

        if (!currentDeviceId) {
            showNotification('请先选择设备', 'warning');
            return;
        }

        const rows = elements.tableFeatureMapping.querySelectorAll('.feature-mapping-row');
        const mappings = [];

        // 收集特征映射
        rows.forEach(row => {
            const featureId = row.dataset.featureId;
            const select = row.querySelector('.table-select');
            const switchEl = row.querySelector('.switch input[type="checkbox"]');

            if (select && select.value) {
                const tableName = select.value;
                const isEnabled = switchEl ? switchEl.checked : true;

                // 检查特征是否已存在
                const existingIndex = mappings.findIndex(m => m.feature_id === parseInt(featureId));
                if (existingIndex !== -1) {
                    console.warn(`特征ID ${featureId} 已存在映射，跳过重复`);
                    return;
                }

                mappings.push({
                    data_source_id: currentDataSourceId,
                    database_name: currentDatabase,
                    device_id: currentDeviceId,
                    feature_id: parseInt(featureId),
                    table_name: tableName,
                    column_name: 'PointValue',  // 默认列名
                    timestamp_column: 'UpdateDateTime',  // 默认时间戳列名
                    is_active: isEnabled,
                    sync_frequency: 15  // 默认15分钟同步一次
                });
            }
        });

        if (mappings.length === 0) {
            showNotification('请至少为一个特征选择特征表', 'warning');
            return;
        }

        console.log('📤 发送映射数据:', mappings);

        // 保存映射到API（使用批量保存接口）
        const response = await fetch(API.FEATURE_MAPPINGS_BATCH_SAVE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(mappings)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({ detail: '服务器错误' }));
            throw new Error(errorData.detail || '保存映射失败');
        }

        const result = await response.json();
        console.log('✅ 保存映射结果:', result);

         if (result.success > 0) {
                    showNotification(`成功保存 ${result.success} 个特征映射`, 'success');

                    // 保存成功后，重新加载设备映射以更新界面
                    await loadDeviceFeatureMappings(currentDeviceId);

                    // 重新加载表映射界面，显示已保存的状态
                    if (currentDataSourceId && currentDatabase) {
                        loadDatabaseTables(currentDataSourceId, currentDatabase);
                    }
                }
        if (result.failed > 0) {
            showNotification(`有 ${result.failed} 个特征映射保存失败`, 'error');
        }

    } catch (error) {
        console.error('❌ 保存映射配置失败:', error);
        showNotification('保存失败: ' + error.message, 'error');
    }
}

    // 测试数据源连接
    async function testDataSource(dsId) {
        const dataSource = dataSources.find(ds => ds.id === dsId);
        if (!dataSource) return;

        console.log('🔍 调试 - 数据源对象:', dataSource);
        console.log('🔍 调试 - database_name:', dataSource.database_name);
        console.log('🔍 调试 - database:', dataSource.database);

        showNotification(`正在测试连接 ${dataSource.name}...`, 'info');

        try {
            // 确保我们使用正确的字段名
            const dbName = dataSource.database_name || dataSource.database || '';

            console.log('🔍 调试 - 最终数据库名:', dbName);

            if (!dbName) {
                showNotification('数据库名称不能为空', 'error');
                return;
            }

            const requestData = {
                host: dataSource.host,
                port: dataSource.port,
                database_name: dbName,
                username: dataSource.username,
                password: dataSource.password || '',
                charset: dataSource.charset || 'utf8mb4',
                timeout: dataSource.timeout || 10
            };

            console.log('🔍 调试 - 发送的请求数据:', requestData);

            const response = await fetch(API.TEST_CONNECTION, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: '服务器错误' }));
                let errorMessage = response.statusText;
                if (Array.isArray(errorData.detail)) {
                    errorMessage = errorData.detail.map(err => err.msg).join(', ');
                } else if (errorData.detail) {
                    errorMessage = errorData.detail;
                }
                throw new Error(`连接测试失败: ${errorMessage}`);
            }

            const result = await response.json();
            if (result.status === 'success') {
                dataSource.connection_status = 'connected';
                dataSource.status = 'connected';
                showNotification(`连接 ${dataSource.name} 测试成功`, 'success');
            } else {
                dataSource.connection_status = 'disconnected';
                dataSource.status = 'disconnected';
                showNotification(`连接失败: ${result.message}`, 'error');
            }
        } catch (error) {
            console.error('❌ 测试连接失败:', error);
            dataSource.connection_status = 'disconnected';
            dataSource.status = 'disconnected';
            showNotification(`连接 ${dataSource.name} 失败: ${error.message}`, 'error');
        }

        renderDataSourceList();
    }

    // 编辑数据源
    function editDataSource(dsId) {
        const dataSource = dataSources.find(ds => ds.id === dsId);
        if (!dataSource) return;

        editingDataSourceId = dsId;
        const modal = document.getElementById('data-source-modal');
        const form = document.getElementById('data-source-form');

        // 填充表单
        document.getElementById('ds-name').value = dataSource.name;
        document.getElementById('ds-host').value = dataSource.host;
        document.getElementById('ds-port').value = dataSource.port;
        document.getElementById('ds-database').value = dataSource.database_name || dataSource.database;
        document.getElementById('ds-username').value = dataSource.username;
        document.getElementById('ds-password').value = dataSource.password || '';
        document.getElementById('ds-charset').value = dataSource.charset;
        document.getElementById('ds-timeout').value = dataSource.timeout;
        document.getElementById('test-result').textContent = '';
        document.getElementById('test-result').className = 'test-result';
        modal.classList.add('active');
    }

    // 修改删除数据源函数，确保传递正确的ID
    function deleteDataSource(dsId) {
        const dataSource = dataSources.find(ds => ds.id === dsId);
        if (!dataSource) {
            showNotification('数据源不存在', 'error');
            return;
        }

        editingDataSourceId = dsId;
        const modal = document.getElementById('delete-confirm-modal');
        document.getElementById('delete-message').textContent =
            `确定要删除数据源 "${dataSource.name}" 吗？\n\n` +
            `⚠️ 此操作将同时删除：\n` +
            `• 该数据源的所有配置\n` +
            `• 所有相关的特征表映射\n` +
            `• 同步历史记录（如果存在）\n\n` +
            `此操作不可恢复！`;

        modal.classList.add('active');
    }

    // 确认删除
    async function confirmDelete() {
        if (!editingDataSourceId) return;

        try {
            const dataSource = dataSources.find(ds => ds.id === editingDataSourceId);
            if (!dataSource) {
                showNotification('数据源不存在', 'error');
                closeAllModals();
                return;
            }

            showNotification(`正在删除数据源 "${dataSource.name}"...`, 'info');

            // 调用后端API删除数据源
            const response = await fetch(API.DATA_SOURCE(editingDataSourceId), {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: '删除失败' }));
                throw new Error(errorData.detail || '删除失败');
            }

            const deletedDataSource = await response.json();

            // 从前端数组中删除
            const index = dataSources.findIndex(ds => ds.id === editingDataSourceId);
            if (index !== -1) {
                dataSources.splice(index, 1);
            }

            showNotification(`数据源 "${deletedDataSource.name}" 已删除，相关映射配置也已清除`, 'success');
            closeAllModals();

            // 重新加载数据源列表
            await loadDataSources();

            // 如果删除的是当前选择的数据源，重置选择
            if (currentDataSourceId === editingDataSourceId) {
                elements.selectDataSource.value = '';
                await handleDataSourceChange();
            }

            // 清理本地存储中的相关映射
            cleanupLocalStorageMappings(editingDataSourceId);

        } catch (error) {
            console.error('❌ 删除数据源失败:', error);
            showNotification('删除失败: ' + error.message, 'error');
            closeAllModals();
        }
    }

    // 新增：清理本地存储中该数据源的映射
    function cleanupLocalStorageMappings(dataSourceId) {
        try {
            const savedData = localStorage.getItem('feature_table_mappings');
            if (!savedData) return;

            const tableMappings = JSON.parse(savedData);
            const cleanedMappings = {};

            // 遍历所有映射，移除包含该数据源的条目
            Object.keys(tableMappings).forEach(key => {
                // 检查键是否包含该数据源ID
                if (!key.startsWith(`${dataSourceId}_`)) {
                    cleanedMappings[key] = tableMappings[key];
                }
            });

            // 保存清理后的映射
            localStorage.setItem('feature_table_mappings', JSON.stringify(cleanedMappings));

            // 更新全局变量
            window.tableMappings = cleanedMappings;

            console.log(`✅ 清理了数据源 ${dataSourceId} 的本地映射缓存`);
        } catch (error) {
            console.warn('清理本地存储映射失败:', error);
        }
    }


    // 辅助函数
function showLoading(element, message) {
    if (element && element.tagName === 'SELECT') {
        const originalHTML = element.innerHTML;
        element.disabled = true;
        element.innerHTML = `<option value="">${message}</option>`;
        return originalHTML; // 返回原始HTML以便恢复
    } else if (element) {
        element.innerHTML = `
            <div class="loading">
                <i class="fas fa-spinner fa-spin"></i> ${message}
            </div>
        `;
    }
}
    function showError(element, message) {
        if (element) {
            element.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle"></i> ${message}
                </div>
            `;
        }
    }

    function showNotification(message, type = 'info') {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 9999;
            animation: slideIn 0.3s ease;
            max-width: 400px;
            display: flex;
            align-items: center;
            gap: 10px;
        `;

        if (type === 'success') {
            notification.style.background = 'linear-gradient(135deg, #28a745, #20c997)';
        } else if (type === 'error') {
            notification.style.background = 'linear-gradient(135deg, #dc3545, #e83e8c)';
        } else if (type === 'warning') {
            notification.style.background = 'linear-gradient(135deg, #ffc107, #fd7e14)';
        } else {
            notification.style.background = 'linear-gradient(135deg, #17a2b8, #20c997)';
        }

        notification.innerHTML = `
            <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle'}"></i>
            <span>${message}</span>
        `;

        document.body.appendChild(notification);

        // 3秒后移除通知
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);

        // 添加CSS动画
        if (!document.querySelector('#notification-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-styles';
            style.textContent = `
                @keyframes slideIn {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                @keyframes slideOut {
                    from {
                        transform: translateX(0);
                        opacity: 1;
                    }
                    to {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }

    async function simulateApiDelay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

// 更新UI状态
function updateUI() {
    console.log('🎨 更新UI状态');

    // 检查元素是否存在再设置值
    const importStartDate = document.getElementById('import-start-date');
    const importEndDate = document.getElementById('import-end-date');

    if (importStartDate && importEndDate) {
        // 设置默认日期（最近30天）
        const today = new Date();
        const oneMonthAgo = new Date(today);
        oneMonthAgo.setDate(today.getDate() - 30);

        importStartDate.valueAsDate = oneMonthAgo;
        importEndDate.valueAsDate = today;
    } else {
        console.log('⚠️ 日期输入框不存在，跳过设置默认日期');
    }
}

    // 公开的方法
    return {
        init,
        testDataSource,
        editDataSource,
        deleteDataSource,
         showCreateTableModal,
        showNotification
    };
})();

// 全局导出
if (typeof window !== 'undefined') {
    window.ConfigPage = ConfigPage;
}