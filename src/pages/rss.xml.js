import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';

export async function GET(context) {
  const posts = (await getCollection('blog')).sort(
    (a, b) => b.data.date.getTime() - a.data.date.getTime()
  );

  return rss({
    title: 'Ultra Zoom Blog',
    description:
      'Release notes, tips, and use-case guides for Ultra Zoom, the hover-to-zoom browser extension.',
    site: context.site,
    trailingSlash: false,
    items: posts.map(post => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.date,
      categories: [post.data.category],
      link: `/blog/${post.id}`,
    })),
    customData: '<language>en-us</language>',
  });
}
