export default function SetupGuide() {
  return (
    <section id="setup" className="max-w-5xl mx-auto px-6 py-24 w-full">
      <div className="text-center mb-12">
        <h2 className="text-3xl md:text-5xl font-black uppercase tracking-tighter">Developer & Setup Guide</h2>
        <p className="text-muted mt-4 font-medium max-w-2xl mx-auto">
          Mekanisme instalasi berbasis script otonom. Auto-download dan injeksi binari untuk dependensi ExifTool & FFmpeg akan berjalan di latar belakang (Zero-Setup).
        </p>
      </div>

      <div className="bg-[#111111] border border-borderline rounded-xl overflow-hidden shadow-2xl">
        {/* Terminal Header */}
        <div className="bg-[#1a1a1a] border-b border-borderline px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500"></div>
            <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
            <div className="w-3 h-3 rounded-full bg-green-500"></div>
            <span className="ml-4 text-xs font-mono text-muted">administrator@nra-metadata:~</span>
          </div>
          <div className="text-[10px] uppercase text-muted font-bold tracking-widest">NRA-METADATA/CLI</div>
        </div>
        
        {/* Terminal Body */}
        <div className="p-6 md:p-8 font-mono text-sm leading-relaxed overflow-x-auto">
          <div className="text-muted mb-2"># 1. Kloning repositori (atau unduh Installer v1.2.5 untuk end-user)</div>
          <div className="text-white mb-6">
            <span className="text-neon">git clone</span> https://github.com/novri-ra/NRA-Metadata.git<br/>
            <span className="text-neon">cd</span> NRA-Metadata
          </div>

          <div className="text-muted mb-2"># 2. Struktur Direktori Proyek</div>
          <div className="text-gray-400 mb-6 border-l-2 border-borderline pl-4">
            .<br/>
            ├── apps/ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span className="text-muted opacity-50"># Modul GUI dan antarmuka utama (CustomTkinter)</span><br/>
            ├── backend/ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span className="text-muted opacity-50"># Logika filter.py, csv_exporter.py, & vision ingestion</span><br/>
            ├── packages/ &nbsp;&nbsp;&nbsp;&nbsp;<span className="text-muted opacity-50"># Asset statis & library tambahan</span><br/>
            ├── tests/ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<span className="text-muted opacity-50"># 235 Unit testing suit (pytest)</span><br/>
            └── run_app.bat &nbsp;&nbsp;<span className="text-muted opacity-50"># Entry point utama Windows</span>
          </div>

          <div className="text-muted mb-2"># 3. Jalankan aplikasi (Bootstrapper otomatis)</div>
          <div className="text-white mb-6">
            .\\run_app.bat
          </div>

          <div className="text-muted mb-2"># Catatan Autentikasi (Google Apps Script Server)</div>
          <div className="text-gray-400">
            Jika menggunakan server otentikasi mandiri, pastikan pengaturan Google Apps Script <strong>New Deployment</strong> diatur sebagai:<br/>
            <span className="text-neon">-</span> Execute as: <strong>Me (email_anda@gmail.com)</strong><br/>
            <span className="text-neon">-</span> Who has access: <strong>Anyone</strong><br/>
            <br/>
            <span className="opacity-70 text-xs">Atau gunakan mode offline mutlak dengan environment variable <code className="bg-white/10 px-1 rounded text-white">DEBUG=1</code> atau dengan membuat file <code className="bg-white/10 px-1 rounded text-white">.dev_mode</code> di root direktori.</span>
          </div>
        </div>
      </div>
    </section>
  );
}