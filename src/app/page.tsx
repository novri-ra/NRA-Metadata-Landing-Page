
import Link from 'next/link';
import { getProjects } from '@/lib/projects';

export default function Home() {
  const projects = getProjects();
  return (
    <div className="space-y-16 animate-in fade-in duration-700">
      <section>
        <h1 className="text-4xl font-bold mb-4">NRA.</h1>
        <p className="text-gray-400">Senior Fullstack Developer.</p>
      </section>
      
      <section className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {projects.map((p) => (
          <Link key={p.slug} href={`/projects/${p.slug}`} className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition">
            <h3 className="text-xl font-bold mb-2">{p.title}</h3>
            <p className="text-gray-400 mb-4">{p.description}</p>
            <div className="flex gap-2 flex-wrap">
              {p.stack.map(t => <span key={t} className="px-2 py-1 bg-white/10 rounded text-xs">{t}</span>)}
            </div>
          </Link>
        ))}
      </section>
    </div>
  );
}
