#!/bin/bash
# Install espeak-ng into ~/.local/opt/espeak-ng WITHOUT root (Debian/Ubuntu/antiX):
# apt-get download fetches the .deb files as the user, dpkg -x unpacks them.
set -euo pipefail
DEST="$HOME/.local/opt/espeak-ng"
MB="$HOME/.local/opt/mbrola"
mbrola_pt() {
  # MBROLA Brazilian voices (much less robotic), also without root
  local data="$1"
  [ -n "$data" ] || return 0
  if [ ! -e "$data/mbrola/br3" ]; then
    mkdir -p "$MB/debs" && (cd "$MB/debs" && timeout 300 apt-get download mbrola mbrola-br1 mbrola-br3 mbrola-br4 >/dev/null 2>&1 && for d in ./*.deb; do dpkg -x "$d" "$MB"; done; rm -rf "$MB/debs") || { echo "aviso: vozes MBROLA não instaladas (sigo com a voz padrão)"; return 0; }
    mkdir -p "$data/mbrola"
    for v in br1 br3 br4; do [ -f "$MB/usr/share/mbrola/$v/$v" ] && ln -sfn "$MB/usr/share/mbrola/$v/$v" "$data/mbrola/$v"; done
  fi
  echo "vozes MBROLA pt-BR: use \"voice\": \"mb-br3\" (ou mb-br1, mb-br4)"
}
if command -v espeak-ng >/dev/null 2>&1; then
  echo "espeak-ng já está no PATH: $(command -v espeak-ng) (vozes MBROLA do sistema: sudo apt install mbrola-br3)"; exit 0
fi
if [ -x "$DEST/usr/bin/espeak-ng" ]; then
  echo "espeak-ng já instalado em $DEST"; mbrola_pt "$(ls -d "$DEST"/usr/lib/*-linux-gnu/espeak-ng-data 2>/dev/null | head -1)"; exit 0
fi
command -v apt-get >/dev/null 2>&1 || { echo "sem apt-get: instale espeak-ng pelo gerenciador do sistema, ou use \"voice\": \"none\""; exit 1; }
mkdir -p "$DEST/debs"
cd "$DEST/debs"
timeout 300 apt-get download espeak-ng libespeak-ng1 espeak-ng-data libpcaudio0 libsonic0
for d in ./*.deb; do dpkg -x "$d" "$DEST"; done
rm -rf "$DEST/debs"
LIB=$(ls -d "$DEST"/usr/lib/*-linux-gnu | head -1)
LD_LIBRARY_PATH="$LIB" ESPEAK_DATA_PATH="$LIB" "$DEST/usr/bin/espeak-ng" -q "ok" && echo "espeak-ng instalado em $DEST (sem root)"
mbrola_pt "$LIB/espeak-ng-data"
