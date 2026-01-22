// 分子设计平台主模块
class MoleculeDesignPlatform {
    constructor() {
        this.pollInterval = null;
        this.displayedCount = 0; // 记录已显示的日志条数
        this.init();
    }

    // 初始化应用
    init() {
        this.bindEvents();
        this.loadModels();
    }

    // 绑定事件监听器
    bindEvents() {
        // 分子生成按钮事件
        document.getElementById('genBtn').onclick = () => this.generateMolecule();
        
        // 训练表单提交事件
        document.getElementById('trainForm').onsubmit = (e) => this.handleTrainSubmit(e);
    }

    // 切换选项卡
    switchTab(id, el) {
        // 移除所有活动状态
        document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
        
        // 添加当前活动状态
        el.classList.add('active');
        
        // 显示对应面板
        document.getElementById('genPanel').style.display = id === 'genPanel' ? 'block' : 'none';
        document.getElementById('trainPanel').style.display = id === 'trainPanel' ? 'block' : 'none';
    }

    // 加载模型列表
    async loadModels() {
        try {
            const res = await fetch('/get_models');
            const data = await res.json();
            const modelSelect = document.getElementById('modelSelect');
            modelSelect.innerHTML = data.models.map(model => `<option value="${model}">${model}</option>`).join('');
        } catch(e) {
            console.error("模型列表获取失败", e);
        }
    }

    // 开始轮询训练状态
    async startPolling() {
        const progressBar = document.getElementById('trainProgressBar');
        const statusText = document.getElementById('statusText');
        const logArea = document.getElementById('trainLogs');
        const trainBtn = document.getElementById('trainBtn');

        this.pollInterval = setInterval(async () => {
            try {
                const res = await fetch('/get_train_status');
                const data = await res.json();

                if (data.status === "training" || data.status === "success" || data.status === "error") {
                    // 更新进度条
                    const progress = Math.round((data.current_epoch / data.total_epochs) * 100);
                    progressBar.style.width = progress + "%";

                    // 增量日志显示
                    if (data.logs && data.logs.length > this.displayedCount) {
                        for (let i = this.displayedCount; i < data.logs.length; i++) {
                            const div = document.createElement('div');
                            div.innerText = data.logs[i];
                            logArea.appendChild(div);
                            this.displayedCount++;
                        }
                        // 自动滚动到底部
                        logArea.scrollTop = logArea.scrollHeight;
                    }

                    // 当状态不再是 training 时恢复按钮
                    if (data.status === "success" || data.status === "error") {
                        clearInterval(this.pollInterval);

                        trainBtn.disabled = false;
                        trainBtn.innerHTML = `<i class="bi bi-rocket-takeoff"></i> 启动异步训练任务`;

                        if (data.status === "success") {
                            statusText.innerText = "✅ 训练已成功完成";
                            progressBar.classList.remove('progress-bar-animated');
                            this.loadModels(); // 自动刷新模型下拉列表
                        } else {
                            statusText.innerText = "❌ 训练出现错误";
                        }
                    } else {
                        statusText.innerText = "模型训练中...";
                    }
                }
            } catch (e) {
                console.error("轮询异常", e);
            }
        }, 800);
    }

    // 处理训练表单提交
    async handleTrainSubmit(e) {
        e.preventDefault();

        // 锁定按钮
        const trainBtn = document.getElementById('trainBtn');
        trainBtn.disabled = true;
        trainBtn.innerHTML = `<span class="spinner-border spinner-border-sm"></span> 训练任务运行中...`;

        // 重置 UI 状态
        document.getElementById('trainNotify').classList.remove('d-none');
        document.getElementById('trainLogs').innerHTML = "";
        this.displayedCount = 0;

        const formData = new FormData(e.target);
        try {
            await fetch('/start_train', {
                method: 'POST',
                body: formData
            });
            this.startPolling(); // 开始监听后端 logs 列表
        } catch (e) {
            alert("启动失败，请检查后端连接");
            // 报错时恢复按钮
            trainBtn.disabled = false;
            trainBtn.innerHTML = `<i class="bi bi-rocket-takeoff"></i> 启动异步训练任务`;
        }
    }

    // 生成分子
    async generateMolecule() {
        const genBtn = document.getElementById('genBtn');
        genBtn.disabled = true;
        genBtn.innerText = "生成中...";
        
        try {
            const res = await fetch('/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    target: document.getElementById('targetSelect').value,
                    model_file: document.getElementById('modelSelect').value
                })
            });
            const data = await res.json();
            
            if (!data.error) {
                // 显示结果
                document.getElementById('emptyState').style.display = 'none';
                document.getElementById('resultDisplay').style.display = 'block';
                document.getElementById('molImg').src = 'data:image/png;base64,' + data.image;
                document.getElementById('smilesCode').innerText = data.smiles;
                document.getElementById('qedVal').innerText = data.metrics.qed;
                document.getElementById('logpVal').innerText = data.metrics.logp;
                document.getElementById('mwVal').innerText = data.metrics.mw;
                document.getElementById('moreMetrics').innerText = `氢键供体: ${data.metrics.hbd} | 氢键受体: ${data.metrics.hba}`;
            } else {
                alert(data.error);
            }
        } catch (e) {
            alert("生成请求失败");
        } finally {
            genBtn.disabled = false;
            genBtn.innerText = "执行生成";
        }
    }
}

// 全局函数，用于HTML中的事件调用
function switchTab(id, el) {
    window.moleculeApp.switchTab(id, el);
}

function loadModels() {
    window.moleculeApp.loadModels();
}

// 页面加载完成后初始化应用
window.addEventListener('DOMContentLoaded', () => {
    window.moleculeApp = new MoleculeDesignPlatform();
});