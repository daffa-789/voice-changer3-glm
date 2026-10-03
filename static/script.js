// ═══════════════════════════════════════════════════════════
// VOICE CHANGER PRO — Frontend Logic (Applio-style Pairing)
// ═══════════════════════════════════════════════════════════
'use strict';

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const DEFAULTS = { pitch: 0, indexRate: 0.75, f0Method: 'rmvpe', autoEnhance: true };

const TOAST_ICONS = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
function showToast(message, type = 'info', timeout = 4000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = document.createElement('span');
    icon.className = 'toast-icon';
    icon.textContent = TOAST_ICONS[type] || TOAST_ICONS.info;
    const msg = document.createElement('span');
    msg.textContent = message;
    toast.append(icon, msg);
    document.body.appendChild(toast);

    const remove = () => {
        toast.classList.add('fade-out');
        toast.addEventListener('animationend', () => toast.remove(), { once: true });
    };
    const t = setTimeout(remove, timeout);
    toast.addEventListener('click', () => { clearTimeout(t); remove(); });
}

function initTheme() {
    const saved = localStorage.getItem('vc-theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const theme = saved || (prefersDark ? 'dark' : 'light');
    applyTheme(theme);
    const btn = $('#themeToggle');
    if (btn) {
        btn.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme');
            applyTheme(current === 'dark' ? 'light' : 'dark');
        });
    }
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('vc-theme', theme);
    const btn = $('#themeToggle');
    if (btn) btn.textContent = theme === 'dark' ? '🌙' : '☀️';
}

async function api(url, { method = 'GET', body, formEntries, okMessage } = {}) {
    try {
        let res;
        if (body instanceof FormData) {
            res = await fetch(url, { method, body });
        } else if (formEntries) {
            const fd = new FormData();
            for (const [k, v] of Object.entries(formEntries)) {
                if (v !== null && v !== undefined) fd.append(k, v);
            }
            res = await fetch(url, { method, body: fd });
        } else {
            res = await fetch(url, { method });
        }
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            const detail = data.detail || data.error || `HTTP ${res.status}`;
            if (okMessage) showToast(`${okMessage} gagal: ${detail}`, 'error');
            return { ok: false, error: detail, data };
        }
        return { ok: true, data };
    } catch (err) {
        console.error(err);
        if (okMessage) showToast(`${okMessage} gagal. Cek koneksi server.`, 'error');
        return { ok: false, error: String(err) };
    }
}

// ═══════════════════════════════════════════════════════════
// MODEL MANAGEMENT (Applio-style)
// ═══════════════════════════════════════════════════════════

let currentModelData = null;

async function loadModels() {
    const { ok, data } = await api('/models');
    if (!ok) {
        showToast('Gagal memuat daftar model', 'error');
        return;
    }
    currentModelData = data;
    updateModelSelectors(data.models, data.current_pth, data.current_index);
    updateModelList(data.paired_models, data.orphaned_indices, data.current_pth, data.current_index);
    updateModelStatus(data);
}

function updateModelStatus(data) {
    const statusEl = $('#modelStatus');
    if (!statusEl) return;
    
    const pthCount = data.models?.pth?.length || 0;
    const indexCount = data.models?.index?.length || 0;
    const pairedCount = data.paired_models?.filter(m => m.has_index)?.length || 0;
    
    if (pthCount === 0) {
        statusEl.innerHTML = `<span class="status-warn">● Belum ada model — upload file .pth untuk memulai</span>`;
    } else {
        statusEl.innerHTML = `
            <span class="status-ok">● ${pthCount} model tersedia</span>
            ${pairedCount > 0 ? `<span class="status-index"> • ${pairedCount} dengan index</span>` : ''}
        `;
    }
}

function updateModelSelectors(models, currentPth, currentIndex) {
    const pthSelect = $('#pthModel');
    const indexSelect = $('#indexModel');
    if (!pthSelect || !indexSelect) return;

    pthSelect.innerHTML = '<option value="">— Pilih Model —</option>';
    indexSelect.innerHTML = '<option value="null">— Auto (Cari Index) —</option>';

    (models.pth || []).forEach(pth => {
        const opt = document.createElement('option');
        opt.value = pth;
        opt.textContent = pth.replace('.pth', '');
        if (pth === currentPth) opt.selected = true;
        pthSelect.appendChild(opt);
    });

    (models.index || []).forEach(index => {
        const opt = document.createElement('option');
        opt.value = index;
        opt.textContent = index.replace('.index', '').split('/').pop();
        if (index === currentIndex) opt.selected = true;
        indexSelect.appendChild(opt);
    });
}

// ═══════════════════════════════════════════════════════════
// MODEL LIST RENDERING (Combined Cards Like Applio)
// ═══════════════════════════════════════════════════════════

function updateModelList(pairedModels, orphanedIndices, currentPth, currentIndex) {
    const el = $('#modelList');
    if (!el) return;
    
    if (!pairedModels?.length && !orphanedIndices?.length) {
        el.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📭</div>
                <div>Belum ada model</div>
                <div class="empty-sub">Upload file .pth untuk memulai</div>
            </div>`;
        return;
    }

    // Render paired models (with or without index)
    const modelCards = pairedModels.map(model => {
        const isActive = model.is_active;
        const hasIndex = model.has_index;
        const baseName = model.name;
        
        return `
            <div class="model-card ${isActive ? 'active' : ''} ${hasIndex ? 'has-index' : 'no-index'}" 
                 data-pth="${model.pth}" 
                 data-index="${model.index || ''}"
                 onclick="selectModelCard(this)">
                <div class="model-card-header">
                    <div class="model-card-icon">
                        ${isActive ? '🎤' : '🎵'}
                    </div>
                    <div class="model-card-info">
                        <div class="model-card-name">${escapeHtml(baseName)}</div>
                        <div class="model-card-meta">
                            ${hasIndex 
                                ? `<span class="meta-badge meta-index">📇 ${escapeHtml(getShortIndexName(model.index))}</span>` 
                                : '<span class="meta-badge meta-no-index">⚠️ Tanpa Index</span>'
                            }
                        </div>
                    </div>
                    ${isActive ? '<span class="active-badge">AKTIF</span>' : ''}
                </div>
                <div class="model-card-actions">
                    <button class="btn-card btn-load" onclick="event.stopPropagation(); loadModelByName('${escapeHtml(baseName)}')" 
                            ${isActive ? 'disabled' : ''} title="Load model ini">
                        ${isActive ? '✓ Aktif' : '▶ Load'}
                    </button>
                    <button class="btn-card btn-delete" onclick="event.stopPropagation(); deleteModel('${model.pth}')" 
                            ${isActive ? 'disabled' : ''} title="Hapus model">
                        🗑️
                    </button>
                    ${hasIndex ? `
                        <button class="btn-card btn-delete-index" onclick="event.stopPropagation(); deleteModel('${model.index}')" 
                                ${isActive ? 'disabled' : ''} title="Hapus index saja">
                            🗑️ Index
                        </button>
                    ` : ''}
                </div>
            </div>`;
    }).join('');

    // Render orphaned indices (index tanpa .pth)
    const orphanCards = (orphanedIndices || []).map(orphan => {
        return `
            <div class="model-card orphan" data-index="${orphan.index}">
                <div class="model-card-header">
                    <div class="model-card-icon">📇</div>
                    <div class="model-card-info">
                        <div class="model-card-name">${escapeHtml(orphan.name)}</div>
                        <div class="model-card-meta">
                            <span class="meta-badge meta-orphan">⚠️ Index tanpa model</span>
                        </div>
                    </div>
                </div>
                <div class="model-card-actions">
                    <button class="btn-card btn-delete" onclick="event.stopPropagation(); deleteModel('${orphan.index}')" title="Hapus index">
                        🗑️
                    </button>
                </div>
            </div>`;
    }).join('');

    el.innerHTML = modelCards + orphanCards;
}

function getShortIndexName(indexPath) {
    if (!indexPath) return '';
    return indexPath.split('/').pop().replace('.index', '');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ═══════════════════════════════════════════════════════════
// MODEL ACTIONS
// ═══════════════════════════════════════════════════════════

function selectModelCard(card) {
    // Remove previous selection
    $$('.model-card.selected').forEach(c => c.classList.remove('selected'));
    card.classList.add('selected');
    
    // Update selectors to match
    const pth = card.dataset.pth;
    const index = card.dataset.index;
    
    const pthSelect = $('#pthModel');
    const indexSelect = $('#indexModel');
    
    if (pthSelect && pth) pthSelect.value = pth;
    if (indexSelect) indexSelect.value = index || 'null';
}

async function loadModelByName(modelName) {
    if (!modelName) return;
    
    showToast(`Memuat model "${modelName}"...`, 'info');
    
    const { ok, error, data } = await api('/set_model_by_name', {
        method: 'POST',
        formEntries: { model_name: modelName },
        okMessage: 'Load model'
    });
    
    if (ok) {
        showToast(`✓ Model "${modelName}" berhasil dimuat${data.index ? ' dengan index' : ''}`, 'success');
        await loadModels();
    }
}

window.selectModelCard = selectModelCard;
window.loadModelByName = loadModelByName;

async function uploadModel(file) {
    if (!file) return;
    showToast(`Mengunggah ${file.name}...`, 'info');
    
    const fd = new FormData();
    fd.append('file', file);

    const { ok, data, error } = await api('/models/upload', {
        method: 'POST', body: fd, okMessage: 'Upload',
    });

    if (ok) {
        const kind = file.name.endsWith('.pth') ? '🧠 Model' : '📇 Index';
        let message = `${kind} "${file.name}" berhasil (${data.size_mb} MB)`;
        
        if (data.has_pair) {
            message += ` ✓ Terhubung dengan pasangan!`;
        }
        
        showToast(message, 'success');
        await loadModels();
    }
}

async function uploadModelPair(pthFile, indexFile) {
    if (!pthFile && !indexFile) return;
    
    showToast('Mengunggah pair model...', 'info');
    
    const fd = new FormData();
    if (pthFile) fd.append('pth_file', pthFile);
    if (indexFile) fd.append('index_file', indexFile);

    const { ok, data, error } = await api('/models/upload-pair', {
        method: 'POST', body: fd, okMessage: 'Upload pair',
    });

    if (ok) {
        const results = data.uploaded || [];
        let message = '✓ Upload berhasil: ';
        message += results.map(r => `${r.filename} (${r.size_mb} MB)`).join(', ');
        showToast(message, 'success');
        await loadModels();
    }
}

async function deleteModel(filename) {
    if (!filename) return;
    if (!confirm(`Yakin ingin menghapus "${filename}"?`)) return;
    
    const { ok, error } = await api(`/models/${encodeURIComponent(filename)}`, {
        method: 'DELETE', okMessage: 'Hapus model',
    });

    if (ok) {
        showToast(`"${filename}" berhasil dihapus`, 'success');
        await loadModels();
    } else {
        showToast(`Gagal hapus: ${error}`, 'error');
    }
}

window.deleteModel = deleteModel;

async function applyModel() {
    const pth = $('#pthModel')?.value;
    let index = $('#indexModel')?.value;
    
    if (!pth) { 
        showToast('Pilih model .pth terlebih dahulu', 'error'); 
        return; 
    }
    
    // If "Auto" selected, let backend find the index
    if (index === 'null') {
        index = null;
    }
    
    showToast('Memuat model...', 'info');
    
    const { ok, error, data } = await api('/set_model', {
        method: 'POST',
        formEntries: { pth, index },
        okMessage: 'Load model',
    });
    
    if (ok) {
        const indexInfo = data.index ? ' dengan index' : ' (tanpa index)';
        showToast(`✓ Model "${pth.replace('.pth', '')}" aktif${indexInfo}`, 'success');
        await loadModels();
    }
}

// ═══════════════════════════════════════════════════════════
// AUDIO UPLOAD & CONVERSION
// ═══════════════════════════════════════════════════════════

let selectedAudioFile = null;
const VALID_AUDIO_EXT = ['.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'];
const VALID_AUDIO_TYPES = ['audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/aac', 'audio/x-m4a', 'audio/flac', 'audio/ogg'];

function setupFileUpload() {
    const area = $('#uploadArea');
    const input = $('#audioFile');
    if (!area || !input) return;
    
    area.addEventListener('click', () => input.click());
    input.addEventListener('change', e => { if (e.target.files.length) handleAudioFile(e.target.files[0]); });
    area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('dragover'); });
    area.addEventListener('dragleave', () => area.classList.remove('dragover'));
    area.addEventListener('drop', e => {
        e.preventDefault(); area.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleAudioFile(e.dataTransfer.files[0]);
    });
}

function handleAudioFile(file) {
    const hasValidExt = VALID_AUDIO_EXT.some(ext => file.name.toLowerCase().endsWith(ext));
    if (!VALID_AUDIO_TYPES.includes(file.type) && !hasValidExt) {
        showToast('Format tidak didukung. Gunakan MP3, WAV, M4A, FLAC, atau OGG.', 'error');
        return;
    }
    
    selectedAudioFile = file;
    const area = $('#uploadArea');
    const nameEl = $('.file-name');
    const iconEl = $('.upload-icon');
    
    area?.classList.add('has-file');
    if (nameEl) nameEl.textContent = `📎 ${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} MB`;
    if (iconEl) iconEl.textContent = '🎵';
    showAudioPreview(file);
    showToast('Audio siap dikonversi', 'success');
}

function showAudioPreview(file) {
    const preview = $('#previewSection');
    const audio = $('#audioPreview');
    if (!preview || !audio) return;
    audio.src = URL.createObjectURL(file);
    preview.classList.add('active');
}

async function convertVoice() {
    if (!selectedAudioFile) {
        showToast('Upload file audio terlebih dahulu', 'error');
        return;
    }
    
    const pitch = parseInt($('#pitch')?.value || 0, 10);
    const indexRate = parseFloat($('#indexRate')?.value || 0.75);
    const f0Method = $('#f0Method')?.value || 'rmvpe';
    const autoEnhance = $('#autoEnhance')?.checked ? '1' : '0';

    const fd = new FormData();
    fd.append('audio', selectedAudioFile);
    fd.append('pitch', pitch);
    fd.append('index_rate', indexRate);
    fd.append('f0_method', f0Method);
    fd.append('auto_enhance', autoEnhance);

    const loadingEl = $('#loading');
    const resultEl = $('#result');
    loadingEl?.classList.add('active');
    resultEl?.classList.remove('active');
    showToast('Sedang mengkonversi audio dengan kualitas terbaik...', 'info');

    const { ok, data, error } = await api('/convert', { method: 'POST', body: fd });
    loadingEl?.classList.remove('active');

    if (ok) {
        showResult(data);
        showToast('✓ Konversi berhasil!', 'success');
    } else {
        showToast(`Konversi gagal: ${error}`, 'error');
    }
}

function showResult(data) {
    const resultEl = $('#result');
    const audio = $('#resultAudio');
    const nameEl = $('#resultModelName');
    
    if (!resultEl || !audio) return;
    
    audio.src = data.audio;
    if (nameEl) {
        let info = `🎤 Model: ${data.model_name}`;
        if (data.index_used) {
            info += ` • 📇 ${getShortIndexName(data.index_used)}`;
        }
        nameEl.textContent = info;
    }
    
    resultEl.classList.add('active');
    resultEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function downloadResult() {
    const audio = $('#resultAudio');
    if (!audio?.src) return;
    
    const link = document.createElement('a');
    link.href = audio.src;
    link.download = `converted_${Date.now()}.wav`;
    link.click();
    showToast('Download dimulai', 'success');
}

// ═══════════════════════════════════════════════════════════
// PARAMETER CONTROLS
// ═══════════════════════════════════════════════════════════

function setupSliders() {
    $$('input[type="range"]').forEach(slider => {
        const valueInput = document.getElementById(slider.id + 'Value');
        if (!valueInput) return;
        
        slider.addEventListener('input', e => {
            valueInput.value = e.target.value;
            validateInput(valueInput);
        });
        
        valueInput.addEventListener('input', e => {
            slider.value = e.target.value;
            validateInput(valueInput);
        });
    });
}

function validateInput(input) {
    const min = parseFloat(input.min);
    const max = parseFloat(input.max);
    const val = parseFloat(input.value);
    input.classList.toggle('out-of-range', !Number.isNaN(val) && (val < min || val > max));
}

function resetParams() {
    $('#pitch').value = DEFAULTS.pitch;
    $('#pitchValue').value = DEFAULTS.pitch;
    $('#indexRate').value = DEFAULTS.indexRate;
    $('#indexRateValue').value = DEFAULTS.indexRate;
    $('#f0Method').value = DEFAULTS.f0Method;
    $('#autoEnhance').checked = DEFAULTS.autoEnhance;
    $$('.control-value-input').forEach(el => el.classList.remove('out-of-range'));
    showToast('Parameter direset ke default', 'info', 2000);
}

// ═══════════════════════════════════════════════════════════
// MODEL UPLOAD HANDLER (Support Multiple Files)
// ═══════════════════════════════════════════════════════════

function setupModelUpload() {
    const modelFileInput = $('#modelFileInput');
    const uploadBtn = $('#uploadModelBtn');
    
    if (uploadBtn) {
        uploadBtn.addEventListener('click', () => {
            modelFileInput?.click();
        });
    }
    
    if (modelFileInput) {
        modelFileInput.setAttribute('multiple', '');
        modelFileInput.addEventListener('change', async e => {
            const files = Array.from(e.target.files);
            if (!files.length) return;
            
            // Separate .pth and .index files
            const pthFiles = files.filter(f => f.name.endsWith('.pth'));
            const indexFiles = files.filter(f => f.name.endsWith('.index'));
            
            if (pthFiles.length === 1 && indexFiles.length === 1) {
                // Upload as pair
                await uploadModelPair(pthFiles[0], indexFiles[0]);
            } else {
                // Upload individually
                for (const file of files) {
                    await uploadModel(file);
                }
            }
            
            e.target.value = '';
        });
    }
}

// ═══════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    loadModels();
    setupFileUpload();
    setupSliders();
    setupModelUpload();

    // Model list click delegation
    $('#modelList')?.addEventListener('click', e => {
        const btn = e.target.closest('[data-delete]');
        if (btn) {
            e.stopPropagation();
            deleteModel(btn.dataset.delete);
        }
    });

    // Button handlers
    $('#applyModelBtn')?.addEventListener('click', applyModel);
    $('#convertBtn')?.addEventListener('click', convertVoice);
    $('#downloadBtn')?.addEventListener('click', downloadResult);
    $('#resetBtn')?.addEventListener('click', () => location.reload());
    $('#resetParamsBtn')?.addEventListener('click', resetParams);

    // Keyboard shortcuts
    document.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            convertVoice();
        }
    });
});
