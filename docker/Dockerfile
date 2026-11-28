FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# tesseract-ocr/-deu, ghostscript, qpdf: Laufzeit-Abhängigkeiten von OCRmyPDF (Lehrkraft-
# Editor, Textextraktion bei Seiten ohne Textebene – siehe CLAUDE.md).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl ca-certificates \
       tesseract-ocr tesseract-ocr-deu ghostscript qpdf \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv

WORKDIR /code

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

ARG TARGETARCH
ARG TAILWIND_VERSION=4.3.5
RUN case "$TARGETARCH" in \
      amd64) tailwind_arch="x64" ;; \
      arm64) tailwind_arch="arm64" ;; \
      *) echo "Nicht unterstützte Architektur: $TARGETARCH" >&2 && exit 1 ;; \
    esac \
    && curl -sL \
       "https://github.com/tailwindlabs/tailwindcss/releases/download/v${TAILWIND_VERSION}/tailwindcss-linux-${tailwind_arch}" \
       -o /usr/local/bin/tailwindcss \
    && chmod +x /usr/local/bin/tailwindcss

ENV PATH="/code/.venv/bin:${PATH}"

EXPOSE 8000

ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["python", "app/manage.py", "runserver", "0.0.0.0:8000"]
