#!/usr/bin/env python3
"""Daily IT news collector.

Runs `claude -p` per topic with WebSearch enabled, asks for up to 3 fresh,
non-duplicate articles with an analyst-style insight, and renders a single
consulting-newsletter-style daily briefing page plus a root archive index.
"""
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import make_pdf
import render

BASE_DIR = Path(__file__).resolve().parent
TOPICS_PATH = BASE_DIR / "topics.json"
HISTORY_PATH = BASE_DIR / "history.json"
NEWS_DIR = BASE_DIR / "news"

HISTORY_RETENTION_DAYS = 14
MAX_RETRIES = 2
MAX_PARALLEL_TOPICS = 4  # concurrent `claude -p` calls; keep below API rate limits

ARTICLE_SCHEMA = {
    "type": "object",
    "properties": {
        "articles": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "summary": {"type": "string"},
                    "insight": {"type": "string"},
                    "related_to": {"type": ["string", "null"]},
                },
                "required": ["title", "url", "summary", "insight", "related_to"],
            },
        }
    },
    "required": ["articles"],
}


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_prompt(topic, recent_titles):
    recent_block = ""
    if recent_titles:
        bullet_list = "\n".join(f"- {t}" for t in recent_titles)
        recent_block = (
            f"\n\n최근 14일간 이미 다룬 이 주제의 기사 제목 목록 (아래와 중복되는 뉴스는 절대 선택하지 마라):\n"
            f"{bullet_list}\n"
        )

    return (
        f"당신은 전문 컨설팅펌 소속의 시니어 테크 애널리스트입니다. 아래 주제에 대해 웹 검색으로 "
        f"오늘 기준 가장 중요하고 최신인 뉴스를 조사해 클라이언트용 브리핑 자료를 작성하세요.\n\n"
        f"주제: {topic['name']}\n"
        f"설명: {topic['description']}\n"
        f"검색 힌트: {topic['query_hint']}\n"
        f"{recent_block}\n"
        f"지시사항:\n"
        f"1. 위 '최근 다룬 기사 목록'과 겹치지 않는, 주요하고 신뢰할 수 있는 뉴스를 최대 3개까지 선정하라. "
        f"정말 중요한 뉴스가 없으면 그보다 적은 개수(0개 포함)를 반환해도 된다.\n"
        f"2. 만약 선정한 기사가 최근 목록의 특정 기사와 이어지는 후속 소식이면, related_to 필드에 "
        f"그 과거 기사의 정확한 제목 문자열을 넣어라. 관련이 없으면 null로 두어라.\n"
        f"3. summary는 한국어로 5~6문장, 핵심 사실관계(누가, 무엇을, 왜 지금)를 구체적 수치·인용과 "
        f"함께 상세히 작성하라.\n"
        f"4. insight 필드에는 '왜 이 뉴스가 중요한가'를 컨설턴트 관점에서 2~3문장으로 작성하라 — "
        f"산업/기업/실무자에게 미치는 영향, 향후 전망, 경쟁 구도 변화 등을 담아라. 단순 요약 반복 금지.\n"
        f"5. url은 실제 접근 가능한 원문 기사 링크를 넣어라.\n"
        f"6. 결과는 오직 지정된 JSON 스키마 형식으로만 응답하라."
    )


def call_claude(prompt):
    cmd = [
        "claude", "-p", prompt,
        "--allowedTools", "WebSearch",
        "--output-format", "json",
        "--json-schema", json.dumps(ARTICLE_SCHEMA),
        "--no-session-persistence",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"claude exited {result.returncode}: {result.stderr[:500]}")

    outer = json.loads(result.stdout)
    # --output-format json wraps the final assistant text in a "result" field.
    text = outer.get("result", "")
    if isinstance(text, dict):
        return text
    return json.loads(text)


def fetch_articles_for_topic(topic, recent_titles):
    prompt = build_prompt(topic, recent_titles)
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = call_claude(prompt)
            return data.get("articles", [])
        except Exception as e:
            last_err = e
            print(f"  [{topic['id']}] attempt {attempt} failed: {e}", file=sys.stderr)
    print(f"  [{topic['id']}] giving up after {MAX_RETRIES} attempts: {last_err}", file=sys.stderr)
    return None  # signals failure, distinct from an empty list


def prune_history(history, today):
    cutoff = today - timedelta(days=HISTORY_RETENTION_DAYS)
    cutoff_str = cutoff.strftime("%Y-%m-%d")
    history["articles"] = [a for a in history["articles"] if a["date"] >= cutoff_str]


def recent_titles_for_topic(history, topic_id):
    return [a["title"] for a in history["articles"] if a["topic"] == topic_id]


def find_related_url(history, topic_id, related_title):
    if not related_title:
        return None
    for a in reversed(history["articles"]):
        if a["topic"] == topic_id and a["title"] == related_title:
            return a["url"]
    return None


def scan_archive_tree():
    tree = {}
    if not NEWS_DIR.exists():
        return tree
    for year_dir in sorted(NEWS_DIR.iterdir()):
        if not year_dir.is_dir():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            for day_html in sorted(month_dir.glob("*.html")):
                rel_html = day_html.relative_to(BASE_DIR).as_posix()
                day_num = int(day_html.stem)
                day_pdf = day_html.with_suffix(".pdf")
                rel_pdf = day_pdf.relative_to(BASE_DIR).as_posix() if day_pdf.exists() else None
                tree.setdefault(year_dir.name, {}).setdefault(month_dir.name, []).append(
                    (day_num, rel_html, rel_pdf)
                )
    return tree


def main():
    topics = load_json(TOPICS_PATH, [])
    if not topics:
        print("topics.json이 비어 있거나 없습니다.", file=sys.stderr)
        sys.exit(1)

    history = load_json(HISTORY_PATH, {"articles": []})

    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")
    year, month, day = today.strftime("%Y"), today.strftime("%m"), today.strftime("%d")

    month_dir = NEWS_DIR / year / month
    month_dir.mkdir(parents=True, exist_ok=True)
    day_file = month_dir / f"{day}.html"

    print(f"=== {date_str} IT 뉴스 수집 시작 ({len(topics)}개 주제, 최대 {MAX_PARALLEL_TOPICS}개 동시 실행) ===")

    # Snapshot recent titles before firing off parallel calls; history is only
    # mutated back on the main thread once each future resolves.
    recent_by_topic = {t["id"]: recent_titles_for_topic(history, t["id"]) for t in topics}
    articles_by_topic_id = {}

    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_TOPICS) as pool:
        future_to_topic = {
            pool.submit(fetch_articles_for_topic, topic, recent_by_topic[topic["id"]]): topic
            for topic in topics
        }
        for future in as_completed(future_to_topic):
            topic = future_to_topic[future]
            articles = future.result()
            status_note = " (수집 실패 - 건너뜀)" if articles is None else f" ({len(articles)}건)"
            print(f"[{topic['id']}] 완료{status_note}")
            articles_by_topic_id[topic["id"]] = articles if articles is not None else []

    topic_results = []
    for topic in topics:
        articles = articles_by_topic_id[topic["id"]]
        enriched = []
        for i, a in enumerate(articles, start=1):
            related_url = find_related_url(history, topic["id"], a.get("related_to"))
            enriched.append({**a, "related_url": related_url, "anchor": f"{topic['id']}-{i}"})
            history["articles"].append({
                "title": a["title"],
                "url": a["url"],
                "topic": topic["id"],
                "date": date_str,
            })

        topic_results.append({"topic": topic, "articles": enriched})

    prune_history(history, today)
    save_json(HISTORY_PATH, history)

    pdf_file = day_file.with_suffix(".pdf")

    # Render once without the PDF link to produce the source HTML for Chrome
    # to print, then re-render with the link once we know conversion succeeded.
    day_page_html = render.render_day_page(today, topic_results)
    day_file.write_text(day_page_html, encoding="utf-8")

    if make_pdf.convert(day_file, pdf_file):
        print(f"PDF 생성 완료: {pdf_file}")
        day_page_html = render.render_day_page(today, topic_results, pdf_filename=pdf_file.name)
        day_file.write_text(day_page_html, encoding="utf-8")
    else:
        print("PDF 생성을 건너뛰었습니다 (HTML은 정상 생성됨).", file=sys.stderr)

    tree = scan_archive_tree()
    archive_html = render.render_root_index(tree)
    (BASE_DIR / "archive.html").write_text(archive_html, encoding="utf-8")

    landing_html = render.render_landing_page(tree, topics)
    (BASE_DIR / "index.html").write_text(landing_html, encoding="utf-8")

    print(f"=== 완료: {day_file} ===")
    print(str(day_file))


if __name__ == "__main__":
    main()
