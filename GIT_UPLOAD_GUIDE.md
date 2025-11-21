# Git 업로드 가이드

## 현재 상태
✅ isms_p.db: 101개 항목 포함 (648KB)
✅ README.md: 프로젝트 설명서
✅ .gitignore: Git 제외 파일 설정

## 로컬 PC에서 실행할 명령어

### 1. 기존 저장소가 있다면
```bash
cd Silas_ISMS-P
git pull origin main  # 또는 master
```

### 2. 파일 확인
```bash
# database 디렉토리에 isms_p.db 파일이 있는지 확인
ls -la database/

# DB 파일 정보 확인
python3 -c "import sqlite3; conn = sqlite3.connect('database/isms_p.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM isms_requirements'); print(f'항목 수: {cursor.fetchone()[0]}개')"
```

### 3. Git 추가 및 커밋
```bash
# 모든 변경사항 추가
git add .

# 커밋 메시지와 함께 커밋
git commit -m "Add ISMS-P database with 101 certification requirements"

# 원격 저장소 설정 (처음 한 번만)
git remote add origin https://github.com/kgg1226/Silas_ISMS-P.git

# 브랜치 설정 (main 또는 master)
git branch -M main

# GitHub에 푸시
git push -u origin main
```

### 4. 이미 원격 저장소가 설정되어 있다면
```bash
git add database/isms_p.db README.md .gitignore
git commit -m "Add ISMS-P database with 101 items"
git push
```

## 확인 방법
```bash
# Git 상태 확인
git status

# 마지막 커밋 확인
git log --oneline -1

# 원격 저장소 확인
git remote -v
```

## GitHub에서 확인
https://github.com/kgg1226/Silas_ISMS-P/tree/main/database

여기서 isms_p.db 파일이 보이면 성공입니다!
