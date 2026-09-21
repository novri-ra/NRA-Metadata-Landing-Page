export default function Hero() {
  return (
    <section className="relative w-full max-w-7xl mx-auto px-6 pt-24 pb-20 md:pt-32 md:pb-24 flex flex-col items-center text-center gap-8 overflow-hidden">
      {/* Background Glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-neon/10 blur-[120px] rounded-full pointer-events-none"></div>
      
      <div className="inline-flex items-center gap-2 border border-neon/30 bg-neon/5 text-neon px-5 py-2 rounded-full text-xs font-bold uppercase tracking-widest relative z-10">
        <i className="fa-solid fa-bolt" aria-hidden="true"></i> Batch Metadata Studio & Microstock Compliance Engine untuk Era Generative AI
      </div>
      
      <h1 className="text-5xl md:text-7xl lg:text-8xl font-black uppercase tracking-tighter leading-[0.95] relative z-10">
        REAL AUTOMATION.<br/>
        <span className="text-neon glow-text block my-2">REAL COMPLIANCE.</span>
        <span className="block">REAL METADATA.</span>
      </h1>
      
      <p className="text-muted text-base md:text-xl max-w-3xl font-medium leading-relaxed relative z-10 mt-4">
        Otomasi tingkat profesional untuk analisis visual, pembangkitan Title / Description / Keywords, injeksi langsung IPTC-XMP, dan ekspor CSV multi-agensi — dengan kepatuhan penuh terhadap regulasi 2026 dan perlindungan keamanan <span className="text-white font-bold">Zero Zip-Slip</span>.
      </p>
      
      <div className="flex flex-col sm:flex-row items-center gap-4 mt-6 relative z-10 w-full sm:w-auto">
        <a href="https://github.com/novri-ra/NRA-Metadata/releases" className="w-full sm:w-auto bg-neon text-black font-bold px-8 py-4 rounded-full hover:bg-[#99db00] transition-all glow-box flex items-center justify-center gap-3">
          <i className="fa-solid fa-download text-lg" aria-hidden="true"></i> 
          <span className="flex flex-col items-start leading-tight">
            <span>UNDUH INSTALLER (v1.2.5)</span>
            <span className="text-[10px] opacity-80 uppercase tracking-widest font-semibold">NRA-Metadata-Setup-Final.exe</span>
          </span>
        </a>
        <a href="#setup" className="w-full sm:w-auto border border-borderline hover:border-white text-white font-bold px-8 py-4 rounded-full transition-all flex items-center justify-center gap-2">
          <i className="fa-solid fa-terminal" aria-hidden="true"></i> SETUP GUIDE
        </a>
      </div>
    </section>
  );
}