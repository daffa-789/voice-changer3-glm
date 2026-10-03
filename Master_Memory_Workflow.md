---
type: memory
kind: project
name: "master-voice-changer3-glm"
description: "Memory terpusat voice changer3 glm — web UI FastAPI untuk RVC multi-model (rvc-python), upload/pairing model, konversi suara"
scope: project
project: "voice changer3 glm"
status: broken-needs-models
updated: 2026-09-25
tags: ["memory/project", "project/voice changer3 glm"]
---

# Master Memory Workflow — voice changer3 glm

> Memory terpusat proyek ini, disusun 23 September 2026 dari kode. **Proyek ini tidak bisa
> dipakai apa adanya: folder `models/` KOSONG**, sehingga `/convert` selalu membalas 503.
> **Koreksi 2026-09-25:** klaim "`venv/` rawan ikut ter-commit" di R5 **sudah terjadi**, bukan
> lagi ancaman — diverifikasi lewat `git ls-files`. R5 juga diperluas dengan bentuk risiko
> keamanan yang sebelumnya tidak tercatat (CORS, path traversal, RCE via pickle).

**Lokasi:** `C:\Users\Daffa\Desktop\Folder Space AI\Folder Space Semester 6\voice changer3 glm`
**Status:** Semester 6, commit terakhir 2026-07-14 (`update`, `c6554ac3`), `main.py` dimodifikasi 2026-07-13.
Repo punya **5 commit** total, `main` **ahead 4** dari `origin/main` (`4e27fcb4`, 2026-06-23), dan
**tanpa `.gitignore`**; 99,98% berkas ter-track adalah `venv/` (rinci di R5). Nama projek menyandang
"glm" (dibuat bersama model GLM), ukuran folder ±3,6 GB — hampir semuanya `venv/`.

## R1. Angka Kunci

| Aspek | Nilai |
|---|---|
| Bentuk | Web UI FastAPI + `main.py` tunggal (618 baris) + `static/` (±1.196 baris) → ±1.814 baris / 4 file |
| Engine | **RVC** (Retrieval-based Voice Conversion) via `rvc-python==0.1.5` |
| Dependensi kunci | `fastapi==0.128.8`, `uvicorn[standard]==0.39.0`, `torch`/`torchaudio` ≥2.0, `faiss-cpu==1.7.3`, `torchcrepe`, `librosa`, `pyworld`, `praat-parselmouth`, `hydra-core==1.0.7`, wheel `fairseq` cp310 (dari HF `Jmica/rvc`) |
| Python | venv **3.10.11** — wheel fairseq ter-pin cp310 |
| Server | `python main.py` → uvicorn `0.0.0.0:8000` — **bind ke semua interface**, tanpa auth (lihat R5) |
| Model | `models/` **0 berkas** (tidak ada `.pth` / `.index`, termasuk `trained_index/`) |

## R2. Cara Menjalankan (kalau model sudah ada)

```bash
# Windows, dari ROOT proyek (path model relatif terhadap CWD!)
.\venv\Scripts\activate
python main.py          # → http://localhost:8000
```
Letakkan pasangan `*.pth` + `*.index` di `models/`, atau unggah lewat UI.
**⚠️ Sebelum menyalakan:** server bind `0.0.0.0:8000` tanpa auth dan tanpa rate limit, dan
endpoint upload menerima file yang nanti dieksekusi `torch.load` — baca dulu blok keamanan di R5
sebelum menyalakannya di jaringan bersama.

## R3. Fitur Nyata di `main.py`

- Monkey-patch `torch.load(weights_only=False)` — wajib, kalau tidak `rvc-python` gagal muat checkpoint.
- **Pairing otomatis `.pth` ↔ `.index`** (exact lalu contains match); deteksi versi model **v1/v2**
  lewat keberadaan key `weight`.
- Endpoint: `/`, `/health`, `/api/status`, `/models`, `/models/paired`, `POST /models/upload`,
  `POST /models/upload-pair`, `DELETE /models/{filename}`, `POST /set_model`, `/set_model_by_name`,
  `POST /convert`.
- Parameter `/convert`: pitch **−24…24**, `index_rate` 0…1, `f0_method` ∈
  `rmvpe | fcpe | harvest | pm | crepe | mangio-crepe`, `filter_radius`, `rms_mix_rate`, `protect`,
  `auto_enhance`.
- `enhance_audio()` memakai Butterworth `filtfilt`; output ditulis ke
  `tempfile.gettempdir()/voice_changer`.
- `static/` = `index.html` + `script.js` + `style.css` (vanilla), di-mount `StaticFiles`.

## R4. Mismatch README (49 baris)

1. README menyebut wheel fairseq untuk **Python 3.9** — pin aktual di `requirements.txt` **cp310**.
2. README mengasumsikan model sudah tersedia ("Unlimited Upload", "Real AI Voice Conversion") —
   tidak dapat diverifikasi dan **tidak benar di kondisi sekarang** (folder model kosong).

## R5. Status, Risiko & Gotchas

### 🔴 Fungsional
- **Butuh model RVC** (`.pth` + `.index`) agar berfungsi; tanpanya aplikasi hanya UI + 503.
  Diverifikasi 25 Sep 2026: `models/` berisi **0 berkas** (dan tidak ada satu pun file di bawah
  `models/` yang ter-track git — `git ls-files models` = kosong), jadi model juga hilang di hasil clone.

### 🔴 `venv/` SUDAH ter-commit — bukan lagi risiko "rawan"
**Koreksi 2026-09-25:** versi lama menulis "**Tidak ada `.gitignore`** → `venv/` dan `models/` rawan
ikut ter-commit". Realitasnya lebih buruk: itu **sudah terjadi**.

- `git ls-files` → **41.855 berkas ter-track**, dan **41.848 di antaranya ada di bawah `venv/`** (99,98%).
  Hanya **7 berkas** yang bukan `venv/`: `main.py`, `requirements.txt`, `README.md`,
  `static/index.html`, `static/script.js`, `static/style.css`, `.vscode/settings.json`.
- Penyebab: commit **`bfaaf87e` "update py ke 3.10"** (2026-06-25) yang menambahkan `venv/`
  (41.590 berkas saat itu), lalu bertambah jadi 41.848 di `29d8d01d` "update lagi".
- **Belum ter-push** — `main` **ahead 4** dari `origin/main`; `origin/main` masih di `4e27fcb4`
  (2026-06-23) yang berisi **0 berkas `venv/`**. Ini satu-satunya kabar baik di bagian ini.
- Pemulihan lokal (lakukan SEBELUM ada yang menekan `git push`):
  `git rm -r --cached venv` lalu buat **`.gitignore`** — saat ini **file `.gitignore` memang tidak ada
  sama sekali** di repo (dicek `ls -la`, bukan cuma kosong). Setelah itu 4 commit lokal bisa di-commit
  dengan `venv/` keluar dari index.
  Kalau terlanjur ter-push, repo butuh penulisan ulang riwayat (`git filter-repo`) — `git rm --cached`
  saja tidak mengecilkan repo yang sudah naik ke GitHub.
- ⚠️ **`git rm --cached` tidak mengembalikan disk.** `venv/` = 2,2 GB dan `.git/` **sudah membengkak ke
  ±1,5 GB** karena blob 41 ribu file itu ter-object di lokal (`git count-objects -v -H`). Untuk
  reclaim: buang `venv/` dari seluruh riwayat lokal (`git filter-repo` / `BFG`) lalu
  `git reflog expire --expire=now --all && git gc --prune=now`, atau clone ulang dari `origin/main`
  yang masih bersih. Ukur dulu sebelum menyimpulkan "sudah rapi".
- Catatan: `README.md` juga sudah dihapus dari working tree (` D` di `git status`) karena isinya diserap
  ke arsip di bawah — belum di-stage.

### 🔴 Bentuk risiko keamanan (tidak tercatat sama sekali sebelumnya)
Semua titik ini ada di `main.py` tunggal, dan saling menguatkan:

1. **CORS dikonfigurasi saling bertentangan** — `main.py:40-42`:
   `CORSMiddleware` dengan `allow_origins=["*"]` **merangkap** `allow_credentials=True`. Kombinasi ini
   membuat semua endpoint bisa dipanggil dari origin mana pun; browser mana pun yang sedang membuka
   halaman di mesin ini bisa jadi pijakan.
2. **Nama file dari klien dipakai mentah sebagai path (path traversal).**
   - Upload `POST /models/upload` (`main.py:343-356`): `filename = file.filename` lalu
     `save_path = MODELS_DIR / filename`, plus `save_path.parent.mkdir(parents=True, exist_ok=True)`.
     Yang divisifikasi **hanya** ekstensi (`endswith('.pth'/'.index')`), tidak ada pembersihan
     `..` — nama seperti `../../berkas.pth` tertulis di luar `models/`, dan `mkdir(parents=True)`
     ikut membuat direktorinya.
   - Hapus `DELETE /models/{filename}` (`main.py:445-457`): `file_path = MODELS_DIR / filename`
     langsung di-`.unlink()`. FastAPI melarang `/` di segmen itu, tapi `..\` tidak dibersihkan dan
     mesinnya Windows → penghapusan di luar `models/` terbuka. Endpoint ini juga tidak menuntut
     autentikasi apa pun.
3. **File unggahan akhirnya dieksekusi `torch.load` (pickle) ⇒ remote code execution.**
   `main.py:11-16` me-monkey-patch `torch.load` agar memaksa `weights_only=False`, dan
   `detect_model_version()` memanggil `torch.load(pth_path, map_location="cpu")` (`main.py:204`)
   yang dipicu `load_model()` dari `/set_model` & `/set_model_by_name` (dan otomatis saat startup,
   `main.py:281`). Alur serangannya lengkap: unggah `.pth` berisi pickle jahat → panggil
   `/set_model` → kode berjalan sebagai proses server. Monkey-patch yang "wajib supaya rvc-python jalan"
   inilah yang menghapus satu-satunya pertahahan PyTorch terhadap pickle.
4. **Permukaan jaringannya terbuka:** `uvicorn.Config(app, host="0.0.0.0", port=8000,
   timeout_keep_alive=600)` + `uvicorn.Server(config).run()` (`main.py:611-618`) —
   **tanpa autentikasi dan tanpa rate limit di endpoint mana pun**, termasuk unggah & hapus model.
   Jadi poin 1-3 bisa dijangkau siapa pun yang bisa merute ke port 8000 di LAN. **Jangan pernah
   proyek ini jalan di jaringan bersama**, dan jangan dibalik ke `0.0.0.0` tanpa proxy + auth.
5. **`GET /api/status` membocorkan path absolut server** — `main.py:309` mengirim
   `"models_dir": str(MODELS_DIR.absolute())` ke klien anon. Bukan kritis sendiri, tapi memberi
   penyerang kepastian struktur direktori untuk serangan traversal di atas.

### 🟡 Gotchas kode yang menjebak saat "merapikan"
- **`f0_method` bisa diam-diam kembali ke `rmvpe`.** Di `/convert`, nilainya di-set lewat guard
  `hasattr` — `if hasattr(rvc_infer, 'f0_method')` dan `if hasattr(rvc_infer, 'f0_extractor')`
  (`main.py:556-559`). Kalau `rvc-python` di-upgrade dan kedua atribut itu hilang/berganti nama,
  guard-nya **tidak** melempar error: parameter pilihan user hanya diabaikan dan model tetap memakai
  default internal (`rmvpe`). Diperparat oleh validasi di `main.py:534-535` yang **senyap** memaksa
  nilai di luar daftar menjadi `"rmvpe"` alih-alih menolak request. Jangan simpulkan "metode F0 tidak
  pengaruhi hasil" — cek dulu atributnya masih ada.
- **Jangan "perbaiki" anotasi `get_paired_models()`.** `main.py:154` menulis
  `-> List[Dict[str, Any]]` tetapi `main.py:199` mengembalikan **tuple** `(paired_models, orphaned_indices)`.
  **Tiga** pemanggil sudah bergantung pada bentuk tuple itu dan melakukan unpacking:
  `/models` (`:319`), `/models/paired` (`:331`), dan `/models/upload` (`:381`, `paired_models, _`).
  Menyelaraskan anotasi dengan benar (`return paired_models` saja) akan merusak ketiga endpoint itu —
  kalau mau membereskan, ubah pemanggilnya juga, bukan hanya type hint-nya.
- **Tidak ada `.gitignore`** sama sekali (lihat lagi blok `venv/` di atas) → `models/` pun ikut rawan
  ter-commit kalau model diunduh ke situ.
- `MODELS_DIR = Path("models")` relatif terhadap CWD → jalan hanya dari root proyek.
- `hydra-core==1.0.7` sangat lama; bisa bertabrakan dengan paket modern.
- Pin wheel fairseq di `requirements.txt:9` adalah **cp310** (Python 3.10.11), bukan 3.9 seperti
  README — jadi venv lama tidak bisa dipakai ulang begitu saja setelah upgrade Python.

## R6. Aturan Memory Proyek Ini

Berkas ini satu-satunya memory terpusat proyek. Perubahan berarti dicatat di sini.

---

## Peta Dokumen Proyek

Berkas ini adalah **satu-satunya memory terpusat** untuk proyek `voice changer3 glm`.
Perubahan berarti dicatat di sini lewat commit `docs(memory): catat …`.

### Diserap ke arsip di bawah (file aslinya dihapus)
- `voice changer3 glm` root: `README.md` → **file aslinya dihapus**

### Dibiarkan (bukan memory)
- (tidak ada)

---

## Arsip Dokumen Sumber (verbatim)

Isi setiap sumber dipertahankan apa adanya; separator hanya menandai batas antar dokumen.
Diarsipkan saat konsolidasi memory 2026-09-23 (generator satu-kali pakai, sudah dihapus)

<!-- ARCHIVE-BEGIN -->
<details>
<summary>README.md · 49 baris · disalin verbatim</summary>

<!-- BEGIN SOURCE: README.md -->

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

<!-- END SOURCE: README.md -->
</details>
<!-- ARCHIVE-END -->
