<div align="center">

# 🚀 NRA-Metadata

**Batch Metadata Studio & Microstock Compliance Engine untuk Era Generative AI**

Otomasi tingkat profesional untuk analisis visual, pembangkitan Title / Description / Keywords, injeksi langsung IPTC-XMP, dan ekspor CSV multi-agensi — dengan kepatuhan penuh terhadap regulasi 2025–2026.

[![Tests](https://img.shields.io/badge/Tests-230%2F230_Passing-success?style=for-the-badge)](#)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python)](#)
[![GUI](https://img.shields.io/badge/CustomTkinter-Modern_UI-8b5cf6?style=for-the-badge)](#)
[![Engine](https://img.shields.io/badge/Engine-ExifTool-ff69b4?style=for-the-badge)](#)
[![OS](https://img.shields.io/badge/Windows_Ghost_Spectre-Optimized-2ea043?style=for-the-badge&logo=windows)](#)
[![Compliance](https://img.shields.io/badge/Compliance-2026_Ready-8b5cf6?style=for-the-badge)](#)

</div>

---

## 🎯 Tentang Proyek

NRA-Metadata menggantikan kurasi manual yang memakan waktu berjam-jam dengan pipa kerja vision-AI yang presisi. Sistem membaca pratinjau visual (bukan nama file), mendeskripsikan aset secara kontekstual, menyetel keyword terhadap aturan tiap agensi, lalu mengukir hasilnya langsung ke biner file via ExifTool — tanpa prompt mentah tertulis di XMP, sehingga **integritas manifest C2PA tetap terjaga**.

Alur kerja inti:

- **Multi-Provider Vision LLM** — Gemini, OpenAI, Mistral, Groq, serta endpoint OpenAI-compatible/9router, dengan failover otomatis dan rotasi API key.
- **Preview Rendering Headless** — raster, EPS/AI (Ghostscript), SVG (Edge/svglib), dan video (FFmpeg) dirender jadi pratinjau sebelum dianalisis.
- **Normalisasi & Compliance Filter** — limit judul per-agensi, hard-cap keyword, deduplikasi/stemming, blacklist trademark, dan penegakkan kuota presisi.
- **Direct Embedding & Ekspor CSV** — metadata langsung di-injeksi ke IPTC/XMP + CSV multi-agensi siap unggah.

---

## ⚖️ Matriks Kepatuhan Microstock (2025–2026)

Nilai-nilai ini dieksekusi oleh `packages/shared_utils/filter.py` dan `csv_exporter.py`, diverifikasi menyeluruh ke pedoman resmi agensi.

| Agen | Panduan Judul | Panduan Deskripsi | Keyword | Catatan Keluhan Kepatuhan |
| :--- | :--- | :--- | :--- | :--- |
| **Adobe Stock** | Target SEO **50–70 karakter**; peringatan lunak (soft-warning) amber di rentang pelampauan; pemotongan ketat di batas maksimal (200) | Deskripsi makna penuh ≥ 5 kata | **5–49 keyword** | Pelarang kata pembuka spam: `Vector`, `Illustration`, `Isolated`, `Set of`, `Collection of`. Kategori Adobe (kode 1–21) dipetakan otomatis lewat `taxonomy.py`. |
| **Shutterstock** | Maksimal sesuai batas agensi, format kalimat profesional | Deskripsi **narasi kontekstual 250–800 karakter** (bukan daftar tag) | **7–50 keyword** | Format CSV ekspor mengikuti struktur resmi dashboard kontributor. |
| **Vecteezy** | Maksimum 150 karakter | Maksimum 200 karakter | **Tepat 30 keyword (hard-cap)** | Memenuhi persis batas kuota untuk menghindari **penolakan batch otomatis**; deduplikasi & stemming dijalankan sebelum pemangkasan. |
| **Freepik** | Maksimum 200 karakter | Maksimum 200 karakter | **5–50 keyword** | Delimiter wajib **titik-koma `;`** pada CSV; kolom dipisah dari spasi agar tidak rusak saat impor. |
| **Dreamstime** | Maksimum sesuai batas agensi | Lengkap & kontekstual | Kuota sesuai pedoman | **Injeksi otomatis pernyataan AI provenance** pada kolom metadata, memenuhi kewajiban disclosure. |
| **iStock / Getty** | Format editorial **5W**: `[City, Country - Month Day, Year]` | Deskripsi saksi mata, pasti, dan kontekstual | Free-text terms **≤ 64 karakter** per istilah | Caption editorial dibangun dari tanggal buat file yang dinormalisasi ke `YYYYMMDD`. |

*Algoritma pemangkasan teks memotong pada batas kata (`word-boundary`) — tidak pernah memenggal di tengah kalimat.*

---

## 🛡️ Standar IPTC 2025.1 & Integritas C2PA

Kepatuhan terhadap spesifikasi IPTC 2025.1 untuk asset yang diproduksi oleh AI diimplementasikan garis-keras di `backend/processors/exiftool_client.py` dan `packages/shared_utils/csv_exporter.py`:

- **`XMP:DigitalSourceType`** ditulis sebagai `trainedAlgorithmicMedia` (URI resmi `http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia`).
- **`XMP-iptcExt:AISystemUsed`** dan **`XMP-iptcExt:AISystemVersionUsed`** mencatat provider & model AI generatif yang digunakan.
- **Non-Destructive:** aplikasi **tidak pernah menulis prompt mentah alias workflow** apa pun ke XMP. Hal ini menjaga integritas dan validitas **manifest C2PA** di file.
- Pada asset buatan manusia, sistem **membuang junk metadata AI** (mis. `PNG:parameters`, `PNG:prompt`, `PNG:workflow`) serta `XMP-xmpGImg` agar tidak salah-etik sebagai konten AI.
- Semua penulisan dicapai lewat streaming argument ExifTool (bukan file JSON sementara) dengan flag `-api Windows=1`, `-api LargeFileSupport=1`, dan overwrite in-place.

---

## 🖥️ Dirancang untuk Windows Ghost Spectre

Aplikasi dioptimalkan untuk instalasi Windows *debloated* seperti **Ghost Spectre Superlite**:

- **Zero Console Flash:** seluruh subprocess (ExifTool, Ghostscript, FFmpeg) dijalankan dengan flag **`CREATE_NO_WINDOW` + `SW_HIDE`** (`backend/processors/_tools.py::no_window_kwargs`). Tidak ada window `cmd.exe` yang berkedip di tengah batch — dan tidak ada freeze GUI ("Not Responding") saat menunggu tool eksternal.
- **3-Level Smart Probing:** deteksi biner ExifTool/Ghostscript/FFmpeg berjalan dalam urutan — (1) pindai rekursif folder `tools/` proyek (shallow-first), (2) PATH sistem, (3) lokasi instalasi standar Windows — dengan probe verifikasi **≤ 2 detik** dan **auto-skip** bila biner valid sudah ditemukan (`system_detector.py`).
- **Sorting Versi Cerdas:** Ghostscript diurutkan secara numerik (`gs10 > gs9`) agar tidak memilih instalasi usang di Program Files.
- **Setup Script Mandiri:** `scripts/setup_tools.ps1` dan `scripts/setup_tools.bat` — unduh otomatis ExifTool, Ghostscript, dan FFmpeg dengan **TLS 1.2/1.3**, User-Agent browser untuk menghindari *HTTP 403 Forbidden*, verifikasi biner ≤ 2 detik, dan *idempotent* (melewati tool yang sudah ada).

---

## 🧱 Arsitektur

Struktur modular dengan `separation of concerns` antara UI, jaringan AI, konfigurasi terenkripsi, dan eksekusi utilitas OS.

```text
NRA-Metadata/
├── apps/
│   ├── cli/
│   │   └── src/main.py              # Headless batch runner (entrypoint: nra-cli)
│   └── desktop/
│       └── src/main.py              # Orkestrasi GUI CustomTkinter, migrasi key, modal auth
├── backend/
│   ├── ai/
│   │   ├── provider_router.py       # Dispatch multi-provider + builder prompt vision
│   │   └── failover_handler.py      # Exponential backoff, rotasi key, deteksi rate-limit/auth
│   ├── core/
│   │   ├── config_manager.py        # Enkripsi DPAPI config.enc, SQLite cache (SHA-256), import RJ
│   │   ├── worker_pool.py           # ThreadPoolExecutor, pause/cancel, companion sync, cost tracker
│   │   └── utils/key_manager.py     # Parser fleksibel API key & factory client OpenAI-compatible
│   └── processors/
│       ├── exiftool_client.py       # Streaming ExifTool: IPTC/XMP, tanggal, pembersihan AI junk
│       ├── system_detector.py       # Smart probing 3 level + cache deteksi tool
│       ├── media_converter.py       # Render pratinjau: raster/EPS/SVG/video
│       ├── ghostscript_preview.py   # Rasterisasi -dSAFER + fallback ExifTool -PreviewImage
│       └── _tools.py                # no_window_kwargs, exiftool_flags, pencatat file gagal
├── packages/
│   └── shared_utils/
│       ├── filter.py                # PLATFORM_RULES, normalisasi, compliance validator, Auto-Fix
│       ├── csv_exporter.py          # CSV per-agensi + sanitasi teks + caption editorial 5W
│       ├── taxonomy.py              # Kategori Adobe (kode 1–21) & Shutterstock (27)
│       ├── tools_setup.py           # Downloader biner terverifikasi (idempotent)
│       ├── license_manager.py       # HWID MachineGuid, session offline, auto-kick lintas perangkat
│       ├── cost_tracker.py          # Estimasi biaya USD per provider/model
│       ├── env_check.py             # Diagnostik lingkungan (ExifTool, Edge)
│       ├── updater.py               # Pemeriksa versi GitHub non-blocking
│       └── logger.py                # Logging konsol + CSV terstruktur
├── scripts/
│   ├── setup_tools.bat              # One-click setup biner eksternal
│   ├── setup_tools.ps1              # Bootstrap PowerShell ber-TLS 1.2+
│   └── build_portable.py            # Rakit distribusi portabel (.zip) + skeleton tools/
├── tests/                           # 230 unit test (unittest, tanpa framework)
├── tools/                           # Biner eksternal: ExifTool, Ghostscript, FFmpeg (diisi setup_tools)
├── run_app.bat                      # Zero-setup launcher
├── requirements.txt
└── pyproject.toml                   # requires-python >= 3.11, script nra-cli
```

### Alur Pipeline

```text
Ingest ──► Preview Rendering ──► Vision Prompting ──► Metadata Normalization
   │            │                      │                     │ & Compliance Filter
   │      (raster/EPS/SVG/       (multi-provider,      (limit judul, hard-cap
   │       video → gambar)        target_kw default 49)  keyword, dedup, blacklist)
   ▼
Direct Embedding (ExifTool IPTC/XMP)  ──►  Multi-Agency CSV Generation
                                              (Adobe, SS, Freepik, Vecteezy,
                                               Dreamstime, iStock/Getty)
```

### Ketahanan Runtime

- **Failover AI:** backoff eksponensial `[3s, 6s, 12s, 24s, 48s]`, hingga 5 percobaan, rotasi API key thread-safe, deteksi rate-limit (HTTP 429 / quota) dan kegagalan autentikasi (401/403), serta pindah provider otomatis.
- **Worker Pool:** `ThreadPoolExecutor` dengan pause/cancel sinyal, pembersihan worker stale, cache metadata berbasis hash **SHA-256** (SQLite WAL), pemindai companion files (`.eps` + `.jpg`, `.svg`, `.mov`, `.zip`).
- **Anti-Korupsi File:** sebelum injeksi, atribut *read-only* dibersihkan; penulisan ExifTool streaming; file gagal dicatat di `failed_files.log` untuk retry manual.
- **Batasan MIC:** semua subprocess berjalan pada *Medium Integrity Level* tanpa eskalasi, selaras dengan kebijakan keamanan Windows modern.

---

## 💿 Keamanan & Lisensi

- **DPAPI Local Encryption:** API key & konfigurasi disimpan terenkripsi native Windows di `config.enc` (ctypes DPAPI) — tidak pernah plaintext.
- **Serverless Auth:** backend Google Apps Script untuk registrasi, HWID binding (MachineGuid), sesi offline hingga 3 hari, dan auto-kick bila akun dipakai perangkat lain.
- **Injection Shield:** seluruh eksekusi tool eksternal berbasis daftar argumen (`list`), tanpa shell, dan validasi path absolut (anti *command injection* / *path traversal*).

---

## 🚀 Panduan Instalasi & Setup

### Persyaratan

- **Windows 10/11** (atau Windows Ghost Spectre Superlite) — modul DPAPI & HWID berjalan native di NT.
- **Python ≥ 3.11** (wajib; syarat `pyproject.toml`).
- **Microsoft Edge** — untuk rendering headless pratinjau SVG.

### 1. Zero-Setup (direkomendasikan)

Klik dua kali **`run_app.bat`** di folder proyek. Launcher mendeteksi Python yang tersedia, atau mengunduh environment portabel lokal beserta seluruh dependensinya secara otomatis, lalu membuka aplikasi.

### 2. Setup Manual

```bash
git clone https://github.com/novri-ra/NRA-Metadata.git
cd NRA-Metadata
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Setup Biner Eksternal

Jalankan sekali (idempotent, dapat diulang kapan saja):

```powershell
# PowerShell
Set-ExecutionPolicy -Scope Process Bypass
powershell -ExecutionPolicy Bypass -File scripts\setup_tools.ps1
```

```bat
:: atau lewat Command Prompt / double-click
scripts\setup_tools.bat
```

Unduhan dijalankan dengan TLS 1.2+, User-Agent browser, verifikasi biner ≤ 2 detik, dan penolakan HTML (anti-halaman 403). ExifTool, Ghostscript, dan FFmpeg akan ditempatkan di `tools/`.

### 4. Konfigurasi API Key

Buka aplikasi desktop dan masukkan API key di panel provider, atau impor otomatis dari konfigurasi RJ Auto Metadata. Key disimpan terenkripsi DPAPI di:

```text
%USERPROFILE%\Documents\NRA Metadata\config.enc
```

Untuk mengubah lokasi simpan (contoh: di portable/Flashdisk), set variabel lingkungan **`NRA_CONFIG_DIR`**.

### 5. Menjalankan Aplikasi

```bash
python apps/desktop/src/main.py
```

### 6. Headless CLI (Batch Server / Otomasi)

```bash
# melalui entrypoint terpasang
nra-cli --input DIR --output OUT --provider Gemini --api-key KEY --target-kw 49 --workers 2

# atau langsung
python apps/cli/src/main.py --input DIR --output OUT --provider Mistral --api-key KEY --import-rj
```

Argumen: `--provider {Gemini,OpenAI,Mistral}` · `--target-kw` (default `49`) · `--workers` (default `2`) · `--config-dir` · `--import-rj [PATH]` (impor key dari RJ sebelum jalan).

### 7. Menjalankan Pengujian

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

**230/230 test lulus** (tanpa framework, murni `unittest`). CI `windows-latest · Python 3.11` menjalankan suite yang sama plus lint `flake8` (E9/F63/F7/F82, `max-complexity=10`, `max-line-length=127`).

---

## 🧪 Troubleshooting Umum

| Gejala | Solusi |
| :--- | :--- |
| `ExifTool not found` | Jalankan `scripts/setup_tools.ps1`; pastikan `tools/exiftool` terisi, atau ExifTool ada di PATH. |
| CSV Freepik rusak saat impor | Gunakan file dari folder ekspor — delimiter titik-koma `;` sudah diterapkan; jangan ganti dengan koma. |
| Metadata tidak tertulis pada `.eps/.ai` | Tutup file di Adobe Illustrator saat batch berjalan (Windows file-locking); pastikan atribut read-only dilepas. |
| Proses AI mandek (rate limit) | Pool melakukan backoff otomatis hingga 48 detik + rotasi key; periksa konsol untuk laporan resmi. |
| Sesi berakhir "login perangkat lain" | Login ulang dari perangkat aktif; auto-kick melindungi sesi dari kebocoran lisensi. |

---

## 📜 Lisensi

MIT — © 2026 Novri Rizki Akbar. Utilitas metadata `ExifTool` (Phil Harvey) digunakan di bawah lisensi GPL/Artistic yang berlaku.

> **"Empower Your Portfolio, Scale Your Keywords, Secure Your Workflow."**