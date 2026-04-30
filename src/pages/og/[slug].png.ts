import type { APIContext } from 'astro';
import { getCollection } from 'astro:content';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import fs from 'node:fs/promises';
import path from 'node:path';

const fontRegular = await fs.readFile(
  path.resolve('./src/assets/fonts/DejaVuSans-Regular.ttf')
);
const fontBold = await fs.readFile(
  path.resolve('./src/assets/fonts/DejaVuSans-Bold.ttf')
);

interface OgCard {
  title: string;
  eyebrow: string;
}

const SITE_PAGES: Record<string, OgCard> = {
  home: {
    eyebrow: 'Browser extension',
    title: 'Hover-to-zoom for Chrome and Firefox, with zero tracking.',
  },
  pricing: {
    eyebrow: 'Pricing',
    title: 'Free on every site. Pro from $3.99/mo with a 7-day free trial.',
  },
  help: {
    eyebrow: 'Help & docs',
    title: 'Setup, keyboard shortcuts, and supported sites for Ultra Zoom.',
  },
  sites: {
    eyebrow: 'Supported sites',
    title: '70+ image-heavy sites, hover-zoomed out of the box.',
  },
  'whats-new': {
    eyebrow: "What's new",
    title: 'On-device AI upscaling, theater mode, reverse image search, and more.',
  },
  realtors: {
    eyebrow: 'For realtors',
    title: 'Spot deferred maintenance before you book the showing.',
  },
  press: {
    eyebrow: 'Press kit',
    title: 'Launch release, boilerplate, and assets for Ultra Zoom.',
  },
  contact: {
    eyebrow: 'Contact',
    title: 'Get help, report bugs, or request new sites.',
  },
  terms: {
    eyebrow: 'Terms',
    title: 'Terms of use for the Ultra Zoom browser extension.',
  },
  privacy: {
    eyebrow: 'Privacy',
    title: 'Zero telemetry, zero tracking. How Ultra Zoom handles your data.',
  },
  blog: {
    eyebrow: 'Blog',
    title: 'Release notes, tips, and stories from the Ultra Zoom team.',
  },
  'compare-imagus': {
    eyebrow: 'Comparison',
    title: 'Ultra Zoom vs. Imagus — a privacy-first, actively maintained alternative.',
  },
  'compare-hover-zoom-plus': {
    eyebrow: 'Comparison',
    title: 'Ultra Zoom vs. Hover Zoom Plus — a modern, privacy-first alternative.',
  },
};

export async function getStaticPaths() {
  const posts = await getCollection('blog');
  const blogPaths = posts.map(post => ({
    params: { slug: post.id },
    props: {
      card: { eyebrow: post.data.category, title: post.data.title } as OgCard,
    },
  }));
  const sitePaths = Object.entries(SITE_PAGES).map(([slug, card]) => ({
    params: { slug },
    props: { card },
  }));
  return [...blogPaths, ...sitePaths];
}

export async function GET({ props }: APIContext) {
  const { card } = props as { card: OgCard };

  const svg = await satori(
    {
      type: 'div',
      props: {
        style: {
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          width: '1200px',
          height: '630px',
          padding: '72px',
          background: 'linear-gradient(135deg, #0d1117 0%, #161b22 60%, #1f2937 100%)',
          color: '#e6edf3',
          fontFamily: 'DejaVu Sans',
        },
        children: [
          {
            type: 'div',
            props: {
              style: {
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                fontSize: '28px',
                color: '#58a6ff',
                fontWeight: 700,
                letterSpacing: '-0.01em',
              },
              children: [
                {
                  type: 'div',
                  props: {
                    style: {
                      width: '40px',
                      height: '40px',
                      borderRadius: '10px',
                      background: '#58a6ff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#0d1117',
                      fontSize: '26px',
                      fontWeight: 700,
                    },
                    children: 'UZ',
                  },
                },
                'Ultra Zoom',
              ],
            },
          },
          {
            type: 'div',
            props: {
              style: {
                display: 'flex',
                flexDirection: 'column',
                gap: '24px',
              },
              children: [
                {
                  type: 'div',
                  props: {
                    style: {
                      fontSize: '22px',
                      color: '#8b949e',
                      textTransform: 'uppercase',
                      letterSpacing: '0.12em',
                      fontWeight: 700,
                    },
                    children: card.eyebrow,
                  },
                },
                {
                  type: 'div',
                  props: {
                    style: {
                      fontSize: '64px',
                      lineHeight: 1.15,
                      fontWeight: 700,
                      color: '#e6edf3',
                      letterSpacing: '-0.02em',
                    },
                    children: card.title,
                  },
                },
              ],
            },
          },
          {
            type: 'div',
            props: {
              style: {
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                width: '100%',
                fontSize: '24px',
                color: '#8b949e',
                borderTop: '1px solid #30363d',
                paddingTop: '24px',
              },
              children: [
                {
                  type: 'div',
                  props: {
                    style: { display: 'flex', color: '#58a6ff', fontWeight: 700 },
                    children: 'ultrazoom.app',
                  },
                },
                {
                  type: 'div',
                  props: {
                    style: { display: 'flex' },
                    children: 'Hover-to-zoom for Chrome & Firefox',
                  },
                },
              ],
            },
          },
        ],
      },
    },
    {
      width: 1200,
      height: 630,
      fonts: [
        { name: 'DejaVu Sans', data: fontRegular, weight: 400, style: 'normal' },
        { name: 'DejaVu Sans', data: fontBold, weight: 700, style: 'normal' },
      ],
    }
  );

  const png = new Resvg(svg, { fitTo: { mode: 'width', value: 1200 } })
    .render()
    .asPng();

  return new Response(png, {
    headers: { 'Content-Type': 'image/png' },
  });
}
