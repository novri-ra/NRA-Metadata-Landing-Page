### [v1.1.23] - 2026-08-05
**Fix: Start Button Terkunci Meskipun Canva Terhubung & Prompt Terisi**
- **Masalah:** Tombol "Run" tetap disabled karena status evaluasi DOM `startBtn` tidak mempertimbangkan kondisi field teks pada awal muat dan saat mengetik.
- **Akar Masalah:** Evaluator event untuk `promptInput` tidak disinkronisasi dengan variabel kondisi "Connected".
- **Solusi (Ponytail clean-code):** Menambahkan logika pengecekan panjang karakter (length > 0) ke inline-hook saat state UI di-refresh. Tombol langsung aktif (enabled) secara instan.
