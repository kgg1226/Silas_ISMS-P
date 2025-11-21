#!/bin/bash
# ISMS-P Git 업로드 자동화 스크립트

echo "================================"
echo "ISMS-P Git 업로드 시작"
echo "================================"
echo ""

# Git 사용자 정보 설정 (필요시 수정)
# git config --global user.name "Your Name"
# git config --global user.email "your.email@example.com"

# 현재 상태 확인
echo "📊 Git 상태 확인..."
git status
echo ""

# 파일 추가
echo "➕ 파일 추가 중..."
git add .
echo ""

# 커밋
echo "💾 커밋 생성 중..."
git commit -m "Add ISMS-P database with 101 certification requirements

- Database: isms_p.db (648KB)
- Total items: 101
- Chapter 1: 관리체계 수립 및 운영 (16개)
- Chapter 2: 보호대책 요구사항 (64개)
- Chapter 3: 개인정보 처리 단계별 요구사항 (21개)
"
echo ""

# 원격 저장소 확인
echo "🌐 원격 저장소 확인..."
if git remote get-url origin > /dev/null 2>&1; then
    echo "✅ 원격 저장소 이미 설정됨"
else
    echo "⚙️  원격 저장소 설정 중..."
    git remote add origin https://github.com/kgg1226/Silas_ISMS-P.git
    echo "✅ 원격 저장소 설정 완료"
fi
echo ""

# 브랜치 확인 및 설정
echo "🌿 브랜치 확인..."
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo "⚙️  main 브랜치로 변경 중..."
    git branch -M main
fi
echo ""

# 푸시
echo "🚀 GitHub에 업로드 중..."
git push -u origin main
echo ""

if [ $? -eq 0 ]; then
    echo "================================"
    echo "✅ 업로드 성공!"
    echo "================================"
    echo ""
    echo "확인: https://github.com/kgg1226/Silas_ISMS-P"
else
    echo "================================"
    echo "❌ 업로드 실패"
    echo "================================"
    echo ""
    echo "수동으로 실행해주세요:"
    echo "git push -u origin main"
fi
