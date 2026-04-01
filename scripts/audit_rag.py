"""ISMS-P RAG 품질 최종 감사"""
import sqlite3
import json
from collections import Counter

DB = "C:/Silas_ISMS-P/data/isms_p.db"
FIELDS = [
    "certification_criteria",
    "key_checks",
    "detailed_explanation",
    "evidence_examples",
    "related_laws",
    "defect_cases",
]
FIELD_SHORT = ["CC", "KC", "DE", "EE", "RL", "DC"]


def has_content(val):
    if not val:
        return False
    v = val.strip()
    return v not in ("", "[]", "null", "None")


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM isms_requirements ORDER BY item_code")
    rows = cur.fetchall()

    total_score = 0
    grade_dist = Counter()
    chapter_scores = {}
    weak_items = []

    header = f"{'코드':<8} {'항목명':<28} "
    header += " ".join(f"{s:>3}" for s in FIELD_SHORT)
    header += f"  {'점수':>5}  {'등급'}"
    print(header)
    print("-" * 90)

    for r in rows:
        scores = {f: (1 if has_content(r[f]) else 0) for f in FIELDS}
        pct = sum(scores.values()) / 6 * 100
        total_score += pct

        if pct >= 100:
            grade = "S"
        elif pct >= 83:
            grade = "A"
        elif pct >= 67:
            grade = "B"
        elif pct >= 50:
            grade = "C"
        else:
            grade = "D"

        grade_dist[grade] += 1

        ch = str(r["chapter"] or r["item_code"].split(".")[0])
        chapter_scores.setdefault(ch, []).append(pct)

        title = (r["item_title"] or "?")[:26]
        vals = " ".join(f"{scores[f]:>3}" for f in FIELDS)
        mark = " *" if pct < 67 else ""
        print(f"{r['item_code']:<8} {title:<28} {vals}  {pct:>5.1f}%  {grade}{mark}")

        if pct <= 50:
            missing = [f for f in FIELDS if not scores[f]]
            weak_items.append((r["item_code"], r["item_title"], missing, pct))

    avg = total_score / len(rows)
    print(f"\n{'=' * 90}")
    print(f"전체 항목: {len(rows)}개")
    print(f"평균 RAG 점수: {avg:.1f}%")
    print(f"등급 분포: {dict(grade_dist.most_common())}")

    ch_names = {
        "1": "관리체계 수립 및 운영",
        "2": "보호대책 요구사항",
        "3": "개인정보 처리단계별",
    }
    print("\n장별 평균:")
    for ch in sorted(chapter_scores.keys()):
        sc = chapter_scores[ch]
        ch_avg = sum(sc) / len(sc)
        name = ch_names.get(ch, ch)
        print(f"  제{ch}장 ({name}): {ch_avg:.1f}% ({len(sc)}항목)")

    if weak_items:
        print(f"\n부족 항목 (C등급 이하): {len(weak_items)}건")
        for code, title, missing, pct in weak_items:
            print(f"  {code} | {title} | 누락: {missing} ({pct:.0f}%)")
    else:
        print("\nC등급 이하 항목: 없음")

    conn.close()


if __name__ == "__main__":
    main()
