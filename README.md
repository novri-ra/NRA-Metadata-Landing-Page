<div align="center">
  <img src="https://img.shields.io/badge/Status-Active_Development-success?style=for-the-badge&logo=github" alt="Status" />
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python" />
  <img src="https://img.shields.io/badge/CustomTkinter-Modern_UI-8b5cf6?style=for-the-badge&logo=pypi" alt="CustomTkinter" />
  
  <h1>NRA-Metadata</h1>
  <p><b>AI-Powered Microstock Metadata Generator & Embedder</b></p>
  <p>Alat otomasi tingkat profesional untuk pembuatan, manajemen, dan injeksi metadata (Title, Description, Keywords) ke aset visual microstock. Ditenagai oleh Multi-Provider Vision AI (Mistral, Gemini, OpenAI, Groq) dan dirancang untuk alur kerja kontributor massal.</p>
</div>

---

## ✨ Fitur Unggulan

Aplikasi ini dilengkapi dengan fitur tingkat mahir untuk memastikan metadata yang dihasilkan memiliki SEO optimal, relevan, dan 100% patuh terhadap aturan standar agensi microstock global.

### 🧠 Multi-Provider AI Engine & Custom Context
Dukung generasi metadata otomatis menggunakan Vision AI (multimodal) terbaru dari **Gemini** (1.5 Flash/Pro), **OpenAI** (GPT-4o), **Mistral**, dan **Groq** (LLaMA 3.2 Vision). 
- **Custom AI Context Prompting**: Tambahkan instruksi kustom spesifik pada sidebar (misal: *"Fokus pada modern flat vector style"*, atau *"Islamic Ramadan theme"*) untuk memandu AI saat menganalisis visual.
- **Style Presets**: Arahan gaya otomatis (*General Commercial*, *Icons & Clipart*, *Backgrounds & Patterns*, *Characters & Mascot*, dll) untuk memperkuat relevansi intent pencarian.

### 🎛️ Visual Keyword Chips & Redundancy Detector
- **Drag & Reorder**: Atur prioritas kata kunci cukup dengan menggeser (*drag*) chip keyword secara visual.
- **Stemming Conflict Detector**: Mendeteksi secara cerdas (*live*) kata kunci yang berulang, memiliki akar kata yang sama (misal: *run*, *running*), atau bentuk jamak (*apple*, *apples*). Tersedia opsi otomatis menghapus redundansi dalam satu klik.
- **Mandatory Injector**: Masukkan kata kunci kustom wajib yang selalu menempel di awal (prioritas tinggi) atau di akhir untuk seluruh batch file. Limit bawaan dibatasi dengan aman pada standar 49 keywords.

### ⚙️ Full Application State & Auto-Save Persistence
Seluruh konfigurasi dari posisi jendela, lebar sidebar/log pane, provider AI, pengaturan *mandatory keywords*, hingga opsi sinkronisasi otomatis **disimpan dan dimuat ulang** (*auto-load & auto-save*) setiap kali Anda membuka atau menutup aplikasi. Anda tidak perlu mengatur ulang preferensi Anda dari awal.

### 🖼️ Asset Multi-Variant Metadata Synchronizer
Jangan membuang waktu men-tag file satu per satu. Sistem akan secara otomatis menyelaraskan (sinkronisasi) metadata dari file _preview_ ke seluruh file pendamping (Companion files) dengan nama yang sama, termasuk ekstensi `.svg`, `.eps`, `.ai`, `.jpg`, `.png`, `.mp4`, dan `.mov`. Fitur **Auto-Zip Vector** juga tersedia untuk menyatukan EPS+JPG secara otomatis setelah diproses.

### 📋 Selective File Queue & Batch Processing
- **File Queue Manager**: Tinjau antrean file langsung di antarmuka utama. Anda bisa memilih tombol **[Skip/Exclude]** pada setiap baris untuk mengecualikan file dari proses Batch secara langsung, tanpa harus memindahkan/menghapus file fisiknya.
- **Batch Export Summary Report**: Setiap kali proses batch selesai, pop-up dialog akan memberikan estimasi token yang terpakai, kalkulasi biaya API ($), jumlah file sukses/gagal, dan akses instan ke ekspor CSV.

### 📝 Offline Metadata CSV Importer & Multi-Platform Exporter
- **Import Metadata from CSV...**: Impor metadata massal (Filename, Title, Description, Keywords) langsung dari file CSV tanpa harus memanggil API AI. Mode offline ini 100% hemat biaya. Begitu diimpor, UI akan langsung melakukan pembaruan status Visual Chips & Live Compliance.
- **Export CSV Format**: Setelah diproses, satu klik akan membuat file CSV ekspor siap-unggah ke berbagai format yang didukung secara *native*: **Adobe Stock**, **Shutterstock**, **Freepik**, **Vecteezy**, dan **Generic**.

### ✅ Live SEO & Platform Compliance Validator
Di dalam panel *Inspector*, setiap aset divalidasi langsung (*real-time*) sesuai kriteria ketat agensi sebelum disematkan ke dalam metadata (EXIF/IPTC/XMP):
- *Real-time Quality & Spam Score Checker*.
- Menampilkan peringatan warna interaktif jika melebihi panjang karakter atau melanggar jumlah minimum kata kunci platform.
- Termasuk tombol **Auto-Fix** cerdas yang mengembalikan struktur kalimat ke standar platform tujuan.

---

## 📂 Struktur Proyek (Architecture)

NRA-Metadata dibangun dengan pendekatan Monorepo modular untuk menjaga skalabilitas fungsionalitas UI, sinkronisasi background thread, dan API wrapper AI.

```text
nra-metadata/
├── apps/
│   ├── cli/                   # Akses eksekusi command line murni
│   └── desktop/               # Antarmuka grafis CustomTkinter (GUI)
│       ├── build_desktop.bat  # Skrip build standalone Windows executable
│       └── src/
│           └── main.py        # Core application, Layout UI, & State Manager
├── packages/
│   ├── ai_engine/             # Logika Vision Model, prompt generator, & API Wrapper
│   │   ├── __init__.py
│   │   └── service.py         # AI Inference, prompt injection & fallback handler
│   ├── media_processor/       # Engine pembaca/ekstraksi metadata fisik (ExifTool)
│   │   ├── embedder.py        # Embed IPTC/XMP tags (JPG/EPS/SVG)
│   │   └── previews.py        # Ekstraksi visual cepat untuk AI preview image
│   └── shared_utils/          # Helper modules
│       ├── cache.py           # SQLite local cache (hemat regenerasi model AI)
│       ├── config.py          # Auto-save persistent state manager
│       ├── csv_exporter.py    # Formatter output Adobe, SS, Freepik, dsb.
│       ├── filter.py          # Logika NLP (Redundancy, Plural/Stemming checks)
│       ├── ftp_uploader.py    # Integrasi FTP/SFTP uploader massal
│       └── presets.py         # Keyword preset JSON local storage
```

---

## 🚀 Panduan Instalasi & Persyaratan Sistem

### Prasyarat
1. **Python 3.10** atau lebih baru.
2. **ExifTool** (Wajib): Aplikasi bergantung pada [ExifTool](https://exiftool.org/) untuk manipulasi EXIF/IPTC/XMP yang berstandar industri. Pastikan `exiftool` terdaftar di dalam environment variable `PATH` sistem Anda.

### Cara Instalasi

1. Clone repositori ini:
   ```bash
   git clone https://github.com/novri-ra/NRA-Metadata.git
   cd NRA-Metadata
   ```
2. Buat virtual environment (direkomendasikan):
   ```bash
   python -m venv venv
   # Di Windows:
   venv\Scripts\activate
   # Di Linux/Mac:
   source venv/bin/activate
   ```
3. Install dependensi modul:
   ```bash
   pip install -r nra_metadata.egg-info/requires.txt
   ```
   *(Bila requirements file tidak tersedia, Anda bisa menggunakan modul standar `Pillow`, `customtkinter`, `requests`, `google-generativeai`, `openai`, dsb).*

### Menjalankan Aplikasi
Jalankan file entry GUI desktop langsung dengan perintah:
```bash
python apps/desktop/src/main.py
```
*(Catatan: Aplikasi dirancang Anti-Tearing untuk scrollable widget, rendering kanvas menggunakan akselerasi responsif)*

---

## 📖 Panduan Penggunaan Lengkap (Step-by-Step Guide)

### 1. Konfigurasi AI & Pemilihan Model
Buka aplikasi, fokus ke **Sidebar Kiri (Section AI Engine)**:
- Pilih **Provider** (Misalnya `Gemini`).
- Pilih varian **Model** (`gemini-1.5-flash` sangat direkomendasikan untuk tugas massal karena murah & cepat).
- Masukkan **API Key** yang Anda dapatkan dari console developer provider AI masing-masing.
- Atur **Temperature** (0.2 - 0.4 disarankan untuk respons teknis berformat JSON). 

### 2. Pengaturan Batas Keyword & Extra Guidance
Buka section **Keywords & Style**:
- Tetapkan batas **Min KW** dan **Max KW** (Default industri aman: 49).
- Apabila aset Anda memiliki satu tema tetap, isikan pada input **Mandatory Keywords** (Misal: `3d, render, illustration`).
- Gunakan dropdown **Inject at** untuk menaruh kata wajib tersebut di "Start (Priority)" atau "End".
- Pada **Extra AI Context / Focus**, masukkan deskripsi atau arahan kustom tambahan jika aset memerlukan penjelasan spesifik khusus yang luput dari model AI (Contoh: *"This is a UI dashboard, focus on web elements and layout components"*).

### 3. Manajemen Antrean & Seleksi File
Buka blok **Folder Bar** di kolom utama:
- Klik **Browse** dan pilih folder yang berisi aset master (JPG, EPS, SVG). 
- Di **File Queue**, Anda akan melihat daftar file. Gunakan kotak centang di sisi kiri baris file untuk menandai file sebagai **"Skipped"**. File ini otomatis dihiraukan saat pemrosesan berjalan (tanpa perlu repot membuangnya dari OS). Anda dapat menggunakan tombol *Include All / Exclude All*.

### 4. Menjalankan Batch & Inspector
- Di panel Sidebar bawah, tekan tombol hijau **Start Processing**.
- Biarkan model bekerja memanggil AI dan menanam metadata. Status bar akan menunjukkan progres dan log mendetail di sisi panel kanan-bawah.
- Anda dapat klik file yang sudah selesai (*Done*) untuk melihat hasil *Real-time* di **Inspector Kanan**. Anda akan melihat preview gambar, skor kepatuhan, dan Visual Chips dari keywords yang ditanamkan.

### 5. Memperbaiki Redundancy & Mengubah Teks
Jika di Inspector terdapat alert **Redundansi Warna Kuning**, Anda dapat menekan tombol **Remove Redundancies** untuk membersihkan frasa yang tumpang tindih secara cerdas. Anda juga dapat mengatur format **Title Case**, **Sentence**, atau **lowercase** cukup dengan satu klik di toolbar format Title/Description. Posisikan urutan keyword baru jika diperlukan dengan mengklik arah geser pada *Chips*. Semua aksi ini aman berkat fitur **Undo/Redo Manager** (`Ctrl+Z` / `Ctrl+Y`).

### 6. Sinkronisasi File Companion & Ekspor Platform
Pilih tab **Output & Export**:
- Centang format platform CSV (seperti *Adobe Stock*, *Shutterstock*, dll).
- Setelah batch selesai, muncul dialog **Batch Processing Summary Report**. Di sana Anda bisa melihat rincian Token, Error, Cost ($), dan dapat langsung menuju menu *Copy Summary* atau membuka folder. Ekspor metadata file `.csv` otomatis ada di dalam folder kerja dengan standar agensi yang dipilih. 

---

## ⚖️ Tabel Standar & Kepatuhan Platform

Aplikasi memonitor standar (*Live Compliance Validator*) dengan basis rujukan metrik platform terbaru:

| Platform | Maksimal Title/Desc | Minimal Kata di Judul | Keyword Minimal | Keyword Maksimal |
| :--- | :---: | :---: | :---: | :---: |
| **Adobe Stock** | 200 Karakter | 1 kata | 5 | 49 |
| **Shutterstock** | 150 Karakter | 5 kata | 7 | 50 |
| **Freepik** | 100 Karakter | 1 kata | 5 | 50 |
| **Vecteezy** | 150 Karakter | 1 kata | 5 | 50 |

---

## 🛠 Troubleshooting & FAQ

1. **Error: "ExifTool not found / embed failed"**
   * Solusi: Pastikan `exiftool.exe` sudah Anda download dari situs resmi dan terdaftar di *Environment Variables (System PATH)* Windows/OS Anda. Jika belum, letakkan file exe exiftool langsung ke root instalasi Python Anda atau root `nra-metadata/`.
2. **Glitch Visual / Tearing saat scroll**
   * Solusi: Pada branch stabil `development` ke atas, aplikasi ini menggunakan Native Tkinter hardware acceleration yang dirancang solid (Anti-Tearing). Pastikan driver grafis (*GPU*) dasar OS Anda cukup diperbarui.
3. **API Cost atau Rate Limits Terlampaui**
   * Solusi: Kurangi jumlah **Workers** (Concurrency) di settingan *Processing* pada Sidebar menjadi 1 atau 2 agar tidak melempar terlalu banyak hit API serentak ke model, terutama jika menggunakan OpenAI Tier gratis atau Groq public key.

---

## 🛡 Lisensi & Kredit

Dikembangkan oleh **Novri Rizki Akbar** (NRA). Hak Cipta dilindungi.
Program ini dirancang khusus untuk memotong waktu input repetitif sehingga seniman dan ilustrator vektor/bitmap microstock dapat berfokus 100% pada proses kreatif mereka.

*Dibangun dengan cinta, Python 3, dan CustomTkinter.*