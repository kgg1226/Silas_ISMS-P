"""행정규칙 API 응답 구조 확인용 테스트"""
import os
os.environ.setdefault("LAW_API_KEY", "un67")

from app.law_sync import _fetch_xml, LAW_API_BASE_SEARCH
import xml.etree.ElementTree as ET

# 행정규칙으로 검색
print("=== admrul: 개인정보의 안전성 확보조치 기준 ===")
root = _fetch_xml(LAW_API_BASE_SEARCH, {
    "target": "admrul",
    "query": "개인정보의 안전성 확보조치 기준",
    "display": "3",
    "sort": "lasc",
})
if root is not None:
    xml_str = ET.tostring(root, encoding="unicode")
    print(xml_str[:3000])
else:
    print("응답 없음")

print("\n=== admrul: 집적정보통신시설 보호지침 ===")
root2 = _fetch_xml(LAW_API_BASE_SEARCH, {
    "target": "admrul",
    "query": "집적정보통신시설 보호지침",
    "display": "3",
    "sort": "lasc",
})
if root2 is not None:
    xml_str2 = ET.tostring(root2, encoding="unicode")
    print(xml_str2[:3000])
else:
    print("응답 없음")
