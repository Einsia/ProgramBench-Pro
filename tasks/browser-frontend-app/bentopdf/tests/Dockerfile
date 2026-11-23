FROM program-bench-bentopdf-base:1.0.0
COPY requirements-verifier.txt /tmp/requirements-verifier.txt
RUN /opt/venv/bin/pip install --no-cache-dir --require-hashes --only-binary=:all: \
      --target /opt/verifier-lib -r /tmp/requirements-verifier.txt && rm /tmp/requirements-verifier.txt && \
    chmod -R u=rwX,go=rX /opt/verifier-lib
COPY --from=runtime . /opt/blackbox/runtime/
COPY . /tests/
COPY --from=scoring scoring.py /tests/evaluation/scoring.py
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime && chmod 700 /tests && chmod 700 /tests/test.sh
