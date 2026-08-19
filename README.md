# 🚀 NRA-Metadata: Enterprise-Grade Automated Metadata Studio & Microstock Compliance Engine

NRA-Metadata adalah aplikasi desktop mutakhir berbasis Python yang dirancang khusus untuk memecahkan tantangan terbesar para kontributor microstock: manajemen dan penulisan metadata skala besar secara otomatis, cerdas, dan aman. Dengan mengandalkan arsitektur **AI Vision LLM multi-provider** (OpenAI, Gemini, Mistral, Claude, dll.) dan **ExifTool**, NRA-Metadata mengubah alur kerja kurasi dan optimasi metadata menjadi proses yang sangat cepat, minim kesalahan (error-free), dan mematuhi seluruh standar ketat industri microstock global.

Sistem ini tidak hanya menawarkan fungsionalitas pembuatan kata kunci otomatis, melainkan menghadirkan ekosistem manajemen aset terlengkap mulai dari injeksi data secara luring, validasi SEO, hingga pengelolaan lisensi perangkat dengan keamanan sekelas enterprise.

---

## 🛡️ Fitur Keamanan & Sistem Autentikasi

NRA-Metadata dibangun dengan mengutamakan perlindungan kekayaan intelektual, privasi, dan kepemilikan lisensi perangkat pengguna. 

1. **Serverless Google Sheets Auth Backend**
   Sistem lisensi dan database pengguna sepenuhnya menggunakan arsitektur serverless melalui *Google Apps Script Web App*. Seluruh manajemen status pengguna, penyimpanan hash password, hingga pelacakan alamat IP beroperasi tanpa membutuhkan server fisik mandiri, memastikan uptime yang tinggi dan bebas biaya pemeliharaan server lokal.
2. **Single-Device HWID Binding (Proteksi Sesi Ganda)**
   Akun pengguna secara cerdas diikat (binding) ke **Sidik Jari Perangkat Keras (Hardware ID / HWID)** yang unik. Sistem secara otomatis mengekstrak *Windows MachineGuid* dari Registry (`HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`) dikombinasikan dengan node jaringan UUID yang kemudian di-hash menggunakan SHA-256. Jika akun yang sama dicoba login di komputer lain, sistem secara instan menolak sesi ganda, mengunci aplikasi pengguna pertama dengan peringatan `"Sesi Berakhir: Akun digunakan di perangkat lain"`, dan mengeluarkan akun tersebut (Auto-kick).
3. **DPAPI Local Encryption**
   Demi melindungi API Key (seperti OpenAI/Gemini) dan token sesi dari akses yang tidak sah atau pencurian malware, NRA-Metadata mengenkripsi konfigurasi lokal secara native ke dalam file `config.enc`. Aplikasi memanggil fungsi Windows Data Protection API (DPAPI) melalui modul `ctypes`, yang memastikan bahwa hanya perangkat dan *user account* Windows yang sama yang dapat mendekripsi data tersebut.
4. **Path Traversal & Command Injection Guard**
   Setiap alur input dari pengguna dan jalur file (file paths) dibersihkan secara ketat (`os.path.abspath`) sebelum berinteraksi dengan utilitas baris perintah eksternal (Command Execution) seperti ExifTool, Ghostscript, maupun FFmpeg. Ini secara total menutup celah keamanan Command Injection dan serangan Path Traversal (`../`).

---

## ✨ Katalog Fitur Unggulan Studio

Setiap modul antarmuka NRA-Metadata dibangun secara detail untuk mengakomodasi alur kerja microstock yang sangat kompleks:

- **Multi-Provider AI Vision & Prompt Guidance**
  Mendukung integrasi API dari Gemini, OpenAI, Mistral, Groq, hingga Claude. Sistem ini dapat menganalisis dan men-tag aset visual secara massal. Pengguna diberikan kebebasan mengatur *Temperature* (kreativitas model), *Worker Concurrency* (paralel processing), hingga menyisipkan *Konteks Kustom* tambahan untuk mengarahkan gaya metadata secara presisi.
- **Interactive Visual Keyword Chips**
  Kata kunci tidak lagi sekadar teks yang dipisahkan koma. Antarmuka menggunakan *Visual Chips* interaktif layaknya platform web modern. Pengguna dapat mengubah urutan kata kunci dengan klik, menghapus dengan cepat (quick delete), serta menambah kata kunci baru secara instan dengan proteksi deteksi duplikasi.
- **Smart Redundancy & Stemming Filter**
  Menggunakan algoritma Natural Language Processing ringan, sistem dapat membersihkan kata-kata duplikat secara cerdas, baik berupa perbedaan tunggal/jamak (*apple* vs *apples*), bentuk turunan/gerund (*run* vs *running*), maupun kesalahan tipografi.
- **Batas Default 49 Keywords & Mandatory Keyword Injector**
  Menerapkan batas aman industri yakni maksimal 49 kata kunci. Fitur Injektor memungkinkan pengguna menyisipkan kata kunci wajib (seperti nama brand, lokasi, atau tema portofolio) di posisi terdepan atau terbelakang secara serentak ke ratusan aset.
- **Asset Multi-Variant Metadata Synchronizer**
  Solusi bagi kreator ilustrasi dan video. NRA-Metadata dapat menyinkronkan dan menempelkan metadata yang sama persis dari aset pratinjau (contoh: `.jpg`) ke aset bundle pendampingnya seperti `.eps`, `.ai`, `.svg`, `.mov`, dan arsip `.zip`.
- **Selective File Queue (Antrean Selektif)**
  Pengguna memegang kendali penuh atas file mana yang akan diproses. Tersedia fungsi abaikan file (Exclude/Skip) per baris di daftar antrean atau eksekusi massal (Include All / Exclude All).
- **Keyword Presets Library & Blacklist Manager**
  Simpan kombinasi set kata kunci yang sering digunakan sebagai *Preset*, dan kelola daftar *Blacklist* untuk secara otomatis menolak kata kunci yang melanggar ketentuan microstock (kata sensitif, hak cipta/trademark, dan NSFW).
- **Live SEO Quality & Spam Score Checker**
  Modul ini membedah metadata secara real-time untuk menyajikan metrik kualitas (Quality Metrics) dan mendeteksi taktik berlebihan (*Keyword Stuffing*). Semakin optimal distribusi kata kunci, semakin tinggi visibilitas aset Anda di mesin pencari agensi.
- **Platform Compliance Matrix**
  Fitur ini secara aktif memeriksa kepatuhan spesifikasi input pengguna terhadap aturan ketat empat raksasa agensi: Adobe Stock, Shutterstock, Freepik, dan Vecteezy. Jika ada yang melanggar batas (misalnya deskripsi melampaui 200 karakter), modul *Auto-Fix* siap memangkas dan menyesuaikannya.
- **Multi-Platform CSV Exporter & Bulk CSV Importer**
  Sistem mendukung ekspor otomatis tabel CSV yang diformat spesifik untuk masing-masing agensi microstock di akhir pemrosesan. Lebih dari itu, tersedia fitur Impor CSV bagi Anda yang ingin me-retag metadata luring tanpa perlu membakar saldo (token) API AI.
- **Full Application State Persistence**
  Anda tidak akan pernah kehilangan konfigurasi kerja. Segala bentuk tata letak (layout), ukuran panel, kolom input teks, dan preferensi aplikasi disimpan (*auto-save*) saat Anda menutup aplikasi dan dipulihkan sepenuhnya di sesi berikutnya.
- **Anti-Tearing & High-Performance Canvas Rendering**
  Struktur komponen antarmuka *scrollable* pada CustomTkinter telah dikalibrasi untuk mencegah fenomena transisi yang kasar (*flickering* & *ghosting*), menghasilkan pengalaman *scrolling* panel dengan sangat mulus.
- **History Manager & Text Case Formatters**
  Setiap modifikasi manual teks didukung dengan tumpukan riwayat (Undo/Redo), lengkap dengan pengubah struktur teks pintar (Title Case, Sentence case, Lowercase) untuk menyeragamkan judul dan deskripsi.

---

## 📂 Struktur Direktori & Arsitektur Proyek

NRA-Metadata dibangun dengan struktur termodularisasi tingkat lanjut yang memisahkan logika antarmuka, proses AI, dan utilitas sistem.

```text
NRA-Metadata/
├── apps/
│   └── desktop/
│       └── src/
│           └── main.py              # Inti Aplikasi UI (CustomTkinter), State Manager, Orkestrasi Batch AI
├── packages/
│   ├── ai_engine/
│   │   └── service.py               # Integrasi Multi-API LLM Vision, Parser Respons Metadata
│   ├── media_processor/
│   │   ├── embedder.py              # Subprocess Wrapper ExifTool, Manajemen Metadata XML SVG
│   │   └── previews.py              # Ekstraksi Raster Thumbnail (Headless Edge, Ghostscript, FFmpeg)
│   └── shared_utils/
│       ├── auth_backend.js          # Google Apps Script Web App Backend Code (Database Serverless)
│       ├── license_manager.py       # Kelas AuthClient, Generate HWID, Cek IP, Manajemen Sesi Lisensi
│       ├── config.py                # Wrapper DPAPI Windows, Penulisan State Lokal Terenkripsi
│       └── csv_importer.py          # Modul Impor Tagging Luring (Offline Retagging)
├── tools/                           # Dependensi Biner Eksternal (ExifTool, dll. - opsional/harus disiapkan)
├── config.enc                       # Konfigurasi Lokal Terenkripsi (dihasilkan otomatis oleh sistem)
└── README.md                        # Dokumentasi Komprehensif Resmi
```

---

## 💻 Persyaratan Sistem & Prasyarat

- **Sistem Operasi**: Windows 10, Windows 11 (Disarankan, karena dukungan DPAPI native dan ekstraksi MachineGuid Registry).
- **Environment**: Python 3.10 atau versi yang lebih baru.
- **Biner Eksternal**:
  - `exiftool.exe` (Wajib, untuk penulisan tag ke dalam file gambar/vektor).
  - Browser Microsoft Edge (Digunakan untuk *headless screenshot* aset SVG).
  - *Opsional*: Ghostscript (`gswin64c.exe`) untuk aset EPS, dan FFmpeg untuk aset Video.

---

## 🛠️ Panduan Instalasi & Persiapan Lingkungan

1. **Unduh (Clone) Repository**
   ```bash
   git clone https://github.com/username/NRA-Metadata.git
   cd NRA-Metadata
   ```
2. **Siapkan Virtual Environment (Direkomendasikan)**
   ```bash
   python -m venv venv
   # Mengaktifkan venv pada Windows:
   venv\Scripts\activate
   ```
3. **Instalasi Dependensi Python**
   ```bash
   pip install -r requirements.txt
   ```
   *(Pastikan paket seperti `customtkinter`, `requests`, dan `Pillow` terinstal dengan sukses).*
4. **Siapkan File Biner**
   Letakkan biner `exiftool.exe` ke dalam path sistem atau direktori yang sesuai dengan konfigurasi di dalam modul `embedder.py` (secara default akan mencari di `tools/exiftool/exiftool.exe` atau PATH OS).

---

## 📖 Panduan Penggunaan Menyeluruh (Workflow Guide)

Ikuti langkah-langkah di bawah ini untuk memulai kurasi batch pertama Anda:

### 1. Registrasi / Login Akun & Validasi Lisensi
Saat menjalankan aplikasi pertama kali (`python apps/desktop/src/main.py`), Anda akan disambut oleh Modal Antarmuka Autentikasi. Silakan masuk ke tab "Buat Akun Baru" jika belum memiliki lisensi. Setelah mendaftar, lakukan Login. Sistem akan mengekstrak sidik jari unik Windows Anda (HWID) dan mengotorisasi Anda.

### 2. Konfigurasi Model AI & API Key
Di panel sisi kiri aplikasi, pilih Penyedia AI yang Anda gunakan (contoh: OpenAI atau Gemini). Masukkan **API Key** resmi Anda. Sesuaikan *Temperature* jika ingin metadata yang lebih bervariasi, serta tambahkan *Extra Prompt Context* jika Anda sedang fokus pada ceruk (*niche*) tema tertentu.

### 3. Memuat Direktori & Manajemen Antrean
Klik tombol **"Select Folder"** untuk memilih direktori berisi aset grafis/video yang ingin diproses. Daftar *File Queue* akan otomatis terisi. Centang atau hilangkan centang pada item file individu untuk mengecualikan (exclude) file yang belum siap diproses.

### 4. Menjalankan Batch Processing
Tekan tombol **"Start Processing"**. Aplikasi akan segera memverifikasi legalitas sesi Anda (*background session guard*). Jika sesi aman, sistem akan mendistribusikan pekerjaan tersebut dengan multithreading ke API LLM. Bar pemuatan (Progress Bar) dan log sistem akan diperbarui secara *real-time*. Di akhir proses, sebuah laporan rekapan token (biaya estimasi) dan jumlah keberhasilan akan dimunculkan.

### 5. Inspeksi Metadata & Visual Chips
Setelah AI selesai bekerja, klik file apa pun di antrean untuk membukanya di panel Inspector Kanan.
- Gunakan fitur **Visual Chips** untuk menghapus tag usang atau menambahkan *Mandatory Keyword* yang baru.
- Perhatikan blok metrik warna-warni; pastikan indikator **Spam Score** berwarna hijau (aman) dan patuhi arahan modul **Redundancy Filter** jika mendeteksi teks duplikat.

### 6. Validasi Compliance & Sinkronisasi File Companion
Di area bawah Inspector, aktifkan *Compliance Matrix* untuk memverifikasi apakah total teks telah memenuhi standar industri. Ketika metadata telah sempurna, Anda tidak perlu men-tag ulang aset `.eps` atau `.zip` yang satu nama. Seluruh modifikasi langsung disinkronkan ke dalam metadata masing-masing bundel file tersebut secara mandiri.
Untuk alur distribusi yang menggunakan portal upload CSV, cukup buka folder output untuk mengambil dokumen ekspor CSV spesifik platform Anda.

---

## ⚖️ Tabel Standar Kepatuhan Platform Microstock

NRA-Metadata menggunakan matriks internal berikut untuk menjustifikasi parameter validasi:

| Platform Agency | Panjang Minimum Judul | Batas Maksimum Judul / Deskripsi | Minimum Tags | Maksimum Tags |
| :--- | :--- | :--- | :--- | :--- |
| **Shutterstock** | 5 Karakter | 200 Karakter | 7 Kata Kunci | 50 Kata Kunci |
| **Adobe Stock** | 5 Karakter | 200 Karakter | 5 Kata Kunci | 49 Kata Kunci |
| **Freepik** | 5 Karakter | 200 Karakter | 5 Kata Kunci | 50 Kata Kunci |
| **Vecteezy** | 5 Karakter | 150 Karakter | 5 Kata Kunci | 50 Kata Kunci |

*(Catatan: NRA-Metadata otomatis memperingatkan Anda jika judul lebih dari 200 karakter atau kata kunci melampaui 49 agar selalu dalam jangkauan aman universal semua agen).*

---

## ⚠️ Troubleshooting & FAQ (Tanya Jawab Kendala)

- **Masalah: Peringatan "Sesi Berakhir: Akun digunakan di perangkat lain".**
  *Solusi*: Akun Anda telah melakukan login di mesin atau PC lain, yang menyebabkan pergantian Session Token (KICKED) oleh Server Google Apps Script. Silakan Login kembali dari komputer saat ini untuk merebut otoritas lisensi (yang secara otomatis akan mengeluarkan sesi PC lain).
- **Masalah: Aplikasi crash / tidak bisa dibuka / Layar blank di panel scroll.**
  *Solusi*: Pastikan versi instalasi `customtkinter` pada python Anda mutakhir. Sistem anti-tearing NRA-Metadata menggunakan lapisan pewarnaan kanvas di latar belakang yang membutuhkan pembaruan terbaru perpustakaan grafis.
- **Masalah: Biner ExifTool gagal menulis ("SKIP ERROR ExifTool").**
  *Solusi*: Periksa apakah file aset sedang dibuka/terkunci (lock file) oleh aplikasi Editor Gambar lain seperti Adobe Illustrator atau Photoshop. Pastikan juga file `exiftool.exe` memiliki izin administratif yang sah dan tidak diblokir oleh Windows Defender.
- **Masalah: Estraksi thumbnail SVG gagal atau tidak muncul.**
  *Solusi*: Headless rasterization mengandalkan browser bawaan Microsoft Edge. Pastikan path instalasi `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` ada. Jika menggunakan sistem OS lain, integrasikan dependensi Python `svglib` tambahan.

---

## 📜 Lisensi, Kredit & Kontribusi

Dipersembahkan sebagai fondasi *internal tools* untuk manajemen studio microstock komersial tingkat tinggi.

Arsitektur aplikasi dan sistem lisensi (HWID Serverless Auth & DPAPI) adalah hak cipta independen kontributor. Permintaan pembaruan (Pull Requests) atau pengembangan garpu (*forks*) diizinkan berdasarkan persetujuan tertulis dari pengelola repositori utama (Maintainer). Terimakasih kepada proyek open source `ExifTool` karya Phil Harvey.

**"Empower Your Portfolio, Scale Your Keywords, Secure Your Workflow."**
