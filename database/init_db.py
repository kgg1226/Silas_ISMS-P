# [여기에 DB 초기화 코드 붙여넣기]
#!/usr/bin/env python3
"""
ISMS-P 데이터베이스 초기화 스크립트
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv('DB_PATH', 'data/isms_p.db')

def init_database():
    """데이터베이스 초기화 및 샘플 데이터 입력"""
    
    # data 디렉토리 생성
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"📁 Initializing database: {DB_PATH}")
    
    # ISMS-P 인증기준 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS isms_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT UNIQUE NOT NULL,
        category TEXT,
        title TEXT NOT NULL,
        description TEXT,
        requirement TEXT,
        control_objective TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 증적 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS evidences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT NOT NULL,
        evidence_type TEXT,
        content TEXT,
        file_path TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_code) REFERENCES isms_requirements(item_code)
    )
    ''')
    
    # 컴플라이언스 체크 로그
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS compliance_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT,
        check_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT,
        notes TEXT
    )
    ''')
    
    # 문서 테이블
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        file_type TEXT,
        category TEXT,
        parsed_at TIMESTAMP,
        data TEXT
    )
    ''')
    
    print("✅ Tables created successfully")
    
    # 샘플 ISMS-P 인증기준 데이터
    sample_requirements = [
        # 1. 관리체계 수립 및 운영
        ('1.1.1', '관리체계 기반 마련', '정책 수립', 
         '정보보호 및 개인정보보호 정책 수립',
         '최고경영자는 조직의 정보보호 및 개인정보보호 활동에 대한 방향을 제시하는 정책을 수립하여야 한다.',
         '정보보호 및 개인정보보호 정책을 수립하고 승인한다'),
        
        ('1.1.2', '관리체계 기반 마련', '범위 설정',
         '관리체계 범위 설정',
         '관리체계의 적용 범위를 명확히 설정하여야 한다.',
         '조직, 자산, 정보시스템 등 관리체계의 범위를 설정한다'),
        
        ('1.2.1', '관리체계 기반 마련', '조직 구성',
         '정보보호 조직 구성',
         '정보보호 및 개인정보보호 책임과 역할을 정의하고 담당 조직을 구성·운영하여야 한다.',
         '정보보호 조직을 구성하고 책임과 역할을 부여한다'),
        
        # 2. 보호대책 요구사항
        ('2.1.1', '정책·조직·자산 관리', '정보자산 식별',
         '정보자산 식별 및 관리',
         '보호대상 정보자산을 식별하고 중요도를 평가하여 관리하여야 한다.',
         '정보자산을 식별하고 중요도를 평가한다'),
        
        ('2.2.1', '인적보안', '주요 직무자 지정',
         '주요 직무자 지정 및 관리',
         '정보보호 및 개인정보보호 관련 주요 직무를 정의하고 담당자를 지정하여야 한다.',
         '주요 직무를 정의하고 담당자를 지정한다'),
        
        ('2.3.1', '외부자 보안', '외부자 계약 시 보안',
         '외부자 보안 계약',
         '외부자가 조직의 정보자산에 접근 시 보안 요구사항을 계약서에 명시하여야 한다.',
         '외부자 계약 시 보안 조항을 포함한다'),
        
        ('2.4.1', '물리보안', '보호구역 지정',
         '물리적 보호구역 지정',
         '중요 정보자산이 위치한 구역을 물리적 보호구역으로 지정하고 통제하여야 한다.',
         '물리적 보호구역을 지정하고 출입을 통제한다'),
        
        ('2.5.1', '인증 및 권한 관리', '사용자 계정 관리',
         '사용자 식별 및 인증',
         '사용자 계정을 발급·변경·삭제하는 절차를 수립·이행하여야 한다.',
         '사용자 계정 관리 절차를 수립하고 이행한다'),
        
        ('2.5.2', '인증 및 권한 관리', '접근권한 관리',
         '접근권한 부여 및 관리',
         '정보자산에 대한 접근권한을 업무 역할에 따라 부여하고 관리하여야 한다.',
         '역할 기반으로 접근권한을 부여하고 관리한다'),
        
        ('2.6.1', '접근통제', '네트워크 접근',
         '네트워크 접근통제',
         '네트워크에 대한 접근을 인가된 사용자 및 시스템만 허용하여야 한다.',
         '네트워크 접근을 통제한다'),
        
        ('2.7.1', '암호화 적용', '암호정책 수립',
         '암호화 정책 및 절차',
         '암호화 적용 대상, 암호 알고리즘, 키 관리 등의 정책을 수립하여야 한다.',
         '암호화 정책을 수립하고 이행한다'),
        
        ('2.8.1', '정보시스템 도입 및 개발 보안', '보안 요구사항 정의',
         '정보시스템 도입·개발 시 보안',
         '정보시스템 도입·개발 시 보안 요구사항을 정의하고 적용하여야 한다.',
         '보안 요구사항을 정의하고 구현한다'),
        
        ('2.9.1', '시스템 및 서비스 운영 관리', '로그 관리',
         '로그 기록 및 보존',
         '정보시스템 사용에 대한 로그를 기록하고 안전하게 보존하여야 한다.',
         '로그를 기록하고 정기적으로 검토한다'),
        
        ('2.9.2', '시스템 및 서비스 운영 관리', '로그 점검',
         '로그 정기 검토',
         '정보시스템 로그를 정기적으로 검토하여 이상행위를 탐지하여야 한다.',
         '로그를 분석하여 이상행위를 탐지한다'),
        
        ('2.10.1', '시스템 및 서비스 보안 관리', '악성코드 통제',
         '악성코드 관리',
         '악성코드 감염을 예방하고 탐지·치료·복구 절차를 수립·이행하여야 한다.',
         '악성코드 대응 체계를 구축하고 운영한다'),
        
        ('2.11.1', '사고 예방 및 대응', '사고 대응 절차',
         '침해사고 대응',
         '침해사고 탐지·대응·복구를 위한 절차를 수립·이행하여야 한다.',
         '침해사고 대응 절차를 수립하고 훈련한다'),
        
        ('2.12.1', '재해 복구', '백업 및 복구',
         '백업 관리',
         '중요 정보자산에 대한 백업 및 복구 절차를 수립·이행하여야 한다.',
         '정기적으로 백업하고 복구 테스트를 수행한다'),
        
        # 3. 개인정보 처리단계별 요구사항
        ('3.1.1', '개인정보 수집 시 보호조치', '수집 제한',
         '개인정보 최소 수집',
         '개인정보는 서비스 제공에 필요한 최소한으로 수집하여야 한다.',
         '필요 최소한의 개인정보만 수집한다'),
        
        ('3.1.2', '개인정보 수집 시 보호조치', '동의 획득',
         '정보주체 동의',
         '개인정보 수집 시 정보주체의 동의를 받아야 한다.',
         '개인정보 수집 시 동의를 받는다'),
        
        ('3.2.1', '개인정보 보관 및 이용 시 보호조치', '접근권한 제한',
         '개인정보 접근 제한',
         '개인정보에 대한 접근권한을 업무 목적에 따라 최소한으로 제한하여야 한다.',
         '개인정보 접근을 최소한으로 제한한다'),
        
        ('3.2.2', '개인정보 보관 및 이용 시 보호조치', '암호화',
         '개인정보 암호화',
         '개인정보를 안전하게 저장·전송하기 위해 암호화하여야 한다.',
         '개인정보를 암호화하여 저장하고 전송한다'),
        
        ('3.3.1', '개인정보 제공 시 보호조치', '제공 관리',
         '개인정보 제3자 제공',
         '개인정보를 제3자에게 제공 시 법적 근거를 확보하고 정보주체에게 고지하여야 한다.',
         '제3자 제공 시 법적 절차를 준수한다'),
        
        ('3.4.1', '개인정보 파기 시 보호조치', '파기 절차',
         '개인정보 안전한 파기',
         '보유기간이 경과하거나 처리 목적이 달성된 개인정보는 안전하게 파기하여야 한다.',
         '개인정보를 복구 불가능하게 파기한다'),
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO isms_requirements 
        (item_code, category, title, description, requirement, control_objective)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', sample_requirements)
    
    conn.commit()
    
    # 입력된 데이터 확인
    cursor.execute('SELECT COUNT(*) FROM isms_requirements')
    count = cursor.fetchone()[0]
    
    print(f"✅ Inserted {count} ISMS-P requirements")
    
    # 샘플 데이터 출력
    cursor.execute('SELECT item_code, title FROM isms_requirements ORDER BY item_code LIMIT 5')
    print("\n📋 Sample data:")
    for row in cursor.fetchall():
        print(f"  - {row[0]}: {row[1]}")
    
    conn.close()
    print(f"\n✅ Database initialization complete!")
    print(f"📍 Database location: {os.path.abspath(DB_PATH)}")

if __name__ == "__main__":
    init_database()