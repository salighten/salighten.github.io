display notification "IT 뉴스 수집을 시작합니다..." with title "IT 뉴스 수집"

set scriptDir to "/Users/hanaha/document/workspace/study/it-news"

try
	do shell script "cd " & quoted form of scriptDir & " && ./run.sh"
on error errMsg
	display notification "실행 스크립트 호출 중 오류: " & errMsg with title "IT 뉴스 수집 실패"
end try
