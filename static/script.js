// ═══════════════════════════════════════════════════════════
// VOICE CHANGER AI — Frontend Logic
// Clean, modular, no inline styles.
// ═══════════════════════════════════════════════════════════

'use strict';

/* ── Tiny helpers ────────────────────────────────────────── */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const DEFAULTS = { pitch: 0, indexRate: 0.75, rmsMixRate: 0.25, protect: 0.33, filterRadius: 3 };

/* ── Toast (uses CSS classes, not inline styles) ─────────── */
const TOAST_ICONS = { success: '✅', error: '❌', info: 'ℹ️' };

function showToast(message, type = 'info', timeout = 3800) {
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

/* ── Theme toggle (persisted) ────────────────────────────── */
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

/* ── Generic fetch wrapper ───────────────────────────────── */
async function api(url, { method = 'GET', body, formEntries, okMessage } = {}) {
    try {
        let res;
        if (body instanceof FormData) {
            res = await fetch(url, { method, body });
        } else if (formEntries) {
            const fd = new FormData();
            for (const [k, v] of Object.entries(formEntries)) fd.append(k, v);
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

/* ═══════════════════════════════════════════════════════════
   MODEL MANAGEMENT
   ═══════════════════════════════════════════════════════════ */
async function loadModels() {
    const { ok, data } = await api('/models');
    if (!ok) {
        showToast('Gagal memuat daftar model', 'error');
        return;
    }
    updateModelSelectors(data.models, data.current_pth, data.current_index);
    updateModelList(data.models, data.current_pth);
}

function updateModelSelectors(models, currentPth, currentIndex) {
    const pthSelect = $('#pthModel');
    const indexSelect = $('#indexModel');
    if (!pthSelect || !indexSelect) return;

    pthSelect.innerHTML = '<option value="">— Pilih Model —</option>';
    indexSelect.innerHTML = '<option value="null">— Tanpa Index —</option>';

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
        opt.textContent = index.replace('.index', '');
        if (index === currentIndex) opt.selected = true;
        indexSelect.appendChild(opt);
    });

    const statusEl = $('#modelStatus');
    if (statusEl) {
        const count = models.pth?.length || 0;
        statusEl.innerHTML = count
            ? `<span class="status-ok">● ${count} model tersedia</span>`
            : `<span class="status-warn">● Belum ada model — upload file .pth</span>`;
    }
}

function updateModelList(models, currentPth) {
    const el = $('#modelList');
    if (!el) return;

    if (!models.pth?.length) {
        el.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📭</div>
                <div>Belum ada model</div>
                <div class="empty-sub">Upload file .pth untuk memulai</div>
            </div>`;
        return;
    }

    el.innerHTML = models.pth.map(pth => {
        const isActive = pth === currentPth;
        const baseName = pth.replace('.pth', '');
        const indexFile = models.index.find(idx => idx.replace('.index', '') === baseName);

        return `
            <div class="model-item ${isActive ? 'active' : ''}" data-model="${pth}">
                <span class="model-icon">${isActive ? '🎤' : '🎵'}</span>
                <div class="model-info">
                    <div class="model-name">${baseName}</div>
                    ${indexFile ? `<div class="model-index">📇 ${indexFile}</div>` : ''}
                </div>
                ${isActive ? '<span class="badge">active</span>' : ''}
                <button class="btn-delete" data-delete="${pth}" title="Hapus model" ${isActive ? 'disabled' : ''}>🗑</button>
            </div>`;
    }).join('');
}

async function uploadModel(file) {
    if (!file) return;
    showToast(`Mengunggah ${file.name}…`, 'info');

    const fd = new FormData();
    fd.append('file', file);

    const { ok, data, error } = await api('/models/upload', {
        method: 'POST',
        body: fd,
        okMessage: 'Upload',
    });

    if (ok) {
        const kind = file.name.endsWith('.pth') ? '🧠 Model' : '📇 Index';
        showToast(`${kind} "${file.name}" berhasil (${data.size_mb} MB)`, 'success');
        await loadModels();
    }
}

async function deleteModel(filename) {
    if (!filename) return;
    if (!confirm(`Yakin ingin menghapus "${filename}"?`)) return;

    const { ok, error } = await api(`/models/${encodeURIComponent(filename)}`, {
        method: 'DELETE',
        okMessage: 'Hapus model',
    });
    if (ok) {
        showToast(`"${filename}" dihapus`, 'success');
        await loadModels();
    }
}

async function applyModel() {
    const pth = $('#pthModel')?.value;
    const index = $('#indexModel')?.value;
    if (!pth) {
        showToast('Pilih model .pth terlebih dahulu', 'error');
        return;
    }

    showToast('Memuat model…', 'info');
    const { ok, error } = await api('/set_model', {
        method: 'POST',
        formEntries: { pth, index: index === 'null' ? '' : index },
        okMessage: 'Load model',
    });

    if (ok) {
        showToast(`Model "${pth.replace('.pth', '')}" aktif`, 'success');
        await loadModels();
    }
}

/* ═══════════════════════════════════════════════════════════
   AUDIO UPLOAD & CONVERSION
   ═══════════════════════════════════════════════════════════ */
let selectedAudioFile = null;

const VALID_AUDIO_EXT = ['.mp3', '.wav', '.m4a', '.aac'];
const VALID_AUDIO_TYPES = ['audio/mpeg', 'audio/wav', 'audio/mp4', 'audio/aac', 'audio/x-m4a'];

function setupFileUpload() {
    const area = $('#uploadArea');
    const input = $('#audioFile');
    if (!area || !input) return;

    area.addEventListener('click', () => input.click());

    input.addEventListener('change', e => {
        if (e.target.files.length) handleAudioFile(e.target.files[0]);
    });

    area.addEventListener('dragover', e => {
        e.preventDefault();
        area.classList.add('dragover');
    });
    area.addEventListener('dragleave', () => area.classList.remove('dragover'));
    area.addEventListener('drop', e => {
        e.preventDefault();
        area.classList.remove('dragover');
        if (e.dataTransfer.files.length) handleAudioFile(e.dataTransfer.files[0]);
    });
}

function handleAudioFile(file) {
    const hasValidExt = VALID_AUDIO_EXT.some(ext => file.name.toLowerCase().endsWith(ext));
    if (!VALID_AUDIO_TYPES.includes(file.type) && !hasValidExt) {
        showToast('Format tidak didukung. Gunakan MP3, WAV, M4A, atau AAC.', 'error');
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
    const filterRadius = parseInt($('#filterRadius')?.value || 3, 10);
    const rmsMixRate = parseFloat($('#rmsMixRate')?.value || 0.25);
    const protect = parseFloat($('#protect')?.value || 0.33);

    const fd = new FormData();
    fd.append('audio', selectedAudioFile);
    fd.append('pitch', pitch);
    fd.append('index_rate', indexRate);
    fd.append('filter_radius', filterRadius);
    fd.append('rms_mix_rate', rmsMixRate);
    fd.append('protect', protect);

    const loadingEl = $('#loading');
    const resultEl = $('#result');
    loadingEl?.classList.add('active');
    resultEl?.classList.remove('active');

    showToast('Sedang mengkonversi…', 'info');

    const { ok, data, error } = await api('/convert', { method: 'POST', body: fd });
    loadingEl?.classList.remove('active');

    if (ok) {
        showResult(data);
        showToast('Konversi berhasil!', 'success');
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
    if (nameEl) nameEl.textContent = `🎤 Model: ${data.model_name}`;

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

/* ═══════════════════════════════════════════════════════════
   SLIDER CONTROLS
   ═══════════════════════════════════════════════════════════ */
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
    $('#pitch').value = DEFAULTS.pitch;          $('#pitchValue').value = DEFAULTS.pitch;
    $('#indexRate').value = DEFAULTS.indexRate;  $('#indexRateValue').value = DEFAULTS.indexRate;
    $('#rmsMixRate').value = DEFAULTS.rmsMixRate; $('#rmsMixRateValue').value = DEFAULTS.rmsMixRate;
    $('#protect').value = DEFAULTS.protect;      $('#protectValue').value = DEFAULTS.protect;
    $('#filterRadius').value = DEFAULTS.filterRadius; $('#filterRadiusValue').value = DEFAULTS.filterRadius;
    $$('.control-value-input').forEach(el => el.classList.remove('out-of-range'));
    showToast('Parameter direset ke default', 'info', 2000);
}

/* ═══════════════════════════════════════════════════════════
   INIT
   ═══════════════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    loadModels();
    setupFileUpload();
    setupSliders();

    // Event delegation for delete buttons inside model list
    $('#modelList')?.addEventListener('click', e => {
        const btn = e.target.closest('[data-delete]');
        if (btn) deleteModel(btn.dataset.delete);
    });

    $('#applyModelBtn')?.addEventListener('click', applyModel);
    $('#uploadModelBtn')?.addEventListener('click', () => $('#modelFileInput')?.click());
    $('#convertBtn')?.addEventListener('click', convertVoice);
    $('#downloadBtn')?.addEventListener('click', downloadResult);
    $('#resetBtn')?.addEventListener('click', () => location.reload());
    $('#resetParamsBtn')?.addEventListener('click', resetParams);

    const modelFileInput = $('#modelFileInput');
    modelFileInput?.addEventListener('change', e => {
        if (e.target.files.length) uploadModel(e.target.files[0]);
        e.target.value = '';
    });

    // Keyboard shortcut: Ctrl/Cmd + Enter to convert
    document.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            convertVoice();
        }
    });

    console.log('%c🎤 Voice Changer AI ready', 'color:#4f46e5;font-weight:bold');
});
