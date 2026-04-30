import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import fs from 'node:fs';
import path from 'node:path';

const NOINDEX_PATHS = ['/success', '/account', '/feedback', '/r', '/z'];

function loadBlogDates() {
  const dir = path.resolve('./src/content/blog');
  const out = new Map();
  if (!fs.existsSync(dir)) return out;
  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith('.md')) continue;
    const slug = file.replace(/\.md$/, '');
    const src = fs.readFileSync(path.join(dir, file), 'utf8');
    const m = src.match(/^---\s*([\s\S]*?)\s*---/);
    if (!m) continue;
    const dateMatch = m[1].match(/^date:\s*['"]?([0-9TZ:.\-+]+)['"]?\s*$/m);
    if (dateMatch) {
      const d = new Date(dateMatch[1]);
      if (!isNaN(d.getTime())) out.set(slug, d.toISOString());
    }
  }
  return out;
}

export default defineConfig({
  site: 'https://ultrazoom.app',
  build: {
    format: 'file',
  },
  trailingSlash: 'never',
  integrations: [
    sitemap({
      filter: page => {
        const url = new URL(page);
        return !NOINDEX_PATHS.some(
          p => url.pathname === p || url.pathname.startsWith(p + '/')
        );
      },
      serialize: (() => {
        const dates = loadBlogDates();
        return item => {
          const url = new URL(item.url);
          const match = url.pathname.match(/^\/blog\/(.+?)\/?$/);
          if (match && dates.has(match[1])) {
            item.lastmod = dates.get(match[1]);
          }
          return item;
        };
      })(),
    }),
  ],
});
