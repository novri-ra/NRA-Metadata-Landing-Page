import { getProjectBySlug, getProjects } from '@/lib/projects';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import Markdown from 'react-markdown';
import { ArrowLeft } from 'lucide-react';

export function generateStaticParams() {
  return getProjects().map((p) => ({ slug: p.slug }));
}

export default function ProjectPage({ params }: { params: { slug: string } }) {
  const project = getProjectBySlug(params.slug);
  if (!project) notFound();

  return (
    <article className="max-w-4xl mx-auto animate-in fade-in slide-in-from-bottom-8 duration-1000 ease-out">
      <Link href="/" className="inline-flex items-center text-xs font-bold uppercase tracking-widest text-neutral-500 hover:text-[#ff2a4d] transition-colors mb-16">
        <ArrowLeft className="mr-2" size={16} /> Back to HQ
      </Link>
      
      <header className="mb-16 relative">
        <div className="absolute -top-32 -left-32 w-64 h-64 bg-[#6E001B]/20 blur-[100px] rounded-full pointer-events-none" />
        <h1 className="text-5xl md:text-7xl font-black tracking-tighter text-white uppercase leading-[0.9] mb-8 relative z-10">
          {project.title}
        </h1>
        
        <div className="flex flex-wrap gap-3 relative z-10">
          {project.stack.map(tech => (
            <span key={tech} className="px-4 py-1.5 rounded-full bg-[#111] text-neutral-300 text-xs font-bold uppercase tracking-widest border border-neutral-800">
              {tech}
            </span>
          ))}
        </div>
      </header>

      <div className="prose prose-invert prose-neutral max-w-none 
        prose-headings:font-black prose-headings:uppercase prose-headings:tracking-tight 
        prose-h1:text-4xl prose-h2:text-2xl 
        prose-a:text-[#ff2a4d] hover:prose-a:text-[#ff2a4d]/80
        prose-strong:text-white prose-p:text-neutral-400 prose-p:leading-relaxed
        prose-hr:border-neutral-900 prose-blockquote:border-l-[#6E001B] prose-blockquote:bg-[#111] prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:rounded-r-lg">
        <Markdown>{project.content}</Markdown>
      </div>
    </article>
  );
}
