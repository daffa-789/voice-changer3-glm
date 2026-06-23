# 🎤 RVC Voice Changer — Multi Model

Aplikasi web berbasis FastAPI untuk mengubah suara menjadi karakter **apapun** menggunakan teknologi **RVC (Retrieval-based Voice Conversion)** dengan pipeline AI lengkap (SynthesizerTrn, HuBERT, dan FAISS Index).

## ✨ Fitur Utama

- 🧠 **Real AI Voice Conversion** - Menggunakan `rvc-python` dan model `.pth` asli
- ⏱️ **Durasi Presisi** - Audio 30 detik tetap 30 detik (tidak dipercepat)
- 🎧 **Preview Audio** - Dengar audio original sebelum convert
- 🎛️ **Kontrol Presisi** - Input manual nilai parameter (slider + number input)
- 📁 **Unlimited Upload** - Tidak ada batas ukuran file
- 🌐 **Web UI Modern** - Drag & drop, responsive, clean design
- 🚀 **Tanpa C++ Compiler** - Install mudah dengan pre-built wheels

## ⚠️ Solusi Teknis (PENTING!)

Proyek ini memecahkan **3 masalah klasik** RVC di Windows:

### 1. Masalah C++ Compiler (`crtdbg.h not found`)
**Solusi:** Menggunakan **pre-built wheel** `fairseq` dari HuggingFace yang sudah di-compile untuk Windows + Python 3.9.

### 2. Masalah Pip 24.1+ & OmegaConf
**Solusi:** Install wheel dengan flag `--no-deps` untuk bypass metadata `omegaconf` lama.

### 3. Masalah PyTorch 2.6+ (`weights_only=True`)
**Solusi:** Monkey-patch `torch.load` di `main.py` untuk memaksa `weights_only=False`.

## 🛠 Tech Stack

| Layer | Teknologi |
|-------|-----------|
| **Backend** | FastAPI, Uvicorn, Python-Multipart |
| **Frontend** | Vanilla HTML/CSS/JS |
| **AI Engine** | rvc-python, fairseq (Pre-built), PyTorch |
| **Audio ML** | HuBERT, FAISS-CPU, Torchcrepe |
| **Audio I/O** | Librosa, Soundfile, Pydub, SciPy |

## 📁 Struktur Folder
voice-changer/
├── models/
│ ├── Model1_e170_s54910.pth # Model AI (SynthesizerTrn)
│ └── added_IVF..._Model1_v2.index # FAISS Index
├── static/
│ ├── index.html # Frontend HTML
│ ├── style.css # Styling
│ └── script.js # Frontend Logic
├── main.py # Backend API
├── requirements.txt # Dependencies
└── README.md # Dokumentasi# voice-changer3-glm
