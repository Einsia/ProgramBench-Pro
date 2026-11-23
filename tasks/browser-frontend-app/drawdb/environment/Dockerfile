FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac AS base

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip nodejs npm git curl ca-certificates \
    sqlite3 jq ripgrep build-essential libsqlite3-dev tini unzip \
    libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2t64 \
    libnss3 libnspr4 libpango-1.0-0 libcairo2 libx11-6 libxcb1 libxext6 \
    fonts-liberation fonts-noto-cjk && rm -rf /var/lib/apt/lists/*

# Python packages are pinned (requirements plus full constraints) and the Node
# toolchain installs from its lockfile for a reproducible environment.
COPY requirements.txt constraints.txt /tmp/
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt -c /tmp/constraints.txt && \
    rm /tmp/requirements.txt /tmp/constraints.txt
ENV PATH="/opt/venv/bin:$PATH" \
    PLAYWRIGHT_BROWSERS_PATH=/opt/browsers \
    NODE_PATH=/opt/node_modules
RUN python -m playwright install chromium && chmod -R a+rX /opt/browsers

# Shared packages provide an offline Node toolchain for applications.
COPY package.json package-lock.json /opt/
RUN cd /opt && npm ci --no-audit --no-fund && npm cache clean --force

# Offline copies of three public CDN packages (their npm releases, pinned by sha256): the black-box runtime's
# browser answers requests for their CDN addresses from /opt/cdn-mirror, since the page runs without network.
RUN mkdir -p /tmp/cdn /opt/cdn-mirror && cd /tmp/cdn && \
    curl -fsSL -o bi.tgz https://registry.npmjs.org/bootstrap-icons/-/bootstrap-icons-1.11.1.tgz && \
    curl -fsSL -o fa.tgz https://registry.npmjs.org/@fortawesome/fontawesome-free/-/fontawesome-free-6.5.2.tgz && \
    curl -fsSL -o monaco.tgz https://registry.npmjs.org/monaco-editor/-/monaco-editor-0.52.2.tgz && \
    printf '%s\n' \
      '710d6dbfb3397bbc29e004aa62b71aa532192e779c2451cf3de0e93f81fd9a0c  bi.tgz' \
      '1622d514686c299db3ffe9405c4f124778ce812658f66282d4524247e66fff9c  fa.tgz' \
      'c280cdcf0b0c13d1a2bf01af958d4387ed06d7f6c918401d00c4adcae1bc72b6  monaco.tgz' | sha256sum -c - && \
    mkdir -p /opt/cdn-mirror/bootstrap-icons@1.11.1 /opt/cdn-mirror/font-awesome@6.5.2 \
             /opt/cdn-mirror/monaco-editor@0.52.2 && \
    tar -xzf bi.tgz -C /opt/cdn-mirror/bootstrap-icons@1.11.1 --strip-components=1 package/font package/LICENSE && \
    tar -xzf fa.tgz -C /opt/cdn-mirror/font-awesome@6.5.2 --strip-components=1 package/css package/webfonts \
        package/LICENSE.txt && \
    tar -xzf monaco.tgz -C /opt/cdn-mirror/monaco-editor@0.52.2 --strip-components=1 package/min/vs package/LICENSE \
        package/ThirdPartyNotices.txt && \
    cd / && rm -rf /tmp/cdn && chmod -R u=rwX,go=rX /opt/cdn-mirror

RUN useradd -m -u 1001 -s /bin/bash agent && \
    mkdir -p /app/solution && chown root:root /app && chmod 755 /app && chown agent:agent /app/solution
WORKDIR /app/solution
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]

# Native command-line tools from pinned official releases.
FROM base AS command-tools
USER root
RUN python3 -c "import urllib.request; urllib.request.urlretrieve('https://registry.npmjs.org/@openai/codex/-/codex-0.162.1-linux-x64.tgz', '/tmp/codex.tgz')" && \
    echo '7417711678b464eee70664126e39e88bb3c84c2928da0e71f14b56e04ff5c09f  /tmp/codex.tgz' | sha256sum -c - && \
    mkdir -p /command-tools && \
    tar -xzf /tmp/codex.tgz -C /command-tools --strip-components=4 package/vendor/x86_64-unknown-linux-musl/bin/codex package/vendor/x86_64-unknown-linux-musl/bin/codex-code-mode-host && \
    rm /tmp/codex.tgz
# Checksum: https://downloads.claude.ai/claude-code-releases/2.1.296/manifest.json, platforms.linux-x64.checksum.
RUN python3 -c "import urllib.request; urllib.request.urlretrieve('https://downloads.claude.ai/claude-code-releases/2.1.296/linux-x64/claude', '/command-tools/claude')" && \
    echo '24972e3bc859fab2b46ed4c1e51f7d6130f06d3bd550811a114640de3370d0de  /command-tools/claude' | sha256sum -c - && \
    chmod 755 /command-tools/claude && \
    test "$(/command-tools/claude --version)" = '2.1.296 (Claude Code)' && \
    test "$(/command-tools/codex --version)" = 'codex-cli 0.162.1'

FROM base AS agent
COPY --from=command-tools /command-tools/codex /command-tools/codex-code-mode-host /command-tools/claude /usr/local/bin/
RUN test "$(claude --version)" = '2.1.296 (Claude Code)' && \
    test "$(codex --version)" = 'codex-cli 0.162.1'
# The same application runtime is installed in every environment:
# blackbox --target self runs it on the agent's own /app/solution.
COPY runtime/ /opt/blackbox/runtime/
# Public exploration documents.
COPY samples/ /app/samples/
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime /app/samples && \
    install -m 755 /opt/blackbox/runtime/blackbox_client.py /usr/local/bin/blackbox && \
    install -m 755 /opt/blackbox/runtime/blackbox_health.py /usr/local/bin/blackbox-health && \
    mkdir -p /blackbox && chown agent:agent /blackbox

ENTRYPOINT ["/usr/bin/tini", "--", "python3", "-I", "-B", "/opt/blackbox-agent/entrypoint.py"]

# The reference product keeps its private root-only socket. Only this image
# exposes a fixed-target relay to the solving user and checks health as agent.
COPY agent_runtime/ /opt/blackbox-agent/
RUN chmod -R u=rwX,go=rX /opt/blackbox-agent && \
    install -m 755 /opt/blackbox-agent/health.py /usr/local/bin/blackbox-health
ENV BLACKBOX_SOCKET=/run/pbp-reference/reference.sock
CMD ["sleep", "infinity"]
