class ChatWidget {
    constructor() {
        this.isOpen = false;
        this.apiUrl = 'http://localhost:8000/api/v1/chat';
        this.currentConversationId = null;    // 当前选中对话ID
        this.conversations = [];              // 对话列表
        this.currentModel = 'qwen';   // 默认使用 DeepSeek

        // 拖动相关（窗口）
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.windowStartX = 0;
        this.windowStartY = 0;

        // 拖动相关（浮动按钮）
        this.isBtnDragging = false;
        this.btnDragStartX = 0;
        this.btnDragStartY = 0;
        this.btnStartX = 0;
        this.btnStartY = 0;

        // 推荐问题（可从后端获取，这里先硬编码示例）
        this.recommendations = [
            "制冷原理是什么",
            "主机1功率多少",
            "室外温度多少",
            "现在1号主机状态"
        ];

        this.init();
    }

    init() {
        this.createDOM();
        this.setInitialPosition();
        this.bindEvents();
        this.loadConversations();    // 初始化时加载对话列表
        this.initVoiceInput();
    }

    initVoiceInput() {
        this.voiceInput = new VoiceInput({
            inputEl: this.inputEl,
            micBtnEl: this.micBtnEl,
            voiceApiUrl: this.apiUrl + '/voice',
            onResult: (text) => {
                this.inputEl.value = text;
                this.inputEl.focus();
            }
        });
    }

    createDOM() {
        // 浮动按钮
        this.toggleBtn = document.createElement('button');
        this.toggleBtn.className = 'chat-widget-toggle';
        this.toggleBtn.innerHTML = '<i class="fas fa-robot"></i>';
        document.body.appendChild(this.toggleBtn);

        // 聊天窗口整体容器
        this.widget = document.createElement('div');
        this.widget.className = 'chat-widget';
        this.widget.innerHTML = `
            <!-- 侧边栏（对话列表） -->
            <div class="chat-sidebar">
                <div class="sidebar-header">
                    <h3>对话历史</h3>
                    <div class="sidebar-header-actions">
                        <button class="new-conv-btn" title="新建对话"><i class="fas fa-plus"></i></button>
                        <button class="sidebar-close-btn" title="关闭"><i class="fas fa-times"></i></button>
                    </div>
                </div>
                <div class="conversation-list"></div>
            </div>

            <!-- 主聊天区域 -->
            <div class="chat-main">
                <div class="chat-widget-header">
                    <button class="sidebar-toggle-btn" title="对话列表">
                        <i class="fas fa-bars"></i>
                    </button>
                    <span><i class="fas fa-brain"></i> 暖通AI助手</span>
                    <div class="chat-widget-header-actions">
                        <select class="model-selector" id="modelSelector">
                            <option value="deepseek" >🧠 DeepSeek</option>
                            <option value="qwen" selected>🤖 Qwen 2.5:14b</option>
                        </select>
                        <button class="chat-widget-fullscreen" title="全屏">
                            <i class="fas fa-expand"></i>
                        </button>
                        <button class="chat-widget-close">&times;</button>
                    </div>
                </div>
                <div class="chat-widget-body">
                    <!-- 推荐问题 -->
                    <div class="recommendations-area">
                        <span class="rec-label">推荐问题：</span>
                        <div class="rec-tags"></div>
                    </div>
                    <div class="chat-messages"></div>
                    <div class="chat-input-area">
                        <input type="text" class="chat-input" placeholder="输入您的问题...">
                        <button class="chat-mic-btn" title="语音输入"><i class="fas fa-microphone"></i></button>
                        <button class="chat-send-btn"><i class="fas fa-paper-plane"></i></button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(this.widget);

        // 缓存DOM引用
        this.sidebar = this.widget.querySelector('.chat-sidebar');
        this.convListEl = this.widget.querySelector('.conversation-list');
        this.messagesContainer = this.widget.querySelector('.chat-messages');
        this.inputEl = this.widget.querySelector('.chat-input');
        this.micBtnEl = this.widget.querySelector('.chat-mic-btn');
        this.recTagsEl = this.widget.querySelector('.rec-tags');

        // 初始化推荐问题标签
        this.renderRecommendations();
    }

    setInitialPosition() {
        const winW = window.innerWidth;
        const winH = window.innerHeight;
        const widgetW = 380;
        const widgetH = 500;
        const margin = 30;
        const bottomMargin = 100;

        this.widget.style.left = (winW - widgetW - margin) + 'px';
        this.widget.style.top = (winH - widgetH - bottomMargin) + 'px';
        this.widget.style.right = 'auto';
        this.widget.style.bottom = 'auto';
    }

    bindEvents() {
        // 浮动按钮：点击打开/关闭，长按拖动
        this.toggleBtn.addEventListener('mousedown', (e) => this.onBtnDragStart(e));
        this.toggleBtn.addEventListener('touchstart', (e) => this.onBtnDragStart(e), { passive: false });
        window.addEventListener('mousemove', (e) => this.onBtnDragMove(e));
        window.addEventListener('touchmove', (e) => this.onBtnDragMove(e), { passive: false });
        window.addEventListener('mouseup', (e) => this.onBtnDragEnd(e));
        window.addEventListener('touchend', (e) => this.onBtnDragEnd(e));

        // 关闭按钮
        const closeBtn = this.widget.querySelector('.chat-widget-close');
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleChat(false);
        });

        // 全屏按钮
        const fullscreenBtn = this.widget.querySelector('.chat-widget-fullscreen');
        fullscreenBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleFullscreen();
        });

        // 侧边栏切换按钮
        const sidebarToggle = this.widget.querySelector('.sidebar-toggle-btn');
        sidebarToggle.addEventListener('click', () => {
            this.widget.classList.toggle('sidebar-open');
        });

        // 关闭侧边栏
        const sidebarCloseBtn = this.widget.querySelector('.sidebar-close-btn');
        sidebarCloseBtn.addEventListener('click', () => {
            this.widget.classList.remove('sidebar-open');
        });

        // 新建对话
        const newConvBtn = this.widget.querySelector('.new-conv-btn');
        newConvBtn.addEventListener('click', () => this.createNewConversation());

        // 发送消息
        const sendBtn = this.widget.querySelector('.chat-send-btn');
        sendBtn.addEventListener('click', () => this.sendMessage());
        this.inputEl.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });
        const modelSelector = this.widget.querySelector('#modelSelector');
        modelSelector.addEventListener('change', (e) => {
            this.currentModel = e.target.value;
        });
        // 拖动事件（头部）
        const header = this.widget.querySelector('.chat-widget-header');
        header.addEventListener('mousedown', (e) => this.onDragStart(e));
        window.addEventListener('mousemove', (e) => this.onDragMove(e));
        window.addEventListener('mouseup', (e) => this.onDragEnd(e));
        header.addEventListener('touchstart', (e) => this.onDragStart(e), { passive: false });
        window.addEventListener('touchmove', (e) => this.onDragMove(e), { passive: false });
        window.addEventListener('touchend', (e) => this.onDragEnd(e));
    }

    /* ========== 推荐问题渲染 ========== */
    renderRecommendations() {
        this.recTagsEl.innerHTML = '';
        this.recommendations.forEach(q => {
            const tag = document.createElement('span');
            tag.className = 'rec-tag';
            tag.textContent = q;
            tag.addEventListener('click', () => {
                this.inputEl.value = q;
                this.sendMessage();
            });
            this.recTagsEl.appendChild(tag);
        });
    }

    /* ========== 对话列表管理 ========== */
    async loadConversations() {
        try {
            const res = await fetch(`${this.apiUrl}/conversations`);
            if (!res.ok) throw new Error('加载失败');
            this.conversations = await res.json();
            this.renderConversationList();

            // 如果有对话，默认选中最新一个；否则自动创建新对话
            if (this.conversations.length > 0) {
                this.switchConversation(this.conversations[0].id);
            } else {
                await this.createNewConversation();
            }
        } catch (e) {
            console.error('加载对话列表失败', e);
            // 失败时也创建一个新对话保证可用
            await this.createNewConversation();
        }
    }

    renderConversationList() {
        this.convListEl.innerHTML = '';
        this.conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = 'conv-item';
            if (conv.id === this.currentConversationId) {
                item.classList.add('active');
            }
            item.innerHTML = `
                <span class="conv-title">${this.escapeHtml(conv.title)}</span>
                <button class="conv-delete" data-id="${conv.id}"><i class="fas fa-trash"></i></button>
            `;

            item.querySelector('.conv-title').addEventListener('click', () => {
                this.switchConversation(conv.id);
            });

            item.querySelector('.conv-delete').addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteConversation(conv.id);
            });

            this.convListEl.appendChild(item);
        });
    }

    async createNewConversation() {
        // 新对话不需要后端创建，只需将 currentConversationId 置空
        this.currentConversationId = null;
        this.clearMessages();
        this.inputEl.value = '';
        this.renderConversationList(); // 取消所有高亮
    }

    async switchConversation(convId) {
        if (this.currentConversationId === convId) return;

        this.currentConversationId = convId;
        this.renderConversationList();

        // 加载历史消息
        try {
            const res = await fetch(`${this.apiUrl}/conversations/${convId}`);
            if (!res.ok) throw new Error('加载失败');
            const data = await res.json();

            this.clearMessages();
            data.messages.forEach(msg => {
                // 只展示 user 和 assistant 消息，不展示 system/tool
                if (msg.role === 'user' || msg.role === 'assistant') {
                    const className = msg.role === 'assistant' ? 'ai' : 'user';
                    this.addMessage(className, msg.content, '', false);
                }
            });
        } catch (e) {
            console.error('加载历史消息失败', e);
            alert('加载历史消息失败');
        }
    }

    async deleteConversation(convId) {
        if (!confirm('确定删除这个对话吗？')) return;

        try {
            const res = await fetch(`${this.apiUrl}/conversations/${convId}`, {
                method: 'DELETE'
            });
            if (!res.ok) throw new Error('删除失败');

            // 如果删除的是当前对话，切换到其他对话或新建
            if (this.currentConversationId === convId) {
                this.conversations = this.conversations.filter(c => c.id !== convId);
                if (this.conversations.length > 0) {
                    this.switchConversation(this.conversations[0].id);
                } else {
                    this.createNewConversation();
                }
            } else {
                this.conversations = this.conversations.filter(c => c.id !== convId);
                this.renderConversationList();
            }
        } catch (e) {
            console.error('删除对话失败', e);
            alert('删除失败，请稍后重试');
        }
    }

    clearMessages() {
        this.messagesContainer.innerHTML = '';
    }

    /* ========== 发送消息（适配conversation_id） ========== */
    async sendMessage() {
        const message = this.inputEl.value.trim();
        if (!message) return;

        this.addMessage('user', message);
        this.inputEl.value = '';

        const loadingMsg = this.addMessage('ai', '思考中...', 'loading');

        try {
            const body = { message,model: this.currentModel };
            if (this.currentConversationId) {
                body.conversation_id = this.currentConversationId;
            }

            const response = await fetch(this.apiUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();

            // 更新当前对话ID（新对话时后端会返回ID）
            if (!this.currentConversationId && data.conversation_id) {
                this.currentConversationId = data.conversation_id;
                // 刷新对话列表
                await this.loadConversations();
                // 标题会自动更新
            }

            // 如果标题有变化，更新列表
            if (data.title) {
                const conv = this.conversations.find(c => c.id === data.conversation_id);
                if (conv) {
                    conv.title = data.title;
                    this.renderConversationList();
                }
            }

            this.updateMessage(loadingMsg.id, data.response, 'ai');
        } catch (error) {
            this.updateMessage(loadingMsg.id, '抱歉，请求失败，请稍后重试。', 'ai error');
        }
    }

    addMessage(role, content, className = '', scroll = true) {
        const msgId = Date.now() + Math.random();
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${role} ${className}`;
        msgDiv.dataset.id = msgId;
        msgDiv.textContent = content;
        this.messagesContainer.appendChild(msgDiv);
        if (scroll) {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
        return { id: msgId, element: msgDiv };
    }

    updateMessage(msgId, newContent, newClass = '') {
        const msgDiv = this.messagesContainer.querySelector(`.chat-message[data-id="${msgId}"]`);
        if (msgDiv) {
            msgDiv.textContent = newContent;
            msgDiv.className = `chat-message ${newClass}`;
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /* ========== 拖动逻辑（保持不变） ========== */
    onDragStart(e) {
        // 如果正在全屏状态，不允许拖动
        if (this.widget.classList.contains('fullscreen')) return;

        // 只允许在头部区域拖动，且不点击按钮和下拉框时
        if (e.target.closest('button, select')) return;

        this.isDragging = true;
        const pos = this.widget.getBoundingClientRect();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;

        this.windowStartX = pos.left;
        this.windowStartY = pos.top;
        this.dragStartX = clientX;
        this.dragStartY = clientY;

        this.widget.style.transition = 'none';
        e.preventDefault();
    }

    onDragMove(e) {
        if (!this.isDragging) return;

        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;

        const deltaX = clientX - this.dragStartX;
        const deltaY = clientY - this.dragStartY;

        let newLeft = this.windowStartX + deltaX;
        let newTop = this.windowStartY + deltaY;

        // 边界限制，防止拖出屏幕
        const winW = window.innerWidth;
        const winH = window.innerHeight;
        const widgetW = this.widget.offsetWidth;
        const widgetH = this.widget.offsetHeight;

        newLeft = Math.max(0, Math.min(newLeft, winW - widgetW));
        newTop = Math.max(0, Math.min(newTop, winH - widgetH));

        this.widget.style.left = newLeft + 'px';
        this.widget.style.top = newTop + 'px';
        this.widget.style.right = 'auto';
        this.widget.style.bottom = 'auto';

        e.preventDefault();
    }

    onDragEnd() {
        if (this.isDragging) {
            this.isDragging = false;
            this.widget.style.transition = '';
        }
    }

    /* ========== 全屏切换 ========== */
    toggleFullscreen() {
        const isFull = this.widget.classList.contains('fullscreen');
        const icon = this.widget.querySelector('.chat-widget-fullscreen i');

        if (isFull) {
            this.widget.classList.remove('fullscreen');
            icon.className = 'fas fa-expand';
            // 恢复原来位置（用 setInitialPosition 或留下当前 left/top）
            this.setInitialPosition();
        } else {
            // 保存当前非全屏位置（用于退出全屏后恢复）
            const rect = this.widget.getBoundingClientRect();
            this._lastLeft = rect.left;
            this._lastTop = rect.top;

            this.widget.classList.add('fullscreen');
            icon.className = 'fas fa-compress';
        }
    }

    /* ========== 浮动按钮拖动逻辑 ========== */
    onBtnDragStart(e) {
        this.isBtnDragging = true;
        this._btnMoved = false;

        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;

        const rect = this.toggleBtn.getBoundingClientRect();
        this.btnStartX = rect.left;
        this.btnStartY = rect.top;
        this.btnDragStartX = clientX;
        this.btnDragStartY = clientY;

        this.toggleBtn.classList.add('dragging');
        this.toggleBtn.style.transition = 'none';
        // 切换为 left/top 定位
        this.toggleBtn.style.right = 'auto';
        this.toggleBtn.style.bottom = 'auto';
        this.toggleBtn.style.left = rect.left + 'px';
        this.toggleBtn.style.top = rect.top + 'px';

        e.preventDefault();
    }

    onBtnDragMove(e) {
        if (!this.isBtnDragging) return;

        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;

        const deltaX = clientX - this.btnDragStartX;
        const deltaY = clientY - this.btnDragStartY;

        if (Math.abs(deltaX) > 3 || Math.abs(deltaY) > 3) {
            this._btnMoved = true;
        }

        let newLeft = this.btnStartX + deltaX;
        let newTop = this.btnStartY + deltaY;

        const winW = window.innerWidth;
        const winH = window.innerHeight;
        const btnW = this.toggleBtn.offsetWidth;
        const btnH = this.toggleBtn.offsetHeight;

        newLeft = Math.max(0, Math.min(newLeft, winW - btnW));
        newTop = Math.max(0, Math.min(newTop, winH - btnH));

        this.toggleBtn.style.left = newLeft + 'px';
        this.toggleBtn.style.top = newTop + 'px';

        e.preventDefault();
    }

    onBtnDragEnd(e) {
        if (!this.isBtnDragging) return;

        this.isBtnDragging = false;
        this.toggleBtn.classList.remove('dragging');
        this.toggleBtn.style.transition = '';

        // 只有没有移动时才视为点击
        if (!this._btnMoved) {
            this.toggleChat();
        }

        e.preventDefault();
    }

    toggleChat(force = null) {
        this.isOpen = force !== null ? force : !this.isOpen;
        this.widget.classList.toggle('open', this.isOpen);
        this.toggleBtn.classList.toggle('hidden', this.isOpen);
        if (this.isOpen) {
            this.inputEl.focus();
        }
    }
}

// 自动初始化
document.addEventListener('DOMContentLoaded', () => {
    window.chatWidget = new ChatWidget();
});