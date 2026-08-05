### [v1.1.25] - 2026-08-05
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
