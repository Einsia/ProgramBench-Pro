FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac AS base
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip ca-certificates tini locales ncurses-term file coreutils \
    build-essential pkg-config libncursesw5-dev libfaad-dev libao-dev libasound2-dev \
    libcddb2-dev libcdio-cdda-dev libdiscid-dev libavformat-dev libavcodec-dev libswresample-dev \
    libflac-dev libjack-dev libmad0-dev libmodplug-dev libmpcdec-dev libsystemd-dev \
    libopusfile-dev libpulse-dev libsamplerate0-dev libsndio-dev libvorbis-dev libwavpack-dev pulseaudio && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt constraints.txt /tmp/
RUN python3 -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt -c /tmp/constraints.txt && \
    python3 -c "import os; os.remove('/tmp/requirements.txt'); os.remove('/tmp/constraints.txt')"
ENV PATH="/opt/venv/bin:$PATH" TERM=xterm-256color LANG=C.UTF-8 LC_ALL=C.UTF-8 TZ=UTC PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONNOUSERSITE=1
RUN /opt/venv/bin/pip check && python3 -c 'import pyte,wcwidth; print("runtime deps importable")'
RUN test ! -e /usr/bin/cmus && test ! -d /usr/lib/cmus
RUN groupadd -g 1001 agent && useradd -m -u 1001 -g 1001 -s /bin/bash agent && mkdir -p /app/solution /blackbox && chown agent:agent /app/solution /blackbox
WORKDIR /app/solution
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]
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

# Install the pinned agent CLIs into the agent image.
FROM base AS agent
COPY --from=command-tools /command-tools/codex /command-tools/codex-code-mode-host /command-tools/claude /usr/local/bin/
RUN test "$(claude --version)" = '2.1.296 (Claude Code)' && \
    test "$(codex --version)" = 'codex-cli 0.162.1'

COPY runtime/ /opt/blackbox/runtime/
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime && install -m 755 /opt/blackbox/runtime/blackbox_client.py /usr/local/bin/blackbox && install -m 755 /opt/blackbox/runtime/blackbox_health.py /usr/local/bin/blackbox-health && chmod 1777 /blackbox
ENTRYPOINT ["/usr/bin/tini", "--", "python3", "-I", "-B", "/opt/blackbox-agent/entrypoint.py"]
CMD ["sleep", "infinity"]

# The reference product keeps its private root-only socket. Only this image
# exposes a fixed-target relay to the solving user and checks health as agent.
COPY agent_runtime/ /opt/blackbox-agent/
RUN chmod -R u=rwX,go=rX /opt/blackbox-agent && \
    install -m 755 /opt/blackbox-agent/health.py /usr/local/bin/blackbox-health
ENV BLACKBOX_SOCKET=/run/pbp-reference/reference.sock
