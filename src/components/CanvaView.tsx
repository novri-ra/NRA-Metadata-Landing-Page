export default function CanvaView() {
  return (
    <div className="animate-in fade-in duration-500">
      <section className="relative w-full max-w-7xl mx-auto px-6 pt-24 pb-20 flex flex-col items-center text-center gap-8 overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-500/10 blur-[120px] rounded-full pointer-events-none"></div>
        
        <div className="inline-flex items-center gap-2 border border-indigo-500/30 bg-indigo-500/5 text-indigo-400 px-5 py-2 rounded-full text-xs font-bold uppercase tracking-widest relative z-10">
          <i className="fa-brands fa-chrome" aria-hidden="true"></i> Chrome Extension Automation
        </div>
        
        <h1 className="text-5xl md:text-7xl font-black uppercase tracking-tighter leading-[0.95] relative z-10">
          CANVA AUTO<br/>
          <span className="text-indigo-400 glow-text-indigo block my-2">PROMPTER.</span>
        </h1>
        
        <p className="text-muted text-base md:text-xl max-w-3xl font-medium leading-relaxed relative z-10 mt-4">
          Ekstensi Chrome cerdas untuk mengotomatisasi injeksi prompt pada antarmuka Canva Text-to-Image. Secara instan memproses antrean desain dari payload eksternal dengan bypass seleksi DOM otomatis.
        </p>

        <div className="flex flex-col sm:flex-row items-center gap-4 mt-6 relative z-10">
          <a href="https://github.com/novri-ra/NRA-Canva-Auto-Prompter" target="_blank" rel="noreferrer" className="w-full sm:w-auto bg-indigo-500 text-white font-bold px-8 py-4 rounded-full hover:bg-indigo-400 transition-all shadow-[0_0_20px_rgba(99,102,241,0.3)] flex items-center justify-center gap-3">
            <i className="fa-solid fa-download text-lg" aria-hidden="true"></i> UNDUH EKSTENSI (v1.2.1)
          </a>
        </div>
      </section>

      <section className="border-y border-borderline bg-surface/50">
        <div className="max-w-7xl mx-auto px-6 py-10">
          <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-10 md:justify-between divide-x-0 md:divide-x divide-borderline">
            <div className="flex flex-col items-center text-center gap-3 px-4 flex-1">
              <i className="fa-brands fa-js text-2xl text-muted mb-1"></i>
              <span className="text-3xl font-black text-white">Vanilla JS</span>
              <span className="text-[10px] md:text-xs text-muted uppercase font-bold tracking-[0.15em]">Lightweight Stack</span>
            </div>
            <div className="flex flex-col items-center text-center gap-3 px-4 flex-1">
              <i className="fa-solid fa-robot text-2xl text-muted mb-1"></i>
              <span className="text-3xl font-black text-indigo-400">Zero-Click</span>
              <span className="text-[10px] md:text-xs text-muted uppercase font-bold tracking-[0.15em]">DOM Automation</span>
            </div>
            <div className="flex flex-col items-center text-center gap-3 px-4 flex-1">
              <i className="fa-solid fa-bolt text-2xl text-muted mb-1"></i>
              <span className="text-3xl font-black text-white">Manifest V3</span>
              <span className="text-[10px] md:text-xs text-muted uppercase font-bold tracking-[0.15em]">Chrome Store Ready</span>
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-4xl mx-auto px-6 py-24 w-full">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-black uppercase tracking-tighter">Instalasi Developer (Unpacked)</h2>
        </div>
        <div className="bg-[#111111] border border-borderline rounded-xl overflow-hidden shadow-2xl">
          <div className="bg-[#1a1a1a] border-b border-borderline px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-red-500"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
            </div>
          </div>
          <div className="p-6 md:p-8 font-mono text-sm leading-relaxed overflow-x-auto text-left">
            <div className="text-muted mb-2"># 1. Posisikan di direktori canva-prompter</div>
            <div className="text-white mb-6">
              <span className="text-indigo-400">cd</span> apps/canva-prompter
            </div>
            <div className="text-muted mb-2"># 2. Buka Ekstensi Chrome</div>
            <div className="text-white mb-6">
              Kunjungi <span className="text-indigo-400">chrome://extensions/</span>
            </div>
            <div className="text-muted mb-2"># 3. Mode Developer</div>
            <div className="text-white">
              Aktifkan <strong>Developer mode</strong> &gt; Klik <strong>Load unpacked</strong> &gt; Pilih direktori <code>apps/canva-prompter</code>.
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}