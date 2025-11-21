@echo off
chcp 65001 > nul
REM ISMS-P Git 업로드 자동화 스크립트 (Windows)

echo ================================
echo ISMS-P Git 업로드 시작
echo ================================
echo.

REM Git 사용자 정보 설정 (필요시 주석 해제)
REM git config --global user.name "Your Name"
REM git config --global user.email "your.email@example.com"

REM 현재 상태 확인
echo 📊 Git 상태 확인...
git status
echo.

REM 파일 추가
echo ➕ 파일 추가 중...
git add .
echo.

REM 커밋
echo 💾 커밋 생성 중...
git commit -m "Add ISMS-P database with 101 certification requirements" -m "" -m "- Database: isms_p.db (648KB)" -m "- Total items: 101" -m "- Chapter 1: 관리체계 수립 및 운영 (16개)" -m "- Chapter 2: 보호대책 요구사항 (64개)" -m "- Chapter 3: 개인정보 처리 단계별 요구사항 (21개)"
echo.

REM 원격 저장소 확인
echo 🌐 원격 저장소 확인...
git remote get-url origin > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo ✅ 원격 저장소 이미 설정됨
) else (
    echo ⚙️  원격 저장소 설정 중...
    git remote add origin https://github.com/kgg1226/Silas_ISMS-P.git
    echo ✅ 원격 저장소 설정 완료
)
echo.

REM 브랜치 확인 및 설정
echo 🌿 브랜치 확인...
for /f "tokens=*" %%i in ('git branch --show-current') do set CURRENT_BRANCH=%%i
if not "%CURRENT_BRANCH%"=="main" (
    echo ⚙️  main 브랜치로 변경 중...
    git branch -M main
)
echo.

REM 푸시
echo 🚀 GitHub에 업로드 중...
git push -u origin main
echo.

if %ERRORLEVEL% EQU 0 (
    echo ================================
    echo ✅ 업로드 성공!
    echo ================================
    echo.
    echo 확인: https://github.com/kgg1226/Silas_ISMS-P
) else (
    echo ================================
    echo ❌ 업로드 실패
    echo ================================
    echo.
    echo 수동으로 실행해주세요:
    echo git push -u origin main
)

pause
