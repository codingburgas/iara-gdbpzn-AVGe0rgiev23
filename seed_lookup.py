# seed_lookup.py
# ---------------------------------------------------------
# Seeds the Species and GearType lookup tables with
# realistic Black Sea / Bulgarian fisheries data.
#
# Usage:
#   python seed_lookup.py
# ---------------------------------------------------------

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from iara_app import create_app, db
from iara_app.models import Species, GearType


# ── BLACK SEA SPECIES ─────────────────────────────────────────────────────────
SPECIES_DATA = [
    # (name_bg, name_en, scientific_name, min_size_cm, max_size_cm,
    #  season_start, season_end, daily_limit_kg, is_protected, notes)

    # ── Commercial species ──────────────────────────────────────────────────
    ("Калкан",       "Turbot",      "Scophthalmus maximus",    45, None, "01-04", "30-09", None,  False,
     "Most valuable Black Sea flatfish. Minimum size strictly enforced."),

    ("Цаца",         "Sprat",       "Sprattus sprattus",       6,  None, None,    None,    None,  False,
     "Small pelagic schooling fish, major commercial species."),

    ("Хамсия",       "European anchovy", "Engraulis encrasicolus", 8, None, None, None, None, False,
     "Key pelagic species; important for the ecosystem and local fishing economy."),

    ("Кефал",        "Grey mullet", "Mugil cephalus",          25, None, None,    None,    None,  False,
     "Common coastal species. Several sub-species present."),

    ("Паламуд",      "Atlantic bonito", "Sarda sarda",         25, None, "01-07", "30-11", None, False,
     "Migratory pelagic species, seasonal fishery."),

    ("Чернокоп",     "Black scorpionfish", "Scorpaena porcus", 15, None, None,    None,    None,  False,
     "Demersal rocky-habitat species."),

    ("Барбун",       "Red mullet",  "Mullus barbatus",         13, None, None,    None,    None,  False,
     "Important bottom-dwelling species with strict size limits."),

    ("Лефер",        "Bluefish",    "Pomatomus saltatrix",     20, None, "01-06", "30-10", None, False,
     "Highly migratory predatory species."),

    ("Сафрид",       "Horse mackerel", "Trachurus mediterraneus", 15, None, None, None, None, False,
     "Abundant pelagic species in the Black Sea."),

    ("Пясъчна змиорка", "Sand smelt", "Atherina boyeri",       7,  None, None,    None,    2,     False,
     "Coastal species, popular in recreational fishing."),

    ("Бяла риба",    "Pontic shad", "Alosa immaculata",        30, None, "01-04", "31-05", None, False,
     "Migratory anadromous species, fishery restricted during spawning."),

    ("Зарган",       "Garfish",     "Belone belone",           35, None, "01-04", "30-06", None, False,
     "Surface-dwelling species, seasonal appearance."),

    # ── Shellfish / invertebrates ───────────────────────────────────────────
    ("Черна мида",   "Mediterranean mussel", "Mytilus galloprovincialis", 5, None, None, None, None, False,
     "Farmed and wild-harvested. Minimum shell length enforced."),

    ("Рапана",       "Veined rapa whelk", "Rapana venosa",     10, None, None,    None,    None,  False,
     "Invasive predator of native bivalves, commercial harvest encouraged."),

    ("Скарида",      "Shrimp",      "Penaeus spp.",             4,  None, None,    None,    None,  False,
     "Various shrimp species, mainly in trawl by-catch."),

    # ── Protected / endangered ─────────────────────────────────────────────
    ("Есетра",       "Beluga sturgeon", "Huso huso",           None, None, None, None, None, True,
     "Critically endangered. Fully protected — any catch is prohibited. All landings must be reported."),

    ("Морска крава", "Black Sea bottlenose dolphin", "Tursiops truncatus ponticus",
     None, None, None, None, None, True,
     "Strictly protected mammal. By-catch must be immediately reported to IARA."),

    ("Морска свиня", "Harbour porpoise", "Phocoena phocoena relicta",
     None, None, None, None, None, True,
     "Critically endangered Black Sea sub-species. Strictly protected."),

    ("Рибарка",      "Seahorse",    "Hippocampus guttulatus",  None, None, None, None, None, True,
     "Protected species, prohibited to catch, trade or possess."),
]


# ── GEAR TYPES ────────────────────────────────────────────────────────────────
GEAR_DATA = [
    # (code, name, description, mesh_size_required, min_mesh_size_mm, is_legal)

    # ── Trawls ─────────────────────────────────────────────────────────────
    ("OTB",  "Bottom otter trawl",
     "Single-boat bottom trawl with otter boards. Used for demersal species.",
     True, 40, True),

    ("TBB",  "Beam trawl",
     "Trawl spread by a rigid beam, typically used for flatfish and shrimp.",
     True, 40, True),

    ("PTB",  "Pair bottom trawl",
     "Bottom trawl operated by two vessels. High efficiency, strictly regulated.",
     True, 40, True),

    ("OTM",  "Midwater otter trawl",
     "Pelagic trawl targeting mid-water schooling fish (anchovy, sprat).",
     True, 10, True),

    ("DRB",  "Dredge",
     "Gear dragged along the seabed to collect shellfish (mussels, razor clams).",
     False, None, True),

    # ── Seines ─────────────────────────────────────────────────────────────
    ("PS",   "Purse seine",
     "Large net encircling a school of fish from above, closed at the bottom. Used for pelagic species.",
     True, 10, True),

    ("SB",   "Boat seine",
     "Shore or boat-deployed seine net for coastal demersal fish.",
     True, 30, True),

    # ── Gillnets & entangling nets ──────────────────────────────────────────
    ("GNS",  "Set bottom gillnet",
     "Stationary gillnet anchored on the seabed. Used for demersal species.",
     True, 90, True),

    ("GND",  "Drifting gillnet",
     "Gillnet that drifts with the current. Regulated for pelagic species.",
     True, 50, True),

    ("GTR",  "Trammel net",
     "Triple-layer net with inner fine mesh and outer larger mesh. Highly selective.",
     True, 90, True),

    # ── Longlines & hooks ─────────────────────────────────────────────────
    ("LLS",  "Set longline",
     "A main line with multiple branch lines and baited hooks, set on the seabed.",
     False, None, True),

    ("LLD",  "Drifting longline",
     "Longline suspended in the water column, used for pelagic species.",
     False, None, True),

    ("FPO",  "Fish pot / trap",
     "Cage-type traps deployed on the seabed for crustaceans and fish.",
     False, None, True),

    # ── Recreational gear ─────────────────────────────────────────────────
    ("LHP",  "Hand line and pole",
     "Rod and line fishing. Standard recreational fishing method.",
     False, None, True),

    ("SV",   "Cast net",
     "Circular throw net for shallow coastal areas.",
     True, 14, True),

    # ── Prohibited gear ───────────────────────────────────────────────────
    ("ELF",  "Electric fishing device",
     "Any device using electric current to stun or attract fish. Prohibited in all waters.",
     False, None, False),

    ("EXP",  "Explosive device",
     "Use of explosives or chemical substances to catch fish. Strictly prohibited.",
     False, None, False),

    ("TSP",  "Towed seine on spawning grounds",
     "Seine nets towed across designated spawning or nursery areas. Prohibited during closed season.",
     False, None, False),

    ("DNS",  "Dynamite net",
     "Use of underwater concussion methods. Prohibited.",
     False, None, False),

    ("UWT",  "Undersize-mesh trawl",
     "Trawl with mesh size below the legal minimum. Prohibited.",
     True, 0, False),
]


def seed_lookup():
    app = create_app()
    with app.app_context():
        _seed_species()
        _seed_gear_types()
        db.session.commit()
        print("\n✅  Lookup data seeded successfully.")


def _seed_species():
    added = 0
    skipped = 0
    for row in SPECIES_DATA:
        (name_bg, name_en, sci, min_sz, max_sz,
         ss, se, daily, protected, notes) = row

        if Species.query.filter_by(name_bg=name_bg).first():
            skipped += 1
            continue

        sp = Species(
            name_bg=name_bg,
            name_en=name_en,
            scientific_name=sci,
            min_size_cm=min_sz,
            max_size_cm=max_sz,
            season_start=ss,
            season_end=se,
            daily_limit_kg=daily,
            is_protected=protected,
            notes=notes,
        )
        db.session.add(sp)
        added += 1

    db.session.flush()
    print(f"  Species:    {added} added, {skipped} already existed.")


def _seed_gear_types():
    added = 0
    skipped = 0
    for row in GEAR_DATA:
        code, name, desc, mesh_req, min_mesh, legal = row

        if GearType.query.filter_by(code=code).first():
            skipped += 1
            continue

        gt = GearType(
            code=code,
            name=name,
            description=desc,
            mesh_size_required=mesh_req,
            min_mesh_size_mm=min_mesh,
            is_legal=legal,
        )
        db.session.add(gt)
        added += 1

    db.session.flush()
    print(f"  Gear types: {added} added, {skipped} already existed.")


if __name__ == "__main__":
    seed_lookup()
