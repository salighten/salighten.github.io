"""Convert a rendered daily briefing HTML file into a link-preserving PDF.

Uses Google Chrome / Chromium-family headless mode (--print-to-pdf), which
renders the actual HTML/CSS and keeps hyperlinks clickable in the resulting
PDF. Operates on the already-rendered HTML file via a file:// URL, so
relative asset paths (assets/style.css) resolve exactly as they do when a
person opens the file in a browser.

Requires a Chromium-family browser (Chrome, Chromium, Edge, or Brave) to be
installed. If none is found, conversion is skipped with a clear message
rather than silently producing a broken PDF via an unreliable UI-automation
fallback.
"""
import shutil
import subprocess
import sys
from pathlib import Path

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
]


def find_chrome_binary():
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    for name in ("chromium", "google-chrome", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def html_to_pdf_via_chrome(chrome_bin, html_path: Path, pdf_path: Path) -> bool:
    file_url = html_path.resolve().as_uri()
    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--print-to-pdf-no-header",
        f"--print-to-pdf={pdf_path}",
        file_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"Chrome PDF 변환 실패: {result.stderr[:500]}", file=sys.stderr)
        return False
    return pdf_path.exists() and pdf_path.stat().st_size > 0


def convert(html_path: Path, pdf_path: Path) -> bool:
    chrome_bin = find_chrome_binary()
    if not chrome_bin:
        print(
            "PDF 변환 건너뜀: Chrome/Chromium/Edge/Brave 중 설치된 브라우저를 찾지 못했습니다. "
            "PDF가 필요하면 Google Chrome을 설치해주세요.",
            file=sys.stderr,
        )
        return False
    return html_to_pdf_via_chrome(chrome_bin, html_path, pdf_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: make_pdf.py <input.html> <output.pdf>", file=sys.stderr)
        sys.exit(2)
    ok = convert(Path(sys.argv[1]), Path(sys.argv[2]))
    sys.exit(0 if ok else 1)
