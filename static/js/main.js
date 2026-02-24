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
        document.getElementById('mwMinSlider').value = 50;
        document.getElementById('mwMaxSlider').value = 600;
        document.getElementById('mwMinValue').textContent = '50';
        document.getElementById('mwMaxValue').textContent = '600';
        
        // LogP默认值
        document.getElementById('logpMinSlider').value = -3;
        document.getElementById('logpMaxSlider').value = 7;
        document.getElementById('logpMinValue').textContent = '-3.0';
        document.getElementById('logpMaxValue').textContent = '7.0';
        
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
        document.getElementById('qedSlider').value = 0.3;
        document.getElementById('qedValue').textContent = '0.3';
        
        // SA默认值
        document.getElementById('saSlider').value = 6.0;
        document.getElementById('saValue').textContent = '6.0';
        
        // 样本数量默认值
        document.getElementById('sampleCountSlider').value = 100;
        document.getElementById('sampleCountValue').textContent = '100';
        document.getElementById('decodeBatchSizeSelect').value = '8';
        document.getElementById('tanimotoSlider').value = 0.85;
        document.getElementById('tanimotoValue').textContent = '0.85';
        
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
        
        // 模型与采样设置折叠事件
        const genSampleSettings = document.getElementById('genSampleSettings');
        const genSampleIcon = document.querySelector('[data-bs-target="#genSampleSettings"] i');
        if (genSampleSettings && genSampleIcon) {
            genSampleSettings.addEventListener('show.bs.collapse', () => {
                genSampleIcon.classList.remove('bi-chevron-right');
                genSampleIcon.classList.add('bi-chevron-down');
            });
            genSampleSettings.addEventListener('hide.bs.collapse', () => {
                genSampleIcon.classList.remove('bi-chevron-down');
                genSampleIcon.classList.add('bi-chevron-right');
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
        const tanimotoSlider = document.getElementById('tanimotoSlider');
        const tanimotoValue = document.getElementById('tanimotoValue');
        if (tanimotoSlider && tanimotoValue) {
            tanimotoSlider.addEventListener('input', () => {
                tanimotoValue.textContent = tanimotoSlider.value;
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
        const statusEl = document.getElementById('trainStatusText');
        const progressPercentEl = document.getElementById('trainProgressPercent');
        const logArea = document.getElementById('trainLogs');
        const trainBtn = document.getElementById('trainBtn');

        this.pollInterval = setInterval(async () => {
            try {
                const res = await fetch('/get_train_status');
                const data = await res.json();

                if (data.status === "training" || data.status === "success" || data.status === "error") {
                    const progress = data.total_epochs ? Math.round((data.current_epoch / data.total_epochs) * 100) : 0;
                    progressBar.style.width = progress + "%";
                    if (progressPercentEl) progressPercentEl.textContent = progress + "%";

                    if (data.logs && data.logs.length > this.displayedCount) {
                        for (let i = this.displayedCount; i < data.logs.length; i++) {
                            const div = document.createElement('div');
                            div.innerText = data.logs[i];
                            logArea.appendChild(div);
                            this.displayedCount++;
                        }
                        logArea.scrollTop = logArea.scrollHeight;
                    }

                    if (data.status === "success" || data.status === "error") {
                        clearInterval(this.pollInterval);
                        trainBtn.disabled = false;
                        trainBtn.innerHTML = `<i class="bi bi-rocket-takeoff me-2"></i>启动训练`;
                        if (data.status === "success") {
                            if (statusEl) statusEl.innerText = "✅ 训练已成功完成";
                            progressBar.classList.remove('progress-bar-animated');
                            this.loadModels();
                        } else {
                            if (statusEl) statusEl.innerText = "❌ 训练出现错误";
                        }
                    } else {
                        if (statusEl) statusEl.innerText = "模型训练中...";
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
        trainBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2"></span>训练中...`;

        // 重置 UI 状态：显示进度卡片、隐藏占位提示
        document.getElementById('trainNotify').classList.remove('d-none');
        const idleHint = document.getElementById('trainIdleHint');
        if (idleHint) idleHint.classList.add('d-none');
        document.getElementById('trainLogs').innerHTML = "";
        const pct = document.getElementById('trainProgressPercent');
        if (pct) pct.textContent = "0%";
        this.displayedCount = 0;

        const formData = new FormData(e.target);
        try {
            const res = await fetch('/start_train', { method: 'POST', body: formData });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || data.error) {
                this.showErrorToast(data.error || "启动失败，请稍后重试");
                trainBtn.disabled = false;
                trainBtn.innerHTML = `<i class="bi bi-rocket-takeoff me-2"></i>启动训练`;
                return;
            }
            this.startPolling(); // 开始监听后端 logs 列表
        } catch (e) {
            this.showErrorToast("启动失败，请检查后端连接");
            trainBtn.disabled = false;
            trainBtn.innerHTML = `<i class="bi bi-rocket-takeoff me-2"></i>启动训练`;
        }
    }

    // 开始分子生成轮询
    async startGeneratePolling() {
        const genBtn = document.getElementById('genBtn');
        const statusEl = document.getElementById('genStatusText');
        const progressPercentEl = document.getElementById('genProgressPercent');
        const logArea = document.getElementById('generateLogs');
        const progressBar = document.getElementById('generateProgressBar');
        let displayedCount = 0;

        this.pollInterval = setInterval(async () => {
            try {
                const res = await fetch('/get_generate_status');
                const data = await res.json();

                if (data.status === "generating" || data.status === "success" || data.status === "error") {
                    const total = data.total_samples || 1;
                    const progress = Math.round((data.current_sample / total) * 100);
                    if (progressBar) progressBar.style.width = progress + "%";
                    if (progressPercentEl) progressPercentEl.textContent = progress + "%";

                    if (data.logs && data.logs.length > displayedCount) {
                        for (let i = displayedCount; i < data.logs.length; i++) {
                            const div = document.createElement('div');
                            div.innerText = data.logs[i];
                            logArea.appendChild(div);
                            displayedCount++;
                        }
                        logArea.scrollTop = logArea.scrollHeight;
                    }

                    if (data.status === "success" || data.status === "error") {
                        clearInterval(this.pollInterval);
                        genBtn.disabled = false;
                        genBtn.innerText = "执行生成";
                        if (data.status === "success") {
                            if (statusEl) {
                                statusEl.innerText = "✅ 分子生成已成功完成";
                                statusEl.classList.remove('d-none');
                            }
                            if (progressBar) progressBar.classList.remove('progress-bar-animated');
                            const emptyEl = document.getElementById('emptyState');
                            const resultEl = document.getElementById('resultDisplay');
                            if (data.valid_molecules && data.valid_molecules.length > 0) {
                                if (emptyEl) emptyEl.style.display = 'none';
                                if (resultEl) resultEl.style.display = 'block';
                                const bestMol = data.best_mol || data.valid_molecules[0];
                                this.displayMolecule(bestMol);
                                this.addMoleculeSwitcher(data.valid_molecules);
                            } else {
                                if (emptyEl) {
                                    emptyEl.style.display = 'block';
                                    emptyEl.innerHTML = '<i class="bi bi-info-circle display-6 text-secondary"></i><p class="mt-3 text-muted">本次未生成满足条件的分子，可放宽约束后重试。</p>';
                                }
                                if (resultEl) resultEl.style.display = 'none';
                            }
                        } else {
                            if (statusEl) statusEl.innerText = "❌ 分子生成出现错误";
                            this.showErrorToast(data.error);
                        }
                    } else {
                        if (statusEl) statusEl.innerText = `生成中 ${data.current_sample}/${data.total_samples}`;
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
        const relaxedHint = document.getElementById('relaxedConstraintHint');
        if (relaxedHint) {
            if (mol.relaxed) {
                relaxedHint.classList.remove('d-none');
            } else {
                relaxedHint.classList.add('d-none');
            }
        }
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
        
        // ADMET 评估展示
        const logS = metrics.log_solubility != null ? metrics.log_solubility : '—';
        const solLabel = metrics.solubility_label || '—';
        const perm = metrics.permeability || '—';
        const bbb = metrics.bbb_potential || '—';
        const mr = metrics.mol_refractivity != null ? metrics.mol_refractivity : '—';
        const riskCount = metrics.risk_substructure_count != null ? metrics.risk_substructure_count : '—';
        const riskSummary = metrics.risk_summary || '—';
        document.getElementById('admetLogS').innerText = logS;
        document.getElementById('admetSolubilityLabel').innerText = typeof solLabel === 'string' ? solLabel : '—';
        document.getElementById('admetPermeability').innerText = perm;
        document.getElementById('admetBBB').innerText = bbb;
        document.getElementById('admetMR').innerText = mr;
        document.getElementById('admetRiskCount').innerText = riskCount;
        document.getElementById('admetRiskSummary').innerText = riskSummary;
        
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
    }

    // 添加分子切换功能（下拉 + 上一个/下一个）
    addMoleculeSwitcher(molecules) {
        const switcherContainer = document.getElementById('moleculeSwitcher') || (() => {
            const div = document.createElement('div');
            div.id = 'moleculeSwitcher';
            div.className = 'mt-3';
            document.querySelector('#resultDisplay').insertBefore(div, document.querySelector('#resultDisplay > div'));
            return div;
        })();

        const select = document.createElement('select');
        select.id = 'moleculeSelect';
        select.className = 'form-select';
        select.innerHTML = molecules.map((mol, index) => {
            const score = mol.score != null ? mol.score.toFixed(2) : '—';
            return `<option value="${index}">分子 ${index + 1} (分数: ${score})</option>`;
        }).join('');
        select.addEventListener('change', () => {
            const index = parseInt(select.value, 10);
            if (!isNaN(index) && this.generatedMolecules && this.generatedMolecules[index]) {
                this.displayMolecule(this.generatedMolecules[index]);
                this.updatePrevNextButtons();
            }
        });

        const prevBtn = document.createElement('button');
        prevBtn.type = 'button';
        prevBtn.className = 'btn btn-sm btn-outline-primary';
        prevBtn.textContent = '上一个';
        prevBtn.id = 'moleculePrevBtn';
        prevBtn.addEventListener('click', () => {
            const sel = document.getElementById('moleculeSelect');
            if (!sel || !this.generatedMolecules || this.generatedMolecules.length === 0) return;
            const idx = parseInt(sel.value, 10);
            if (idx > 0) this.switchMolecule(idx - 1);
            this.updatePrevNextButtons();
        });

        const nextBtn = document.createElement('button');
        nextBtn.type = 'button';
        nextBtn.className = 'btn btn-sm btn-outline-primary';
        nextBtn.textContent = '下一个';
        nextBtn.id = 'moleculeNextBtn';
        nextBtn.addEventListener('click', () => {
            const sel = document.getElementById('moleculeSelect');
            if (!sel || !this.generatedMolecules || this.generatedMolecules.length === 0) return;
            const idx = parseInt(sel.value, 10);
            if (idx < this.generatedMolecules.length - 1) this.switchMolecule(idx + 1);
            this.updatePrevNextButtons();
        });

        switcherContainer.innerHTML = '';
        const label = document.createElement('label');
        label.className = 'form-label text-primary mb-1';
        label.textContent = '切换分子 (按分数从高到低)';
        switcherContainer.appendChild(label);
        const row = document.createElement('div');
        row.className = 'd-flex align-items-center gap-2 flex-wrap';
        row.appendChild(select);
        row.appendChild(prevBtn);
        row.appendChild(nextBtn);
        switcherContainer.appendChild(row);
        this.generatedMolecules = molecules;
        this.updatePrevNextButtons();
    }

    updatePrevNextButtons() {
        const select = document.getElementById('moleculeSelect');
        const prevBtn = document.getElementById('moleculePrevBtn');
        const nextBtn = document.getElementById('moleculeNextBtn');
        if (!select || !prevBtn || !nextBtn || !this.generatedMolecules || this.generatedMolecules.length === 0) return;
        const idx = parseInt(select.value, 10);
        const total = this.generatedMolecules.length;
        prevBtn.disabled = idx <= 0;
        nextBtn.disabled = idx >= total - 1;
    }

    // 切换分子（供外部或下拉/按钮调用）
    switchMolecule(index) {
        if (this.generatedMolecules && this.generatedMolecules[index]) {
            this.displayMolecule(this.generatedMolecules[index]);
            const select = document.getElementById('moleculeSelect');
            if (select) select.value = String(index);
        }
    }

    // 生成分子
    async generateMolecule() {
        const genBtn = document.getElementById('genBtn');
        genBtn.disabled = true;
        genBtn.innerText = "生成中...";
        const genStatus = document.getElementById('genStatusText');
        const genPct = document.getElementById('genProgressPercent');
        if (genStatus) genStatus.innerText = "任务已提交，等待进度...";
        if (genPct) genPct.textContent = "0%";
        const gp = document.getElementById('generateProgressBar');
        if (gp) gp.style.width = "0%";
        const genLogs = document.getElementById('generateLogs');
        if (genLogs) genLogs.innerHTML = "";
        
        try {
            const res = await fetch('/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    model_file: document.getElementById('modelSelect').value,
                    sample_count: parseInt(document.getElementById('sampleCountSlider').value),
                    decode_batch_size: parseInt(document.getElementById('decodeBatchSizeSelect').value),
                    tanimoto_threshold: parseFloat(document.getElementById('tanimotoSlider').value),
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
            const data = await res.json().catch(() => ({}));
            if (!res.ok || data.error) {
                this.showErrorToast(data.error || "生成请求失败，请稍后重试");
                genBtn.disabled = false;
                genBtn.innerText = "执行生成";
                return;
            }
            this.startGeneratePolling();
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