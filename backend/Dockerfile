FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend \
    HOME=/home/mindlens

WORKDIR /app

# Non-root runtime user. UID 1000 matches the convention most container
# platforms expect; --home is explicit so any library that writes a cache under
# $HOME has a directory it owns.
RUN addgroup --system --gid 1000 mindlens && \
    adduser --system --uid 1000 --ingroup mindlens \
        --home /home/mindlens --shell /usr/sbin/nologin mindlens && \
    mkdir -p /home/mindlens

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
RUN chown -R mindlens:mindlens /app /home/mindlens

USER mindlens
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --workers 1"]
