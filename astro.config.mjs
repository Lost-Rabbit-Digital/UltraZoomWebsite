import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://ultrazoom.app',
  build: {
    format: 'file',
  },
  trailingSlash: 'never',
  integrations: [
    sitemap({
      filter: page => !page.includes('/success'),
    }),
  ],
});
