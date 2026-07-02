"""HTML rendering helpers for the IT news digest (single-page daily briefing)."""
from html import escape
from urllib.parse import urlparse

PAGE_HEAD = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<link rel="stylesheet" href="{css_path}">
</head>
<body>
<div class="page">
"""

PAGE_TAIL = """</div>
</body>
</html>
"""

WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]


def domain_of(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "") or url
    except Exception:
        return url


def render_masthead(date_obj, css_path, root_path, pdf_filename=None, home_path=None):
    weekday = WEEKDAY_KO[date_obj.weekday()]
    date_label = date_obj.strftime(f"%Y년 %m월 %d일 ({weekday})")
    pdf_link = f' · <a class="pdf-link" href="{escape(pdf_filename)}">PDF 다운로드</a>' if pdf_filename else ""
    home_link = f'<a href="{home_path}">홈</a> · ' if home_path else ""
    return (
        '<header class="masthead">'
        f'<nav class="breadcrumb">{home_link}<a href="{root_path}">전체 아카이브</a>{pdf_link}</nav>'
        '<div class="masthead-kicker">DAILY INTELLIGENCE BRIEFING</div>'
        '<h1 class="masthead-title">AI &amp; ML Weekly Pulse</h1>'
        f'<div class="masthead-date">{escape(date_label)}</div>'
        '<p class="masthead-desc">'
        'Agent · Foundation Model · Deep Learning · 예측/인과추론 · ML Engineering · FDE 영역에서 '
        '오늘 주목해야 할 시그널을 선별하고, 실무 관점의 인사이트를 더했습니다.'
        '</p>'
        '</header>'
    )


def render_toc(topic_results):
    items = []
    for r in topic_results:
        topic = r["topic"]
        count = len(r["articles"])
        items.append(
            f'<li><a href="#{topic["id"]}"><span class="toc-name">{escape(topic["name"])}</span>'
            f'<span class="toc-count">{count}</span></a></li>'
        )
    return (
        '<nav class="toc">'
        '<div class="toc-title">오늘의 목차</div>'
        f'<ul class="toc-list">{"".join(items)}</ul>'
        '</nav>'
    )


def render_article(a, index):
    parts = [f'<article class="article" id="{a.get("anchor", "")}">']
    parts.append('<div class="article-index">' + f'{index:02d}' + '</div>')
    parts.append('<div class="article-body">')
    parts.append(
        f'<h3 class="article-title"><a href="{escape(a["url"])}" target="_blank" rel="noopener">'
        f'{escape(a["title"])}</a></h3>'
    )
    parts.append(f'<div class="article-source">{escape(domain_of(a["url"]))}</div>')
    parts.append(f'<p class="article-summary">{escape(a["summary"])}</p>')

    if a.get("insight"):
        parts.append(
            '<div class="insight-box">'
            '<div class="insight-label">WHY IT MATTERS</div>'
            f'<p class="insight-text">{escape(a["insight"])}</p>'
            '</div>'
        )

    if a.get("related_to"):
        if a.get("related_url"):
            parts.append(
                f'<a class="related-link" href="{escape(a["related_url"])}" target="_blank" rel="noopener">'
                f'↳ 연결된 이전 기사: {escape(a["related_to"])}</a>'
            )
        else:
            parts.append(f'<span class="related-link">↳ 연결된 이전 기사: {escape(a["related_to"])}</span>')

    parts.append('</div>')  # article-body
    parts.append('</article>')
    return "".join(parts)


def render_topic_section(topic, articles):
    parts = [f'<section class="topic-section" id="{topic["id"]}">']
    parts.append('<div class="topic-heading">')
    parts.append(f'<h2 class="topic-title">{escape(topic["name"])}</h2>')
    parts.append(f'<p class="topic-desc">{escape(topic["description"])}</p>')
    parts.append('</div>')

    if not articles:
        parts.append('<div class="empty-state">오늘은 이 주제에서 새로 다룰 만한 주요 뉴스가 없었습니다.</div>')
    else:
        for i, a in enumerate(articles, start=1):
            parts.append(render_article(a, i))

    parts.append('<a class="back-to-top" href="#top">↑ 목차로 돌아가기</a>')
    parts.append('</section>')
    return "".join(parts)


def render_day_page(date_obj, topic_results, css_path="../../../assets/style.css",
                     root_path="../../../archive.html", pdf_filename=None,
                     home_path="../../../index.html"):
    """topic_results: list of dict(topic=topic_def, articles=[...])"""
    date_str = date_obj.strftime("%Y-%m-%d")
    parts = [PAGE_HEAD.format(title=f"AI & ML Weekly Pulse - {date_str}", css_path=css_path)]
    parts.append('<div id="top"></div>')
    parts.append(render_masthead(date_obj, css_path, root_path, pdf_filename, home_path))
    parts.append(render_toc(topic_results))

    for r in topic_results:
        parts.append(render_topic_section(r["topic"], r["articles"]))

    parts.append(
        '<footer class="page-footer">'
        f'<div>AI &amp; ML Weekly Pulse · {escape(date_str)}</div>'
        '<div class="footer-sub">본 브리핑은 공개된 뉴스와 자료를 바탕으로 자동 수집·요약되었습니다.</div>'
        '</footer>'
    )
    parts.append(PAGE_TAIL)
    return "".join(parts)


def latest_entry(tree):
    """tree: dict year -> dict month -> list of (day, html_path, pdf_path|None). Returns
    (year, month, day, html_path, pdf_path) for the most recent entry, or None if empty."""
    if not tree:
        return None
    year = max(tree.keys())
    months = tree[year]
    month = max(months.keys())
    day_num, html_path, pdf_path = max(months[month], key=lambda x: x[0])
    return year, month, day_num, html_path, pdf_path


def render_landing_page(tree, topics):
    """Project-intro landing page: what this is, latest briefing CTA, full archive link."""
    latest = latest_entry(tree)
    parts = [PAGE_HEAD.format(title="AI & ML Weekly Pulse", css_path="assets/style.css")]
    parts.append(
        '<header class="masthead masthead-root">'
        '<div class="masthead-kicker">DAILY INTELLIGENCE BRIEFING</div>'
        '<h1 class="masthead-title">AI &amp; ML Weekly Pulse</h1>'
        '<p class="masthead-desc">'
        'AI Agent, LLM/Foundation Model, Deep Learning, 예측·인과추론, ML Engineering, FDE(Forward '
        'Deployed Engineer) 영역의 주요 뉴스를 매일 자동으로 수집해 컨설팅 리포트 형식으로 정리합니다. '
        '각 기사에는 실무 관점의 인사이트를 함께 담아, 단순 스크랩이 아닌 브리핑으로 소비할 수 있게 만들었습니다.'
        '</p>'
        '</header>'
    )

    if latest:
        year, month, day_num, html_path, pdf_path = latest
        date_label = f"{year}년 {int(month)}월 {day_num}일"
        pdf_cta = f' <a class="pdf-link" href="{pdf_path}">PDF</a>' if pdf_path else ""
        parts.append(
            '<div class="landing-cta">'
            f'<div class="landing-cta-label">최신 브리핑 · {escape(date_label)}</div>'
            f'<a class="landing-cta-button" href="{html_path}">최신 브리핑 보기 →</a>'
            f'<a class="landing-cta-button landing-cta-secondary" href="archive.html">전체 아카이브</a>'
            f'{pdf_cta}'
            '</div>'
        )
    else:
        parts.append('<div class="empty-state">아직 수집된 뉴스가 없습니다.</div>')

    parts.append('<div class="landing-topics">')
    parts.append('<div class="toc-title">다루는 주제</div>')
    parts.append('<ul class="landing-topic-list">')
    for t in topics:
        parts.append(
            f'<li><span class="landing-topic-name">{escape(t["name"])}</span>'
            f'<span class="landing-topic-desc">{escape(t["description"])}</span></li>'
        )
    parts.append('</ul>')
    parts.append('</div>')

    parts.append(
        '<footer class="page-footer">'
        '<div>AI &amp; ML Weekly Pulse</div>'
        '<div class="footer-sub">본 브리핑은 공개된 뉴스와 자료를 바탕으로 자동 수집·요약되었습니다.</div>'
        '</footer>'
    )
    parts.append(PAGE_TAIL)
    return "".join(parts)


def render_root_index(tree):
    """tree: dict year -> dict month -> list of (day, html_path, pdf_path|None)"""
    parts = [PAGE_HEAD.format(title="AI & ML Weekly Pulse - 아카이브", css_path="assets/style.css")]
    parts.append(
        '<header class="masthead masthead-root">'
        '<nav class="breadcrumb"><a href="index.html">홈</a></nav>'
        '<div class="masthead-kicker">ARCHIVE</div>'
        '<h1 class="masthead-title">AI &amp; ML Weekly Pulse</h1>'
        '<p class="masthead-desc">연도 · 월 · 일별로 정리된 AI/ML 산업 인텔리전스 브리핑 아카이브</p>'
        '</header>'
    )

    if not tree:
        parts.append('<div class="empty-state">아직 수집된 뉴스가 없습니다.</div>')
    else:
        for year in sorted(tree.keys(), reverse=True):
            parts.append(f'<div class="tree-year">{escape(year)}년</div>')
            months = tree[year]
            for month in sorted(months.keys(), reverse=True):
                parts.append(f'<div class="tree-month">{int(month)}월</div>')
                parts.append('<ul class="tree-list tree-days">')
                for day_num, html_path, pdf_path in sorted(months[month], key=lambda x: x[0], reverse=True):
                    parts.append(f'<li><a href="{html_path}">{day_num}일 브리핑</a>')
                    if pdf_path:
                        parts.append(f' <a class="pdf-link" href="{pdf_path}">PDF</a>')
                    parts.append('</li>')
                parts.append("</ul>")

    parts.append(PAGE_TAIL)
    return "".join(parts)
