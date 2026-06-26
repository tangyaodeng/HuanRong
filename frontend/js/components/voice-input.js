class VoiceInput {
    constructor(options) {
        this.inputEl = options.inputEl;
        this.micBtnEl = options.micBtnEl;
        this.onResult = options.onResult || (() => {});
        this.onStateChange = options.onStateChange || (() => {});
        // 语音识别后端地址，由 chat-widget 传入
        this.voiceApiUrl = options.voiceApiUrl || '/api/v1/chat/voice';

        this.mediaRecorder = null;
        this.audioChunks = [];
        this.audioStream = null;
        this.currentState = 'idle';
        this.errorTimer = null;
        this.supported = false;

        this._checkSupport();
        this._bindEvents();
    }

    /* ========== 浏览器支持检测 ========== */
    _checkSupport() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this._setState('disabled');
            this.micBtnEl.title = '浏览器不支持麦克风访问，请使用 Chrome、Edge 或 Firefox';
            return;
        }
        if (typeof MediaRecorder === 'undefined') {
            this._setState('disabled');
            this.micBtnEl.title = '浏览器不支持录音功能，请使用 Chrome、Edge 或 Firefox';
            return;
        }
        this.supported = true;
    }

    /* ========== 事件绑定 ========== */
    _bindEvents() {
        this.micBtnEl.addEventListener('click', () => this.toggle());
    }

    /* ========== 公开 API ========== */
    async start() {
        if (!this.supported || this.currentState === 'recording') return;

        try {
            // 请求麦克风权限
            this.audioStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 16000,
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            // 确定最佳 MIME 类型
            const mimeType = this._getBestMimeType();

            this.mediaRecorder = new MediaRecorder(this.audioStream, {
                mimeType: mimeType,
                audioBitsPerSecond: 32000
            });

            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data && event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = () => this._onRecordingStop();

            this.mediaRecorder.start();
            this._setState('recording');

        } catch (e) {
            console.warn('麦克风访问失败:', e);
            this._setState('error');
            this._scheduleReset();
            // 更新 title 提示用户
            this.micBtnEl.title = '麦克风访问被拒绝，请在浏览器设置中允许';
        }
    }

    stop() {
        if (!this.mediaRecorder || this.currentState !== 'recording') return;

        this.mediaRecorder.stop();
        this._setState('processing');

        // 释放麦克风
        if (this.audioStream) {
            this.audioStream.getTracks().forEach(track => track.stop());
            this.audioStream = null;
        }
    }

    toggle() {
        if (this.currentState === 'idle') {
            this.start();
        } else if (this.currentState === 'recording') {
            this.stop();
        }
        // processing 状态不响应点击
    }

    /* ========== 录音结束 → 发送后端 ========== */
    async _onRecordingStop() {
        if (this.audioChunks.length === 0) {
            this._setState('error');
            this._scheduleReset();
            return;
        }

        const blob = new Blob(this.audioChunks, { type: this.mediaRecorder.mimeType });
        this.audioChunks = [];

        try {
            const formData = new FormData();
            formData.append('audio', blob, this._getFileName());

            const response = await fetch(this.voiceApiUrl, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errText = await response.text();
                throw new Error(errText || `HTTP ${response.status}`);
            }

            const data = await response.json();
            if (data.success && data.text) {
                this._setState('idle');
                this.onResult(data.text);
            } else {
                throw new Error(data.detail || '未识别到语音内容');
            }

        } catch (e) {
            console.warn('语音识别请求失败:', e);
            this._setState('error');
            this._scheduleReset();
        }
    }

    /* ========== 工具方法 ========== */
    _getBestMimeType() {
        // 优先 webm (Chrome/Edge)、fallback ogg (Firefox)
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/ogg'
        ];
        for (const t of types) {
            if (MediaRecorder.isTypeSupported(t)) {
                return t;
            }
        }
        return ''; // 浏览器默认
    }

    _getFileName() {
        // 根据 mimeType 推断扩展名
        const mime = this.mediaRecorder.mimeType || '';
        if (mime.includes('webm')) return 'recording.webm';
        if (mime.includes('ogg') || mime.includes('opus')) return 'recording.ogg';
        return 'recording.webm';
    }

    /* ========== 状态管理 ========== */
    _setState(state) {
        // 清除旧状态类
        const states = [
            'voice-btn--idle',
            'voice-btn--recording',
            'voice-btn--processing',
            'voice-btn--error',
            'voice-btn--disabled'
        ];
        this.micBtnEl.classList.remove(...states);

        this.currentState = state;
        this.micBtnEl.classList.add(`voice-btn--${state}`);

        // 更新图标
        const icon = this.micBtnEl.querySelector('i');
        if (icon) {
            switch (state) {
                case 'recording':
                    icon.className = 'fas fa-microphone';
                    break;
                case 'processing':
                    icon.className = 'fas fa-spinner fa-spin';
                    break;
                case 'error':
                    icon.className = 'fas fa-exclamation-triangle';
                    break;
                case 'disabled':
                    icon.className = 'fas fa-microphone-slash';
                    break;
                default:
                    icon.className = 'fas fa-microphone';
            }
        }

        this.onStateChange(state);
    }

    _scheduleReset() {
        clearTimeout(this.errorTimer);
        this.errorTimer = setTimeout(() => {
            if (this.currentState === 'error') {
                this._setState('idle');
            }
        }, 2000);
    }
}
