#!/usr/bin/env bash
# Gera dist/nota_mgb-<versão>.zip para enviar ao plugins.qgis.org.
# Só entram arquivos versionados no git (commite antes de empacotar).
set -euo pipefail

cd "$(dirname "$0")/.."
PLUGIN=nota_mgb
VERSION=$(grep -E '^version=' "$PLUGIN/metadata.txt" | cut -d= -f2 | tr -d '[:space:]')

if [ -n "$(git status --porcelain "$PLUGIN")" ]; then
  echo "Há mudanças não commitadas em $PLUGIN/. Faça o commit antes de empacotar." >&2
  exit 1
fi

mkdir -p dist
OUT="dist/${PLUGIN}-${VERSION}.zip"
rm -f "$OUT"
git ls-files "$PLUGIN" | zip -q "$OUT" -@

echo "Gerado: $OUT"
unzip -l "$OUT"
