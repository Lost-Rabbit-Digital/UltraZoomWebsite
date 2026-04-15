import { defineConfig } from 'astro/config';

export default defineConfig({
  site: 'https://ultrazoom.app',
  build: {
    format: 'file',
  },
  trailingSlash: 'never',
});
