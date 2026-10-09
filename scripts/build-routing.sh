#!/usr/bin/env bash
set -euo pipefail

COUNTRY="${1:-dk}"
WORK_ROOT="${WORK_ROOT:-$PWD/.routing-build}"
VALHALLA_IMAGE="${VALHALLA_IMAGE:-ghcr.io/valhalla/valhalla-scripted:3.8.0}"

case "$COUNTRY" in
  dk)
    COUNTRY_NAME="Dänemark"
    PBF_URL="https://download.geofabrik.de/europe/denmark-latest.osm.pbf"
    PBF_NAME="denmark-latest.osm.pbf"
    ;;
  *)
    echo "Unsupported country: $COUNTRY" >&2
    exit 2
    ;;
esac

OUT="$PWD/build/routing/$COUNTRY"
rm -rf "$OUT"
mkdir -p "$OUT" "$WORK_ROOT"

echo "Downloading $PBF_URL"
curl -fL --retry 3 --retry-delay 5 "$PBF_URL" -o "$OUT/$PBF_NAME"

echo "Generating Valhalla configuration"
docker run --rm   --entrypoint /bin/bash   -v "$OUT:/custom_files"   "$VALHALLA_IMAGE"   -lc 'valhalla_build_config     --mjolnir-tile-dir /custom_files/valhalla_tiles     --mjolnir-tile-extract /custom_files/valhalla_tiles.tar     --mjolnir-timezone /custom_files/timezones.sqlite     --mjolnir-admin /custom_files/admins.sqlite     > /custom_files/valhalla.json'

python3 - "$OUT/valhalla.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
cfg = json.loads(path.read_text())

mj = cfg.setdefault("mjolnir", {})
mj.update({
    "max_cache_size": 1000000000,
    "id_table_size": 1300000000,
    "use_lru_mem_cache": False,
    "lru_mem_cache_hard_control": False,
    "use_simple_mem_cache": False,
    "concurrency": "2",
    "hierarchy": True,
    "shortcuts": True,
    "keep_all_osm_node_ids": False,
    "keep_osm_node_ids": False,
    "include_platforms": False,
    "include_driveways": True,
    "include_construction": False,
    "include_bicycle": False,
    "include_pedestrian": False,
    "include_driving": True,
    "import_bike_share_stations": False,
    "global_synchronized_cache": False,
    "max_concurrent_reader_users": 1,
    "reclassify_links": True,
})

dp = mj.setdefault("data_processing", {})
dp.update({
    "infer_internal_intersections": True,
    "infer_turn_channels": True,
    "apply_country_overrides": True,
    "grid_divisions_within_tile": 32,
    "use_admin_db": True,
    "use_direction_on_ways": False,
    "allow_alt_name": False,
    "use_urban_tag": False,
    "use_rest_area": False,
    "scan_tar": False,
    "build_bounding_circles": True,
})

path.write_text(json.dumps(cfg, indent=2) + "\n")
PY

echo "Building Valhalla routing graph"
docker run --rm   -v "$OUT:/custom_files"   -e use_tiles_ignore_pbf=False   -e force_rebuild=True   -e build_admins=True   -e build_time_zones=True   -e build_tar=True   -e serve_tiles=False   -e build_elevation=False   -e build_transit=False   -e update_existing_config=True   -e use_default_speeds_config=True   -e server_threads=2   "$VALHALLA_IMAGE"   build_tiles

test -s "$OUT/valhalla_tiles.tar"

sha256sum "$OUT/valhalla_tiles.tar" | tee "$OUT/valhalla_tiles.tar.sha256"
stat -c '%s' "$OUT/valhalla_tiles.tar" | tee "$OUT/valhalla_tiles.tar.size"

cat > "$OUT/build-info.txt" <<EOF
country=$COUNTRY
countryName=$COUNTRY_NAME
pbfUrl=$PBF_URL
valhallaImage=$VALHALLA_IMAGE
output=valhalla_tiles.tar
EOF

mkdir -p "$OUT/release"
rm -f "$OUT/release/"*

SIZE="$(stat -c '%s' "$OUT/valhalla_tiles.tar")"
LIMIT=1073741824

if [ "$SIZE" -gt "$LIMIT" ]; then
  split -b "$LIMIT" -d -a 2     "$OUT/valhalla_tiles.tar"     "$OUT/release/valhalla_tiles.tar.part"
else
  cp "$OUT/valhalla_tiles.tar" "$OUT/release/valhalla_tiles.tar"
fi

for f in "$OUT"/release/*; do
  sha256sum "$f"
  stat -c '%n %s bytes' "$f"
done

echo "Built routing package in $OUT"
