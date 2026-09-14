FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_THREAD_LIMIT=1 TMPDIR=/tmp

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    tesseract-ocr-ara \
    tesseract-ocr-osd \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY . .

RUN useradd --uid 10001 --create-home vault \
    && mkdir -p /app/staticfiles \
    && mkdir -p /opt/easyocr-models \
    && mkdir -p /tmp/easyocr-user-network \
    && chown -R vault:vault /app/staticfiles \
    && chown -R vault:vault /opt/easyocr-models \
    && chmod 777 /tmp/easyocr-user-network

RUN python -c "import easyocr; easyocr.Reader(['en'],gpu=False,model_storage_directory='/opt/easyocr-models',user_network_directory='/tmp/easyocr-user-network',download_enabled=True,verbose=False)"

RUN chmod -R a+rX /opt/easyocr-models \
    && chmod 777 /tmp/easyocr-user-network

USER vault

RUN VAULT_TESTING=1 python manage.py collectstatic --noinput

CMD ["gunicorn","app.wsgi:application","--bind","0.0.0.0:8000","--certfile","/run/vault-secrets/internal.crt","--keyfile","/run/vault-secrets/internal.key","--workers","2","--threads","1","--timeout","180","--max-requests","300","--max-requests-jitter","50","--access-logfile","/dev/null","--error-logfile","-"]