export default function Features() {
  return (
    <section id="features" className="max-w-7xl mx-auto px-6 py-24">
      <div className="text-center mb-16">
        <h2 className="text-3xl md:text-5xl font-black uppercase tracking-tighter">Arsitektur & Fitur Utama</h2>
        <p className="text-muted mt-4 max-w-2xl mx-auto font-medium">NRA-Metadata menggantikan kurasi manual yang memakan waktu berjam-jam dengan pipa kerja vision-AI yang presisi dan arsitektur pengolahan massal (batch processing) yang sangat optimal.</p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Fitur 1 */}
        <div className="bg-surface border border-borderline rounded-2xl p-8 hover:border-neon/40 transition-colors group">
          <div className="w-14 h-14 bg-borderline rounded-xl flex items-center justify-center text-2xl text-white group-hover:text-neon group-hover:bg-neon/10 transition-colors mb-6">
            <i className="fa-solid fa-brain" aria-hidden="true"></i>
          </div>
          <h3 className="text-xl font-bold mb-3 uppercase tracking-wide">Multi-Provider Vision LLM</h3>
          <p className="text-muted leading-relaxed font-medium text-sm">
            Dilengkapi failover otomatis dan rotasi API key. Mendukung provider Gemini, OpenAI, Mistral, Groq, serta endpoint kompatibel (seperti 9router). Vision Ingestion Engine secara otomatis melakukan komposit kanvas RGBA transparan di atas warna putih murni sebelum parsing AI untuk mencegah kesalahan deteksi dan halusinasi background hitam.
          </p>
        </div>
        
        {/* Fitur 2 */}
        <div className="bg-surface border border-borderline rounded-2xl p-8 hover:border-neon/40 transition-colors group">
          <div className="w-14 h-14 bg-borderline rounded-xl flex items-center justify-center text-2xl text-white group-hover:text-neon group-hover:bg-neon/10 transition-colors mb-6">
            <i className="fa-solid fa-eye-slash" aria-hidden="true"></i>
          </div>
          <h3 className="text-xl font-bold mb-3 uppercase tracking-wide">Preview Rendering Headless</h3>
          <p className="text-muted leading-relaxed font-medium text-sm">
            Tidak bergantung pada antarmuka yang memakan memori. Raster, vektor EPS/AI (melalui Ghostscript), grafis SVG (melalui Microsoft Edge/svglib), dan Video (via FFmpeg) dirender secara headless menjadi pratinjau sebelum analisis. Membersihkan semua sisa temp secara deterministik di blok akhir eksekusi, menjamin disk tetap bersih.
          </p>
        </div>

        {/* Fitur 3 */}
        <div className="bg-surface border border-borderline rounded-2xl p-8 hover:border-neon/40 transition-colors group">
          <div className="w-14 h-14 bg-borderline rounded-xl flex items-center justify-center text-2xl text-white group-hover:text-neon group-hover:bg-neon/10 transition-colors mb-6">
            <i className="fa-solid fa-server" aria-hidden="true"></i>
          </div>
          <h3 className="text-xl font-bold mb-3 uppercase tracking-wide">Arsitektur Keamanan & Concurrency</h3>
          <p className="text-muted leading-relaxed font-medium text-sm">
            <strong>Thread-Safe I/O:</strong> Membungkus interaksi penulisan ekspor metadata CSV massal menggunakan instance <code className="text-neon bg-neon/10 px-1 rounded">threading.Lock()</code> untuk mencegah korupsi race condition (hingga 20 thread worker).
            <br/><br/>
            <strong>Anti Thread Starvation:</strong> IO HTTP lock (misal: Mistral) dilepas tepat waktu saat pemanggilan request jaringan.
            <br/><br/>
            <strong>Chunked Video Streaming:</strong> Ekspor IPTC memproses secara chunk 64KB, mencegah OOM (Out of Memory) pada pemrosesan file raksasa/4K.
          </p>
        </div>

        {/* Fitur 4 */}
        <div className="bg-surface border border-borderline rounded-2xl p-8 hover:border-neon/40 transition-colors group">
          <div className="w-14 h-14 bg-borderline rounded-xl flex items-center justify-center text-2xl text-white group-hover:text-neon group-hover:bg-neon/10 transition-colors mb-6">
            <i className="fa-solid fa-code-merge" aria-hidden="true"></i>
          </div>
          <h3 className="text-xl font-bold mb-3 uppercase tracking-wide">Standar IPTC 2025.1 & Integritas C2PA</h3>
          <p className="text-muted leading-relaxed font-medium text-sm">
            Menulis metadata secara non-destruktif. Mencatat properti <code className="text-neon bg-neon/10 px-1 rounded">XMP:DigitalSourceType</code> (trainedAlgorithmicMedia) dan rincian AI system (XMP-iptcExt) tanpa pernah menuliskan *prompt* mentah. Hal ini menjamin integritas <strong>Manifest C2PA</strong> tetap utuh. Fitur <em>AI-Junk Cleansing</em> akan menghapus residu PNG parameters bagi aset karya manusia agar terhindar dari cap salah klasifikasi.
          </p>
        </div>
      </div>
    </section>
  );
}