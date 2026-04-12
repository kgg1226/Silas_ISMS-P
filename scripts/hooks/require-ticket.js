#!/usr/bin/env node
/**
 * Sentix PreToolUse hook — require-ticket
 *
 * Write / Edit / MultiEdit 도구 호출 직전에 실행되어 활성 Governor 사이클이
 * 있는지 확인한다. 활성 사이클이 없고 허용 경로가 아니면 차단한다.
 *
 * Hook input (stdin, JSON):
 *   {
 *     tool_name: "Write" | "Edit" | "MultiEdit",
 *     tool_input: { file_path: "...", ... },
 *     ...
 *   }
 *
 * Exit codes:
 *   0 = 허용 (통과)
 *   2 = 차단 (stderr 메시지가 Claude 에게 표시됨)
 *   기타 = 훅 자체 오류 → fail-open (작업 허용, 로그만)
 *
 * 등록: .claude/settings.json hooks.PreToolUse matcher "Write|Edit|MultiEdit"
 */

import { readFileSync, existsSync } from 'node:fs';
import { resolve, relative } from 'node:path';

// ── 허용 경로 패턴 (차단 없이 통과) ─────────────────
// 이유: 티켓 없이도 안전하게 수정 가능한 영역
const ALLOW_PATTERNS = [
  /^tasks\//,              // Sentix 자체가 tasks/ 를 관리
  /^\.sentix\/constraints\.md$/,  // 피드백 루프가 자동 추가
  /^\.sentix\/config\.toml$/,     // sentix config set 이 수정
  /^\.sentix\/plugins\//,         // 로컬 플러그인
  /^\.claude\/rules\//,    // 규칙 파일 (auto-rule-promoter 가 씀)
  /^__tests__\//,          // 테스트 추가 (하드룰 1 지원)
  /^README\.md$/,          // 최상위 프로젝트 소개 (사용자 직접 편집 범주)
  /^CHANGELOG\.md$/,       // 릴리즈 노트 (CI/수동 모두 사용)
  /\/handoff\.md$/,        // 인수 문서
  /\/lessons\.md$/,        // 학습 기록 (dev-fix 가 씀)
  /\/patterns\.md$/,       // 패턴 기록 (pattern-engine 이 씀)
  /\/agent-metrics\.jsonl$/,
  /\/pattern-log\.jsonl$/,
  /\/governor-state\.json$/,
];

// ── 훅 본체 ─────────────────────────────────────────
let inputJson = '';
process.stdin.setEncoding('utf-8');
process.stdin.on('data', (chunk) => { inputJson += chunk; });
process.stdin.on('end', () => {
  try {
    const input = inputJson ? JSON.parse(inputJson) : {};
    const toolName = input.tool_name || '';
    const toolInput = input.tool_input || {};
    const filePath = toolInput.file_path || '';

    // matcher 가 Write|Edit|MultiEdit 로 필터하지만 double-check
    if (!['Write', 'Edit', 'MultiEdit'].includes(toolName)) {
      process.exit(0);
    }

    if (!filePath) {
      // file_path 가 없으면 판정 불가 — 통과 (fail-open)
      process.exit(0);
    }

    // 상대 경로 정규화
    const cwd = process.cwd();
    let relPath = filePath;
    try {
      relPath = relative(cwd, resolve(filePath));
    } catch { /* 그대로 사용 */ }
    relPath = relPath.replace(/\\/g, '/'); // Windows 정규화

    // 허용 패턴 매칭
    for (const pattern of ALLOW_PATTERNS) {
      if (pattern.test(relPath)) {
        process.exit(0);
      }
    }

    // Governor state 확인
    const statePath = resolve(cwd, 'tasks/governor-state.json');
    if (!existsSync(statePath)) {
      block(relPath, 'Governor 사이클이 없습니다 (tasks/governor-state.json 없음)');
    }

    let state;
    try {
      state = JSON.parse(readFileSync(statePath, 'utf-8'));
    } catch (e) {
      // state 파싱 실패 → fail-open (파일 파손 시 작업 차단은 과함)
      process.stderr.write(`[sentix-hook] governor-state.json 파싱 실패, 통과: ${e.message}\n`);
      process.exit(0);
    }

    if (state.status !== 'in_progress') {
      block(relPath, `Governor 사이클 상태가 "${state.status}" 입니다 (in_progress 아님)`);
    }

    // 모든 체크 통과
    process.exit(0);
  } catch (e) {
    // 훅 자체 버그 → fail-open (작업 차단은 과함)
    process.stderr.write(`[sentix-hook] require-ticket 훅 오류, 통과: ${e.message}\n`);
    process.exit(0);
  }
});

function block(filePath, reason) {
  const lines = [
    '',
    '╔══════════════════════════════════════════════════════════════╗',
    '║  [SENTIX:BLOCKED] Direct Write/Edit 차단됨                    ║',
    '╚══════════════════════════════════════════════════════════════╝',
    '',
    `  대상:  ${filePath}`,
    `  이유:  ${reason}`,
    '',
    '  Sentix 프로젝트는 Governor 파이프라인을 우회한 직접 수정을 금지합니다.',
    '  코드 변경은 반드시 티켓 → planner → dev → pr-review 순서를 따라야 합니다.',
    '',
    '  해결:',
    '    1. 새 요청으로 사이클 시작:',
    '       $ sentix run "<요청 내용>"',
    '    2. 기존 버그 수정:',
    '       $ sentix ticket create "<버그 설명>"',
    '       $ sentix ticket debug <ticket-id>',
    '    3. 새 기능:',
    '       $ sentix feature add "<기능 설명>"',
    '',
    '  허용 경로 (티켓 없이 수정 가능):',
    '    - tasks/**, .sentix/**, __tests__/**',
    '    - scripts/hooks/**, .claude/rules/**',
    '    - README.md, CHANGELOG.md',
    '    - lessons.md, patterns.md, handoff.md 등 로그 파일',
    '',
  ];
  process.stderr.write(lines.join('\n'));
  process.exit(2); // Claude Code 차단 신호
}
