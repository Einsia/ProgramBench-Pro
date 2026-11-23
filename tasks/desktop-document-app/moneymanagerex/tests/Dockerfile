FROM program-bench-moneymanagerex-base:1.0.0
# The black-box runtime that drives candidates; the same files as the reference image (named build context).
COPY --from=runtime . /opt/blackbox/runtime/
COPY *.py *.md test.sh result-schema.json docker-compose.yaml Dockerfile .dockerignore /tests/
COPY evaluation/ /tests/evaluation/
COPY --from=scoring scoring.py /tests/evaluation/scoring.py
COPY reference/ /tests/reference/
COPY data/ /tests/data/
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime && chmod 700 /tests && chmod 700 /tests/test.sh
