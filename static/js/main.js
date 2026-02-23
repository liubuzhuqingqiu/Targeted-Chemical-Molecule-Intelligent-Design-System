// 分子设计平台主模块
class MoleculeDesignPlatform {
    constructor() {
        this.pollInterval = null;
        this.displayedCount = 0; // 记录已显示的日志条数
        this.radarChart = null; // 雷达图实例
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
        
        // 恢复默认值按钮事件
        document.getElementById('resetBtn').onclick = () => this.resetToDefaults();
        
        // 训练表单提交事件
        document.getElementById('trainForm').onsubmit = (e) => this.handleTrainSubmit(e);
        
        // 滑块值实时更新
        this.bindSliderEvents();
        
        // 折叠符号动态变化
        this.bindCollapseEvents();
    }
    
    // 恢复默认值
    resetToDefaults() {
        // 分子量默认值
        document.getElementById('mwMinSlider').value = 100;
        document.getElementById('mwMaxSlider').value = 500;
        document.getElementById('mwMinValue').textContent = '100';
        document.getElementById('mwMaxValue').textContent = '500';
        
        // LogP默认值
        document.getElementById('logpMinSlider').value = -3;
        document.getElementById('logpMaxSlider').value = 5.0;
        document.getElementById('logpMinValue').textContent = '-3.0';
        document.getElementById('logpMaxValue').textContent = '5.0';
        
        // HBD默认值
        document.getElementById('hbdMinSlider').value = 0;
        document.getElementById('hbdMaxSlider').value = 5;
        document.getElementById('hbdMinValue').textContent = '0';
        document.getElementById('hbdMaxValue').textContent = '5';
        
        // HBA默认值
        document.getElementById('hbaMinSlider').value = 0;
        document.getElementById('hbaMaxSlider').value = 10;
        document.getElementById('hbaMinValue').textContent = '0';
        document.getElementById('hbaMaxValue').textContent = '10';
        
        // RotBonds默认值
        document.getElementById('rotBondsMinSlider').value = 0;
        document.getElementById('rotBondsMaxSlider').value = 10;
        document.getElementById('rotBondsMinValue').textContent = '0';
        document.getElementById('rotBondsMaxValue').textContent = '10';
        
        // QED默认值
        document.getElementById('qedSlider').value = 0.6;
        document.getElementById('qedValue').textContent = '0.6';
        
        // SA默认值
        document.getElementById('saSlider').value = 4.0;
        document.getElementById('saValue').textContent = '4.0';
        
        // 样本数量默认值
        document.getElementById('sampleCountSlider').value = 100;
        document.getElementById('sampleCountValue').textContent = '100';
        
        // 显示成功提示
        this.showSuccessToast('已恢复默认参数值');
    }
    
    // 显示成功提示
    showSuccessToast(message) {
        const successToast = document.createElement('div');
        successToast.className = 'toast align-items-center text-bg-success border-0 position-fixed bottom-5 end-5';
        successToast.role = 'alert';
        successToast.setAttribute('aria-live', 'assertive');
        successToast.setAttribute('aria-atomic', 'true');
        successToast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        document.body.appendChild(successToast);
        
        const toast = new bootstrap.Toast(successToast, {
            autohide: true,
            delay: 2000
        });
        toast.show();
        
        // 2秒后移除元素
        setTimeout(() => {
            successToast.remove();
        }, 2500);
    }
    
    // 绑定折叠事件，实现折叠符号的动态变化
    bindCollapseEvents() {
        // 核心药化规则折叠事件
        const lipinskiRules = document.getElementById('lipinskiRules');
        const lipinskiIcon = document.querySelector('[data-bs-target="#lipinskiRules"] i');
        
        if (lipinskiRules && lipinskiIcon) {
            lipinskiRules.addEventListener('show.bs.collapse', () => {
                lipinskiIcon.classList.remove('bi-chevron-right');
                lipinskiIcon.classList.add('bi-chevron-down');
            });
            
            lipinskiRules.addEventListener('hide.bs.collapse', () => {
                lipinskiIcon.classList.remove('bi-chevron-down');
                lipinskiIcon.classList.add('bi-chevron-right');
            });
        }
        
        // 综合质量评分折叠事件
        const qualityScores = document.getElementById('qualityScores');
        const qualityIcon = document.querySelector('[data-bs-target="#qualityScores"] i');
        
        if (qualityScores && qualityIcon) {
            qualityScores.addEventListener('show.bs.collapse', () => {
                qualityIcon.classList.remove('bi-chevron-right');
                qualityIcon.classList.add('bi-chevron-down');
            });
            
            qualityScores.addEventListener('hide.bs.collapse', () => {
                qualityIcon.classList.remove('bi-chevron-down');
                qualityIcon.classList.add('bi-chevron-right');
            });
        }
        
        // 规则检查折叠事件
        const ruleChecks = document.getElementById('ruleChecks');
        const ruleIcon = document.querySelector('[data-bs-target="#ruleChecks"] i');
        
        if (ruleChecks && ruleIcon) {
            ruleChecks.addEventListener('show.bs.collapse', () => {
                ruleIcon.classList.remove('bi-chevron-right');
                ruleIcon.classList.add('bi-chevron-down');
            });
            
            ruleChecks.addEventListener('hide.bs.collapse', () => {
                ruleIcon.classList.remove('bi-chevron-down');
                ruleIcon.classList.add('bi-chevron-right');
            });
        }
        
        // 雷达图折叠事件
        const radarChartSection = document.getElementById('radarChartSection');
        const radarIcon = document.querySelector('[data-bs-target="#radarChartSection"] i');
        
        if (radarChartSection && radarIcon) {
            radarChartSection.addEventListener('show.bs.collapse', () => {
                radarIcon.classList.remove('bi-chevron-right');
                radarIcon.classList.add('bi-chevron-down');
            });
            
            radarChartSection.addEventListener('hide.bs.collapse', () => {
                radarIcon.classList.remove('bi-chevron-down');
                radarIcon.classList.add('bi-chevron-right');
            });
        }
    }
    
    // 绘制分子性质雷达图
    renderRadarChart(metrics) {
        const ctx = document.getElementById('moleculeRadarChart').getContext('2d');
        
        // 如果已有图表实例，先销毁
        if (this.radarChart) {
            this.radarChart.destroy();
        }
        
        // 数据归一化处理
        const normalizedData = [
            Math.min(metrics.mw / 600, 1),      // 分子量上限600
            Math.min(metrics.logp / 7, 1),      // LogP上限7
            Math.min(metrics.hbd / 10, 1),      // HBD上限10
            Math.min(metrics.hba / 15, 1),      // HBA上限15
            Math.min(metrics.rot_bonds / 15, 1), // 可旋转键上限15
            Math.min(metrics.tpsa / 200, 1)      // TPSA上限200
        ];
        
        this.radarChart = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['分子量 (MW)', '亲油性 (LogP)', '氢键供体 (HBD)', '氢键受体 (HBA)', '可旋转键 (RotB)', '极性表面积 (TPSA)'],
                datasets: [{
                    label: '分子性质',
                    data: normalizedData,
                    backgroundColor: 'rgba(13, 110, 253, 0.2)',
                    borderColor: 'rgba(13, 110, 253, 0.8)',
                    pointBackgroundColor: 'rgba(13, 110, 253, 1)',
                    pointBorderColor: '#fff',
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: 'rgba(13, 110, 253, 1)'
                }, {
                    label: '理想范围',
                    data: [0.83, 0.71, 0.5, 0.67, 0.67, 0.7],
                    backgroundColor: 'rgba(25, 135, 84, 0.1)',
                    borderColor: 'rgba(25, 135, 84, 0.5)',
                    borderDash: [5, 5],
                    pointRadius: 3,
                    pointBackgroundColor: 'rgba(25, 135, 84, 1)'
                }]
            },
            options: {
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 1,
                        ticks: {
                            display: false
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                if (context.datasetIndex === 0) {
                                    // 分子实际值
                                    const labels = ['分子量: ' + metrics.mw + ' Da',
                                                  '亲油性: ' + metrics.logp,
                                                  '氢键供体: ' + metrics.hbd,
                                                  '氢键受体: ' + metrics.hba,
                                                  '可旋转键: ' + metrics.rot_bonds,
                                                  '极性表面积: ' + metrics.tpsa + ' Å²'];
                                    return labels[context.dataIndex];
                                } else {
                                    // 理想范围值
                                    const idealLabels = ['分子量理想上限: 500 Da',
                                                       '亲油性理想上限: 5',
                                                       '氢键供体理想上限: 5',
                                                       '氢键受体理想上限: 10',
                                                       '可旋转键理想上限: 10',
                                                       '极性表面积理想上限: 140 Å²'];
                                    return idealLabels[context.dataIndex];
                                }
                            }
                        }
                    }
                }
            }
        });
    }
    
    // 绑定滑块事件
    bindSliderEvents() {
        // MW滑块
        const mwMinSlider = document.getElementById('mwMinSlider');
        const mwMaxSlider = document.getElementById('mwMaxSlider');
        const mwMinValue = document.getElementById('mwMinValue');
        const mwMaxValue = document.getElementById('mwMaxValue');
        if (mwMinSlider && mwMaxSlider && mwMinValue && mwMaxValue) {
            mwMinSlider.addEventListener('input', () => {
                // 确保最小值不大于最大值
                if (parseInt(mwMinSlider.value) > parseInt(mwMaxSlider.value)) {
                    mwMinSlider.value = mwMaxSlider.value;
                }
                mwMinValue.textContent = mwMinSlider.value;
            });
            mwMaxSlider.addEventListener('input', () => {
                // 确保最大值不小于最小值
                if (parseInt(mwMaxSlider.value) < parseInt(mwMinSlider.value)) {
                    mwMaxSlider.value = mwMinSlider.value;
                }
                mwMaxValue.textContent = mwMaxSlider.value;
            });
        }
        
        // LogP滑块
        const logpMinSlider = document.getElementById('logpMinSlider');
        const logpMaxSlider = document.getElementById('logpMaxSlider');
        const logpMinValue = document.getElementById('logpMinValue');
        const logpMaxValue = document.getElementById('logpMaxValue');
        if (logpMinSlider && logpMaxSlider && logpMinValue && logpMaxValue) {
            logpMinSlider.addEventListener('input', () => {
                if (parseFloat(logpMinSlider.value) > parseFloat(logpMaxSlider.value)) {
                    logpMinSlider.value = logpMaxSlider.value;
                }
                logpMinValue.textContent = parseFloat(logpMinSlider.value).toFixed(1);
            });
            logpMaxSlider.addEventListener('input', () => {
                if (parseFloat(logpMaxSlider.value) < parseFloat(logpMinSlider.value)) {
                    logpMaxSlider.value = logpMinSlider.value;
                }
                logpMaxValue.textContent = parseFloat(logpMaxSlider.value).toFixed(1);
            });
        }
        
        // HBD滑块
        const hbdMinSlider = document.getElementById('hbdMinSlider');
        const hbdMaxSlider = document.getElementById('hbdMaxSlider');
        const hbdMinValue = document.getElementById('hbdMinValue');
        const hbdMaxValue = document.getElementById('hbdMaxValue');
        if (hbdMinSlider && hbdMaxSlider && hbdMinValue && hbdMaxValue) {
            hbdMinSlider.addEventListener('input', () => {
                if (parseInt(hbdMinSlider.value) > parseInt(hbdMaxSlider.value)) {
                    hbdMinSlider.value = hbdMaxSlider.value;
                }
                hbdMinValue.textContent = hbdMinSlider.value;
            });
            hbdMaxSlider.addEventListener('input', () => {
                if (parseInt(hbdMaxSlider.value) < parseInt(hbdMinSlider.value)) {
                    hbdMaxSlider.value = hbdMinSlider.value;
                }
                hbdMaxValue.textContent = hbdMaxSlider.value;
            });
        }
        
        // HBA滑块
        const hbaMinSlider = document.getElementById('hbaMinSlider');
        const hbaMaxSlider = document.getElementById('hbaMaxSlider');
        const hbaMinValue = document.getElementById('hbaMinValue');
        const hbaMaxValue = document.getElementById('hbaMaxValue');
        if (hbaMinSlider && hbaMaxSlider && hbaMinValue && hbaMaxValue) {
            hbaMinSlider.addEventListener('input', () => {
                if (parseInt(hbaMinSlider.value) > parseInt(hbaMaxSlider.value)) {
                    hbaMinSlider.value = hbaMaxSlider.value;
                }
                hbaMinValue.textContent = hbaMinSlider.value;
            });
            hbaMaxSlider.addEventListener('input', () => {
                if (parseInt(hbaMaxSlider.value) < parseInt(hbaMinSlider.value)) {
                    hbaMaxSlider.value = hbaMinSlider.value;
                }
                hbaMaxValue.textContent = hbaMaxSlider.value;
            });
        }
        
        // RotBonds滑块
        const rotBondsMinSlider = document.getElementById('rotBondsMinSlider');
        const rotBondsMaxSlider = document.getElementById('rotBondsMaxSlider');
        const rotBondsMinValue = document.getElementById('rotBondsMinValue');
        const rotBondsMaxValue = document.getElementById('rotBondsMaxValue');
        if (rotBondsMinSlider && rotBondsMaxSlider && rotBondsMinValue && rotBondsMaxValue) {
            rotBondsMinSlider.addEventListener('input', () => {
                if (parseInt(rotBondsMinSlider.value) > parseInt(rotBondsMaxSlider.value)) {
                    rotBondsMinSlider.value = rotBondsMaxSlider.value;
                }
                rotBondsMinValue.textContent = rotBondsMinSlider.value;
            });
            rotBondsMaxSlider.addEventListener('input', () => {
                if (parseInt(rotBondsMaxSlider.value) < parseInt(rotBondsMinSlider.value)) {
                    rotBondsMaxSlider.value = rotBondsMinSlider.value;
                }
                rotBondsMaxValue.textContent = rotBondsMaxSlider.value;
            });
        }
        
        // QED滑块
        const qedSlider = document.getElementById('qedSlider');
        const qedValue = document.getElementById('qedValue');
        if (qedSlider && qedValue) {
            qedSlider.addEventListener('input', () => {
                qedValue.textContent = parseFloat(qedSlider.value).toFixed(2);
            });
        }
        
        // SA滑块
        const saSlider = document.getElementById('saSlider');
        const saValue = document.getElementById('saValue');
        if (saSlider && saValue) {
            saSlider.addEventListener('input', () => {
                saValue.textContent = parseFloat(saSlider.value).toFixed(1);
            });
        }
        
        // 样本数量滑块
        const sampleCountSlider = document.getElementById('sampleCountSlider');
        const sampleCountValue = document.getElementById('sampleCountValue');
        if (sampleCountSlider && sampleCountValue) {
            sampleCountSlider.addEventListener('input', () => {
                sampleCountValue.textContent = sampleCountSlider.value;
            });
        }
    }

    // 显示错误提示
    showErrorToast(message) {
        document.getElementById('errorToastBody').innerText = message;
        new bootstrap.Toast(document.getElementById('errorToast'), {
            autohide: true,
            delay: 3000
        }).show();
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
            // 使用自动消失Toast显示错误
            this.showErrorToast("启动失败，请检查后端连接");
            // 报错时恢复按钮
            trainBtn.disabled = false;
            trainBtn.innerHTML = `<i class="bi bi-rocket-takeoff"></i> 启动异步训练任务`;
        }
    }

    // 开始分子生成轮询
    async startGeneratePolling() {
        const genBtn = document.getElementById('genBtn');
        const statusText = document.getElementById('statusText') || (() => {
            // 创建状态文本元素
            const div = document.createElement('div');
            div.id = 'statusText';
            div.className = 'text-primary mt-2';
            document.querySelector('#genPanel .card').appendChild(div);
            return div;
        })();
        const logArea = document.getElementById('generateLogs') || (() => {
            // 创建日志区域元素
            const div = document.createElement('div');
            div.id = 'generateLogs';
            div.className = 'mt-2 p-2 bg-light rounded text-sm overflow-auto';
            div.style.maxHeight = '200px';
            document.querySelector('#genPanel .card').appendChild(div);
            return div;
        })();
        const progressBar = document.getElementById('generateProgressBar') || (() => {
            // 创建进度条元素
            const div = document.createElement('div');
            div.className = 'mt-2';
            div.innerHTML = `
                <div class="progress" style="height: 10px;">
                    <div id="generateProgressBar" class="progress-bar progress-bar-striped progress-bar-animated bg-primary" style="width: 0%;"></div>
                </div>
            `;
            document.querySelector('#genPanel .card').appendChild(div);
            return document.getElementById('generateProgressBar');
        })();
        
        let displayedCount = 0;

        this.pollInterval = setInterval(async () => {
            try {
                const res = await fetch('/get_generate_status');
                const data = await res.json();

                if (data.status === "generating" || data.status === "success" || data.status === "error") {
                    // 更新进度条
                    const progress = Math.round((data.current_sample / data.total_samples) * 100);
                    progressBar.style.width = progress + "%";

                    // 增量日志显示
                    if (data.logs && data.logs.length > displayedCount) {
                        for (let i = displayedCount; i < data.logs.length; i++) {
                            const div = document.createElement('div');
                            div.innerText = data.logs[i];
                            logArea.appendChild(div);
                            displayedCount++;
                        }
                        // 自动滚动到底部
                        logArea.scrollTop = logArea.scrollHeight;
                    }

                    // 当状态不再是 generating 时恢复按钮
                    if (data.status === "success" || data.status === "error") {
                        clearInterval(this.pollInterval);

                        genBtn.disabled = false;
                        genBtn.innerText = "执行生成";

                        if (data.status === "success") {
                            statusText.innerText = "✅ 分子生成已成功完成";
                            progressBar.classList.remove('progress-bar-animated');
                            
                            // 显示结果
                            if (data.valid_molecules && data.valid_molecules.length > 0) {
                                document.getElementById('emptyState').style.display = 'none';
                                document.getElementById('resultDisplay').style.display = 'block';
                                
                                // 默认显示最佳分子
                                const bestMol = data.best_mol || data.valid_molecules[0];
                                this.displayMolecule(bestMol);
                                
                                // 添加分子切换功能
                                this.addMoleculeSwitcher(data.valid_molecules);
                            }
                        } else {
                            statusText.innerText = "❌ 分子生成出现错误";
                            this.showErrorToast(data.error);
                        }
                    } else {
                        statusText.innerText = `分子生成中... 处理样本 ${data.current_sample}/${data.total_samples}`;
                    }
                }
            } catch (e) {
                console.error("轮询异常", e);
            }
        }, 800);
    }

    // 显示分子信息
    displayMolecule(mol) {
        document.getElementById('molImg').src = 'data:image/png;base64,' + mol.image;
        document.getElementById('smilesCode').innerText = mol.smiles;
        
        // 核心指标展示
        const metrics = mol.metrics;
        
        // QED星级展示
        document.getElementById('qedVal').innerText = metrics.qed;
        const starCount = Math.round(metrics.qed * 5);
        document.getElementById('qedStars').innerText = '⭐'.repeat(starCount) + '☆'.repeat(5 - starCount);
        
        // SA Score标签
        document.getElementById('saScoreVal').innerText = metrics.sa_score;
        let saTag = '';
        if (metrics.sa_score <= 3) {
            saTag = '<span class="text-success">✅ 易于合成</span>';
        } else if (metrics.sa_score <= 5) {
            saTag = '<span class="text-warning">⚠️ 中等难度</span>';
        } else {
            saTag = '<span class="text-danger">❌ 难以合成</span>';
        }
        document.getElementById('saTag').innerHTML = saTag;
        
        // 基础属性已经移到规则检查和雷达图中展示
        
        // Lipinski规则检查
        const totalViolations = metrics.lipinski_ro5_violations + metrics.veber_violations;
        let ruleBadge = '';
        if (totalViolations === 0) {
            ruleBadge = '<span class="badge bg-success">全部通过</span>';
        } else {
            ruleBadge = `<span class="badge bg-warning">违反 ${totalViolations} 项</span>`;
        }
        document.getElementById('ruleStatusBadge').innerHTML = ruleBadge;
        
        // Lipinski详情
        document.getElementById('lipinskiStatus').innerHTML = metrics.lipinski_ro5_violations === 0 
            ? '<span class="text-success">✅ 通过</span>' 
            : `<span class="text-warning">⚠️ 违反 ${metrics.lipinski_ro5_violations} 项</span>`;
        
        const lipinskiChecks = metrics.lipinski_checks;
        document.getElementById('lipinskiMwCheck').innerHTML = lipinskiChecks.mw 
            ? `<span class="text-success">✓ 分子量 (MW): ${metrics.mw} ≤ 500</span>`
            : `<span class="text-danger">✗ 分子量 (MW): ${metrics.mw} > 500</span>`;
        document.getElementById('lipinskiLogpCheck').innerHTML = lipinskiChecks.logp 
            ? `<span class="text-success">✓ 亲油性 (LogP): ${metrics.logp} ≤ 5</span>`
            : `<span class="text-danger">✗ 亲油性 (LogP): ${metrics.logp} > 5</span>`;
        document.getElementById('lipinskiHbdCheck').innerHTML = lipinskiChecks.hbd 
            ? `<span class="text-success">✓ 氢键供体 (HBD): ${metrics.hbd} ≤ 5</span>`
            : `<span class="text-danger">✗ 氢键供体 (HBD): ${metrics.hbd} > 5</span>`;
        document.getElementById('lipinskiHbaCheck').innerHTML = lipinskiChecks.hba 
            ? `<span class="text-success">✓ 氢键受体 (HBA): ${metrics.hba} ≤ 10</span>`
            : `<span class="text-danger">✗ 氢键受体 (HBA): ${metrics.hba} > 10</span>`;
        
        // Veber规则检查
        document.getElementById('veberStatus').innerHTML = metrics.veber_violations === 0 
            ? '<span class="text-success">✅ 通过</span>' 
            : `<span class="text-warning">⚠️ 违反 ${metrics.veber_violations} 项</span>`;
        
        const veberChecks = metrics.veber_checks;
        document.getElementById('veberRotBondsCheck').innerHTML = veberChecks.rot_bonds 
            ? `<span class="text-success">✓ 可旋转键 (RotB): ${metrics.rot_bonds} ≤ 10</span>`
            : `<span class="text-danger">✗ 可旋转键 (RotB): ${metrics.rot_bonds} > 10</span>`;
        document.getElementById('veberTpsaCheck').innerHTML = veberChecks.tpsa 
            ? `<span class="text-success">✓ 极性表面积 (TPSA): ${metrics.tpsa} ≤ 140 Å²</span>`
            : `<span class="text-danger">✗ 极性表面积 (TPSA): ${metrics.tpsa} > 140 Å²</span>`;
        
        // 绘制雷达图
        this.renderRadarChart(metrics);
    }

    // 添加分子切换功能
    addMoleculeSwitcher(molecules) {
        const switcherContainer = document.getElementById('moleculeSwitcher') || (() => {
            // 创建分子切换器容器
            const div = document.createElement('div');
            div.id = 'moleculeSwitcher';
            div.className = 'mt-3';
            document.querySelector('#resultDisplay').insertBefore(div, document.querySelector('#resultDisplay > div'));
            return div;
        })();
        
        // 清空切换器内容
        switcherContainer.innerHTML = `
            <h6 class="mb-2 text-primary">生成的分子列表</h6>
            <div class="d-flex flex-wrap gap-2">
                ${molecules.map((mol, index) => `
                    <button class="btn btn-sm ${index === 0 ? 'btn-primary' : 'btn-outline-primary'}" onclick="window.moleculeApp.switchMolecule(${index})">
                        分子 ${index + 1} (分数: ${mol.score.toFixed(2)})
                    </button>
                `).join('')}
            </div>
        `;
        
        // 保存分子列表到实例
        this.generatedMolecules = molecules;
    }

    // 切换分子
    switchMolecule(index) {
        if (this.generatedMolecules && this.generatedMolecules[index]) {
            this.displayMolecule(this.generatedMolecules[index]);
            // 更新按钮状态
            const buttons = document.querySelectorAll('#moleculeSwitcher button');
            buttons.forEach((btn, i) => {
                if (i === index) {
                    btn.className = 'btn btn-sm btn-primary';
                } else {
                    btn.className = 'btn btn-sm btn-outline-primary';
                }
            });
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
                    model_file: document.getElementById('modelSelect').value,
                    sample_count: parseInt(document.getElementById('sampleCountSlider').value),
                    // 分子约束参数
                    constraints: {
                        // 使用滑块值作为约束参数
                        mw_range: [
                            parseInt(document.getElementById('mwMinSlider').value),
                            parseInt(document.getElementById('mwMaxSlider').value)
                        ],
                        logp_range: [
                            parseFloat(document.getElementById('logpMinSlider').value),
                            parseFloat(document.getElementById('logpMaxSlider').value)
                        ],
                        hbd_range: [
                            parseInt(document.getElementById('hbdMinSlider').value),
                            parseInt(document.getElementById('hbdMaxSlider').value)
                        ],
                        hba_range: [
                            parseInt(document.getElementById('hbaMinSlider').value),
                            parseInt(document.getElementById('hbaMaxSlider').value)
                        ],
                        rot_bonds_range: [
                            parseInt(document.getElementById('rotBondsMinSlider').value),
                            parseInt(document.getElementById('rotBondsMaxSlider').value)
                        ],
                        qed_min: parseFloat(document.getElementById('qedSlider').value),
                        sa_score_max: parseFloat(document.getElementById('saSlider').value)
                    }
                })
            });
            const data = await res.json();
            
            if (!data.error) {
                // 无论响应如何，只要没有错误就开始轮询生成状态
                this.startGeneratePolling();
            } else {
                // 使用自动消失Toast显示错误
                this.showErrorToast(data.error);
                genBtn.disabled = false;
                genBtn.innerText = "执行生成";
            }
        } catch (e) {
            console.error("生成请求失败:", e);
            this.showErrorToast("生成请求失败: " + e.message);
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