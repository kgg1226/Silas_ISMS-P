#!/usr/bin/env python3
"""
ISMS-P MCP 서버 — 호환성 래퍼.
실제 구현은 isms_mcp_server.py로 통합되었습니다.
기존 진입점(server.py)을 사용하는 설정이 있을 수 있으므로 리다이렉트합니다.
"""

from mcp_server.isms_mcp_server import main, server, DB_PATH  # noqa: F401

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
