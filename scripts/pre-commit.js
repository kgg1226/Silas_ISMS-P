#!/usr/bin/env node

/**
 * sentix pre-commit hook — 커밋 전 검증 게이트 실행
 *
 * .git/hooks/pre-commit에 설치되어 git commit 시 자동 실행.
 * verify-gates.js를 호출하여 하드 룰 위반 시 커밋을 블로킹한다.
 *
 * 설치: sentix init (자동) 또는 수동:
 *   cp scripts/pre-commit.js .git/hooks/pre-commit
 *   chmod +x .git/hooks/pre-commit
 */

import { execSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// sentix가 설치된 프로젝트의 루트 찾기
const projectRoot = execSync('git rev-parse --show-toplevel', { encoding: 'utf-8' }).trim();

async function main() {
  // verify-gates.js 동적 임포트
  let runGates;
  try {
    // npx로 설치된 경우
    const gatesPath = resolve(projectRoot, 'node_modules', 'sentix', 'src', 'lib', 'verify-gates.js');
    const mod = await import(gatesPath);
    runGates = mod.runGates;
  } catch {
    try {
      // 로컬 개발 (sentix 프로젝트 자체)
      const gatesPath = resolve(projectRoot, 'src', 'lib', 'verify-gates.js');
      const mod = await import(gatesPath);
      runGates = mod.runGates;
    } catch {
      // verify-gates를 찾을 수 없으면 통과
      process.exit(0);
    }
  }

  const results = runGates(projectRoot);

  if (!results.passed) {
    console.error('\n[SENTIX:GATE] Commit blocked — verification gate failed\n');
    for (const v of results.violations) {
      console.error(`  ✗ [${v.rule}] ${v.message}`);
    }
    console.error('\nFix violations and try again.\n');
    process.exit(1);
  }

  // 통과 시 조용히 진행
}

main().catch(() => process.exit(0)); // 에러 시 커밋 허용 (안전 폴백)
