# 🤖 NRA DreamLab

<div align="center">

![NRA DreamLab](https://img.shields.io/badge/NRA-DreamLab-00C4CC?style=for-the-badge&logo=canva&logoColor=white)

**Automate bulk AI image generation & downloading on [Canva Dream Lab](https://www.canva.com/dream-lab)**

[![Chrome Extension](https://img.shields.io/badge/Chrome-Extension-4285F4?logo=google-chrome&logoColor=white)](https://www.google.com/chrome/)
[![Manifest V3](https://img.shields.io/badge/Manifest-V3-success)](https://developer.chrome.com/docs/extensions/mv3/)
[![JavaScript](https://img.shields.io/badge/JavaScript-ES6+-F7DF1E?logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript)
[![License](https://img.shields.io/badge/License-Educational-orange)](LICENSE)

[Features](#-features) · [Installation](#-installation) · [Usage](#-usage) · [Release Notes](#-release-notes) · [Author](#-author)

</div>

---

## 💡 What Is This?

**NRA DreamLab** is a Chrome extension that automates prompt input and image downloading on [Canva Dream Lab](https://www.canva.com/dream-lab). Queue multiple prompts, configure style & aspect ratio, and let the bot handle generation, rate-limit cooldowns, and batch downloading — all hands-free.

> **Who is this for?** Content creators, designers, and marketers who need to generate large batches of AI images efficiently.

---

## ✨ Features

- **Bulk Prompt Queue** — Paste hundreds of prompts (one per line) or import from `.txt` files
- **Auto Style & Aspect Ratio** — Set per-session or randomize per prompt
- **Smart Download** — Polls DOM for newly rendered download buttons
- **Native DOM Injection** — Stable, fast, and resolution-independent interaction (No CDP Debugger banner)
- **Rate Limit Handling** — Auto-detects cooldown modals and waits before retrying
- **Configurable Delays** — Safety delay, save delay, and batch auto-stop limit
- **Real-time Session Analytics** — Live stats: prompts processed, images downloaded, **Avg Speed, and ETA**
- **Prompt Presets** — Save/load/delete named prompt sets
- **Failed & Quarantine Queues** — Automatically rescues blocked prompts for retry
- **Retro Pixel UI** — CRT scanline side-panel with multiple themes (Retro, Hacker, Light)
- **Keyboard Shortcut** — `Ctrl+Shift+P` to pause/resume without opening the panel

---

## 📦 Installation

1. Download or clone this repository:
   ```bash
   git clone https://github.com/novri-ra/Canva-Auto-Prompter.git
   ```
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable **Developer mode** (toggle in top-right)
4. Click **Load unpacked** and select the project folder
5. Open [Canva Dream Lab](https://www.canva.com/dream-lab)

---

## 🚀 Usage

1. Click the extension icon or open the **side panel** on `canva.com/dream-lab`
2. Paste your prompts (one per line) in the **Prompt Text** area
3. Configure **Aspect Ratio**, **Image Style**, and **Download Count** in Settings
4. Click **Run** — the bot will type each prompt, generate images, and download them automatically
5. Monitor real-time progress, speed, and ETA in **Session Analytics**

---

## 📋 Release Notes

NEW ARCHITECTURAL CORE FEATURES (v1.1.17 - Update 2026-07-17)

1. ANTI-BLUR SMART RENDERING STABILIZATION FILTER
Sistem otomasi kini dilengkapi dengan filter pelacakan state visual Canva secara berurutan. Bot mendeteksi transisi dari fase 'Sketching' hingga masuk ke fase kritis 'Finalizing your image...'. Tepat setelah teks pemrosesan hilang dari layar, sistem menyuntikkan Jeda Kestabilan Grafis (Post-Finalizing Render Delay) selama 5 detik penuh. Hal ini memastikan aset gambar ter-render tajam 100% dan terhindar dari unduhan visual kasar atau blur. Batas toleransi tunggu total (maxWaitTimeMs) juga telah dilebarkan menjadi 240.000ms (4 menit) untuk mengamankan loop dari crash kemacetan antrean server.

2. 5-SECOND POST-COOLDOWN SESSION RECOVERY GATES
Untuk meredam paparan Rate Limit berantai akibat pembatasan ketat akun dari perlindungan server Canva, bot kini dilengkapi dengan gerbang pemulihan pasca-cooldown. Jeda istirahat statis selama 5 detik (await delay(5000)) secara otomatis disuntikkan langsung pada blok PRE-FLIGHT GATEKEEPER (sebelum pengetikan prompt baru dimulai) dan blok POST-FLIGHT CHECK (sesudah penanganan batasan akun pasca-submit). Penundaan taktis ini memberikan nafas bagi kestabilan pertukaran data HTTP sebelum mesin otomasi menembak antrean berikutnya.

3. DUAL-BOX PROMPT ISOLATION & RESCUE FLOW
Pemisahan penanganan antrean prompt gagal telah disempurnakan. Ketika Canva melemparkan penolakan (PROMPT_FAILED), teks prompt murni yang telah disanitasi secara otomatis didistribusikan ke dua kontainer terpisah:
- Failed Prompts Box: Sebagai rekam jejak visual riwayat kegagalan prompt pada sesi berjalan.
- Quarantined Prompts Box: Sebagai area penyelamatan terisolasi di mana user dapat mengembalikan seluruh antrean yang gagal masuk kembali ke antrean utama hanya dengan satu klik tombol Retry Quarantine tanpa kehilangan data.

4. UNIFIED CUSTOM DOWNLOAD FOLDER STORAGE SYNC
Seluruh penamaan kunci penyimpanan lokal (chrome.storage.local) untuk pengaturan tingkat lanjut telah diselaraskan secara total dengan background service worker. Penggunaan parameter data dipastikan seragam menggunakan key 'createSubfolder' untuk toggle pengelompokan folder Canva_Auto, dan key 'downloadFolder' untuk direktori folder kustom Downloads. Hal ini menjamin fitur auto-rename file gambar bekerja 100% sinkron dan bebas dari bug ketidakaktifan UI settings.

5. TERMINAL LOG DUPLICATION REDUCTION
Struktur penangkap kesalahan pada loop utama startMainLoop telah dioptimalkan dengan mengeliminasi jalur re-throwing error yang tidak perlu. Pemanggilan aksi interupsi manual (USER_STOPPED) kini ditangani secara tuntas dan lokal oleh handleAutomationError, menghasilkan baris log konsol terminal yang bersih, rapi, dan bebas dari tulisan kembar/ganda.


### v1.1.5 — Viewport Scroll Reset & Production Polish

- **Viewport Scroll Reset:** Added auto-scroll to top (window.scrollTo) when typing a new prompt.
- **Textarea Focus:** Implemented instant visual focus and centering on the textarea container before input simulation starts.
- **Native DOM Injection:** Fully replaced CDP with native events for a cleaner, professional-grade user experience (no "Debugging" warning).
- **Real-time Analytics:** Added dynamic Avg Speed and ETA tracking.
- **Refining Radar:** Updated XPath to detect "Refining" status, ensuring precise download timing.
- **System Stability:** Added anti-sleep prevention to keep machines active during long batch sessions.

### v1.1.4 — Production Polish & Real-time Analytics

- Rebranded to **NRA DreamLab**.
- Implemented robust DOM polling and dynamic button slicing.

### v1.1.3

- Initial release with CDP-based automation and core queueing.

---

## 👤 Author

**Novri Rizki Akbar**

- GitHub: [@novri-ra](https://github.com/novri-ra)
- Support & Premium Products: [lynk.id/novri-ra](https://lynk.id/novri-ra)

---

## 📄 License

This project is for educational purposes only. See [LICENSE](LICENSE) for details.