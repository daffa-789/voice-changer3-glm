# ═════════════════════════════════════════════════════════════════════════════
# IMPORTS
# ═════════════════════════════════════════════════════════════════════════════
import os
import base64
import tempfile
import warnings
from pathlib import Path
from typing import Optional
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

# ═════════════════════════════════════════════════════════════════════════════
# APP SETUP - TANPA BATASAN UPLOAD SIZE
# ═════════════════════════════════════════════════════════════════════════════
# docs_url=None, redoc_url=None, openapi_url=None → matikan API docs bawaan FastAPI
app = FastAPI(title="RVC Voice Changer - Multi Model", docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# ═════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════
MODELS_DIR = Path("models")
MODELS_DIR.mkdir(exist_ok=True)
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"

# State global
rvc_infer = None
current_pth = None
current_index = None

# ═════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════
def get_available_models():
    """Scan folder models/ untuk file .pth dan .index"""
    pth_files = sorted([f.name for f in MODELS_DIR.glob("*.pth")])
    index_files = sorted([f.name for f in MODELS_DIR.glob("*.index")])
    return {"pth": pth_files, "index": index_files}

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
        index_path = MODELS_DIR / index_name if index_name else None
        
        if index_path and index_path.exists():
            rvc_infer = RVCInference(device=DEVICE, index_path=str(index_path))
            print(f"   📇 Index loaded: {index_name}")
            current_index = index_name
        else:
            rvc_infer = RVCInference(device=DEVICE)
            current_index = None
        
        rvc_infer.load_model(str(pth_path))
        current_pth = pth_name
        print(f"   🧠 Model loaded: {pth_name}")
        print("✅ RVC ready!\n")
        return True
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        return False

# Auto-load model pertama saat startup
models = get_available_models()
if models["pth"]:
    first_pth = models["pth"][0]
    # Cari index yang cocok dengan nama model
    matching_index = None
    for idx in models["index"]:
        if first_pth.replace(".pth", "") in idx:
            matching_index = idx
            break
    load_model(first_pth, matching_index)

# ═════════════════════════════════════════════════════════════════════════════
# ROUTES - PAGE & HEALTH
# ═════════════════════════════════════════════════════════════════════════════
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

# ═════════════════════════════════════════════════════════════════════════════
# ROUTES - MODEL MANAGEMENT (TANPA BATASAN UPLOAD)
# ═════════════════════════════════════════════════════════════════════════════
@app.get("/models")
async def list_models():
    """List semua model yang tersedia"""
    return {
        "models": get_available_models(),
        "current_pth": current_pth,
        "current_index": current_index,
    }

@app.post("/models/upload")
async def upload_model(file: UploadFile = File(...)):
    """Upload file .pth atau .index ke folder models/ - TANPA BATASAN UKURAN"""
    
    if not file.filename:
        raise HTTPException(400, "Nama file kosong")
    
    if not file.filename.endswith(('.pth', '.index')):
        raise HTTPException(400, "Hanya file .pth atau .index yang diizinkan")
    
    save_path = MODELS_DIR / file.filename
    
    # Cek apakah file sudah ada
    if save_path.exists():
        raise HTTPException(400, f"File {file.filename} sudah ada. Hapus dulu jika ingin mengganti.")
    
    try:
        # Simpan file dengan chunk besar (1MB) untuk upload file besar
        file_size = 0
        chunk_count = 0
        chunk_size = 1024 * 1024  # 1MB chunk
        
        print(f"\n📤 Mulai upload: {file.filename}")
        
        with save_path.open("wb") as f:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                file_size += len(chunk)
                chunk_count += 1
                
                # Print progress setiap 100MB
                if file_size % (100 * 1024 * 1024) < chunk_size:
                    print(f"   ⏳ Progress: {file_size / 1024 / 1024:.1f} MB")
        
        size_mb = file_size / 1024 / 1024
        print(f"✅ Berhasil: {file.filename} ({size_mb:.2f} MB) - {chunk_count} chunks")
        
        return {
            "success": True, 
            "filename": file.filename, 
            "size_mb": round(size_mb, 2)
        }
    except Exception as e:
        # Hapus file jika gagal di tengah
        if save_path.exists():
            save_path.unlink()
        print(f"❌ Gagal upload: {e}")
        raise HTTPException(500, f"Gagal menyimpan file: {str(e)}")

@app.delete("/models/{filename}")
async def delete_model(filename: str):
    """Hapus file model dari folder models/"""
    file_path = MODELS_DIR / filename
    
    if not file_path.exists():
        raise HTTPException(404, "File tidak ditemukan")
    
    # Proteksi: jangan hapus model yang sedang aktif
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
    """Ganti model yang aktif"""
    if not pth:
        raise HTTPException(400, "File .pth wajib dipilih")
    
    # Kosongkan string kosong jadi None
    if index == "" or index == "null":
        index = None
    
    success = load_model(pth, index)
    if not success:
        raise HTTPException(500, "Gagal load model. Cek console server.")
    
    return {"success": True, "pth": pth, "index": index}

# ═════════════════════════════════════════════════════════════════════════════
# ROUTES - VOICE CONVERSION
# ═════════════════════════════════════════════════════════════════════════════
@app.post("/convert")
async def convert_voice(
    audio: UploadFile = File(...),
    pitch: int = Form(0),              # geser nada (semitone). -24 rendah, +24 tinggi. 0 = tidak berubah.
    index_rate: float = Form(0.75),    # 0–1. Bobot retrieval .index terhadap output. 0 = abaikan index (pakai .pth saja), 1 = timbre index dominan.
    filter_radius: int = Form(3),      # 0–7 (rata median filter). Smoothing kurva pitch. 0 = off, 3 = default aman, >3 makin halus tapi bisa "muted".
    rms_mix_rate: float = Form(0.25),  # 0–1. Campuran volume/energi asli vs model. 0 = pakai energi model, 1 = pakai energi audio input.
    protect: float = Form(0.33),       # 0–0.5. Proteksi konsonan tak bersuara & breathiness. 0 = off (bebas), 0.33 = default, mendekati 0.5 menjaga jelas tapi pitch kurang akurat.
):
    """Konversi suara dengan RVC.

    Parameter tuning:
      • pitch        → -12 = satu oktaf turun, +12 = satu oktaf naik. Cocokkan ke register model.
      • index_rate   → gunakan 0.5–0.8 untuk model matang; 0.75 default. Naikkan ke 1 kalau hasil
                       kurang mirip; turunkan ke 0 kalau muncul artefak/"robotan" atau tanpa .index.
      • filter_radius→ naikkan ke 5–7 kalau audio input berisik agar pitch tidak melompat.
      • rms_mix_rate → 0.25 = sebagian besar mengikuti model (alami untuk voice changer);
                       naikkan ke 1 kalau ingin dinamika volume asli terjaga (mis. berteriak tetap keras).
      • protect      → jaga 0.33 untuk ucapan jelas; turunkan ke 0 untuk nyanyian high-pitch.
    """
    if rvc_infer is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Belum ada model yang aktif. Upload dan pilih model dulu."}
        )

    # ── Validasi range parameter ────────────────────────────────
    if not -24 <= pitch <= 24:
        return JSONResponse(status_code=422, content={"error": f"pitch harus -24..24, dapat {pitch}"})
    if not 0.0 <= index_rate <= 1.0:
        return JSONResponse(status_code=422, content={"error": f"index_rate harus 0..1, dapat {index_rate}"})
    if not 0 <= filter_radius <= 7:
        return JSONResponse(status_code=422, content={"error": f"filter_radius harus 0..7, dapat {filter_radius}"})
    if not 0.0 <= rms_mix_rate <= 1.0:
        return JSONResponse(status_code=422, content={"error": f"rms_mix_rate harus 0..1, dapat {rms_mix_rate}"})
    if not 0.0 <= protect <= 0.5:
        return JSONResponse(status_code=422, content={"error": f"protect harus 0..0.5, dapat {protect}"})
    
    audio_bytes = await audio.read()
    temp_dir = Path(tempfile.gettempdir()) / "voice_changer"
    temp_dir.mkdir(exist_ok=True)
    
    safe_name = Path(audio.filename).stem
    input_path = temp_dir / f"in_{safe_name}.wav"
    output_path = temp_dir / f"out_{safe_name}.wav"
    
    try:
        with open(input_path, "wb") as f:
            f.write(audio_bytes)
        
        print(f"🔄 Converting: {audio.filename} (pitch={pitch}, index_rate={index_rate}, model={current_pth})")
        
        # Set parameter via attribute object
        rvc_infer.f0up_key = pitch
        rvc_infer.index_rate = index_rate
        rvc_infer.filter_radius = filter_radius
        rvc_infer.rms_mix_rate = rms_mix_rate
        rvc_infer.protect = protect
        
        # Jalankan inference (file langsung tersimpan)
        rvc_infer.infer_file(str(input_path), str(output_path))
        
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
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        for p in (input_path, output_path):
            if p.exists():
                p.unlink()

# ═════════════════════════════════════════════════════════════════════════════
# RUN SERVER - DENGAN KONFIGURASI UPLOAD BESAR
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "=" * 60)
    print("   🎤 RVC VOICE CHANGER - MULTI MODEL")
    print(f"   📦 RVC Loaded : {rvc_infer is not None}")
    print(f"   💻 Device     : {DEVICE}")
    print(f"   🎯 Current    : {current_pth or 'None'}")
    print(f"   📁 Models Dir : {MODELS_DIR.absolute()}")
    print(f"   📏 Max Upload : UNLIMITED")
    print("=" * 60)
    print("🚀 http://localhost:8000")
    print("=" * 60 + "\n")
    
    # Konfigurasi uvicorn untuk handle file besar
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        # Timeout panjang untuk upload file besar (10 menit)
        timeout_keep_alive=600,
        # Limit untuk request body (default Starlette 1MB, kita naikkan)
        # Ini tidak berlaku untuk multipart/form-data (upload file)
        # karena uvicorn streaming multipart secara otomatis
    )
    server = uvicorn.Server(config)
    server.run()