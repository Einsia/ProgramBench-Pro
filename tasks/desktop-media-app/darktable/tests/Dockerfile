FROM program-bench-darktable-base:1.0.0
COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN apt-get update && apt-get install -y --no-install-recommends libimage-exiftool-perl && \
    rm -rf /var/lib/apt/lists/* && \
    python3 -m pip install --no-cache-dir -r /tmp/requirements-verifier.txt && \
    rm /tmp/requirements-verifier.txt
# The same application runtime as the reference image, from the named build context.
COPY --from=runtime . /opt/blackbox/runtime/
COPY *.py *.md *.json test.sh result-schema.json docker-compose.yaml Dockerfile .dockerignore /tests/
COPY evaluation/ /tests/evaluation/
COPY --from=scoring scoring.py /tests/evaluation/scoring.py
COPY reference/ /tests/reference/
COPY data/ /tests/data/
COPY requirements-verifier.txt /tests/
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime && chmod 700 /tests && chmod 700 /tests/test.sh
