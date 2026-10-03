import os
import base64
import tempfile
import warnings
from pathlib import Path
from typing import Optional, List, Dict, Any
import torch
import numpy as np

# PyTorch 2.6+ patch untuk HuBERT/fairseq lama
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load

# Suppress warnings
warnings.filterwarnings('ignore', message='.*weight_norm.*')
warnings.filterwarnings('ignore', category=FutureWarning)

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

try:
    from rvc_python.infer import RVCInference
    HAS_RVC_PYTHON = True
except ImportError:
    HAS_RVC_PYTHON = False

# ═══════════════════════════════════════════════════════════════════════════════
# APP SETUP
# ═══════════════════════════════════════════════════════════════════════════════
app = FastAPI(title="RVC Voice Changer Pro", docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"

# State global
rvc_infer = None
current_pth = None
current_index = None

# ═══════════════════════════════════════════════════════════════════════════════
# AUDIO ENHANCER (Professional Quality)
# ═══════════════════════════════════════════════════════════════════════════════
def enhance_audio(input_path, output_path):
    """
    Post-processing audio profesional untuk kualitas terbaik:
    1. High-pass filter di 60Hz (membuang sub-bass rumble)
    2. Peak Normalization ke -1.0 dB
    3. Soft limiting untuk mencegah clipping
    """
    try:
        import soundfile as sf
        from scipy.signal import butter, filtfilt
        
        data, samplerate = sf.read(input_path)
        is_stereo = len(data.shape) > 1
        
        # 1. High-pass filter (Butterworth order 4 untuk slope lebih steep)
        nyq = 0.5 * samplerate
        cutoff = 60.0
        if cutoff < nyq:
            normal_cutoff = cutoff / nyq
            b, a = butter(4, normal_cutoff, btype='high', analog=False)
            if is_stereo:
                data[:, 0] = filtfilt(b, a, data[:, 0])
                data[:, 1] = filtfilt(b, a, data[:, 1])
            else:
                data = filtfilt(b, a, data)
        
        # 2. Peak Normalization ke -1.0 dB (0.891)
        peak = np.max(np.abs(data))
        if peak > 0:
            target_peak = 10 ** (-1.0 / 20.0)
            data = data * (target_peak / peak)
            
        # 3. Soft clip untuk hasil lebih smooth
        data = np.tanh(data * 1.2) / 1.2
        
        # 4. Safety hard clip
        data = np.clip(data, -1.0, 1.0)
        
        sf.write(output_path, data, samplerate)
        print(f"✨ Audio enhanced: High-pass 60Hz, Normalized -1.0dB, Soft-limited")
        return True
    except ImportError:
        print("⚠️ scipy/soundfile tidak terinstall, lewati enhance.")
        return False
    except Exception as e:
        print(f"⚠️ Enhance error: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# MODEL PAIRING SYSTEM (Like Applio RVC)
# ═══════════════════════════════════════════════════════════════════════════════
def get_base_name(filename: str) -> str:
    """Extract base name from .pth or .index file"""
    return Path(filename).stem

def find_matching_index(pth_name: str, index_files: List[str]) -> Optional[str]:
    """
    Smart index matching - finds the best matching index for a .pth file.
    Priority:
    1. Exact match: model.pth -> model.index
    2. Contains match: model_v2.pth -> model_v2.index or model.index
    3. Trained_index subfolder
    """
    if not pth_name or not index_files:
        return None
    
    pth_base = get_base_name(pth_name)
    
    # 1. Exact match
    for idx in index_files:
        if get_base_name(idx) == pth_base:
            return idx
    
    # 2. Contains match (index name contains pth base or vice versa)
    for idx in index_files:
        idx_base = get_base_name(idx)
        if pth_base in idx_base or idx_base in pth_base:
            return idx
    
    # 3. Check for trained_index folder (common in Applio)
    trained_index_dir = MODELS_DIR / "trained_index"
    if trained_index_dir.exists():
        for idx_file in trained_index_dir.glob("*.index"):
            idx_name = idx_file.name
            idx_base = get_base_name(idx_name)
            if pth_base == idx_base or pth_base in idx_base:
                return f"trained_index/{idx_name}"
    
    return None

def get_paired_models() -> List[Dict[str, Any]]:
    """
    Get all models with their paired index files.
    Returns a list of model objects with pairing information.
    """
    pth_files = sorted([f.name for f in MODELS_DIR.glob("*.pth")])
    index_files = sorted([f.name for f in MODELS_DIR.glob("*.index")])
    
    # Also check trained_index subfolder
    trained_index_dir = MODELS_DIR / "trained_index"
    if trained_index_dir.exists():
        for idx_file in trained_index_dir.glob("*.index"):
            index_files.append(f"trained_index/{idx_file.name}")
    
    paired_models = []
    paired_indices = set()
    
    # Pair .pth with matching .index
    for pth in pth_files:
        matching_index = find_matching_index(pth, index_files)
        model_info = {
            "name": get_base_name(pth),
            "pth": pth,
            "index": matching_index,
            "has_index": matching_index is not None,
            "is_active": pth == current_pth,
            "index_is_active": matching_index == current_index if matching_index else False
        }
        paired_models.append(model_info)
        if matching_index:
            paired_indices.add(matching_index)
    
    # Find orphaned index files (no matching .pth)
    orphaned_indices = []
    for idx in index_files:
        if idx not in paired_indices:
            orphaned_indices.append({
                "name": get_base_name(idx),
                "index": idx,
                "pth": None,
                "has_index": True,
                "is_orphan": True,
                "is_active": idx == current_index
            })
    
    return paired_models, orphaned_indices

def detect_model_version(pth_path):
    """Mendeteksi versi model RVC (v1 atau v2) dari file checkpoint."""
    try:
        cpt = torch.load(pth_path, map_location="cpu")
        if "version" in cpt:
            return str(cpt["version"])
        weight = cpt.get("weight", {})
        if "enc_p.emb_phone.weight" in weight:
            shape = weight["enc_p.emb_phone.weight"].shape
            if len(shape) >= 2 and shape[1] == 256:
                return "v1"
            elif len(shape) >= 2 and shape[1] == 768:
                return "v2"
    except Exception as e:
        print(f"⚠️ Gagal mendeteksi versi model: {e}")
    return "v2"

def get_available_models():
    """Scan folder models/ untuk file .pth dan .index"""
    pth_files = sorted([f.name for f in MODELS_DIR.glob("*.pth")])
    index_files = sorted([f.name for f in MODELS_DIR.glob("*.index")])
    
    # Include trained_index subfolder
    trained_index_dir = MODELS_DIR / "trained_index"
    if trained_index_dir.exists():
        for idx_file in trained_index_dir.glob("*.index"):
            index_files.append(f"trained_index/{idx_file.name}")
    
    return {"pth": pth_files, "index": sorted(index_files)}

def load_model(pth_name: str, index_name: Optional[str] = None):
    """Load model RVC dari folder models/"""
    global rvc_infer, current_pth, current_index
    if not HAS_RVC_PYTHON:
        print("❌ rvc-python not installed")
        return False

    pth_path = MODELS_DIR / pth_name
    if not pth_path.exists():
        print(f"❌ Model not found: {pth_path}")
        return False

    try:
        print(f"\n🔄 Loading model: {pth_name}")
        model_version = detect_model_version(pth_path)
        print(f"   🏷️ Detected version: {model_version}")
        
        # Handle index path (might be in subfolder)
        index_path = None
        if index_name:
            if "/" in index_name:
                # Index is in subfolder
                index_path = MODELS_DIR / index_name
            else:
                index_path = MODELS_DIR / index_name
        
        if index_path and index_path.exists():
            rvc_infer = RVCInference(device=DEVICE, index_path=str(index_path))
            print(f"   📇 Index loaded: {index_name}")
            current_index = index_name
        else:
            rvc_infer = RVCInference(device=DEVICE)
            current_index = None
        
        rvc_infer.load_model(str(pth_path), version=model_version)
        current_pth = pth_name
        print(f"   🧠 Model loaded: {pth_name}")
        print("✅ RVC ready!\n")
        return True
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return False

# Auto-load model pertama dengan smart pairing saat startup
models = get_available_models()
if models["pth"]:
    first_pth = models["pth"][0]
    matching_index = find_matching_index(first_pth, models["index"])
    load_model(first_pth, matching_index)

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES - PAGE & HEALTH
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/", response_class=HTMLResponse)
async def root():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "rvc_loaded": rvc_infer is not None,
        "device": DEVICE,
        "current_pth": current_pth,
        "current_index": current_index,
    }

@app.get("/api/status")
async def api_status():
    return {
        "status": "ok",
        "rvc_loaded": rvc_infer is not None,
        "device": DEVICE,
        "current_pth": current_pth,
        "current_index": current_index,
        "models_dir": str(MODELS_DIR.absolute()),
        "models_count": len(list(MODELS_DIR.glob("*.pth")))
    }

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES - MODEL MANAGEMENT (Enhanced)
# ═══════════════════════════════════════════════════════════════════════════════
@app.get("/models")
async def list_models():
    """Get all models with pairing information"""
    paired_models, orphaned_indices = get_paired_models()
    return {
        "models": get_available_models(),
        "paired_models": paired_models,
        "orphaned_indices": orphaned_indices,
        "current_pth": current_pth,
        "current_index": current_index,
    }

@app.get("/models/paired")
async def list_paired_models():
    """Dedicated endpoint for paired models (like Applio)"""
    paired_models, orphaned_indices = get_paired_models()
    return {
        "paired": paired_models,
        "orphans": orphaned_indices,
        "current": {
            "pth": current_pth,
            "index": current_index
        }
    }

@app.post("/models/upload")
async def upload_model(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "Nama file kosong")
    if not file.filename.endswith(('.pth', '.index')):
        raise HTTPException(400, "Hanya file .pth atau .index yang diizinkan")

    # Handle subfolder path (e.g., trained_index/filename.index)
    filename = file.filename
    save_path = MODELS_DIR / filename
    
    # Create subfolder if needed
    save_path.parent.mkdir(parents=True, exist_ok=True)
    
    if save_path.exists():
        raise HTTPException(400, f"File {filename} sudah ada. Hapus dulu jika ingin mengganti.")

    try:
        file_size = 0
        chunk_count = 0
        chunk_size = 1024 * 1024  # 1MB chunk
        
        print(f"\n📤 Mulai upload: {filename}")
        
        with save_path.open("wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                file_size += len(chunk)
                chunk_count += 1
                
                if file_size % (100 * 1024 * 1024) < chunk_size:
                    print(f"   ⏳ Progress: {file_size / 1024 / 1024:.1f} MB")
        
        size_mb = file_size / 1024 / 1024
        print(f"✅ Berhasil: {filename} ({size_mb:.2f} MB) - {chunk_count} chunks")
        
        # Check if there's a matching pair
        paired_models, _ = get_paired_models()
        matched_model = None
        if filename.endswith('.pth'):
            for model in paired_models:
                if model['pth'] == filename and model['has_index']:
                    matched_model = model
                    break
        elif filename.endswith('.index'):
            for model in paired_models:
                if model['index'] == filename:
                    matched_model = model
                    break
        
        return {
            "success": True, 
            "filename": filename, 
            "size_mb": round(size_mb, 2),
            "has_pair": matched_model is not None,
            "paired_with": matched_model['pth'] if matched_model and filename.endswith('.index') else None
        }
    except Exception as e:
        if save_path.exists():
            save_path.unlink()
        print(f"❌ Gagal upload: {e}")
        raise HTTPException(500, f"Gagal menyimpan file: {str(e)}")

@app.post("/models/upload-pair")
async def upload_model_pair(
    pth_file: UploadFile = File(None),
    index_file: UploadFile = File(None)
):
    """Upload a .pth and .index pair together"""
    results = []
    
    if pth_file and pth_file.filename:
        if not pth_file.filename.endswith('.pth'):
            raise HTTPException(400, "File pertama harus .pth")
        
        pth_path = MODELS_DIR / pth_file.filename
        pth_path.parent.mkdir(parents=True, exist_ok=True)
        
        if pth_path.exists():
            raise HTTPException(400, f"File {pth_file.filename} sudah ada")
        
        content = await pth_file.read()
        pth_path.write_bytes(content)
        results.append({"type": "pth", "filename": pth_file.filename, "size_mb": round(len(content) / 1024 / 1024, 2)})
    
    if index_file and index_file.filename:
        if not index_file.filename.endswith('.index'):
            raise HTTPException(400, "File kedua harus .index")
        
        index_path = MODELS_DIR / index_file.filename
        index_path.parent.mkdir(parents=True, exist_ok=True)
        
        if index_path.exists():
            raise HTTPException(400, f"File {index_file.filename} sudah ada")
        
        content = await index_file.read()
        index_path.write_bytes(content)
        results.append({"type": "index", "filename": index_file.filename, "size_mb": round(len(content) / 1024 / 1024, 2)})
    
    return {"success": True, "uploaded": results}

@app.delete("/models/{filename}")
async def delete_model(filename: str):
    file_path = MODELS_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "File tidak ditemukan")

    if filename == current_pth:
        raise HTTPException(400, "Tidak bisa hapus model .pth yang sedang aktif. Pilih model lain dulu.")
    if filename == current_index:
        raise HTTPException(400, "Tidak bisa hapus index yang sedang aktif. Pilih model lain dulu.")

    try:
        file_path.unlink()
        print(f"🗑️ Deleted: {filename}")
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, f"Gagal menghapus file: {str(e)}")

@app.post("/set_model")
async def set_model(pth: str = Form(...), index: Optional[str] = Form(None)):
    if not pth:
        raise HTTPException(400, "File .pth wajib dipilih")
    if index == "" or index == "null" or index == "undefined":
        index = None
    
    # Auto-find matching index if not provided
    if not index:
        models = get_available_models()
        index = find_matching_index(pth, models["index"])
    
    success = load_model(pth, index)
    if not success:
        raise HTTPException(500, "Gagal load model. Cek console server.")
    return {"success": True, "pth": pth, "index": index}

@app.post("/set_model_by_name")
async def set_model_by_name(model_name: str = Form(...)):
    """Set model by base name - automatically finds matching .pth and .index"""
    pth_files = list(MODELS_DIR.glob("*.pth"))
    
    # Find .pth by base name
    matching_pth = None
    for pth in pth_files:
        if get_base_name(pth.name) == model_name or pth.name == model_name:
            matching_pth = pth.name
            break
    
    if not matching_pth:
        raise HTTPException(404, f"Model '{model_name}' tidak ditemukan")
    
    # Find matching index
    models = get_available_models()
    matching_index = find_matching_index(matching_pth, models["index"])
    
    success = load_model(matching_pth, matching_index)
    if not success:
        raise HTTPException(500, "Gagal load model")
    
    return {
        "success": True, 
        "pth": matching_pth, 
        "index": matching_index,
        "message": f"Model '{model_name}' loaded with {'index' if matching_index else 'no index'}"
    }

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES - VOICE CONVERSION (Optimized for Best Quality)
# ═══════════════════════════════════════════════════════════════════════════════
@app.post("/convert")
async def convert_voice(
    audio: UploadFile = File(...),
    pitch: int = Form(0),
    index_rate: float = Form(0.75),
    f0_method: str = Form("rmvpe"),
    auto_enhance: str = Form("1"),
    filter_radius: int = Form(3),
    rms_mix_rate: float = Form(0.25),
    protect: float = Form(0.33),
):
    if rvc_infer is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Belum ada model yang aktif. Upload dan pilih model dulu."}
        )

    if not -24 <= pitch <= 24:
        return JSONResponse(status_code=422, content={"error": f"pitch harus -24..24, dapat {pitch}"})
    if not 0.0 <= index_rate <= 1.0:
        return JSONResponse(status_code=422, content={"error": f"index_rate harus 0..1, dapat {index_rate}"})
    if f0_method not in ["rmvpe", "fcpe", "harvest", "pm", "crepe", "mangio-crepe"]:
        f0_method = "rmvpe"

    audio_bytes = await audio.read()
    temp_dir = Path(tempfile.gettempdir()) / "voice_changer"
    temp_dir.mkdir(exist_ok=True)

    safe_name = Path(audio.filename).stem
    input_path = temp_dir / f"in_{safe_name}.wav"
    output_path = temp_dir / f"out_{safe_name}.wav"

    try:
        with open(input_path, "wb") as f:
            f.write(audio_bytes)
        
        print(f"🔄 Converting: {audio.filename} (pitch={pitch}, index_rate={index_rate}, f0={f0_method}, model={current_pth})")
        
        # Set all inference parameters
        rvc_infer.f0up_key = pitch
        rvc_infer.index_rate = index_rate
        
        # Set F0 Method (Critical for quality)
        if hasattr(rvc_infer, 'f0_method'):
            rvc_infer.f0_method = f0_method
        if hasattr(rvc_infer, 'f0_extractor'):
            rvc_infer.f0_extractor = f0_method
        
        # Advanced parameters for best quality
        rvc_infer.filter_radius = filter_radius
        rvc_infer.rms_mix_rate = rms_mix_rate if index_rate > 0.5 else 1.0
        rvc_infer.protect = protect
        
        rvc_infer.infer_file(str(input_path), str(output_path))
        
        # Auto Enhance (Professional Processing)
        if auto_enhance == "1" and output_path.exists():
            enhance_audio(str(output_path), str(output_path))
        
        if output_path.exists() and output_path.stat().st_size > 0:
            print(f"✅ Output saved to {output_path}")
            converted_bytes = output_path.read_bytes()
        else:
            raise Exception("Inference gagal - file output kosong")
        
        audio_b64 = base64.b64encode(converted_bytes).decode()
        return {
            "success": True,
            "audio": f"data:audio/wav;base64,{audio_b64}",
            "model_name": current_pth.replace(".pth", "") if current_pth else "unknown",
            "index_used": current_index,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        for p in (input_path, output_path):
            if p.exists():
                p.unlink()

# ═══════════════════════════════════════════════════════════════════════════════
# RUN SERVER
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 60)
    print("   🎤 RVC VOICE CHANGER PRO - Smart Model Pairing")
    print(f"   📦 RVC Loaded : {rvc_infer is not None}")
    print(f"   💻 Device     : {DEVICE}")
    print(f"   🎯 Current    : {current_pth or 'None'}")
    if current_index:
        print(f"   📇 Index      : {current_index}")
    print(f"   📁 Models Dir : {MODELS_DIR.absolute()}")
    print("=" * 60)
    print("🚀 http://localhost:8000")
    print("=" * 60 + "\n")

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        timeout_keep_alive=600,
    )
    server = uvicorn.Server(config)
    server.run()
