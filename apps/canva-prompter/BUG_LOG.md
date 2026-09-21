### [v1.1.32] - 2026-08-07
**Verification: Rilis Stabil & Testing Berhasil**
- **Status:** Pengujian pengguna berhasil 100%. Perbaikan terkait cooldown berulang akibat stale DOM dan status tombol Run yang tersangkut telah sepenuhnya teratasi di lingkungan live.
- **Tindakan:** Merilis versi v1.1.32 sebagai versi stabil terbaru.

### [v1.1.31] - 2026-08-07
**Fix: Repeated Cooldown Retrigger from Stale DOM Alerts**
- **Masalah:** Bot kembali memicu siklus cooldown kedua tepat setelah cooldown awal selesai dan prompt baru saja di-submit. POST-FLIGHT CHECK dan Pre-Flight CHECK mengeksekusi `getScreenCooldownMs()` dan membacanya dari teks alert/banner Canva yang masih tertinggal (stale DOM).
- **Akar Masalah:** 
  1. `tagGhostCooldowns` sebelumnya mengecualikan teks cooldown yang berada di dalam kontainer `role="alert"` atau `role="status"`.
  2. `getScreenCooldownMs` menyembunyikan tag dengan `style.display = "none"` tetapi mengambil semua teks menggunakan `document.body.textContent`, yang tetap menangkap elemen `display: none`.
- **Solusi:**
  1. Memperbarui `tagGhostCooldowns` untuk menandai semua elemen cooldown secara inklusif.
  2. Mengganti strategi penyembunyian di `getScreenCooldownMs` dengan secara sementara mengosongkan `.textContent` elemen yang ditandai, dan mengganti fallback ke `innerText` untuk akurasi. Menambahkan pengecekan `aria-disabled` yang lebih ketat pada tombol submit.

### [v1.1.27] - 2026-08-05
**Fix: Threshold Guard MAX_COOLDOWN Prematur**
- **Masalah:** Jika batas limit server di-hit secara wajar dua kali beruntun, pengguna tidak bisa membiarkan timer selesai karena limit `consecutiveCooldownCount >= 2` diletakkan di *awal* fungsi sebelum menunggu, sehingga bot langsung melemparkan error tanpa sempat menunggu cooldown ke-2.
- **Solusi:**
  1. Menaikkan threshold toleransi menjadi `>= 3` berturut-turut.
  2. Memindahkan eksekusi pengecekan threshold (guard) ke **akhir fungsi**, setelah siklus `delay` (while-loop timer cooldown) selesai menunggu dengan tuntas. Hal ini memastikan user tetap dapat melanjutkan eksekusi jika timer berakhir dan server kembali merespons.

**Feat: Max Consecutive Cooldown Guard**
- **Masalah:** Jika limit akun benar-benar habis di level server Canva, bot tetap mencoba mengirim prompt setelah cooldown habis yang memicu server langsung memberikan cooldown berikutnya (Infinite cooldown loops).
- **Solusi:** Menambahkan variabel pelacak `consecutiveCooldownCount`. Setiap kali `handleCooldown()` dipanggil, variabel ini naik 1 (direset ke 0 jika image berhasil didownload). Jika threshold mencapai >= 2, bot akan memotong eksekusi dan mematikan diri sendiri dengan melempar *Error* serta mengganti UI status: `Error: Account limit reached. Automation paused.`


**Fix: Mencegah Retrigger Cooldown Karena Stale DOM**
- **Masalah:** Cooldown sering dieksekusi berulang kali. Setelah hitung mundur cooldown selesai di Pre-Flight, ekstensi terjebak di hitung mundur baru pada Post-Flight karena UI Canva lambat memperbarui pesan rate-limit di layar (DOM masih mengandung teks alert "Try again in...").
- **Solusi:** 
  1. Menambahkan flag `justFinishedCooldown` untuk melewati pemeriksaan _post-flight_ secara sepihak jika loop saat ini baru saja pulih dari _pre-flight cooldown_.
  2. Menambahkan validasi tombol submit (Generate) di `getScreenCooldownMs()`. Jika tombol Generate aktif dan bisa diklik, ekstensi akan secara paksa mereset status bacaan text DOM ke `0 ms` karena secara logika mustahil akun terkunci jika tombolnya aktif.

**Fix: Cooldown Timer Loop & State Reset**
- **Masalah:** Bot terjebak di dalam "Cooldown Loop", mengulang hitungan cooldown terus-menerus tanpa pernah beralih ke prompt selanjutnya meskipun cooldown sudah berakhir.
- **Akar Masalah:** Pemanggilan ganda (paralel) dari `handleCooldown` dan interval timer yang tumpang tindih akibat tidak adanya _guard flag_. State UI dan memory cache saling mengaktifkan cooldown secara rekursif ketika loop mendeteksi teks sisa di UI.
- **Solusi (Ponytail & Systematic Debugging):** 
  1. Menambahkan guard murni (`isCooldownActive`) di level global content script. Pemanggilan `handleCooldown` berikutnya akan di-skip jika flag masih menyala.
  2. Guard membatalkan race-condition tanpa overhead observer baru.


**Fix: Start Button Terkunci Meskipun Canva Terhubung & Prompt Terisi**
- **Masalah:** Tombol "Run" tetap disabled karena status evaluasi DOM `startBtn` tidak mempertimbangkan kondisi field teks pada awal muat dan saat mengetik.
- **Akar Masalah:** Evaluator event untuk `promptInput` tidak disinkronisasi dengan variabel kondisi "Connected".
- **Solusi (Ponytail clean-code):** Menambahkan logika pengecekan panjang karakter (length > 0) ke inline-hook saat state UI di-refresh. Tombol langsung aktif (enabled) secara instan.
