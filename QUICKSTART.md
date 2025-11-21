# 🚀 ISMS-P Git 업로드 퀵 스타트

## ✅ 현재 상태
- **DB 파일**: isms_p.db (648KB)
- **총 항목**: 101개 (완료)
- **데이터**: 전체 ISMS-P 인증기준 포함

## 📦 방법 1: 자동 업로드 (추천)

### Windows
```cmd
upload.bat
```

### Mac/Linux
```bash
chmod +x upload.sh
./upload.sh
```

## 🔧 방법 2: 수동 업로드

```bash
# 1. DB 검증 (선택사항)
python3 verify_db.py

# 2. Git 명령어
git add .
git commit -m "Add ISMS-P database with 101 items"
git push -u origin main
```

## 📋 업로드 전 체크리스트

- [ ] database/isms_p.db 파일 존재 확인
- [ ] Git 사용자 정보 설정 확인
- [ ] GitHub 저장소 접근 권한 확인
- [ ] (선택) verify_db.py로 DB 검증

## 🔍 Git 사용자 정보 설정

처음 사용하는 경우:
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## 📂 업로드 후 확인

GitHub에서 확인:
https://github.com/kgg1226/Silas_ISMS-P

파일 구조:
```
Silas_ISMS-P/
├── database/
│   └── isms_p.db          ← 여기 확인!
├── README.md
├── .gitignore
└── [기타 파일들]
```

## ❓ 문제 해결

### "fatal: unable to access" 오류
- GitHub 로그인 확인
- Personal Access Token 사용 (Settings > Developer settings)

### "remote origin already exists" 오류
```bash
git remote remove origin
git remote add origin https://github.com/kgg1226/Silas_ISMS-P.git
```

### 브랜치 이름이 master인 경우
```bash
git branch -M main
git push -u origin main
```

## 📞 추가 도움이 필요하면

GIT_UPLOAD_GUIDE.md 파일을 참조하세요!
