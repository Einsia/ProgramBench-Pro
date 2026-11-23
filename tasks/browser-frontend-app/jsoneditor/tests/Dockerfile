FROM program-bench-jsoneditor-base:1.0.0
COPY --from=runtime . /opt/blackbox/runtime/
COPY . /tests/
COPY --from=scoring scoring.py /tests/evaluation/scoring.py
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime && chmod 700 /tests && chmod 700 /tests/test.sh
