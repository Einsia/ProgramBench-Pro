FROM debian:trixie@sha256:8c4733a92aacd0bcff3779eadc35a4a5147f36cb20a5fcb56504cbc740212259 AS common

ARG DEBIAN_FRONTEND=noninteractive

# Desktop session, accessibility, GTK 3 with Python bindings and GtkSourceView 4, document and image tools.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python-is-python3 python3-venv python3-pip python3-gi python3-gi-cairo python3-cairo python3-pil python3-lxml \
    gir1.2-gtk-3.0 gir1.2-gtksource-4 gir1.2-pango-1.0 \
    python3-pyatspi gir1.2-atspi-2.0 at-spi2-core dbus dbus-x11 \
    xvfb openbox xdotool xclip x11-utils wmctrl imagemagick librsvg2-common adwaita-icon-theme \
    fonts-dejavu fonts-liberation fonts-noto-cjk \
    sqlite3 7zip poppler-utils file procps libfaketime \
    git curl ca-certificates tini build-essential ripgrep nodejs npm libglib2.0-bin && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GTK_MODULES=gail:atk-bridge \
    NO_AT_BRIDGE=0 \
    GTK_A11Y=always \
    LANG=C.UTF-8

RUN useradd -m -u 1001 -s /bin/bash agent && \
    mkdir -p /app/solution /blackbox && \
    chown agent:agent /app/solution /blackbox
WORKDIR /app/solution

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["sleep", "infinity"]

# Base of the reference and verifier images: adds the shared libraries the pinned CherryTree release
# package depends on. Only those images run the standard answer; the model's image does not have them.
FROM common AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgtkmm-3.0-1t64 libgtksourceview-4-0 libxml++2.6-2v5 libsqlite3-0 libgspell-1-3 libcurl4t64 \
    libuchardet0 libfribidi0 libvte-2.91-0 libspdlog1.15 libatkmm-1.6-1v5 libcairomm-1.0-1v5 libfmt10 \
    libglibmm-2.4-1t64 libpangomm-1.4-1v5 libsigc++-2.0-0v5 && \
    rm -rf /var/lib/apt/lists/*

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

FROM common AS agent
COPY --from=command-tools /command-tools/codex /command-tools/codex-code-mode-host /command-tools/claude /usr/local/bin/
RUN test "$(claude --version)" = '2.1.296 (Claude Code)' && \
    test "$(codex --version)" = 'codex-cli 0.162.1'
# The black-box runtime, the same files as the reference and verifier images: blackbox --target self runs it on the
# model's own /app/solution (with a private desktop of its own), and its desktop module also runs the model's
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
