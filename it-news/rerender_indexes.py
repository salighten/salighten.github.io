#!/usr/bin/env python3
"""Regenerate archive.html and the landing index.html from files already on
disk, without re-running WebSearch collection. Also patches the breadcrumb
of existing day pages that still point at the old index.html-as-archive URL.
"""
import re
from pathlib import Path

import render
from collect_news import BASE_DIR, TOPICS_PATH, load_json, scan_archive_tree

OLD_BREADCRUMB = re.compile(
    r'<nav class="breadcrumb"><a href="([./]*)index\.html">전체 아카이브</a>'
)


def patch_day_page(path: Path):
    text = path.read_text(encoding="utf-8")
    m = OLD_BREADCRUMB.search(text)
    if not m:
        return False
    prefix = m.group(1)
    new_nav = (
        f'<nav class="breadcrumb"><a href="{prefix}index.html">홈</a> · '
        f'<a href="{prefix}archive.html">전체 아카이브</a>'
    )
    text = OLD_BREADCRUMB.sub(new_nav, text, count=1)
    path.write_text(text, encoding="utf-8")
    return True


def main():
    topics = load_json(TOPICS_PATH, [])

    patched = []
    news_dir = BASE_DIR / "news"
    if news_dir.exists():
        for html_path in news_dir.glob("*/*/*.html"):
            if patch_day_page(html_path):
                patched.append(html_path.relative_to(BASE_DIR).as_posix())

    tree = scan_archive_tree()
    archive_html = render.render_root_index(tree)
    (BASE_DIR / "archive.html").write_text(archive_html, encoding="utf-8")

    landing_html = render.render_landing_page(tree, topics)
    (BASE_DIR / "index.html").write_text(landing_html, encoding="utf-8")

    print("patched day pages:", patched or "(none)")
    print("wrote archive.html and index.html")


if __name__ == "__main__":
    main()
