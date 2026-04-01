#!/usr/bin/env python3
"""
ISMS-P 데이터베이스 검증 스크립트
DB 파일이 올바르게 구성되었는지 확인합니다.
"""

import os
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(os.getenv("ISMS_DB_PATH", os.getenv("DB_PATH", "data/isms_p.db")))


def verify_database(db_path: Path = DB_PATH) -> bool:
    """데이터베이스 검증"""

    print("=" * 60)
    print("ISMS-P 데이터베이스 검증")
    print("=" * 60)
    print()

    if not db_path.exists():
        print(f"❌ 오류: {db_path} 파일을 찾을 수 없습니다.")
        return False

    print(f"✅ DB 파일 발견: {db_path}")
    print(f"   크기: {db_path.stat().st_size / 1024:.1f} KB")
    print()

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 테이블 존재 확인
        print("📋 테이블 확인:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        required_tables = ["isms_requirements", "evidences", "evidence_logs"]
        for table in required_tables:
            if table in tables:
                print(f"   ✅ {table}")
            else:
                print(f"   ❌ {table} (누락)")
        print()

        # 데이터 개수 확인
        print("📊 데이터 현황:")

        cursor.execute("SELECT COUNT(*) FROM isms_requirements")
        req_count = cursor.fetchone()[0]
        print(f"   인증기준 항목: {req_count}개")

        if req_count != 101:
            print(f"   ⚠️ 경고: 101개가 아닌 {req_count}개입니다!")
        else:
            print(f"   ✅ 전체 101개 항목 확인")

        cursor.execute("SELECT COUNT(*) FROM evidences")
        evidence_count = cursor.fetchone()[0]
        print(f"   증적 자료: {evidence_count}개")

        cursor.execute("SELECT COUNT(*) FROM evidence_logs")
        log_count = cursor.fetchone()[0]
        print(f"   증적 로그: {log_count}개")
        print()

        # 스키마 필수 컬럼 검증
        print("🔧 스키마 검증:")
        cursor.execute("PRAGMA table_info(isms_requirements)")
        columns = {row[1] for row in cursor.fetchall()}
        required_cols = {
            "item_code", "item_title", "chapter", "section", "section_title",
            "certification_criteria", "key_checks", "detailed_explanation",
            "evidence_examples", "related_laws", "defect_cases",
        }
        missing = required_cols - columns
        if missing:
            print(f"   ❌ 누락 컬럼: {', '.join(sorted(missing))}")
        else:
            print(f"   ✅ 필수 컬럼 {len(required_cols)}개 모두 존재")
        print()

        # 샘플 데이터 확인
        print("🔍 샘플 데이터 (처음 5개):")
        cursor.execute(
            "SELECT item_code, item_title FROM isms_requirements ORDER BY item_code LIMIT 5"
        )
        for i, (code, title) in enumerate(cursor.fetchall(), 1):
            print(f"   {i}. [{code}] {title}")
        print()

        # 장별 통계
        print("📈 장별 통계:")
        chapters = {
            "1": "관리체계 수립 및 운영",
            "2": "보호대책 요구사항",
            "3": "개인정보 처리 단계별 요구사항",
        }
        for chapter_num, chapter_name in chapters.items():
            cursor.execute(
                "SELECT COUNT(*) FROM isms_requirements WHERE chapter = ?",
                (chapter_num,),
            )
            count = cursor.fetchone()[0]
            print(f"   제{chapter_num}장 ({chapter_name}): {count}개")

        print()
        print("=" * 60)
        print("✅ 데이터베이스 검증 완료!")
        print("=" * 60)

        conn.close()
        return True

    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False


if __name__ == "__main__":
    success = verify_database()
    sys.exit(0 if success else 1)
