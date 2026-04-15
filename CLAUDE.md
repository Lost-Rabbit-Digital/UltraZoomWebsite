# CLAUDE.md — Ultra Zoom Website

## Project Overview

Marketing and documentation website for the Ultra Zoom browser extension. Pure static HTML/CSS site deployed to GitHub Pages.

**URL:** https://ultrazoom.app (GitHub Pages)
**Publisher:** Lost Rabbit Digital LLC

## Architecture

```
*.html             Static pages (index, help, blog, contact, privacy, terms)
styles.css         Central stylesheet (dark theme, responsive)
images/            Icons and assets (icon-48.png, icon-128.png)
.github/
  workflows/
    static.yml     Validate -> Build -> Lighthouse -> Deploy pipeline
    record-scroll.yml  Promotional video recording (Playwright)
  lighthouse/
    lighthouserc.json  Lighthouse CI config
  scripts/           Automation scripts
diagrams/          Mermaid diagram source files
```

## Technology Stack

- **Pure HTML/CSS** — no JavaScript framework, no SSG
- **Dark theme** — GitHub-inspired color scheme (`#0d1117` background, `#58a6ff` brand blue)
- **Build tools:** html-validate, clean-css-cli, html-minifier-terser, optipng
- **Hosting:** GitHub Pages (deployed from `_site/` directory)
- **Node.js 24** in CI

## Pages

| Page | File | Purpose |
|------|------|---------|
| Home | `index.html` | Landing page with install buttons, features, pricing |
| Help | `help.html` | Setup guide, keyboard shortcuts, supported sites |
| Blog | `blog.html` | Blog post listings |
| Contact | `contact.html` | Contact form |
| Privacy | `privacy.html` | Privacy policy |
| Terms | `terms.html` | Terms of use |

## CI/CD Pipeline (static.yml)

1. **Validate** — HTML validation (`html-validate`) + link checking (`lychee`)
2. **Build** — Minify CSS (`clean-css`), minify HTML (`html-minifier-terser`), optimize PNGs (`optipng`), output to `_site/`
3. **Lighthouse** — Performance, accessibility, SEO audit with summary
4. **Deploy** — Push `_site/` to GitHub Pages (main branch only, not on PRs)

## Development

No install step needed for basic editing — just edit HTML/CSS files directly.

To run validation locally:
```bash
npx html-validate *.html
```

To build locally:
```bash
npm install --no-save clean-css-cli html-minifier-terser
mkdir -p _site/images
npx cleancss -o _site/styles.css styles.css
for file in *.html; do
  npx html-minifier-terser --collapse-whitespace --remove-comments -o "_site/$file" "$file"
done
cp images/* _site/images/
```

## Design Tokens

```css
--bg-primary:    #0d1117
--bg-secondary:  #161b22
--brand:         #58a6ff
--text-primary:  #e6edf3
--text-secondary:#8b949e
--border:        #30363d
--success:       #3fb950
--error:         #f85149
```

## Conventions

- All styling in `styles.css` — no inline styles, no CSS modules
- Semantic HTML with accessibility focus (skip links, ARIA labels, focus indicators)
- No JavaScript on pages — pure CSS interactions
- Images optimized as PNG via optipng in build pipeline
- `.gitignore` excludes `node_modules/` and `_site/`
