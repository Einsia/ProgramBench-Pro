FROM ubuntu:22.04@sha256:5ec03bb3441e8b0bf3b4f9cd4629a1ae763010dc3035bb8da3ae6cf026486401 AS common

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc6-dev python3 python3-tk python3-pip git curl ca-certificates tini \
    xvfb xdotool wmctrl openbox imagemagick ffmpeg sox \
    x11-utils x11-xserver-utils dbus-x11 pulseaudio \
    fonts-dejavu fonts-liberation fonts-noto-cjk \
    libasound2 libsndfile1 python3-numpy python3-pyatspi python3-gi gir1.2-gtk-3.0 \
    at-spi2-core libatk-adaptor xclip xz-utils ripgrep && \
    rm -rf /var/lib/apt/lists/*

# Node.js is available for application development.
RUN curl -fsSL https://nodejs.org/dist/v22.20.0/node-v22.20.0-linux-x64.tar.xz -o /tmp/node.tar.xz && \
    echo '00bbd05e306ea68b6e13e17360d0e2f680b493ef95f2fea1c4296ff7437530bc  /tmp/node.tar.xz' | sha256sum -c - && \
    tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1 && \
    rm /tmp/node.tar.xz

RUN useradd -m -u 1001 -s /bin/bash agent && \
    mkdir -p /app/solution /blackbox && \
    chown agent:agent /app/solution /blackbox && \
    chown root:root /app && chmod 0755 /app
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp
WORKDIR /app/solution
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]

# Product dependencies for the MuseScore Studio AppImage: graphics, NSS and Qt xcb.
# These are installed only in the application runtime base.
FROM common AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    libegl1 libopengl0 libgl1 libgl1-mesa-dri libglx-mesa0 libnspr4 libnss3 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libxcb-shape0 \
    libxcb-cursor0 libxkbcommon-x11-0 && \
    rm -rf /var/lib/apt/lists/*

# The model's image: the common tools and the black-box runtime, the same files as the
# reference and verifier images (blackbox --target self runs it on the agent's own
# /app/solution); product-specific libraries remain in the separate runtime base.
# Codex CLI 0.162.1 for model runs with Harbor's codex agent: the official npm platform package
# (Apache-2.0), pinned by sha256; only its two native binaries are kept. Because codex is already
# installed, Harbor does not need network access to install the agent.
FROM common AS command-tools
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
FROM common AS agent
COPY --from=command-tools /command-tools/codex /command-tools/codex-code-mode-host /command-tools/claude /usr/local/bin/
RUN test "$(claude --version)" = '2.1.296 (Claude Code)' && \
    test "$(codex --version)" = 'codex-cli 0.162.1'

COPY runtime/ /opt/blackbox/runtime/
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime && \
    install -m 755 /opt/blackbox/runtime/blackbox_client.py /usr/local/bin/blackbox && \
    install -m 755 /opt/blackbox/runtime/blackbox_health.py /usr/local/bin/blackbox-health

ENTRYPOINT ["/usr/bin/tini", "--", "python3", "-I", "-B", "/opt/blackbox-agent/entrypoint.py"]

# The reference product keeps its private root-only socket. Only this image
# exposes a fixed-target relay to the solving user and checks health as agent.
COPY agent_runtime/ /opt/blackbox-agent/
RUN chmod -R u=rwX,go=rX /opt/blackbox-agent && \
    install -m 755 /opt/blackbox-agent/health.py /usr/local/bin/blackbox-health
ENV BLACKBOX_SOCKET=/run/pbp-reference/reference.sock
CMD ["sleep", "infinity"]
