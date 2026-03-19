// 分子设计平台主模块
class MoleculeDesignPlatform {
    constructor() {
        this.pollInterval = null;
        this.scaffoldPollInterval = null;
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
        
        // 骨架优化按钮
        const scaffoldOptimizeBtn = document.getElementById('scaffoldOptimizeBtn');
        if (scaffoldOptimizeBtn) scaffoldOptimizeBtn.onclick = () => this.runScaffoldOptimize();
        
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
    
    bindCollapseEvents() {
        ['lipinskiRules', 'qualityScores', 'ruleChecks'].forEach(id => {
            const el = document.getElementById(id);
            const icon = document.querySelector(`[data-bs-target="#${id}"] i`);
            if (!el || !icon) return;
            el.addEventListener('show.bs.collapse', () => { icon.classList.replace('bi-chevron-right', 'bi-chevron-down'); });
            el.addEventListener('hide.bs.collapse', () => { icon.classList.replace('bi-chevron-down', 'bi-chevron-right'); });
        });
    }
    
    // 绑定范围滑块对（min/max 联动），format 控制显示格式
    _bindRangeSliderPair(minId, maxId, minValId, maxValId, format) {
        const minS = document.getElementById(minId);
        const maxS = document.getElementById(maxId);
        const minV = document.getElementById(minValId);
        const maxV = document.getElementById(maxValId);
        if (!minS || !maxS || !minV || !maxV) return;
        const parse = format === 'float' ? parseFloat : (v) => parseInt(v, 10);
        const display = format === 'float' ? (v) => parseFloat(v).toFixed(1) : (v) => v;
        minS.addEventListener('input', () => {
            if (parse(minS.value) > parse(maxS.value)) minS.value = maxS.value;
            minV.textContent = display(minS.value);
        });
        maxS.addEventListener('input', () => {
            if (parse(maxS.value) < parse(minS.value)) maxS.value = minS.value;
            maxV.textContent = display(maxS.value);
        });
    }

    // 绑定单值滑块
    _bindSingleSlider(sliderId, valueId, format) {
        const slider = document.getElementById(sliderId);
        const valueEl = document.getElementById(valueId);
        if (!slider || !valueEl) return;
        slider.addEventListener('input', () => { valueEl.textContent = format(slider.value); });
    }

    bindSliderEvents() {
        // 5 组范围滑块
        this._bindRangeSliderPair('mwMinSlider', 'mwMaxSlider', 'mwMinValue', 'mwMaxValue', 'int');
        this._bindRangeSliderPair('logpMinSlider', 'logpMaxSlider', 'logpMinValue', 'logpMaxValue', 'float');
        this._bindRangeSliderPair('hbdMinSlider', 'hbdMaxSlider', 'hbdMinValue', 'hbdMaxValue', 'int');
        this._bindRangeSliderPair('hbaMinSlider', 'hbaMaxSlider', 'hbaMinValue', 'hbaMaxValue', 'int');
        this._bindRangeSliderPair('rotBondsMinSlider', 'rotBondsMaxSlider', 'rotBondsMinValue', 'rotBondsMaxValue', 'int');

        // 单值滑块
        this._bindSingleSlider('qedSlider', 'qedValue', v => parseFloat(v).toFixed(2));
        this._bindSingleSlider('saSlider', 'saValue', v => parseFloat(v).toFixed(1));
        this._bindSingleSlider('sampleCountSlider', 'sampleCountValue', v => v);
        this._bindSingleSlider('scaffoldNumSlider', 'scaffoldNumValue', v => v);
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
        const scaffoldPanel = document.getElementById('scaffoldPanel');
        if (scaffoldPanel) scaffoldPanel.style.display = id === 'scaffoldPanel' ? 'block' : 'none';
        document.getElementById('trainPanel').style.display = id === 'trainPanel' ? 'block' : 'none';
    }

    // 骨架跃迁与优化：提交任务并轮询结果
    async runScaffoldOptimize() {
        const hitSmiles = (document.getElementById('scaffoldHitSmiles') && document.getElementById('scaffoldHitSmiles').value || '').trim();
        if (!hitSmiles) {
            this.showErrorToast('请填写苗头化合物 SMILES');
            return;
        }
        const targetProperty = document.getElementById('scaffoldTargetProperty') && document.getElementById('scaffoldTargetProperty').value || 'log_solubility';
        const optimizeDirection = document.getElementById('scaffoldDirection') && document.getElementById('scaffoldDirection').value || 'max';
        const numCandidates = parseInt(document.getElementById('scaffoldNumSlider') && document.getElementById('scaffoldNumSlider').value || 100, 10);

        try {
            const scaffoldModel = document.getElementById('scaffoldModelSelect') && document.getElementById('scaffoldModelSelect').value || '';
            const res = await fetch('/scaffold_optimize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    hit_smiles: hitSmiles,
                    target_property: targetProperty,
                    optimize_direction: optimizeDirection,
                    num_candidates: numCandidates,
                    model_file: scaffoldModel
                })
            });
            const data = await res.json();
            if (!res.ok) {
                this.showErrorToast(data.error || '请求失败');
                return;
            }
            this.startScaffoldOptimizePolling();
        } catch (e) {
            this.showErrorToast('网络错误: ' + (e.message || ''));
        }
    }

    startScaffoldOptimizePolling() {
        const progressBar = document.getElementById('scaffoldProgressBar');
        const progressPercentEl = document.getElementById('scaffoldProgressPercent');
        const logArea = document.getElementById('scaffoldLogs');
        const btn = document.getElementById('scaffoldOptimizeBtn');
        if (btn) btn.disabled = true;

        const escapeHtml = (str) => ('' + (str ?? '')).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
        const updateUI = (data) => {
            const total = data.total_samples || 1;
            const current = data.current_sample || 0;
            const pct = total ? Math.round((current / total) * 100) : 0;
            if (progressBar) progressBar.style.width = pct + '%';
            if (progressPercentEl) progressPercentEl.textContent = pct + '%';
            if (logArea && Array.isArray(data.logs)) {
                logArea.innerHTML = data.logs.map(l => `<div class="log-line">${escapeHtml(l)}</div>`).join('');
                logArea.scrollTop = logArea.scrollHeight;
            }
        };

        const stopPolling = () => {
            if (this.scaffoldPollInterval) {
                clearInterval(this.scaffoldPollInterval);
                this.scaffoldPollInterval = null;
            }
            if (btn) btn.disabled = false;
        };

        const poll = async () => {
            try {
                const res = await fetch('/get_scaffold_optimize_status');
                const data = await res.json();
                updateUI(data);
                if (data.status === 'success') {
                    stopPolling();
                    const resultEl = document.getElementById('scaffoldResultDisplay');
                    const emptyEl = document.getElementById('scaffoldEmptyState');
                    const derivatives = data.derivatives || [];
                    if (derivatives.length > 0) {
                        if (emptyEl) emptyEl.style.display = 'none';
                        if (resultEl) resultEl.style.display = 'block';
                        const hitImg = document.getElementById('scaffoldHitImg');
                        const hitSmilesEl = document.getElementById('scaffoldHitSmilesDisplay');
                        if (hitImg && data.hit_image) hitImg.src = 'data:image/png;base64,' + data.hit_image;
                        if (hitSmilesEl && data.hit_smiles) hitSmilesEl.innerText = data.hit_smiles;
                        window.moleculeApp.scaffoldHitMetrics = data.hit_metrics || {};
                        const list = derivatives.map(d => ({ ...d, metrics: d.metrics || {} }));
                        window.moleculeApp.scaffoldDerivatives = list;
                        window.moleculeApp.displayScaffoldMolecule(list[0]);
                        window.moleculeApp.addScaffoldSwitcher(list, data.target_property);
                    } else {
                        if (resultEl) resultEl.style.display = 'none';
                        if (emptyEl) {
                            emptyEl.style.display = 'block';
                            emptyEl.innerHTML = `
                                <i class="bi bi-exclamation-circle display-4 text-warning"></i>
                                <p class="mt-3 mb-2 fw-bold">未得到有效衍生物</p>
                                <p class="small text-muted mb-1">本次未得到可用衍生物。</p>
                                <p class="small text-muted mb-0">建议：更换 Hit 或调整目标性质后重试。</p>
                                ${(data.hit_scaffold ? `<p class="small text-muted mt-2 mb-0">当前 Hit 骨架: <code>${escapeHtml(data.hit_scaffold)}</code></p>` : '')}
                            `;
                        }
                    }
                }
                if (data.status === 'error') {
                    stopPolling();
                    this.showErrorToast(data.error || '骨架优化失败');
                }
            } catch (e) {
                stopPolling();
                this.showErrorToast('轮询失败');
            }
        };

        poll();
        this.scaffoldPollInterval = setInterval(poll, 1500);
    }

    // 加载模型列表
    async loadModels() {
        try {
            const res = await fetch('/get_models');
            const data = await res.json();
            const models = data.models || [];
            const optionsHtml = models.length
                ? models.map(m => `<option value="${m}">${m}</option>`).join('')
                : '<option value="">暂无模型</option>';
            const modelSelect = document.getElementById('modelSelect');
            if (modelSelect) modelSelect.innerHTML = optionsHtml;
            const scaffoldModelSelect = document.getElementById('scaffoldModelSelect');
            if (scaffoldModelSelect) scaffoldModelSelect.innerHTML = optionsHtml;
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

    // 骨架优化：展示单个衍生物（与 Hit 对比）
    displayScaffoldMolecule(mol) {
        if (!mol) return;
        const imgEl = document.getElementById('scaffoldMolImg');
        const smilesEl = document.getElementById('scaffoldSmilesCode');
        if (imgEl) imgEl.src = mol.image ? 'data:image/png;base64,' + mol.image : '';
        if (smilesEl) smilesEl.innerText = mol.smiles || '';
        const metrics = mol.metrics || {};
        const hitMetrics = this.scaffoldHitMetrics || {};
        const tbody = document.getElementById('scaffoldCompareTableBody');
        const mkNum = (v, d = 3) => (v == null || Number.isNaN(Number(v))) ? '—' : Number(v).toFixed(d);
        const mkDiff = (a, b, reverseGood = false) => {
            if (a == null || b == null || Number.isNaN(Number(a)) || Number.isNaN(Number(b))) return '—';
            const delta = Number(b) - Number(a);
            const sign = delta > 0 ? '+' : '';
            const good = reverseGood ? (delta < 0) : (delta > 0);
            const cls = delta === 0 ? 'text-muted' : (good ? 'text-success' : 'text-danger');
            return `<span class=\"${cls}\">${sign}${delta.toFixed(3)}</span>`;
        };
        if (tbody) {
            const rows = [
                ['QED', hitMetrics.qed, metrics.qed, false, 3],
                ['logP', hitMetrics.logp, metrics.logp, false, 3],
                ['MW', hitMetrics.mw, metrics.mw, false, 2],
                ['HBD', hitMetrics.hbd, metrics.hbd, true, 0],
                ['HBA', hitMetrics.hba, metrics.hba, true, 0],
                ['TPSA', hitMetrics.tpsa, metrics.tpsa, false, 2],
                ['SA Score', hitMetrics.sa_score, metrics.sa_score, true, 3],
                ['ESOL logS', hitMetrics.log_solubility, metrics.log_solubility, false, 3],
            ];
            tbody.innerHTML = rows.map(([name, hv, cv, reverseGood, digits]) => `
                <tr>
                    <td>${name}</td>
                    <td>${mkNum(hv, digits)}</td>
                    <td><strong>${mkNum(cv, digits)}</strong></td>
                    <td>${mkDiff(hv, cv, reverseGood)}</td>
                </tr>
            `).join('');
        }

    }

    addScaffoldSwitcher(derivatives, targetProperty) {
        const container = document.getElementById('scaffoldSwitcher');
        if (!container) return;
        const propLabel = targetProperty === 'log_solubility' ? '水溶性' : (targetProperty === 'qed' ? 'QED' : targetProperty);
        const select = document.createElement('select');
        select.id = 'scaffoldMoleculeSelect';
        select.className = 'form-select';
        select.innerHTML = derivatives.map((mol, i) => {
            const val = mol.target_value != null ? Number(mol.target_value).toFixed(3) : '—';
            return `<option value="${i}">分子 ${i + 1} (${propLabel}: ${val})</option>`;
        }).join('');
        select.addEventListener('change', () => {
            const idx = parseInt(select.value, 10);
            if (!isNaN(idx) && this.scaffoldDerivatives && this.scaffoldDerivatives[idx]) {
                this.displayScaffoldMolecule(this.scaffoldDerivatives[idx]);
                this.updateScaffoldPrevNextButtons();
            }
        });
        const prevBtn = document.createElement('button');
        prevBtn.type = 'button';
        prevBtn.className = 'btn btn-sm btn-outline-primary';
        prevBtn.textContent = '上一个';
        prevBtn.id = 'scaffoldPrevBtn';
        prevBtn.addEventListener('click', () => {
            const sel = document.getElementById('scaffoldMoleculeSelect');
            if (!sel || !this.scaffoldDerivatives || !this.scaffoldDerivatives.length) return;
            const idx = parseInt(sel.value, 10);
            if (idx > 0) this.switchScaffoldMolecule(idx - 1);
            this.updateScaffoldPrevNextButtons();
        });
        const nextBtn = document.createElement('button');
        nextBtn.type = 'button';
        nextBtn.className = 'btn btn-sm btn-outline-primary';
        nextBtn.textContent = '下一个';
        nextBtn.id = 'scaffoldNextBtn';
        nextBtn.addEventListener('click', () => {
            const sel = document.getElementById('scaffoldMoleculeSelect');
            if (!sel || !this.scaffoldDerivatives || !this.scaffoldDerivatives.length) return;
            const idx = parseInt(sel.value, 10);
            if (idx < this.scaffoldDerivatives.length - 1) this.switchScaffoldMolecule(idx + 1);
            this.updateScaffoldPrevNextButtons();
        });
        container.innerHTML = '';
        const label = document.createElement('label');
        label.className = 'form-label text-primary mb-1';
        label.textContent = '切换衍生物 (按目标性质排序)';
        container.appendChild(label);
        const row = document.createElement('div');
        row.className = 'd-flex align-items-center gap-2 flex-wrap';
        row.appendChild(select);
        row.appendChild(prevBtn);
        row.appendChild(nextBtn);
        container.appendChild(row);
        this.scaffoldDerivatives = derivatives;
        this.updateScaffoldPrevNextButtons();
    }

    updateScaffoldPrevNextButtons() {
        const select = document.getElementById('scaffoldMoleculeSelect');
        const prevBtn = document.getElementById('scaffoldPrevBtn');
        const nextBtn = document.getElementById('scaffoldNextBtn');
        if (!select || !prevBtn || !nextBtn || !this.scaffoldDerivatives || !this.scaffoldDerivatives.length) return;
        const idx = parseInt(select.value, 10);
        const total = this.scaffoldDerivatives.length;
        prevBtn.disabled = idx <= 0;
        nextBtn.disabled = idx >= total - 1;
    }

    switchScaffoldMolecule(index) {
        if (this.scaffoldDerivatives && this.scaffoldDerivatives[index]) {
            this.displayScaffoldMolecule(this.scaffoldDerivatives[index]);
            const select = document.getElementById('scaffoldMoleculeSelect');
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
                    decode_batch_size: 4,
                    tanimoto_threshold: 0.90,
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

// 页面加载完成后初始化应用
window.addEventListener('DOMContentLoaded', () => {
    window.moleculeApp = new MoleculeDesignPlatform();
});