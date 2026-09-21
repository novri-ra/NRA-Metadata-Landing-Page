import Link from 'next/link';
import { getProjects } from '@/lib/projects';
import { ArrowUpRight, Code2, PenTool, Layout, MonitorSmartphone } from 'lucide-react';

export default function Home() {
  const projects = getProjects();

  return (
    <div className="space-y-32 animate-in fade-in slide-in-from-bottom-8 duration-1000 ease-out">
      
      {/* HERO SECTION */}
      <section className="space-y-8 relative">
        <div className="absolute -top-32 -left-32 w-96 h-96 bg-[#6E001B]/20 blur-[120px] rounded-full pointer-events-none" />
        <h1 className="text-6xl sm:text-7xl md:text-8xl font-black tracking-tighter text-white uppercase leading-[0.9]">
          Emperor<br/>
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-[#6E001B] to-[#ff2a4d]">Studio.</span>
        </h1>
        <p className="text-neutral-400 text-lg md:text-xl max-w-2xl leading-relaxed font-medium">
          Forging cinematic digital experiences. We blend relentless engineering with uncompromising design to build the web of tomorrow.
        </p>
        
        {/* STATS */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-8 border-t border-neutral-900/50">
          {[
            { label: 'Projects Deployed', value: '45+' },
            { label: 'Lines of Code', value: '1M+' },
            { label: 'Global Clients', value: '12' },
            { label: 'Uptime', value: '99.9%' },
          ].map((stat) => (
            <div key={stat.label} className="space-y-1">
              <p className="text-3xl font-bold text-white">{stat.value}</p>
              <p className="text-xs uppercase tracking-widest text-neutral-600 font-bold">{stat.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* SERVICES / MISSION ARCHIVE */}
      <section>
        <div className="flex items-center justify-between mb-12 border-b border-neutral-900 pb-4">
          <h2 className="text-sm font-bold text-white uppercase tracking-[0.2em]">Mission Archive</h2>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {[
            { icon: Code2, title: 'Fullstack Dev' },
            { icon: Layout, title: 'UI/UX Design' },
            { icon: PenTool, title: 'Creative Direction' },
            { icon: MonitorSmartphone, title: 'Mobile Apps' },
          ].map((service) => (
            <div key={service.title} className="p-6 rounded-2xl bg-[#111] border border-neutral-800/50 hover:border-[#6E001B]/50 transition-colors group">
              <service.icon className="text-neutral-500 group-hover:text-[#ff2a4d] mb-4 transition-colors" size={32} strokeWidth={1.5} />
              <h3 className="font-bold text-white tracking-wide">{service.title}</h3>
            </div>
          ))}
        </div>
      </section>

      {/* BENTO-BOX PROJECT SHOWCASE */}
      <section>
        <div className="flex items-center justify-between mb-12 border-b border-neutral-900 pb-4">
          <h2 className="text-sm font-bold text-white uppercase tracking-[0.2em]">Featured Work</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[300px]">
          {projects.map((project, i) => {
            const isFeatured = i % 4 === 0 || i % 4 === 3;
            
            return (
              <Link 
                key={project.slug} 
                href={`/projects/${project.slug}`}
                className={`group relative flex flex-col justify-end p-8 rounded-3xl bg-[#111] border border-neutral-800/50 hover:border-[#6E001B]/50 transition-all duration-500 overflow-hidden ${isFeatured ? 'md:col-span-2' : 'md:col-span-1'}`}
              >
                <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0A] via-transparent to-transparent opacity-80 z-0" />
                <div className="absolute inset-0 bg-[#6E001B]/5 opacity-0 group-hover:opacity-100 transition-opacity duration-700 z-0" />
                
                <div className="absolute top-8 right-8 z-10 w-12 h-12 rounded-full bg-black/50 backdrop-blur border border-neutral-800 flex items-center justify-center group-hover:bg-[#6E001B] group-hover:border-[#ff2a4d] transition-all duration-300">
                  <ArrowUpRight className="text-neutral-400 group-hover:text-white" size={20} />
                </div>

                <div className="relative z-10">
                  <div className="flex flex-wrap gap-2 mb-4">
                    {project.stack.slice(0, 3).map(tech => (
                      <span key={tech} className="px-3 py-1 rounded-full bg-black/60 backdrop-blur text-neutral-300 text-[10px] font-bold uppercase tracking-wider border border-neutral-800">
                        {tech}
                      </span>
                    ))}
                  </div>
                  <h3 className="text-3xl font-bold text-white mb-2 group-hover:text-[#ff2a4d] transition-colors">
                    {project.title}
                  </h3>
                  <p className="text-neutral-500 text-sm line-clamp-2 max-w-md">
                    {project.description}
                  </p>
                </div>
              </Link>
            );
          })}
          {projects.length === 0 && (
            <div className="col-span-full p-8 rounded-3xl border border-dashed border-neutral-800 flex items-center justify-center text-neutral-500 uppercase tracking-widest text-sm font-bold">
              No transmission found.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
