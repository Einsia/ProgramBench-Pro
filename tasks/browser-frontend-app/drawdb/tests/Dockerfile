FROM program-bench-drawdb-base:1.0.0
# OCR is confined to the verifier and reads only decoded product exports.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && \
    rm -rf /var/lib/apt/lists/*
# Image decoding for the verifier only, outside the Python environment that candidates use.
COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN /opt/venv/bin/pip install --no-cache-dir --no-deps --require-hashes --only-binary=:all: \
      --target /opt/verifier-lib -r /tmp/requirements-verifier.txt && rm /tmp/requirements-verifier.txt && \
    chmod -R u=rwX,go=rX /opt/verifier-lib
# The black-box runtime that drives candidates; the same files as the reference image (named build context).
COPY --from=runtime . /opt/blackbox/runtime/
COPY *.py *.md *.txt test.sh result-schema.json docker-compose.yaml Dockerfile .dockerignore /tests/
COPY evaluation/ /tests/evaluation/
COPY --from=scoring scoring.py /tests/evaluation/scoring.py
COPY reference/ /tests/reference/
COPY data/ /tests/data/
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime && chmod 700 /tests && chmod 700 /tests/test.sh
