FROM ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac AS base

ARG DEBIAN_FRONTEND=noninteractive

# GTK 3 with its Python bindings and pyxdg run the product, libfaketime fixes the clock the product sees (the
# black-box runtime injects it) and git serves the version control plugin.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python3-pip python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 python3-xdg python3-pil python3-dateutil python3-packaging \
    python3-pyatspi gir1.2-atspi-2.0 at-spi2-core dbus-x11 \
    xvfb openbox xdotool xclip x11-utils wmctrl imagemagick faketime \
    git curl ca-certificates tini gettext fonts-dejavu fonts-liberation fonts-noto-cjk librsvg2-common \
    nodejs npm python3-tk ripgrep build-essential libglib2.0-bin && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GTK_MODULES=gail:atk-bridge \
    NO_AT_BRIDGE=0 \
    GTK_A11Y=always

RUN useradd -m -u 1001 -s /bin/bash agent && \
    mkdir -p /app/solution /blackbox && \
    chown agent:agent /app/solution /blackbox
WORKDIR /app/solution

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]

# Native command-line tools, downloaded from their official release locations.
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
# The black-box runtime, the same files as the reference and verifier images: blackbox --target self runs it on the
# local /app/solution (with a private desktop of its own), and its desktop module also runs the application
# development desktop (1280x900, one virtual desktop, ordinary windows maximized) for user agent on display :99.
ENV DISPLAY=:99 \
    XDG_RUNTIME_DIR=/tmp/pbp-desktop/runtime \
    DBUS_SESSION_BUS_ADDRESS=unix:path=/tmp/pbp-desktop/session.sock \
    AT_SPI_BUS_ADDRESS=unix:path=/tmp/pbp-desktop/runtime/at-spi/bus_99
COPY runtime/ /opt/blackbox/runtime/
RUN chmod -R u=rwX,go=rX /opt/blackbox/runtime && \
    install -m 755 /opt/blackbox/runtime/blackbox_client.py /usr/local/bin/blackbox && \
    install -m 755 /opt/blackbox/runtime/blackbox_health.py /usr/local/bin/blackbox-health && \
    chmod 1777 /blackbox
ENTRYPOINT ["/usr/bin/tini", "--", "python3", "-I", "-B", "/opt/blackbox-agent/entrypoint.py", "python3", "-I", "-B", "/opt/blackbox/runtime/blackbox_desktop.py", "session", \
            "--display", ":99", "--root", "/tmp/pbp-desktop", "--screen", "1280x900", "--user", "agent", "--"]
CMD ["sleep", "infinity"]

# The reference product keeps its private root-only socket. Only this image
# exposes a fixed-target relay to the solving user and checks health as agent.
COPY agent_runtime/ /opt/blackbox-agent/
RUN chmod -R u=rwX,go=rX /opt/blackbox-agent && \
    install -m 755 /opt/blackbox-agent/health.py /usr/local/bin/blackbox-health
ENV BLACKBOX_SOCKET=/run/pbp-reference/reference.sock
