# Silas ISMS-P Compliance System

## 개요
ISMS-P (Information Security Management System - Personal Information Protection) 인증 자동화 시스템입니다.

## 데이터베이스 구조

### isms_requirements 테이블
- **101개 항목** 전체 포함
- 1장: 관리체계 수립 및 운영 (16개)
- 2장: 보호대책 요구사항 (64개)  
- 3장: 개인정보 처리 단계별 요구사항 (21개)

### 스키마
- item_code: 항목 코드 (예: 1.1.1)
- title: 항목 제목
- certification_criteria: 인증기준
- key_checkpoint: 주요 확인사항
- evidence_example: 증적 예시
- defect_case: 결함 사례

## 사용 방법

MCP 서버를 통해 Claude Desktop과 연동하여 사용합니다.

### 주요 기능
1. 인증기준 검색 (search_requirements)
2. 상세 정보 조회 (get_requirement_detail)
3. 증적 생성 (generate_evidence)
4. 준수율 확인 (check_compliance)
5. 감사 보고서 생성 (create_audit_report)

## 데이터베이스
- 위치: `database/isms_p.db`
- 크기: 648KB
- 총 항목: 101개
