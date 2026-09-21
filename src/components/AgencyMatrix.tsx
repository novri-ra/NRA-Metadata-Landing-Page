export default function AgencyMatrix() {
  const complianceData = [
    {
      agency: 'Adobe Stock',
      title: 'Target SEO 50–70 karakter',
      desc: 'Deskripsi makna penuh ≥ 5 kata',
      keywords: '5–49 keyword',
      notes: 'Peringatan max 200 karakter. Pelarang kata spam (Vector, Illustration, Isolated). Pemetaan kategori taxonomy otomatis.'
    },
    {
      agency: 'Shutterstock',
      title: 'Maksimal 2048 karakter (2026)',
      desc: 'Narasi kontekstual 250–800 karakter',
      keywords: '7–50 keyword',
      notes: 'Menolak mutlak metadata GenAI (checkbox AI di-set "false" saat ekspor otomatis pada agensi ini).'
    },
    {
      agency: 'Vecteezy',
      title: 'Terbatas 3–8 kata (Max 200 chr)',
      desc: 'Maksimum 200 karakter',
      keywords: '5–50 keyword',
      notes: 'Karakter judul Alfanumerik + [ , . - \' ]. Diawasi ketat via Regex Validator internal sebelum export.'
    },
    {
      agency: 'Freepik',
      title: 'Min 5 kata, Max 200 karakter',
      desc: 'Maksimum 200 karakter',
      keywords: '5–50 keyword',
      notes: 'Delimiter wajib menggunakan titik-koma (;) pada kolom ekspor CSV. Wajib set bendera metadata Generative AI.'
    },
    {
      agency: 'Dreamstime',
      title: 'Min 5 kata, Max 200 karakter',
      desc: 'Min 5 kata hingga 2000 karakter',
      keywords: '5–80 keyword',
      notes: 'Injeksi status otomatis AI provenance divalidasi presisi saat check-box GUI dipilih.'
    },
    {
      agency: 'iStock / Getty',
      title: 'Format editorial 5W (Max 250 chr)',
      desc: 'Maksimum 2000 karakter',
      keywords: 'Maks 50 keyword (≤ 64 char)',
      notes: 'Free-text taxonomy divalidasi beserta penegakan format factual timestamp (YYYYMMDD) pada tag relevan.'
    }
  ];

  return (
    <section id="compliance" className="bg-surface border-y border-borderline py-24 overflow-hidden relative">
      <div className="max-w-7xl mx-auto px-6">
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-5xl font-black uppercase tracking-tighter">Matriks Regulasi 2026</h2>
          <p className="text-muted mt-4 max-w-2xl mx-auto font-medium">Nilai-nilai ini dieksekusi secara presisi oleh modul internal <code className="text-neon bg-neon/10 px-2 py-0.5 rounded">filter.py</code> dan <code className="text-neon bg-neon/10 px-2 py-0.5 rounded">csv_exporter.py</code>, diverifikasi terhadap pedoman resmi agensi.</p>
        </div>

        <div className="overflow-x-auto border border-borderline rounded-2xl bg-base">
          <table className="w-full text-left text-sm whitespace-nowrap md:whitespace-normal">
            <thead className="bg-[#111111] border-b border-borderline text-white">
              <tr>
                <th className="px-6 py-5 font-bold uppercase tracking-wider">Agensi</th>
                <th className="px-6 py-5 font-bold uppercase tracking-wider">Panduan Judul</th>
                <th className="px-6 py-5 font-bold uppercase tracking-wider">Panduan Deskripsi</th>
                <th className="px-6 py-5 font-bold uppercase tracking-wider">Keyword</th>
                <th className="px-6 py-5 font-bold uppercase tracking-wider">Catatan Kepatuhan</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-borderline">
              {complianceData.map((item, idx) => (
                <tr key={idx} className="hover:bg-surface/50 transition-colors group">
                  <td className="px-6 py-5 font-black text-white group-hover:text-neon transition-colors">{item.agency}</td>
                  <td className="px-6 py-5 text-muted font-medium">{item.title}</td>
                  <td className="px-6 py-5 text-muted font-medium">{item.desc}</td>
                  <td className="px-6 py-5 text-white font-bold">{item.keywords}</td>
                  <td className="px-6 py-5 text-muted text-xs leading-relaxed max-w-[300px]">{item.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        <div className="mt-8 text-center text-xs text-muted">
          * Algoritma pemangkasan teks memotong pada batas kata (<code className="text-neon opacity-70">word-boundary</code>) — tidak pernah memenggal di tengah kalimat.
        </div>
      </div>
    </section>
  );
}