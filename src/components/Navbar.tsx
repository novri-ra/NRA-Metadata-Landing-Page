export default function Navbar() {
  return (
    <nav className="sticky top-0 z-50 bg-base/90 backdrop-blur-md border-b border-borderline">
      <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
        <a href="#" className="font-black text-2xl tracking-tighter" aria-label="Beranda NRA-Metadata">
          <span className="text-white">NRA-</span><span className="text-muted">META</span>
        </a>
        <div className="hidden lg:flex items-center gap-8 text-sm font-semibold text-muted">
          <a href="#features" className="hover:text-neon transition-colors" aria-label="Lihat Fitur Utama">FITUR</a>
          <a href="#architecture" className="hover:text-neon transition-colors" aria-label="Lihat Arsitektur">ARSITEKTUR</a>
          <a href="#compliance" className="hover:text-neon transition-colors" aria-label="Lihat Matriks Regulasi">MATRIKS REGULASI</a>
          <a href="#setup" className="hover:text-neon transition-colors" aria-label="Lihat Setup Guide">SETUP GUIDE</a>
        </div>
        <a href="https://github.com/novri-ra/NRA-Metadata" target="_blank" rel="noreferrer" className="hidden md:flex items-center gap-2 border border-borderline hover:border-neon text-white hover:text-neon px-5 py-2.5 rounded-full text-sm font-bold transition-all shadow-none hover:shadow-[0_0_15px_rgba(179,255,0,0.2)]">
          <i className="fa-brands fa-github text-lg" aria-hidden="true"></i> STAR ON GITHUB
        </a>
        <button className="lg:hidden text-white text-2xl" aria-label="Buka Menu Navigasi">
          <i className="fa-solid fa-bars" aria-hidden="true"></i>
        </button>
      </div>
    </nav>
  );
}