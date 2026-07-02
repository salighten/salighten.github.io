#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="$SCRIPT_DIR/last_run.log"

if OUTPUT="$(python3 collect_news.py 2>&1 | tee "$LOG_FILE")"; then
    DAY_INDEX="$(echo "$OUTPUT" | tail -1)"
    if [ -f "$DAY_INDEX" ]; then
        open "$DAY_INDEX"
        osascript -e 'display notification "오늘의 IT 뉴스 정리가 완료되었습니다." with title "IT 뉴스 수집"' || true
    else
        osascript -e 'display notification "수집은 끝났지만 결과 파일을 찾지 못했습니다. last_run.log를 확인하세요." with title "IT 뉴스 수집"' || true
    fi
else
    osascript -e 'display notification "IT 뉴스 수집 중 오류가 발생했습니다. last_run.log를 확인하세요." with title "IT 뉴스 수집 실패"' || true
    exit 1
fi
