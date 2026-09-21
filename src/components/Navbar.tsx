interface NavbarProps {
  activeProject: string;
  setActiveProject: (project: string) => void;
}

export default function Navbar({ activeProject, setActiveProject }: NavbarProps) {
  return (
    <nav className="sticky top-0 z-50 bg-base/90 backdrop-blur-md border-b border-borderline">
      <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
        <a href="#" onClick={(e) => { e.preventDefault(); setActiveProject('metadata'); }} className="font-black text-2xl tracking-tighter" aria-label="Beranda">
          <span className="text-white">NRA-</span><span className="text-muted">PROJECTS</span>
        </a>
        
        {/* Project Selector Menu */}
        <div className="hidden lg:flex items-center gap-4 bg-surface p-1 rounded-full border border-borderline">
          <button 
            onClick={() => setActiveProject('metadata')}
            className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all ${activeProject === 'metadata' ? 'bg-neon text-black' : 'text-muted hover:text-white'}`}
          >
            METADATA ENGINE
          </button>
          <button 
            onClick={() => setActiveProject('canva')}
            className={`px-4 py-1.5 rounded-full text-xs font-bold transition-all ${activeProject === 'canva' ? 'bg-neon text-black' : 'text-muted hover:text-white'}`}
          >
            CANVA AUTO-PROMPTER
          </button>
        </div>

        <a href="https://github.com/novri-ra/NRA-Project" target="_blank" rel="noreferrer" className="hidden md:flex items-center gap-2 border border-borderline hover:border-neon text-white hover:text-neon px-5 py-2.5 rounded-full text-sm font-bold transition-all shadow-none hover:shadow-[0_0_15px_rgba(179,255,0,0.2)]">
          <i className="fa-brands fa-github text-lg" aria-hidden="true"></i> GITHUB
        </a>
        <button className="lg:hidden text-white text-2xl" aria-label="Buka Menu Navigasi">
          <i className="fa-solid fa-bars" aria-hidden="true"></i>
        </button>
      </div>
    </nav>
  );
}