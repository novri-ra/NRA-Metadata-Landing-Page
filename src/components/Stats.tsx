export default function Stats() {
  const stats = [
    { label: 'Unit Tests Passing', value: '235/235', color: 'text-neon glow-text', icon: 'fa-vial-circle-check' },
    { label: 'Python Version', value: '3.11+', color: 'text-white', icon: 'fa-python', isBrand: true },
    { label: 'Security Standard', value: 'Zero Zip-Slip', color: 'text-white', icon: 'fa-shield-halved' },
    { label: 'OS Optimization', value: 'Ghost Spectre', color: 'text-white', icon: 'fa-windows', isBrand: true },
    { label: 'Compliance Ready', value: '2026', color: 'text-neon glow-text', icon: 'fa-calendar-check' },
  ];

  return (
    <section className="border-y border-borderline bg-surface/50">
      <div className="max-w-7xl mx-auto px-6 py-10">
        <div className="flex flex-wrap items-center justify-center gap-x-12 gap-y-10 md:justify-between divide-x-0 md:divide-x divide-borderline">
          {stats.map((stat, idx) => (
            <div key={idx} className="flex flex-col items-center text-center gap-3 px-4 flex-1 min-w-[140px]">
              <i className={`${stat.isBrand ? 'fa-brands' : 'fa-solid'} ${stat.icon} text-2xl text-muted mb-1`} aria-hidden="true"></i>
              <span className={`text-2xl md:text-3xl font-black whitespace-nowrap ${stat.color}`}>
                {stat.value}
              </span>
              <span className="text-[10px] md:text-xs text-muted uppercase font-bold tracking-[0.15em]">
                {stat.label}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}