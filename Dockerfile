FROM python:3.11-slim

# Non-root user
RUN groupadd -r lifelink && useradd -r -g lifelink lifelink

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure DB dir writable
RUN chown -R lifelink:lifelink /app

USER lifelink

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health')" || exit 1

CMD ["python", "app.py"]
