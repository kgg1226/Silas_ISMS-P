# ISMS-P 증적 자동화 MCP 서버

## 설치
```bash
pip install -r requirements.txt
```

## Claude Desktop 설정

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
```json
{
  "mcpServers": {
    "isms-p": {
      "command": "python",
      "args": ["C:\\Silas_ISMS-P\\mcp_server\\server.py"]
    }
  }
}
```

## 사용법

Claude Desktop에서:
- "접근권한 관련 항목 검색해줘"
- "2.7.1 항목 상세 알려줘"
- "증적 현황 점검해줘"