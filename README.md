<div align="center">

# 🚀 NRA-Metadata

**Batch Metadata Studio & Microstock Compliance Engine untuk Era Generative AI**

Otomasi tingkat profesional untuk analisis visual, pembangkitan Title / Description / Keywords, injeksi langsung IPTC-XMP, dan ekspor CSV multi-agensi — dengan kepatuhan penuh terhadap regulasi 2026 dan perlindungan keamanan zero-zip-slip.

[![Tests](https://img.shields.io/badge/Tests-235%2F235_Passing-success?style=for-the-badge)](#)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=for-the-badge&logo=python)](#)
[![GUI](https://img.shields.io/badge/CustomTkinter-Modern_UI-8b5cf6?style=for-the-badge)](#)
[![Security](https://img.shields.io/badge/Security-Zero_Zip--Slip-red?style=for-the-badge)](#)
[![OS](https://img.shields.io/badge/Windows_Ghost_Spectre-Optimized-2ea043?style=for-the-badge&logo=windows)](#)
[![Compliance](https://img.shields.io/badge/Compliance-2026_Ready-8b5cf6?style=for-the-badge)](#)

</div>

---

## 📦 Instalasi & Penggunaan (Standalone Installer)

Rilis terbaru menyediakan Windows Installer yang dapat dijalankan secara mandiri.

* **Lokasi Artefak:** `dist/NRA-Metadata-Setup-Final.exe`
* **Instalasi:** Jalankan installer wizard untuk instalasi otomatis (secara default ke `C:\Program Files\NRA-Metadata`).
* **Uninstalasi:** Prosedur uninstall resmi didukung melalui *Windows Settings > Installed Apps*, atau langsung mengeksekusi `unins000.exe` di direktori instalasi.

---

## 🛠️ Konfigurasi Google Apps Script (Auth Server)
Jika Anda men-deploy server autentikasi mandiri (Google Apps Script), pastikan pengaturan *New Deployment* berikut untuk menghindari error *redirect* halaman HTML:
- **Execute as**: Me (`email_anda@gmail.com`)
- **Who has access**: Anyone
- **URL Web App**: Pastikan berakhiran `/exec` (bukan `/dev`)

*(Untuk lewati autentikasi sepenuhnya, gunakan **Offline Mode** di aplikasi atau jalankan dengan enviroment variable `DEBUG=1` / file `.dev_mode`).*

---

## 🎯 Tentang Proyek

NRA-Metadata menggantikan kurasi manual yang memakan waktu berjam-jam dengan pipa kerja vision-AI yang presisi. Sistem membaca pratinjau visual (bukan nama file), mendeskripsikan aset secara kontekstual, menyetel keyword terhadap aturan tiap agensi, lalu mengukir hasilnya langsung ke biner file via ExifTool — tanpa prompt mentah tertulis di XMP, sehingga **integritas manifest C2PA tetap terjaga**.

Alur kerja inti:

- **Multi-Provider Vision LLM** — Gemini, OpenAI, Mistral, Groq, serta endpoint OpenAI-compatible/9router, dengan failover otomatis dan rotasi API key. Tahan terhadap *thread-starvation*.
- **Preview Rendering Headless** — raster, EPS/AI (Ghostscript), SVG (Edge/svglib), dan video (FFmpeg) dirender jadi pratinjau sebelum dianalisis.
- **Vision Ingestion Engine** — Compositing kanvas RGBA transparan di atas warna putih pekat (255, 255, 255) sebelum parsing AI untuk mencegah kesalahan deteksi dan halusinasi background hitam.
- **Normalisasi & Compliance Filter** — limit judul per-agensi, hard-cap keyword, deduplikasi/stemming, blacklist trademark, dan penegakkan kuota presisi.
- **Direct Embedding & Ekspor CSV** — metadata langsung di-injeksi ke IPTC/XMP secara thread-safe menggunakan *chunked streaming* + CSV multi-agensi siap unggah.

---

## ⚖️ Matriks Regulasi Microstock (Pembaruan 2026)

Nilai-nilai ini dieksekusi secara presisi oleh `filter.py` dan `csv_exporter.py`, diverifikasi menyeluruh ke pedoman resmi masing-masing agensi per tahun 2026.

| Agen | Panduan Judul | Panduan Deskripsi | Keyword | Catatan Keluhan Kepatuhan |
| :--- | :--- | :--- | :--- | :--- |
| **Adobe Stock** | Target SEO **50–70 karakter**; peringatan lunak (soft-warning) amber; max 200 karakter. | Deskripsi makna penuh ≥ 5 kata. | **5–49 keyword** | Pelarang kata pembuka spam: `Vector`, `Illustration`, `Isolated`. Kategori Adobe dipetakan otomatis via kode taxonomy. |
| **Shutterstock** | **Maksimal 2048 karakter** (update limit 2026). | Deskripsi **narasi kontekstual 250–800 karakter**. | **7–50 keyword** | Menolak mutlak pembuatan menggunakan GenAI (AI checkbox `false` dalam ekspor CSV). |
| **Vecteezy** | Terbatas **3–8 kata**, maksimal 200 karakter. Karakter diizinkan: Alfanumerik + `[ , . - ' ]` | Maksimum 200 karakter. | **5–50 keyword** | Aturan karakter spesial yang sangat ketat diawasi via `Regex Validator` sebelum batch dikirim. |
| **Freepik** | Maksimum 200 karakter, minimal 5 kata. | Maksimum 200 karakter. | **5–50 keyword** | Delimiter wajib **titik-koma `;`** pada CSV; kolom Tag dipisah spasi. Wajib set bendera Generative AI. |
| **Dreamstime**| Maksimal 200 karakter, minimal 5 kata. | Deskripsi 5 kata hingga 2000 karakter. | **5–80 keyword** | Injeksi otomatis status AI provenance jika dicentang oleh user. |
| **iStock/Getty**| Format editorial **5W**, maksimum 250 karakter. | Maksimum 2000 karakter. | **Maksimal 50 keyword** (tiap keyword limit ≤ 64 char). | Free-text taxonomy dan penegakan format *factual timestamp* (YYYYMMDD). |

*Algoritma pemangkasan teks memotong pada batas kata (`word-boundary`) — tidak pernah memenggal di tengah kalimat.*

---

## 🛡️ Arsitektur Keamanan & Concurrency 

Sistem secara garis-keras mencegah bottleneck dan ancaman arbitrase runtime:
- **Zero-Zip-Slip Secured**: Ekstraksi dependensi biner otomatis (`tools_setup.py`) secara ketat menolak payload kompresi berisi absolute path traverse (`../`) guna mencegah Remote/Arbitrary Code Execution (ACE) di luar direktori proyek target.
- **Thread-Safe I/O**: Interaksi dengan output CSV massal (exporter metadata) serta sistem Cost Tracker (akuntan token USD) dibungkus instance `threading.Lock()`. Mencegah korupsi race condition yang dapat menyebabkan hilangnya data metadata di CSV saat 20 worker menulis bersamaan.
- **Non-blocking UI Dialogs**: Eksekusi massal (Batch Apply, Batch Replace, dan pengetesan Test Connection FTP) dijalankan terlepas dari *main thread loop* Tkinter lewat thread daemon yang melaporkan via sinkronisasi antrean UI lokal (`root.after`). UI tidak lagi mengalami status "Not Responding" selama file system crawl.
- **Anti Thread Starvation**: Proses IO HTTP lock untuk Mistral dilepas saat `requests.post` API memanggil jaringan. Menjamin API Request mematuhi batas *rate limit* per-detik tanpa membekukan seluruh kolam worker internal.
- **Chunked Video Streaming**: Sinkronisasi injeksi IPTC (ExifTool Pipe) pada metadata kini tidak menyalin seluruh memory file berukuran GB-an dari disk ke RAM. Buffer stream berjalan statik `65536 byte (64 KB) per chunk` mencegah instansi OOM (Out of Memory) ketika memproses render video 4K/besar. 
- **Deterministic Disk Cleanup**: Semua sisa temp rendering Ghostscript/FFmpeg dan Edge dihapuskan pada blok `finally` mutlak. Menghapus jejak footprint disk meski sistem throw exception error/timeout.

---

## 🛡️ Standar IPTC 2025.1 & Integritas C2PA

Aplikasi mencatat aset produksi AI secara non-destruktif:
- **`XMP:DigitalSourceType`** ditulis sebagai `trainedAlgorithmicMedia` URI.
- **`XMP-iptcExt:AISystemUsed`** dan **`XMP-iptcExt:AISystemVersionUsed`** mencatat provider AI generatif yang diketik dalam konfigurasi UI.
- **Non-Destructive:** aplikasi tidak pernah menulis prompt mentah ke dalam XMP. Integritas **manifest C2PA** aman.
- **AI-Junk Cleansing:** Pada asset buatan manusia, membuang junk metadata (`PNG:parameters`, `PNG:workflow`) agar human-art tidak pernah mendapat cap salah *Generated by AI*.

---

## 🖥️ Dirancang untuk Windows Ghost Spectre

Aplikasi dioptimalkan untuk performa maksimum pada Windows instalasi ringan *debloated* (**Ghost Spectre Superlite**):

- **Zero Console Flash:** subprocess dijalankan dengan flag **`CREATE_NO_WINDOW` + `SW_HIDE`**. Tidak ada terminal `cmd.exe` berkedip hitam di tengah pengolahan batch.
- **3-Level Smart Probing:** deteksi biner ExifTool/Ghostscript/FFmpeg dilakukan berurutan — (1) Folder lokal `tools/`, (2) PATH Environment OS, (3) Standard instalasi `Program Files`. Verifikasi instan (≤ 2 detik) dan diskip langsung apabila biner operasional ditemukan.
- **Setup Script Mandiri:** Bootstrapper `scripts/setup_tools.bat` / `.ps1` memutar TLS 1.2+, membungkus identitas User-Agent Mozilla, auto bypass `ExecutionPolicy`, dan setup dependency tanpa menyentuh registry OS target.

---

## 🧱 Setup & Developer Guide

### Struktur Direktori

```text
NRA-Metadata/
├── apps/
│   ├── cli/src/main.py              # Headless batch runner (entrypoint: nra-cli)
│   └── desktop/src/main.py          # GUI CustomTkinter, session auth, wizard
├── backend/
│   ├── ai/                          # API Router, failover ring, RGBA tokenizer
│   ├── core/                        # ThreadPoolExecutor, DPAPI encryption, key parser
│   └── processors/                  # ExifTool pipes, system probe, SVGLib/Ghostscript
├── packages/
│   └── shared_utils/                # Compliance validator, CSV locks, Cost Tracker
├── scripts/
│   ├── setup_tools.bat/.ps1         # Auto downloader dependency biner
│   └── build_portable.py            # .zip compiler
├── tests/                           # 235 unit tests dengan full mock subsystem
├── tools/                           # Runtime binary storage (diisi oleh setup scripts)
├── run_app.bat                      # Zero-setup launcher utama 
└── pyproject.toml                   # Python 3.11+
```

### 1. Zero-Setup (Disarankan)
Klik dua kali **`run_app.bat`** di root folder. Bat launcher akan mendeteksi python global Anda, memeriksa virtual env lokal, atau langsung menarik dan merangkai library PIP dan meluncurkan main loop aplikasi.

### 2. Manual CLI Bootstrap
```bash
git clone https://github.com/novri-ra/NRA-Metadata.git
cd NRA-Metadata
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
scripts\setup_tools.bat
python apps/desktop/src/main.py
```

### 3. Pengujian Suite (Quality Control)
Kode telah ditesting dalam arsitektur penuh dengan **235 Unit Test Terverifikasi** yang meng-cover pipeline parsing JSON AI, ExifTool byte streams, CSV generation, sampai penolakan regulasi Shutterstock dan Vecteezy 2026.
```bash
python -m unittest discover tests -v
```

---

## 🧪 Troubleshooting Umum

| Gejala | Solusi |
| :--- | :--- |
| `ExifTool not found` | Eksekusi `scripts/setup_tools.bat` di terminal sebagai user normal. Pastikan file exe muncul dalam folder `tools/exiftool`. |
| CSV Freepik rusak saat impor | Jangan gunakan MS Excel! Excel otomatis memecah koma dan menghancurkan format titik-koma (`;`) wajib CSV Freepik. Buka CSV dengan Notepad. |
| Memory usage video MP4 naik terus | Stream memori limit ter-hardcode ke 64 KB chunk size. Jika Windows pagefile penuh, tambahkan memori swap Ghost Spectre. |
| AI Vision mendeskripsikan background hitam | Diperbaiki di patch v.Development. Alpha channel (transparansi LA/RGBA) di SVG dan PNG otomatis dikomposit warna putih sebelum dibaca oleh AI Vision (Gemini / Mistral / OpenAI). |

---

## 📜 Lisensi

MIT — © 2026 Novri Rizki Akbar. Utilitas *open-source* `ExifTool` (karya Phil Harvey) dan package biner terkait tertambat di bawah lisensi General Public License (GPL/Artistic). 

> **"Empower Your Portfolio, Scale Your Keywords, Secure Your Workflow."**