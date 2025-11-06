# ---- Base ----
FROM python:3.11-slim

# Fonts + headless deps (lean for e-ink)
# - Enable Debian contrib/non-free for MS core fonts
# - Install small, crisp families: DejaVu, Liberation, Noto(core only), Roboto, Open Sans, Ubuntu, Cantarell
# - Install MS core fonts non-interactively
# - No CJK / No color-emoji (keeps image small for your e-ink themes)
RUN set -eux; \
    sed -ri 's/ main([ ]|$)/ main contrib non-free non-free-firmware /g' /etc/apt/sources.list || true; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates curl wget git \
      fontconfig \
      # core families (good legibility on e-ink)
      fonts-dejavu-core fonts-dejavu-extra \
      fonts-liberation || true; \
    # Liberation package name varies on some bases; try v2 first then fallback
    apt-get install -y --no-install-recommends fonts-liberation2 || true; \
    apt-get install -y --no-install-recommends \
      fonts-noto-core \
      fonts-roboto \
      fonts-open-sans \
      fonts-cantarell \
      # X/GTK bits your Playwright/Chromium needs
      libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 libdrm2 \
      libxkbcommon0 libnss3 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libgtk-3-0 libgbm1 libx11-6 libx11-xcb1 libxcb1 libxext6 libxrender1 \
      libxtst6 libxi6 libpango-1.0-0 libcairo2 libglib2.0-0; \
    # fonts-ubuntu was renamed on some Debian/Ubuntu releases; fall back when needed
    if ! apt-get install -y --no-install-recommends fonts-ubuntu; then \
      apt-get install -y --no-install-recommends fonts-ubuntu-classic || \
      apt-get install -y --no-install-recommends ttf-ubuntu-font-family || true; \
    fi; \
    # Pre-accept EULA and install the Microsoft core fonts
    echo "ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true" | debconf-set-selections; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ttf-mscorefonts-installer || true; \
    # Small fontconfig alias: stable generic family mapping; avoid color emoji on e-ink
    mkdir -p /etc/fonts/conf.d; \
    cat <<'EOF' > /etc/fonts/conf.d/60-family-aliases-kd.conf
<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">
<fontconfig>
  <alias>
    <family>sans-serif</family>
    <prefer>
      <family>Roboto</family>
      <family>DejaVu Sans</family>
      <family>Noto Sans</family>
      <family>Liberation Sans</family>
      <family>Open Sans</family>
      <family>Ubuntu</family>
      <family>Cantarell</family>
    </prefer>
  </alias>
  <alias>
    <family>serif</family>
    <prefer>
      <family>Noto Serif</family>
      <family>Liberation Serif</family>
      <family>DejaVu Serif</family>
    </prefer>
  </alias>
  <alias>
    <family>monospace</family>
    <prefer>
      <family>DejaVu Sans Mono</family>
      <family>Liberation Mono</family>
      <family>Noto Sans Mono</family>
    </prefer>
  </alias>
  <selectfont>
    <rejectfont>
      <pattern><family>Noto Color Emoji</family></pattern>
    </rejectfont>
  </selectfont>
</fontconfig>
EOF
    fc-cache -f && rm -rf /var/lib/apt/lists/*

# avoid playwright trying to download at pip time
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# install python deps
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# install browser (your original step preserved)
RUN playwright install --with-deps chromium || playwright install chromium

# copy the rest
COPY . /app

# run from backend/
WORKDIR /app/backend

ENV PORT=8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
