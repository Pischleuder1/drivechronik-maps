#!/usr/bin/env bash
set -euo pipefail

COUNTRY="${1:-dk}"
WORK_ROOT="${WORK_ROOT:-$PWD/.map-build}"
UPSTREAM_COMMIT="${UPSTREAM_COMMIT:-7adf3bbc34576a3c7e70e069670f404152d88f9e}"

case "$COUNTRY" in
  dk)
    COUNTRY_NAME="Dänemark"
    AREA="denmark"
    LANGUAGES="da,en,de"
    OUTPUT_NAME="denmark.pmtiles"
    ;;
  nl)
    COUNTRY_NAME="Niederlande"
    AREA="netherlands"
    LANGUAGES="nl,en,de"
    OUTPUT_NAME="netherlands.pmtiles"
    ;;
  *)
    echo "Unsupported country: $COUNTRY" >&2
    exit 2
    ;;
esac

SRC="$WORK_ROOT/planetiler-openmaptiles"
OUT="$PWD/build/maps/$COUNTRY"
CACHE="$WORK_ROOT/data"

rm -rf "$SRC"
mkdir -p "$OUT" "$CACHE"

git clone --filter=blob:none https://github.com/openmaptiles/planetiler-openmaptiles.git "$SRC"
git -C "$SRC" checkout "$UPSTREAM_COMMIT"
git -C "$SRC" apply "$PWD/scripts/patches/drivechronik-map.patch"

(
  cd "$SRC"
  ./mvnw -B -ntp -DskipTests=true clean package

  JAR="$(find target -maxdepth 1 -type f -name '*with-deps.jar' -print -quit)"
  test -n "$JAR"

  java -Xmx6g -jar "$JAR" \
    --area="$AREA" \
    --download \
    --download_dir="$CACHE/sources" \
    --tmpdir="$CACHE/tmp-$COUNTRY" \
    --output="$OUT/$OUTPUT_NAME" \
    --force \
    --maxzoom=14 \
    --render_maxzoom=14 \
    --languages="$LANGUAGES" \
    --exclude_layers=poi,mountain_peak,aeroway \
    --output_layerstats=true \
    --layer_stats="$OUT/${OUTPUT_NAME%.pmtiles}.layerstats.tsv.gz"
)

sha256sum "$OUT/$OUTPUT_NAME" | tee "$OUT/$OUTPUT_NAME.sha256"
stat -c '%s' "$OUT/$OUTPUT_NAME" | tee "$OUT/$OUTPUT_NAME.size"

cat > "$OUT/build-info.txt" <<EOF
country=$COUNTRY
countryName=$COUNTRY_NAME
area=$AREA
languages=$LANGUAGES
upstreamCommit=$UPSTREAM_COMMIT
output=$OUTPUT_NAME
EOF

echo "Built $OUT/$OUTPUT_NAME"
