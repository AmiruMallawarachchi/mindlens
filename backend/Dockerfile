FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend \
    HOME=/home/mindlens

WORKDIR /app

# UID 1000, not just --system's arbitrary system UID: Hugging Face Spaces
# runs Docker containers expecting the app user at 1000, and a mismatched
# UID is a real class of permission failure there, not a style preference.
# --home is set explicitly because --system does not create one by default —
# transformers/huggingface_hub write their download cache to
# $HOME/.cache/huggingface at runtime (every from_pretrained call), and
# without a real, owned HOME that cache write fails the first model load.
RUN addgroup --system --gid 1000 mindlens && \
    adduser --system --uid 1000 --ingroup mindlens \
        --home /home/mindlens --shell /usr/sbin/nologin mindlens && \
    mkdir -p /home/mindlens

COPY requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
# /var/data/chroma is Render's persistent-disk mount point (render.yaml) and
# does not exist on Hugging Face Spaces' free tier — harmless to create
# either way, since CHROMADB_PERSIST_DIR only points there under Render.
# On Spaces the setting stays at its default, which resolves under /app and
# is already covered by the recursive chown below.
RUN mkdir -p /var/data/chroma && chown -R mindlens:mindlens /app /var/data /home/mindlens

USER mindlens
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*' --workers 1"]
