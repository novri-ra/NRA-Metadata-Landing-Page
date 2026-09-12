<div align="center">

# 🚀 NRA-Metadata Studio
**Enterprise-Grade Automated Metadata Studio & Microstock Compliance Engine**

[![Status](https://img.shields.io/badge/Status-Active_Development-success?style=for-the-badge&logo=github)](#)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](#)
[![GUI](https://img.shields.io/badge/CustomTkinter-Modern_UI-8b5cf6?style=for-the-badge&logo=pypi)](#)
[![Security](https://img.shields.io/badge/Security-Hardened-red?style=for-the-badge&logo=letsencrypt)](#)
[![Tool](https://img.shields.io/badge/Engine-ExifTool-ff69b4?style=for-the-badge)](#)

<p align="center">
  <i>Alat otomasi tingkat profesional untuk pembuatan, manajemen, dan injeksi metadata (Title, Description, Keywords) ke aset visual microstock. Ditenagai oleh Multi-Provider Vision AI dan dirancang untuk alur kerja kontributor skala masif.</i>
</p>

</div>

---

## 🌟 Tentang Proyek Ini

**NRA-Metadata** adalah aplikasi desktop mutakhir berbasis Python yang dirancang khusus untuk memecahkan tantangan terbesar para kontributor microstock: manajemen dan penulisan metadata skala besar secara otomatis, cerdas, dan aman. 

Dengan mengandalkan arsitektur **AI Vision LLM multi-provider** (Mistral, Gemini, OpenAI, Groq, hingga *9router AI Gateway*) dan keandalan **ExifTool**, NRA-Metadata mengubah alur kerja kurasi metadata menjadi proses yang sangat cepat, minim kesalahan (*error-free*), dan 100% mematuhi standar ketat industri microstock global.

Sistem ini tidak sekadar menghasilkan kata kunci; ia menghadirkan **ekosistem manajemen aset terlengkap**, mulai dari injeksi luring (offline), validasi SEO secara *real-time*, sinkronisasi multi-file (.eps, .ai, .jpg, .zip), hingga pengelolaan otorisasi lisensi berbekal keamanan sekelas *enterprise*.

---

## 🛡️ Arsitektur Keamanan & Sistem Autentikasi

NRA-Metadata dibangun di atas fondasi keamanan tingkat tinggi untuk memastikan privasi, keamanan API Key, dan keutuhan lisensi perangkat Anda.

### 1. Serverless Google Sheets Auth Backend
Meninggalkan arsitektur database relasional tradisional yang memakan biaya server, NRA-Metadata mengadopsi sistem *Serverless* sepenuhnya melalui **Google Apps Script Web App**. Seluruh manajemen registrasi, pelacakan alamat IP publik, dan pencatatan token otorisasi berlangsung secara instan tanpa server fisik mandiri. Ini menjamin sistem dengan uptime 99.9%, tahan terhadap beban masif, dan bebas biaya pemeliharaan.

### 2. Single-Device HWID Binding (Proteksi Sesi Aktif)
Akun pengguna dilindungi dari kebocoran lisensi dengan mengikat (*binding*) sesi ke **Sidik Jari Perangkat Keras (Hardware ID / HWID)**.
- **Ekstraksi Mesin:** Sistem mengekstrak parameter `MachineGuid` secara langsung dari *Windows Registry* (`HKLM\SOFTWARE\Microsoft\Cryptography\MachineGuid`) yang dikombinasikan dengan pengidentifikasi *MAC Address Node*.
- **Auto-Kick:** Jika pengguna mencoba melakukan login dari komputer lain, sistem secara instan mengganti token di awan. Perangkat pertama akan secara langsung menerima peringatan `"Sesi Berakhir: Akun Anda telah login di perangkat lain"` sebelum sesi dihentikan (*locked out*) secara paksa untuk melindungi manipulasi batch processing.

### 3. DPAPI Local Storage Encryption
Penyimpanan API Key sensitif (seperti kredensial OpenAI atau token sesi) tidak pernah ditulis dalam format teks biasa (plaintext). Aplikasi menggunakan enkripsi native dari Microsoft, yakni **Data Protection API (DPAPI)** melalui interaksi *ctypes* tingkat rendah.
- **Keamanan Lapis Baja:** Konfigurasi `.json` tradisional secara dinamis dienkripsi ke dalam berkas `config.enc`. Data ini hanya dapat didekripsi oleh pengguna Windows (User Profile) dan komputer yang sama persis saat data tersebut disimpan.

### 4. Path Traversal & Injection Shield
Setiap interaksi dengan utilitas eksekusi baris perintah pihak ketiga (*ExifTool*, *Ghostscript*, *FFmpeg*) dilindungi ketat menggunakan *command wrapper* berbasis tipe *Array (list)* dan validasi *absolute path* (`os.path.abspath`). Proteksi *sandbox* ini menutup rapat segala bentuk celah serangan penyusupan baris perintah (*Command Injection*) maupun celah lintasan direktori (*Path Traversal - `../`*).

---

## ✨ Katalog Lengkap Fitur Unggulan

### 🤖 AI Vision & 9router Gateway Integration
Dukung pemrosesan visual dengan deretan model LLM Vision terkuat di pasaran: **Mistral, Gemini, OpenAI, Claude, dan Groq**. 
- **9router AI Gateway:** Dukungan bawaan untuk provider *OpenAI-Compatible*, memungkinkan *smart routing* ke endpoint gateway pilihan Anda. Sangat fleksibel, dengan kustomisasi parameter Base URL (`http://localhost...` / `https://api.9router...`).
- **Custom Context Guidance:** Pengguna dapat memberikan instruksi spesifik pada *sidebar* (contoh: *"Fokus pada nuansa pastel, gaya flat design minimalis"*), yang secara presisi mengubah gaya keluaran metadata AI Anda.

### 🏷️ Interactive Visual Keyword Chips
Kata kunci tidak lagi sekadar teks yang menumpuk. Antarmuka UI mengadopsi elemen modern berbasis blok *Visual Chips*.
- **Fungsi Dinamis:** Pengguna dapat mengubah urutan kata kunci dengan mengklik (*drag to reorder*), mengedit secara *inline*, menghapus (*quick delete*), dan menambah kata secara instan.
- **Proteksi Cerdas:** Setiap penambahan kata kunci dicegah apabila mendeteksi entri ganda (*Duplication Protector*).

### 🧹 Smart Redundancy & Stemming Cleanup
Memanfaatkan algoritma *Natural Language Processing* ringan, modul ini bertugas menjaga kebersihan SEO. Sistem dapat mendeteksi kata berlebih akibat stemming bahasa, baik dalam bentuk perbedaan tunggal/jamak (*apple* vs *apples*) maupun bentuk *gerund* (*run* vs *running*). Hanya dalam satu klik, kata tak berguna akan dibersihkan.

### 💉 Batas Default 49 Keywords & Mandatory Tag Injection
Algoritma internal aplikasi menerapkan *safeguard* 49 kata kunci untuk menghindari penalti algoritmik agensi.
- Fitur **Mandatory Injector** memungkinkan Anda menanamkan (inject) kata kunci wajib yang spesifik secara otomatis, memaksanya menempel di urutan paling awal atau paling akhir pada keseluruhan direktori (batch file).

### 📦 Multi-Variant Synchronizer & Auto-Zip
Sistem manajemen aset tercanggih yang meniadakan kerja ganda! Cukup setujui metadata pada berkas tinjauan (`.jpg`), maka NRA-Metadata akan **secara simultan** memindai, mengenkripsi XML, dan menanamkan metadata identik ke setiap *companion bundle file* dengan nama serupa (seperti `.svg`, `.eps`, `.ai`, hingga file video `.mov`, dan arsip terkompresi `.zip`).

### 📌 Selective File Queue
Pemrosesan tidak lagi memaksa Anda menyertakan seluruh aset sekaligus. Lewat tabel antrean sebelah kiri, hilangkan centang dari *checkbox* file individu yang belum selesai digambar, atau gunakan tombol saklar agregat (*Include All* / *Exclude All*).

### 📈 Live SEO, Spam Score & Quality Analyzer
Metrik real-time akan membedah kelayakan kompetitif metadata Anda dan menyajikan **Skor Kualitas (0-100%)**. Modul ini secara aktif meneliti *keyword stuffing* (kata berlebihan), ketiadaan elemen utama, atau densitas deskripsi, yang secara masif berpengaruh pada visibilitas aset saat rilis di mesin pencari.

### ⚖️ Platform Compliance Matrix
Pekerjaan Anda dinilai (*validated*) melawan pedoman resmi empat raksasa agensi secara real-time. Jika batas maksimum karakter dari *Adobe Stock*, *Shutterstock*, *Freepik*, atau *Vecteezy* terlampaui, satu tombol **Auto-Fix** akan memangkas, merapikan, dan mencocokkan standar secara aman.

### 📂 Offline CSV Bulk Importer & Exporter
- **Exporter:** Di akhir pemrosesan AI, tekan satu tombol untuk merender kumpulan CSV yang diformat presisi secara struktural sesuai tuntutan platform (contoh: baris CSV Freepik vs CSV Adobe Stock).
- **Importer:** Membutuhkan retagging tanpa membakar saldo API AI? Muat CSV yang sudah ada, lalu biarkan aplikasi mencangkok (*grafting*) metadata kembali ke file biner secara luring (offline).

### ⚡ High-Performance / Anti-Tearing Rendering
Tidak seperti GUI tradisional, CustomTkinter telah dikalibrasi hingga akarnya (*root config*). Bingkai *scrollable panels* direkayasa ulang lapisan latar belakangnya untuk menghilangkan gangguan transisi pengguliran berbayang (*ghosting*) dan layar robek (*canvas tearing*), menghasilkan navigasi 60FPS yang presisi.

### 💾 Full State Persistence (Undo/Redo Support)
Menekan tutup aplikasi secara sengaja atau tak sengaja tidak akan membuat Anda kehilangan waktu kerja berjam-jam. Tata letak UI, posisi antrean, lebar teks, dan pengaturan mode warna (Dark/Light) **disimpan secara utuh** dalam DPAPI dan akan dipulihkan otomatis saat dibuka kembali. Setiap ketikan kata turut dilindungi tumpukan riwayat modifikasi (*Undo/Redo Manager*).

---

## 📂 Struktur Direktori Modular

NRA-Metadata dibangun dengan *separation of concerns* arsitektur termodularisasi tingkat mahir, yang memisahkan ranah antarmuka, jaringan, proses AI, dan eksekusi utilitas OS.

```text
NRA-Metadata/
├── apps/
│   └── desktop/
│       └── src/
│           └── main.py              # Orkestrasi Sentral GUI (CustomTkinter), State Manager, & Modal Dialog Auth
├── packages/
│   ├── ai_engine/
│   │   └── service.py               # Otak Multi-API LLM Vision, 9router Integration, dan Parser Format JSON
│   ├── media_processor/
│   │   ├── embedder.py              # Subprocess Engine ke ExifTool (Menulis EXIF/IPTC/XMP), Traversal Guard
│   │   └── previews.py              # Modul Headless Rasterization (SVG Edge Screenshot, FFmpeg)
│   └── shared_utils/
│       ├── auth_backend.js          # Skrip Cloud Backend Serverless (Di-deploy ke Google Apps Script)
│       ├── license_manager.py       # Pembangkit HWID MachineGuid, Klien API Login, Manajemen Session Ganda
│       ├── config.py                # Wrapper Windows DPAPI (Ctypes) & Mekanisme State Persistence
│       └── csv_importer.py          # Modul Impor Tagging Luring Berkelompok
├── tools/                           # Dependensi Utilitas Eksternal Mandiri (Wajib: ExifTool)
├── workspace.bat                    # Script Inisiasi Lingkungan Kerja (Virtual Environment Runner)
└── README.md                        # Buku Manual Dokumentasi (Anda membaca ini)
```

---

## 💻 Panduan Instalasi & Setup Lingkungan

### 1. Kebutuhan Prasyarat
- **Sistem Operasi**: Diwajibkan **Windows 10 / 11** (Modul Ekstraksi MachineGuid dan DPAPI beroperasi secara *native* dan asimetris hanya pada sistem NT).
- **Environment**: Python 3.10 atau versi yang lebih baru (Disarankan instalasi resmi `.exe` centang opsi "Add to PATH").
- **Dependencies (Biner Eksternal)**:
  - `exiftool.exe` (Wajib - utilitas pembedah metadata sejati).
  - Browser **Microsoft Edge** (Sudah ada di Windows; ditugaskan secara rahasia sebagai mesin rendering aset gambar vektor/SVG secara *headless*).

### 2. Memulai Repositori
Clone repositori ke penyimpanan *solid state drive* (SSD) utama Anda:
```bash
git clone https://github.com/username/NRA-Metadata.git
cd NRA-Metadata
```

### 3. Eksekusi Lingkungan Virtual
Disarankan untuk melakukan isolasi lingkungan untuk menghindari konflik antar pustaka Python Anda:
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```
*(Paket vital yang digunakan adalah: `customtkinter`, `requests`, `google-genai`, `openai`, `pillow`, dan `pydantic`).*

### 4. Setup Database Serverless (Untuk Maintainer/Developer)
> **Bagi Pengguna Akhir:** Abaikan langkah ini, koneksi API utama sudah disetel oleh Maintainer (URL Cloud).
- Buka portal *Google Apps Script* dan buat lembar *Spreadsheet* baru.
- Sisipkan salinan kode dari `packages/shared_utils/auth_backend.js`.
- Deploy sebagai *Web App* (Eksekusi Atas Nama Anda > Akses Siapa Saja).
- Salin URL Exec dan tempelkan ke variabel `AUTH_API_URL` pada modul `license_manager.py`.

---

## 📖 Alur Kerja Langkah demi Langkah (Workflow Guide)

NRA-Metadata dirancang dengan prinsip UX *One-Stop Studio*. Ikuti urutan di bawah ini untuk memulai penciptaan arsip yang tak tertandingi.

1. **Registrasi Akun & Validasi HWID Perangkat**
   - Jalankan perintah: `python apps/desktop/src/main.py`.
   - Modul Autentikasi dengan gaya palet elegan "Zinc/Indigo" akan menyambut. Klik Tab *Buat Akun Baru* jika ini adalah mesin pertama Anda. Daftar dan lakukan Login. Sidik jari mesin Windows Anda (HWID) telah dicatat.
   
2. **Koneksi Engine & API Parameter**
   - Melalui panel *Sidebar* (kiri), pilih kecerdasan buatan (*Provider*) andalan Anda, seperti **9router**, lalu masukkan *Base URL* serta API Key terkait.
   - Atur level *Temperature* (0.3 direkomendasikan untuk stabilitas struktural, 0.7 untuk kreativitas artistik).
   
3. **Impor Folder (Selective Management)**
   - Klik **Select Folder** dan arahkan ke direktori bahan karya seni Anda. Ratusan berkas akan berjajar membentuk antrean dengan *checkbox*. Centang hijau pada aset yang sudah 100% jadi.
   
4. **Eksekusi Batch Background**
   - Sebelum mulai, sistem mengeksekusi *Auth Guard* secara sembunyi-sembunyi di belakang layar. Selama perangkat Anda aman, tekan **Start Processing**. AI akan menganalisis visual menggunakan konfidensi multithread. Progress bar akan terisi hingga muncul ringkasan panel *(Summary Report)* mencakup kuantitas token, biaya USD (Estimasi), dan total data tertulis.
   
5. **Kurasi Cepat Inspector & Kepatuhan Matriks**
   - Buka sembarang file pada antrean. Area Inspektur (kanan) terbuka lebar.
   - Atur prioritas Visual Chips dengan melakukan Drag. Hapus frasa redudan berkat bantuan **Redundancy Filter**.
   - Cek warna grafik *Spam Score*.
   - Jika teks merah melanggar kebijakan pasar (misal teks kepanjangan), tekan satu tombol **Auto-Fix** dari bilah *Compliance Matrix* untuk memadatkan batas karakter judul/deskripsi.
   
6. **Integrasi Biner & Ekspor Global**
   - Setelah yakin metadata sempurna, tidak perlu melakukan simpan manual. Teks telah otomatis terukir secara mikroskopis di perut file (`.jpg` / `.eps` / `.zip`) lewat *ExifTool*.
   - Gulir panel paling bawah, tekan **Export CSV (Multi-Platform)** untuk mencetak lembar kerja yang siap didistribusikan ke dasbor agensi.

---

## ⚖️ Tabel Matriks Kepatuhan Microstock

NRA-Metadata mengimplementasikan standard kalibrasi yang tidak bisa ditawar sebagai berikut:

| Nama Agen Platform | Ekstensi Maksimal Judul | Batas Karakter Deskripsi | Keyword Minimal | Penalti Batas Tag Tertinggi |
| :--- | :--- | :--- | :--- | :--- |
| **Shutterstock** | 200 Karakter (Opsi) | Maks 200 Karakter | 7 Kata Kunci | **50 Kata Kunci** |
| **Adobe Stock** | 200 Karakter | Maks 200 Karakter | 5 Kata Kunci | **49 Kata Kunci** |
| **Freepik** | 200 Karakter | Maks 200 Karakter | 5 Kata Kunci | **50 Kata Kunci** |
| **Vecteezy** | 150 Karakter | Maks 150 Karakter | 5 Kata Kunci | **50 Kata Kunci** |

*(Perangkat peringatan "Live Compliance" akan menolak input merah yang menerjang batasan di atas, menjaga tingkat penerimaan persetujuan portfolio / Acceptance Rate Anda tetap setinggi langit).*

---

## ⚠️ Troubleshooting & Solusi Kendala Terumum

📝 **Error: "Sesi Berakhir: Akun Anda telah login di perangkat lain"**
> **Kenapa terjadi?** Rekan tim / Karyawan lain telah membuka aplikasi dengan akun Anda di mesin B, menginjeksi token sesi terbaru, melarang token sesi mesin A untuk melanjutkan.
> **Penyelesaian:** Segera tekan tombol 'Login' kembali dari komputer (Mesin A) untuk menarik balik otorisasi lisensi ke perangkat ini.

📝 **Terminal membeku (Freeze) atau Visual Glitch pada UI**
> **Kenapa terjadi?** Akselerasi GPU dari pustaka *Tkinter* bersinggungan di latar belakang.
> **Penyelesaian:** Mutakhirkan `customtkinter` versi terbaru dari *pip*. Fitur Anti-Tearing kami menonaktifkan rendering transparan secara otomatis bila versi tidak selaras.

📝 **Proses AI mandek (Tertahan/Timeout) tanpa alasan**
> **Kenapa terjadi?** Terjadi antrean (Rate Limit) yang ekstrem pada server upstream (seperti OpenAI/Mistral/9router).
> **Penyelesaian:** Modul *AI Engine* NRA-Metadata telah dilengkapi arsitektur `Exponential Backoff`. Ia akan menunggu secara asinkron lalu mengulang pengiriman hingga 3 kali berturut-turut. Tunggu laporan *timeout* resmi di konsol.

📝 **Error Biner ExifTool (Status: SKIP ERROR)**
> **Penyelesaian:** Pastikan biner tidak terblokir oleh *Windows Defender*. Jangan buka file aset (*contoh.ai / contoh.eps*) pada Adobe Illustrator saat NRA-Metadata sedang berjalan, karena sistem operasi OS Windows otomatis memberikan *"File Locking"* yang mencegah penulisan metadata.

---

## 📜 Lisensi, Kredit, & Distribusi

Dikembangkan secara penuh dedikasi sebagai jantung automasi ekosistem studio komersial tingkat makro. 

Arsitektur aplikasi dan sistem lisensi (*HWID Serverless Auth & DPAPI Crypto-Enclave*) adalah hak cipta independen. Pembaruan kode (*Pull Requests*) diterima hanya melalui evaluasi Maintainer resmi. Hak cipta pustaka utilitas metadata sepenuhnya didelegasikan untuk komunitas open source `ExifTool` (Phil Harvey).

> **"Empower Your Portfolio, Scale Your Keywords, Secure Your Workflow."**
  
## Cara Menjalankan Cepat (Zero Setup)  
  
Untuk pengguna Windows, Anda tidak perlu repot menginstal Python secara manual.  
1. Cukup klik ganda (double-click) file **`run_app.bat`** di folder utama proyek ini.  
2. Sistem akan otomatis menggunakan Python di PC Anda jika tersedia, atau mengunduh dan menyiapkan environment Portable secara lokal beserta seluruh dependensinya di latar belakang.  
3. Aplikasi akan langsung terbuka. 
