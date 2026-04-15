# Ultra Zoom Website

Marketing and documentation website for the [Ultra Zoom](https://github.com/lost-rabbit-digital/ultrazoom) browser extension.

## Pages

- **Home** — Landing page with install links, feature overview, and pricing
- **Help** — Setup guide, keyboard shortcuts, and supported sites
- **Blog** — News and updates
- **Contact** — Contact form
- **Privacy** — Privacy policy
- **Terms** — Terms of use

## Development

Edit HTML and CSS files directly — no framework or build step needed for local development.

### Validate locally

```bash
npx html-validate *.html
```

### Build for production

```bash
npm install --no-save clean-css-cli html-minifier-terser
mkdir -p _site/images
npx cleancss -o _site/styles.css styles.css
for file in *.html; do
  npx html-minifier-terser --collapse-whitespace --remove-comments -o "_site/$file" "$file"
done
cp images/* _site/images/
```

## CI/CD

Pushes to `main` trigger the full pipeline:

1. **Validate** — HTML validation + link checking
2. **Build** — Minify HTML/CSS, optimize images
3. **Lighthouse** — Performance and accessibility audit
4. **Deploy** — Publish to GitHub Pages

## License

Copyright 2025 Lost Rabbit Digital LLC. All rights reserved.
