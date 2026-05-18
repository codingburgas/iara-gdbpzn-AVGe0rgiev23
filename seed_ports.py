"""
seed_ports.py — Populates port_location and inspection_location tables.

Run once:
    .venv\\Scripts\\python.exe seed_ports.py

What it does:
1. Inserts ~20 real Bulgarian Black Sea & Danube fishing ports with WGS-84 coords.
2. Generates realistic InspectionLocation rows for existing Inspection records
   that don't already have one (scattered realistically along the Bulgarian coast).
"""

import random
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from run import app
from iara_app import db
from iara_app.models import PortLocation, Inspection, InspectionLocation

# ── 1. Bulgarian fishing ports ─────────────────────────────────────────────────

PORTS = [
    # Black Sea coast (south → north)
    {"name": "Синеморец",    "name_en": "Sinemorets",    "lat": 42.0565, "lng": 27.9769, "region": "Black Sea"},
    {"name": "Царево",       "name_en": "Tsarevo",       "lat": 42.1681, "lng": 27.8490, "region": "Black Sea"},
    {"name": "Китен",        "name_en": "Kiten",         "lat": 42.2303, "lng": 27.7888, "region": "Black Sea"},
    {"name": "Созопол",      "name_en": "Sozopol",       "lat": 42.4172, "lng": 27.6946, "region": "Black Sea"},
    {"name": "Черноморец",   "name_en": "Chernomorets",  "lat": 42.4480, "lng": 27.6500, "region": "Black Sea"},
    {"name": "Бургас",       "name_en": "Burgas",        "lat": 42.5048, "lng": 27.4626, "region": "Black Sea"},
    {"name": "Поморие",      "name_en": "Pomorie",       "lat": 42.5609, "lng": 27.6439, "region": "Black Sea"},
    {"name": "Несебър",      "name_en": "Nessebar",      "lat": 42.6592, "lng": 27.7325, "region": "Black Sea"},
    {"name": "Свети Влас",   "name_en": "Sveti Vlas",    "lat": 42.7025, "lng": 27.7600, "region": "Black Sea"},
    {"name": "Обзор",        "name_en": "Obzor",         "lat": 42.8175, "lng": 27.8806, "region": "Black Sea"},
    {"name": "Бяла",         "name_en": "Byala",         "lat": 42.8700, "lng": 27.9189, "region": "Black Sea"},
    {"name": "Варна",        "name_en": "Varna",         "lat": 43.1851, "lng": 27.9167, "region": "Black Sea"},
    {"name": "Балчик",       "name_en": "Balchik",       "lat": 43.4092, "lng": 28.1597, "region": "Black Sea"},
    {"name": "Каварна",      "name_en": "Kavarna",       "lat": 43.4372, "lng": 28.3388, "region": "Black Sea"},
    {"name": "Шабла",        "name_en": "Shabla",        "lat": 43.5342, "lng": 28.5331, "region": "Black Sea"},
    # Danube
    {"name": "Видин",        "name_en": "Vidin",         "lat": 43.9900, "lng": 22.8710, "region": "Danube"},
    {"name": "Оряхово",      "name_en": "Oryahovo",      "lat": 43.7340, "lng": 23.9590, "region": "Danube"},
    {"name": "Никопол",      "name_en": "Nikopol",       "lat": 43.7069, "lng": 24.8944, "region": "Danube"},
    {"name": "Свищов",       "name_en": "Svishtov",      "lat": 43.6160, "lng": 25.3450, "region": "Danube"},
    {"name": "Русе",         "name_en": "Ruse",          "lat": 43.8564, "lng": 25.9699, "region": "Danube"},
    {"name": "Тутракан",     "name_en": "Tutrakan",      "lat": 44.0487, "lng": 26.6133, "region": "Danube"},
    {"name": "Силистра",     "name_en": "Silistra",      "lat": 44.1148, "lng": 27.2614, "region": "Danube"},
]

# Bounding box for Bulgarian Black Sea EEZ (approximate) — used for inspection scatter
BLACK_SEA_BBOX = {"lat_min": 42.0, "lat_max": 43.6, "lng_min": 27.4, "lng_max": 31.0}
DANUBE_BBOX    = {"lat_min": 43.6, "lat_max": 44.2, "lng_min": 22.8, "lng_max": 27.5}


def seed_ports():
    inserted = 0
    for p in PORTS:
        if PortLocation.query.filter_by(name=p["name"]).first():
            print(f"  skip (exists): {p['name']}")
            continue
        port = PortLocation(
            name    = p["name"],
            name_en = p["name_en"],
            lat     = p["lat"],
            lng     = p["lng"],
            region  = p["region"],
            country = "Bulgaria",
        )
        db.session.add(port)
        inserted += 1
    db.session.commit()
    print(f"  ✓ Inserted {inserted} ports  (skipped {len(PORTS) - inserted} existing)")


def seed_inspection_locations():
    """Add a geo-location to every Inspection that doesn't have one yet."""
    inspections = Inspection.query.all()
    inserted = 0
    skipped  = 0

    for insp in inspections:
        if insp.geo_location:
            skipped += 1
            continue

        # Pick a random bbox — 80% Black Sea, 20% Danube
        bbox = BLACK_SEA_BBOX if random.random() < 0.8 else DANUBE_BBOX
        lat  = round(random.uniform(bbox["lat_min"], bbox["lat_max"]), 6)
        lng  = round(random.uniform(bbox["lng_min"], bbox["lng_max"]), 6)

        loc = InspectionLocation(
            inspection_id = insp.id,
            lat           = lat,
            lng           = lng,
        )
        db.session.add(loc)
        inserted += 1

    db.session.commit()
    print(f"  ✓ Inserted {inserted} inspection locations  (skipped {skipped} existing)")


if __name__ == "__main__":
    with app.app_context():
        print("\n-- Seeding Ports ---------------------------------------------------")
        seed_ports()
        print("\n-- Seeding Inspection Locations ------------------------------------")
        seed_inspection_locations()
        print("\nDone.\n")

