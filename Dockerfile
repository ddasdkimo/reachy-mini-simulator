FROM python:3.12-slim

WORKDIR /app

# 安裝系統依賴（pygame 需要）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libsdl2-2.0-0 \
        libsdl2-mixer-2.0-0 \
        libsdl2-image-2.0-0 \
        libsdl2-ttf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 先複製依賴定義，利用 Docker 層級快取
COPY pyproject.toml .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -e ".[web]" 2>/dev/null || true

# 複製原始碼
COPY reachy_mini_simulator/ reachy_mini_simulator/

# 安裝套件
RUN pip install --no-cache-dir ".[web]"

EXPOSE 8765

# 健康檢查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/api/state')" || exit 1

CMD ["reachy-sim-web"]
