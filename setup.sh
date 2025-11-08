#!/bin/bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p data logs
echo "✅ 설치 완료!"
