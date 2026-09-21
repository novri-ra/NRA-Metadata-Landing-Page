export default function Footer() {
  return (
    <footer className="mt-auto border-t border-borderline bg-base">
      <div className="max-w-7xl mx-auto px-6 py-10 flex flex-col md:flex-row items-center justify-between gap-6 text-center md:text-left">
        <div className="flex flex-col gap-1">
          <p className="text-sm font-bold text-white">
            &copy; 2026 Novri Rizki Akbar. MIT License.
          </p>
          <p className="text-xs text-muted font-medium">
            Dokumentasi dan repositori bersifat privat. Halaman ini merepresentasikan arsitektur teknis NRA-Metadata secara utuh.
          </p>
        </div>
        <div className="flex items-center gap-6">
          <a href="https://github.com/novri-ra/NRA-Metadata" aria-label="GitHub Repository Pribadi" className="text-muted hover:text-white transition-colors text-2xl">
            <i className="fa-brands fa-github" aria-hidden="true"></i>
          </a>
        </div>
      </div>
    </footer>
  );
}