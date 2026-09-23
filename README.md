# blog

A static blog with a deliberately 2000s look (small serif type, classic
link colors, two-column layout with a blogroll sidebar, dashed rules
between posts) — no JS framework, no build step beyond one Python script.

## Writing a post

Create `content/posts/YYYY-MM-DD-your-slug.md`:

```markdown
---
title: Your Post Title
date: 2026-09-23
tags: some, tags
---

Body text goes here, in Markdown (paragraphs, **bold**, *italic*,
`code`, [links](https://example.com), `> block quotes`, and `- ` lists).
```

Then rebuild:

```bash
python3 build.py
```

This regenerates everything in `docs/`, which is what GitHub Pages serves.

## Site settings

- `content/config.json` — site title, tagline, about blurb, base URL, optional custom domain (`cname`)
- `content/about.md` — the About page body
- `templates/base.html` — sidebar blogroll links, page chrome
- `static/style.css` — the look

## Previewing locally

```bash
python3 build.py
cd docs && python3 -m http.server 8765
```

Then open http://localhost:8765/

## Deploying to GitHub Pages

1. Push this repo to GitHub (public or private, Pages works with either on a paid/free plan as applicable).
2. In the repo's Settings -> Pages, set "Build and deployment" source to
   "Deploy from a branch", branch `main`, folder `/docs`.
3. Update `base_url` in `content/config.json` to the resulting Pages URL
   (or your custom domain, if you set `cname`), rebuild, commit, push.

Every time you add or edit a post: `python3 build.py`, then commit and
push both the `content/` source and the regenerated `docs/` output.
