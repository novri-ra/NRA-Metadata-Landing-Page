
import { getProjectBySlug, getProjects } from '@/lib/projects';
import { notFound } from 'next/navigation';
import Link from 'next/link';
import Markdown from 'react-markdown';

export function generateStaticParams() {
  return getProjects().map((p) => ({ slug: p.slug }));
}

export default function ProjectPage({ params }: { params: { slug: string } }) {
  const project = getProjectBySlug(params.slug);
  if (!project) notFound();

  return (
    <article className="max-w-3xl animate-in fade-in duration-700">
      <Link href="/" className="text-gray-400 hover:text-white mb-8 block">← Back</Link>
      <h1 className="text-4xl font-bold mb-4">{project.title}</h1>
      <div className="prose prose-invert max-w-none">
        <Markdown>{project.content}</Markdown>
      </div>
    </article>
  );
}
