FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared ./shared
COPY server ./server

ENV DATABASE_DIR=/data
ENV PORT=10000

EXPOSE 10000

# Render setzt $PORT – Shell-Form für Variable-Expansion
CMD sh -c "uvicorn server.main:app --host 0.0.0.0 --port ${PORT:-10000}"
