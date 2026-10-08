#!/usr/bin/env python3

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path


TESLA_OPERATOR = "Tesla Germany GmbH"


def clean(value):
    return (value or "").strip()


def parse_float(value):
    value = clean(value).replace(",", ".")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_int(value):
    value = clean(value)
    if not value:
        return 0
    try:
        return int(float(value.replace(",", ".")))
    except ValueError:
        return 0


def find_header(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")

        for line_no, row in enumerate(reader, 1):
            cells = [clean(x) for x in row]

            required = {
                "Betreiber",
                "Breitengrad",
                "Längengrad",
                "Status",
            }

            if required.issubset(set(cells)):
                return line_no, cells

    raise RuntimeError("BNetzA-Kopfzeile nicht gefunden")


def read_rows(path):
    header_line, header = find_header(path)

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for _ in range(header_line):
            next(f)

        reader = csv.DictReader(
            f,
            delimiter=";",
            fieldnames=header,
        )

        yield from reader


def normalize_text(value):
    return re.sub(r"\s+", " ", clean(value))


def site_key(row, lat, lon):
    """
    Mehrere Ladeeinrichtungen am exakt gleichen Standort werden zu
    einem Kartenpunkt zusammengeführt.

    Koordinaten werden auf 6 Nachkommastellen normalisiert.
    Adresse dient zusätzlich zur Stabilisierung.
    """
    return (
        round(lat, 6),
        round(lon, 6),
        normalize_text(row.get("Straße")).casefold(),
        normalize_text(row.get("Hausnummer")).casefold(),
        normalize_text(row.get("Postleitzahl")).casefold(),
        normalize_text(row.get("Ort")).casefold(),
    )


def connector_values(row):
    result = set()

    for i in range(1, 7):
        value = normalize_text(row.get(f"Steckertypen{i}"))
        if not value:
            continue

        for part in value.split(";"):
            part = clean(part)
            if part:
                result.add(part)

    return result


def best_name(row):
    for field in (
        "Anzeigename (Karte)",
        "Standortbezeichnung",
        "Betreiber",
    ):
        value = normalize_text(row.get(field))
        if value:
            return value

    return "Ladestation"


def stable_id(key):
    raw = "|".join(str(x) for x in key)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def build(input_path):
    sites = {}

    stats = {
        "rows_total": 0,
        "rows_active": 0,
        "rows_invalid_coordinates": 0,
    }

    for row in read_rows(input_path):
        stats["rows_total"] += 1

        if clean(row.get("Status")) != "In Betrieb":
            continue

        stats["rows_active"] += 1

        lat = parse_float(row.get("Breitengrad"))
        lon = parse_float(row.get("Längengrad"))

        if lat is None or lon is None:
            stats["rows_invalid_coordinates"] += 1
            continue

        # Deutschland grob plausibilisieren
        if not (47.0 <= lat <= 56.0 and 5.0 <= lon <= 16.0):
            stats["rows_invalid_coordinates"] += 1
            continue

        key = site_key(row, lat, lon)

        operator = normalize_text(row.get("Betreiber"))
        kind = normalize_text(row.get("Art der Ladeeinrichtung"))

        charging_points = parse_int(row.get("Anzahl Ladepunkte"))
        power = parse_float(
            row.get("Nennleistung Ladeeinrichtung [kW]")
        )

        is_fast = kind == "Schnellladeeinrichtung"
        is_tesla = operator == TESLA_OPERATOR and is_fast

        if key not in sites:
            sites[key] = {
                "lat": lat,
                "lon": lon,
                "names": [],
                "operators": set(),
                "charging_points": 0,
                "max_power_kw": None,
                "is_fast": False,
                "is_supercharger": False,
                "connectors": set(),
                "street": normalize_text(row.get("Straße")),
                "house_number": normalize_text(row.get("Hausnummer")),
                "postcode": normalize_text(row.get("Postleitzahl")),
                "city": normalize_text(row.get("Ort")),
            }

        site = sites[key]

        name = best_name(row)
        if name and name not in site["names"]:
            site["names"].append(name)

        if operator:
            site["operators"].add(operator)

        site["charging_points"] += charging_points
        site["is_fast"] = site["is_fast"] or is_fast
        site["is_supercharger"] = (
            site["is_supercharger"] or is_tesla
        )

        if power is not None:
            if site["max_power_kw"] is None:
                site["max_power_kw"] = power
            else:
                site["max_power_kw"] = max(
                    site["max_power_kw"],
                    power,
                )

        site["connectors"].update(connector_values(row))

    features = []

    counts = {
        "normal": 0,
        "fast": 0,
        "tesla": 0,
    }

    for key in sorted(sites):
        site = sites[key]

        if site["is_supercharger"]:
            minzoom = 8
            counts["tesla"] += 1
        elif site["is_fast"]:
            minzoom = 10
            counts["fast"] += 1
        else:
            minzoom = 12
            counts["normal"] += 1

        operators = sorted(site["operators"])
        connectors = sorted(site["connectors"])

        name = (
            site["names"][0]
            if site["names"]
            else (
                operators[0]
                if operators
                else "Ladestation"
            )
        )

        properties = {
            "id": stable_id(key),
            "name": name,
            "operators": "; ".join(operators),
            "charging_points": site["charging_points"],
            "max_power_kw": site["max_power_kw"],
            "is_fast": site["is_fast"],
            "is_supercharger": site["is_supercharger"],
            "connectors": "; ".join(connectors),
            "street": site["street"],
            "house_number": site["house_number"],
            "postcode": site["postcode"],
            "city": site["city"],
            "source": "Bundesnetzagentur.de",
        }

        feature = {
            "type": "Feature",
            "tippecanoe": {
                "minzoom": minzoom,
                "maxzoom": 14,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [
                    site["lon"],
                    site["lat"],
                ],
            },
            "properties": properties,
        }

        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }, stats, counts


def sha256_file(path):
    h = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)

    return h.hexdigest()


def run(command, cwd=None):
    print()
    prefix = f"(cd {cwd} && " if cwd else ""
    suffix = ")" if cwd else ""
    print("+", prefix + " ".join(str(x) for x in command) + suffix)

    subprocess.run(
        [str(x) for x in command],
        check=True,
        cwd=cwd,
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "BNetzA-Ladesäulenregister vollständig "
            "in PMTiles umwandeln"
        )
    )

    parser.add_argument(
        "input",
        type=Path,
        help="BNetzA CSV",
    )

    parser.add_argument(
        "--build-dir",
        type=Path,
        default=Path("build"),
        help="Build-Verzeichnis (Standard: build)",
    )

    args = parser.parse_args()

    build_dir = args.build_dir
    build_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    geojson = build_dir / "charging-stations.geojson"
    mbtiles = build_dir / "charging-stations.mbtiles"
    pmtiles = build_dir / "charging-stations.pmtiles"

    data, stats, counts = build(args.input)

    with geojson.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    total = len(data["features"])

    print("===== BNETZA =====")
    print(f"CSV-Zeilen:            {stats['rows_total']:,}")
    print(f"In Betrieb:            {stats['rows_active']:,}")
    print(
        "Ungültige Koordinaten:",
        f"{stats['rows_invalid_coordinates']:,}",
    )

    print()
    print("===== STANDORTE =====")
    print(f"Gesamt:                {total:,}")
    print(f"Tesla Supercharger:    {counts['tesla']:,}")
    print(f"Schnelllader sonst:    {counts['fast']:,}")
    print(f"Normallader:           {counts['normal']:,}")

    for path in (mbtiles, pmtiles):
        if path.exists():
            path.unlink()

    print()
    print("===== MBTILES =====")

    run([
        "tippecanoe",
        "-o", mbtiles.name,
        "-l", "charging_station",
        "-Z8",
        "-z14",
        "--force",
        "--no-feature-limit",
        "--no-tile-size-limit",
        geojson.name,
    ], cwd=build_dir)

    print()
    print("===== PMTILES =====")

    run([
        "pmtiles",
        "convert",
        mbtiles.name,
        pmtiles.name,
    ], cwd=build_dir)

    digest = sha256_file(pmtiles)
    size_bytes = pmtiles.stat().st_size

    print()
    print("===== ERGEBNIS =====")
    print(f"GeoJSON:   {geojson}")
    print(f"MBTiles:   {mbtiles}")
    print(f"PMTiles:   {pmtiles}")
    print(f"Features:  {total}")
    print(f"Bytes:     {size_bytes}")
    print(f"MiB:       {size_bytes / 1024 / 1024:.2f}")
    print(f"SHA256:    {digest}")

    print()
    print("===== PMTILES INFO =====")

    run([
        "pmtiles",
        "show",
        pmtiles.name,
    ], cwd=build_dir)


if __name__ == "__main__":
    main()
