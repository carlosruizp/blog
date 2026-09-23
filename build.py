#!/usr/bin/env python3
"""Static site generator for a 2000s-style blog. Stdlib only, no dependencies.

Usage:
    python3 build.py

Reads Markdown posts from content/posts/*.md, writes static HTML into docs/
(GitHub Pages serves straight from that folder on the main branch).
"""
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from email.utils import format_datetime
from xml.sax.saxutils import escape as xml_escape

ROOT_DIR = Path(__file__).parent
CONTENT_DIR = ROOT_DIR / "content"
POSTS_DIR = CONTENT_DIR / "posts"
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"
OUT_DIR = ROOT_DIR / "docs"

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


# ---------- tiny markdown subset -> html ----------

def render_inline(text):
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img alt="\1" src="\2">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def markdown_to_html(md_text):
    lines = md_text.strip("\n").split("\n")
    html_parts = []
    i = 0
    para_buf = []
    list_buf = []

    def flush_para():
        if para_buf:
            html_parts.append("<p>" + render_inline(" ".join(para_buf)) + "</p>")
            para_buf.clear()

    def flush_list():
        if list_buf:
            items = "".join(f"<li>{render_inline(t)}</li>" for t in list_buf)
            html_parts.append(f"<ul>{items}</ul>")
            list_buf.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            flush_list()
            i += 1
            continue

        heading = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if heading:
            flush_para()
            flush_list()
            level = len(heading.group(1)) + 1  # start headings at h2 (h1 is post title)
            level = min(level, 4)
            html_parts.append(f"<h{level}>{render_inline(heading.group(2))}</h{level}>")
            i += 1
            continue

        if stripped.startswith(">"):
            flush_para()
            flush_list()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            html_parts.append("<blockquote><p>" + render_inline(" ".join(quote_lines)) + "</p></blockquote>")
            continue

        if stripped.startswith("- "):
            flush_para()
            list_buf.append(stripped[2:])
            i += 1
            continue

        para_buf.append(stripped)
        i += 1

    flush_para()
    flush_list()
    return "\n".join(html_parts)


# ---------- front matter ----------

def parse_post(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError(f"{path} is missing --- front matter ---")
    front_raw, body_md = m.group(1), m.group(2)

    meta = {}
    for line in front_raw.strip().split("\n"):
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')

    required = {"title", "date"}
    missing = required - meta.keys()
    if missing:
        raise ValueError(f"{path} missing front matter fields: {missing}")

    date = datetime.strptime(meta["date"], "%Y-%m-%d")
    slug = meta.get("slug") or slugify(meta["title"])

    return {
        "title": meta["title"],
        "date": date,
        "slug": slug,
        "tags": [t.strip() for t in meta.get("tags", "").split(",") if t.strip()],
        "body_html": markdown_to_html(body_md),
        "url": f"posts/{date.year}/{date.month:02d}/{slug}.html",
    }


def slugify(title):
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s.strip("-")


# ---------- templating ----------

def render_base(*, root, page_title, content_html, site, archive_list_html):
    tpl = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
    return (tpl
            .replace("{{ROOT}}", root)
            .replace("{{PAGE_TITLE}}", page_title)
            .replace("{{SITE_TITLE}}", site["title"])
            .replace("{{SITE_TAGLINE}}", site["tagline"])
            .replace("{{ABOUT_BLURB}}", site["about_blurb"])
            .replace("{{CONTENT}}", content_html)
            .replace("{{ARCHIVE_LIST}}", archive_list_html)
            .replace("{{YEAR}}", str(datetime.now().year)))


def render_post_block(post, root, full=True):
    date_str = post["date"].strftime("%A, %d %B %Y")
    body = post["body_html"] if full else post["body_html"]
    title_html = (f'<h2><a href="{root}{post["url"]}">{post["title"]}</a></h2>'
                  if not full else f'<h2>{post["title"]}</h2>')
    tags = ""
    if post["tags"]:
        tags = " &middot; " + ", ".join(post["tags"])
    return f"""
      <div class="post">
        {title_html}
        <div class="byline">posted {date_str}{tags}</div>
        <div class="post-body">
{body}
        </div>
      </div>
"""


def build_archive_list_html(posts, root):
    by_year = {}
    for p in posts:
        by_year.setdefault(p["date"].year, []).append(p)
    parts = []
    for year in sorted(by_year, reverse=True):
        parts.append(f'<li class="archive-year">{year}</li>')
        for p in by_year[year]:
            label = f'{MONTH_NAMES[p["date"].month]} {p["date"].day} &ndash; {p["title"]}'
            parts.append(f'<li><a href="{root}{p["url"]}">{label}</a></li>')
    return "\n".join(parts)


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_rss(posts, site):
    items = []
    for p in posts[:20]:
        link = f'{site["base_url"]}/{p["url"]}'
        items.append(f"""
    <item>
      <title>{xml_escape(p["title"])}</title>
      <link>{link}</link>
      <guid>{link}</guid>
      <pubDate>{format_datetime(p["date"])}</pubDate>
      <description>{xml_escape(p["body_html"])}</description>
    </item>""")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{xml_escape(site["title"])}</title>
    <link>{site["base_url"]}/</link>
    <description>{xml_escape(site["tagline"])}</description>
{''.join(items)}
  </channel>
</rss>
"""


def main():
    site = json.loads((CONTENT_DIR / "config.json").read_text(encoding="utf-8"))

    posts = [parse_post(p) for p in sorted(POSTS_DIR.glob("*.md"))]
    posts.sort(key=lambda p: p["date"], reverse=True)

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    shutil.copytree(STATIC_DIR, OUT_DIR / "static")

    archive_html_root = build_archive_list_html(posts, root="")
    archive_html_deep = build_archive_list_html(posts, root="../../../")

    # index.html — full posts, newest first
    index_content = "".join(render_post_block(p, root="") for p in posts) or "<p>No posts yet.</p>"
    write(OUT_DIR / "index.html", render_base(
        root="", page_title=site["title"], content_html=index_content,
        site=site, archive_list_html=archive_html_root))

    # individual post pages
    for p in posts:
        content = render_post_block(p, root="../../../", full=True)
        write(OUT_DIR / p["url"], render_base(
            root="../../../", page_title=f'{p["title"]} — {site["title"]}',
            content_html=content, site=site, archive_list_html=archive_html_deep))

    # archive.html — links only
    archive_body = "<h2>Archive</h2><ul class=\"module\">" + build_archive_list_html(posts, root="") + "</ul>"
    write(OUT_DIR / "archive.html", render_base(
        root="", page_title=f'Archive — {site["title"]}', content_html=archive_body,
        site=site, archive_list_html=archive_html_root))

    # about.html
    about_path = CONTENT_DIR / "about.md"
    about_html = markdown_to_html(about_path.read_text(encoding="utf-8")) if about_path.exists() else f"<p>{site['about_blurb']}</p>"
    write(OUT_DIR / "about.html", render_base(
        root="", page_title=f'About — {site["title"]}', content_html=f"<h2>About</h2>{about_html}",
        site=site, archive_list_html=archive_html_root))

    # feed.xml
    write(OUT_DIR / "feed.xml", build_rss(posts, site))

    # allow a custom domain via CNAME (only written if configured)
    if site.get("cname"):
        write(OUT_DIR / "CNAME", site["cname"] + "\n")

    print(f"Built {len(posts)} post(s) -> {OUT_DIR}")


if __name__ == "__main__":
    main()
