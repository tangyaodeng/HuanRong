const Navbar = {
            // ====【核心】页面路由配置表 ====
            pageRoutes: {
//                'dashboard': { file: '/frontend/index.html', title: '仪表板', level: 1 },
                'projects': { file: '/frontend/pages/project.html', title: '项目管理', level: 1 },
                'devices': { file: '/frontend/pages/device.html', title: '设备管理', level: 1 },
                'features': { file: '/frontend/pages/features.html', title: '自定义配置', level: 1 },
                'data-sources': { file: '/frontend/pages/config.html', title: '数据源配置', level: 1 },
                'model-training': { file: '/frontend/pages/model-training.html', title: '模型训练', level: 1 },
                // 监控相关的顶级菜单项
                'monitoring-overview': {
                    file: '#',
                    title: '监控总览',
                    level: 1,
                    submenu: [
                        { id: 'monitoring', file: '/frontend/pages/monitoring.html', title: '实时监控', icon: 'chart-line' },
                        { id: 'cooling_pump_monitoring', file: '/frontend/pages/cooling_pump_monitoring.html', title: '冷却泵实时监控', icon: 'tasks' },
                        { id: 'chilled_pump_monitoring', file: '/frontend/pages/chilled_pump_monitoring.html', title: '冷冻泵实时监控', icon: 'layer-group' },
                        { id: 'host_monitoring', file: '/frontend/pages/host_monitoring.html', title: '主机实时监控', icon: 'microchip' },
                        { id: 'cooling_tower_monitoring', file: '/frontend/pages/cooling_tower_monitoring.html', title: '冷却塔实时监控', icon: 'water' },
                        { id: 'load_forecasting', file: '/frontend/pages/load_forecasting.html', title: '负荷预测监控', icon: 'chart-bar' }
                    ]
                },
                'parameter-optimization': {
                    file: '#',
                    title: '参数优化',
                    level: 1,
                    submenu: [
                        { id: 'cooling_opt', file: '/frontend/pages/cooling_opt.html', title: '冷却侧模型优化', icon: 'tasks' },
                        { id: 'chilled_opt', file: '/frontend/pages/chilled_opt.html', title: '冷冻侧模型优化', icon: 'layer-group' },
                    ]
                },
               'knowledge-feeding': { file: '/frontend/pages/knowledge_feeding.html', title: '知识投喂', level: 1 },
            },

            // 添加路径到页面ID的映射
            pathToPageIdMap: {
                '/frontend/index.html': 'dashboard',
                '/frontend/pages/project.html': 'projects',
                '/frontend/pages/device.html': 'devices',
                '/frontend/pages/features.html': 'features',
                '/frontend/pages/config.html': 'data-sources',
                '/frontend/pages/model-training.html': 'model-training',
                '/frontend/pages/monitoring.html': 'monitoring',
                '/frontend/pages/cooling_pump_monitoring.html': 'cooling_pump_monitoring',
                '/frontend/pages/chilled_pump_monitoring.html': 'chilled_pump_monitoring',
                '/frontend/pages/host_monitoring.html': 'host_monitoring',
                '/frontend/pages/cooling_tower_monitoring.html': 'cooling_tower_monitoring',
                '/frontend/pages/load_forecasting.html': 'load_forecasting',
                '/frontend/pages/cooling_opt.html': 'cooling_opt',
                '/frontend/pages/chilled_opt.html': 'chilled_opt',
                '/frontend/pages/knowledge_feeding.html': 'knowledge-feeding',
            },

            // 当前激活的页面ID
            currentPageId: null,

            // ====【核心】初始化导航栏 ====
            init(container, currentPageId = null) {
                if (!container) {
                    console.error('导航栏容器未找到！');
                    return;
                }

                this.container = container;

                // 如果没有显式传入currentPageId，则从当前URL路径推断
                this.currentPageId = currentPageId || this.getCurrentPageIdFromPath();

                this.render();
                this.bindEvents();
            },

            // 根据当前URL路径确定当前页面ID
            getCurrentPageIdFromPath() {
                const currentPath = window.location.pathname;
                console.log('当前路径:', currentPath); // 调试信息

                // 查找路径映射
                for (const [path, pageId] of Object.entries(this.pathToPageIdMap)) {
                    if (currentPath.endsWith(path)) {
                        console.log('匹配到页面ID:', pageId); // 调试信息
                        return pageId;
                    }
                }

                // 默认返回第一个页面ID
                const firstPageId = Object.keys(this.pageRoutes)[0];
                console.log('未匹配到路径，默认页面ID:', firstPageId); // 调试信息
                return firstPageId;
            },

            // ==== 渲染导航栏 ====
            render() {
                const currentPage = this.currentPageId;
                this.container.innerHTML = `
                    <nav class="top-nav">
                        <div class="nav-brand">
                            <i class="fas fa-industry"></i>
                            <span>智慧暖通AI预测系统</span>
                        </div>
                        <ul class="nav-menu">
                            ${this.generateMenuItems(currentPage)}
                        </ul>
                        <div class="nav-info">
                            <div class="time-display" id="current-time">00:00:00</div>
                        </div>
                    </nav>
                `;

                // 重新绑定事件（因为DOM重新生成）
                this.bindEvents();
            },

            // 生成导航菜单HTML
            generateMenuItems(currentPage) {
                let menuHtml = '';

                for (const [pageId, config] of Object.entries(this.pageRoutes)) {
                    if (config.level === 1) { // 只渲染一级菜单
                        const isActive = this.isMenuItemActive(pageId, currentPage);

                        if (config.submenu && config.submenu.length > 0) {
                            // 包含二级菜单的一级菜单项
                            menuHtml += `
                                <li class="nav-item ${isActive ? 'active' : ''} has-submenu"
                                    data-page="${pageId}"
                                    title="${config.title}">
                                    <i class="fas fa-${this.getMenuIcon(pageId)}"></i>
                                    <span>${config.title}</span>
                                    <div class="submenu" id="submenu-${pageId}">
                                        ${this.generateSubmenuItems(config.submenu, currentPage)}
                                    </div>
                                </li>
                            `;
                        } else {
                            // 普通的一级菜单项
                            const isDisabled = config.file === '#';
                            const badge = isDisabled ? '<span class="badge">后续扩展</span>' : '';

                            menuHtml += `
                                <li class="nav-item ${isActive ? 'active' : ''} ${isDisabled ? 'disabled' : ''}"
                                    data-page="${pageId}"
                                    title="${config.title}">
                                    <i class="fas fa-${this.getMenuIcon(pageId)}"></i>
                                    <span>${config.title}</span>
                                    ${badge}
                                </li>
                            `;
                        }
                    }
                }

                return menuHtml;
            },

            // 生成二级菜单HTML
            generateSubmenuItems(submenu, currentPage) {
                let submenuHtml = '';

                submenu.forEach((item, index) => {
                    const isActive = currentPage === item.id;
                    const isDisabled = item.file === '#';
                    const badge = isDisabled ? '<span class="badge">后续扩展</span>' : '';

                    submenuHtml += `
                        <div class="submenu-item ${isActive ? 'active' : ''} ${isDisabled ? 'disabled' : ''}"
                             data-page="${item.id}"
                             title="${item.title}">
                            <i class="fas fa-${item.icon || 'circle'}"></i>
                            <span>${item.title}</span>
                            ${badge}
                        </div>
                    `;
                });

                return submenuHtml;
            },

            // 检查菜单项是否应该激活
            isMenuItemActive(menuId, currentPage) {
                // 如果是一级菜单且包含子菜单，检查当前页面是否属于这个子菜单组
                const config = this.pageRoutes[menuId];
                if (config && config.submenu) {
                    return config.submenu.some(item => item.id === currentPage);
                }

                // 普通菜单项直接比较
                return menuId === currentPage;
            },

            // 菜单图标映射
            getMenuIcon(pageId) {
                const iconMap = {
                    'dashboard': 'tachometer-alt',
                    'projects': 'project-diagram',
                    'devices': 'server',
                    'features': 'sliders-h',
                    'data-sources': 'database',
                    'model-training': 'brain',
                    'monitoring-overview': 'eye',
                    'monitoring': 'chart-line',
                    'cooling_pump_monitoring': 'tasks',
                    'chilled_pump_monitoring': 'layer-group',
                    'host_monitoring': 'microchip',
                    'cooling_tower_monitoring': 'water',
                    'load_forecasting': 'chart-bar',
                    'cooling_opt': 'tasks',
                    'chilled_opt': 'layer-group',

                };
                return iconMap[pageId] || 'circle';
            },

           // ==== 绑定所有事件 ====
            bindEvents() {
                this.updateTime();
                setInterval(() => this.updateTime(), 1000);

                // 绑定一级菜单点击事件
                this.container.querySelectorAll('.nav-item:not(.disabled)').forEach(item => {
                    item.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation(); // 防止事件冒泡

                        const targetPageId = e.currentTarget.dataset.page;
                        const submenu = e.currentTarget.querySelector('.submenu');

                        // 如果是一级菜单且有子菜单，我们允许点击跳转到默认页面
                        if (submenu && !e.target.closest('.submenu-item')) {
                            // 如果当前页面就在子菜单中，点击导航到默认子页面
                            const config = this.pageRoutes[targetPageId];
                            if (config && config.submenu && config.submenu.length > 0) {
                                this.handleNavigation(config.submenu[0].id);
                            }
                        } else {
                            // 普通导航
                            this.handleNavigation(targetPageId);
                        }
                    });

                    // 添加鼠标悬停效果（为了一级菜单）
                    item.addEventListener('mouseenter', (e) => {
                        e.currentTarget.classList.add('hover');
                    });

                    item.addEventListener('mouseleave', (e) => {
                        e.currentTarget.classList.remove('hover');
                    });
                });

                // 绑定二级菜单点击事件
                this.container.querySelectorAll('.submenu-item:not(.disabled)').forEach(item => {
                    item.addEventListener('click', (e) => {
                        e.preventDefault();
                        e.stopPropagation(); // 防止事件冒泡
                        const targetPageId = e.currentTarget.dataset.page;
                        this.handleNavigation(targetPageId);
                    });

                    // 添加鼠标悬停效果（为了二级菜单项）
                    item.addEventListener('mouseenter', (e) => {
                        e.currentTarget.classList.add('hover');
                    });

                    item.addEventListener('mouseleave', (e) => {
                        e.currentTarget.classList.remove('hover');
                    });
                });

                // 监听页面变化，动态更新激活状态
                this.setupPageChangeListener();
            },

            // 监听页面变化以更新导航状态
            setupPageChangeListener() {
                // 监听popstate事件（浏览器前进后退）
                window.addEventListener('popstate', () => {
                    this.currentPageId = this.getCurrentPageIdFromPath();
                    this.render(); // 重新渲染导航栏
                });

                // 如果使用hash路由，监听hashchange事件
                window.addEventListener('hashchange', () => {
                    this.currentPageId = this.getCurrentPageIdFromPath();
                    this.render(); // 重新渲染导航栏
                });
            },

            // ====【核心】处理页面导航 ====
            handleNavigation(targetPageId) {
                if (targetPageId === this.currentPageId) {
                    return;
                }

                // 查找目标页面配置
                let targetConfig = this.pageRoutes[targetPageId];

                // 如果没找到，可能是在子菜单中
                if (!targetConfig) {
                    for (const [pageId, config] of Object.entries(this.pageRoutes)) {
                        if (config.submenu) {
                            const subItem = config.submenu.find(item => item.id === targetPageId);
                            if (subItem) {
                                targetConfig = subItem;
                                break;
                            }
                        }
                    }
                }

                if (!targetConfig || targetConfig.file === '#') {
                    console.warn(`页面 ${targetPageId} 未配置或不可用`);
                    return;
                }

                // 更新当前页面ID
                this.currentPageId = targetPageId;

                // 导航到新页面
                window.location.href = targetConfig.file;
            },

            // ==== 其他辅助方法 ====
            updateTime() {
                const timeDisplay = this.container.querySelector('#current-time');
                if (timeDisplay) {
                    const now = new Date();
                    timeDisplay.textContent = now.toLocaleTimeString('zh-CN', { hour12: false });
                }
            },

            // 手动更新当前页面ID（供外部调用）
            setCurrentPageId(pageId) {
                if (this.pageRoutes[pageId] || this.pathToPageIdMap[Object.keys(this.pathToPageIdMap).find(p => this.pathToPageIdMap[p] === pageId)]) {
                    this.currentPageId = pageId;
                    this.render(); // 重新渲染导航栏
                } else {
                    console.warn(`页面ID "${pageId}" 不存在于路由配置中`);
                }
            }
        };

        // 页面加载完成后初始化导航栏
        document.addEventListener('DOMContentLoaded', function() {
            const navContainer = document.getElementById('navbar-container');
            if (navContainer) {
                Navbar.init(navContainer);
            }
        });