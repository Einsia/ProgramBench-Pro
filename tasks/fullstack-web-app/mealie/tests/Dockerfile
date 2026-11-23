FROM program-bench-mealie-base:1.0.0
# Decoder for public image responses; the candidate cannot access verifier code.
COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/requirements-verifier.txt && rm /tmp/requirements-verifier.txt
# The black-box runtime that drives candidates; the same files as the reference image (named build context).
COPY --from=runtime . /opt/blackbox/runtime/
COPY *.py *.md requirements-verifier.txt test.sh result-schema.json docker-compose.yaml Dockerfile .dockerignore /tests/
COPY evaluation/ /tests/evaluation/
COPY --from=scoring scoring.py /tests/evaluation/scoring.py
COPY reference/ /tests/reference/
COPY data/ /tests/data/
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime && chmod 700 /tests && chmod 700 /tests/test.sh
