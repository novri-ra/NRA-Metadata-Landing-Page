import Link from 'next/link';
import { getProjects } from '@/lib/projects';
import { ArrowUpRight } from 'lucide-react';

export default function Home() {
  const projects = getProjects();

  return (
    <div className="space-y-24 animate-in fade-in slide-in-from-bottom-8 duration-1000 ease-out">
      {/* Hero Section */}
      <section className="space-y-6">
        <h1 className="text-5xl sm:text-6xl font-extrabold tracking-tight text-white drop-shadow-sm">
          NRA<span className="text-neutral-600">.</span>
        </h1>
        <p className="text-neutral-400 text-lg max-w-xl leading-relaxed">
          Senior Fullstack Developer. Building modern, scalable, and high-performance web applications with clean architecture.
        </p>
      </section>

      {/* Bento Box Grid */}
      <section>
        <h2 className="text-sm font-semibold text-neutral-500 uppercase tracking-widest mb-8">
          Selected Projects
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 auto-rows-[250px]">
          {projects.map((project, i) => (
            <Link 
              key={project.slug} 
              href={`/projects/${project.slug}`}
              className={`group relative flex flex-col justify-between p-6 rounded-3xl bg-neutral-900/50 border border-neutral-800 hover:bg-neutral-800 transition-all duration-300 overflow-hidden ${i === 0 ? 'md:col-span-2' : ''}`}
            >
              <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
              
              <div className="relative z-10 flex justify-between items-start">
                <h3 className="text-xl font-bold text-neutral-100 group-hover:text-white transition-colors">
                  {project.title}
                </h3>
                <ArrowUpRight className="text-neutral-600 group-hover:text-white transition-colors" size={22} />
              </div>

              <div className="relative z-10 space-y-4">
                <p className="text-neutral-400 text-sm line-clamp-2">
                  {project.description}
                </p>
                <div className="flex flex-wrap gap-2">
                  {project.stack.slice(0, 3).map(tech => (
                    <span key={tech} className="px-3 py-1 rounded-full bg-black/40 text-neutral-300 text-xs font-medium border border-neutral-800">
                      {tech}
                    </span>
                  ))}
                  {project.stack.length > 3 && (
                    <span className="px-3 py-1 rounded-full bg-black/40 text-neutral-500 text-xs font-medium border border-neutral-800">
                      +{project.stack.length - 3}
                    </span>
                  )}
                </div>
              </div>
            </Link>
          ))}
          {projects.length === 0 && (
            <div className="col-span-full p-8 rounded-3xl border border-dashed border-neutral-800 flex items-center justify-center text-neutral-500">
              No projects found. Add markdown files to src/content/projects.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
