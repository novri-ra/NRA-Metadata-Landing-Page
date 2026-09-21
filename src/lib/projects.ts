
import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';

const contentDir = path.join(process.cwd(), 'src/content/projects');

export type Project = {
  slug: string;
  title: string;
  description: string;
  stack: string[];
  content: string;
};

export function getProjects(): Project[] {
  if (!fs.existsSync(contentDir)) return [];
  const files = fs.readdirSync(contentDir).filter(f => f.endsWith('.md'));
  return files.map(filename => {
    const filePath = path.join(contentDir, filename);
    const { data, content } = matter(fs.readFileSync(filePath, 'utf8'));
    return {
      slug: filename.replace('.md', ''),
      title: data.title || 'Untitled',
      description: data.description || '',
      stack: data.stack || [],
      content,
    };
  });
}

export function getProjectBySlug(slug: string): Project | null {
  const filePath = path.join(contentDir, `${slug}.md`);
  if (!fs.existsSync(filePath)) return null;
  const { data, content } = matter(fs.readFileSync(filePath, 'utf8'));
  return {
    slug,
    title: data.title || 'Untitled',
    description: data.description || '',
    stack: data.stack || [],
    content,
  };
}
