FROM program-bench-stackedit-base:1.0.0
COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-verifier.txt && rm /tmp/requirements-verifier.txt
COPY --from=runtime . /opt/blackbox/runtime/
COPY *.py *.md *.txt test.sh result-schema.json docker-compose.yaml Dockerfile .dockerignore /tests/
COPY evaluation/ /tests/evaluation/
COPY --from=scoring scoring.py /tests/evaluation/scoring.py
COPY reference/ /tests/reference/
COPY fixtures/ /tests/fixtures/
COPY data/ /tests/data/
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime && chmod 700 /tests && chmod 700 /tests/test.sh
