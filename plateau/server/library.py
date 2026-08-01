"""
library.py — the built-in exercise catalog and split-template reference data.

Kept separate from seed.py so the (long, mechanical) reference data doesn't bury
the seeding logic. The engine reads `movement_pattern` (for staleness), so every
entry is tagged; equipment and is_compound drive library search/filtering.

LIBRARY rows: (slug, name, muscle_group, movement_pattern, equipment, is_compound)
Movement patterns: horizontal_push, incline_push, vertical_push, horizontal_pull,
vertical_pull, hinge, squat, lunge, carry, core, isolation.
"""

from __future__ import annotations

LIBRARY = [
    # ---- Chest ----
    ("bench-press", "Bench Press", "chest", "horizontal_push", "barbell", True),
    ("incline-bench-press", "Incline Bench Press", "chest", "incline_push", "barbell", True),
    ("dumbbell-bench-press", "Dumbbell Bench Press", "chest", "horizontal_push", "dumbbell", True),
    ("incline-dumbbell-press", "Incline Dumbbell Press", "chest", "incline_push", "dumbbell", True),
    ("machine-chest-press", "Machine Chest Press", "chest", "horizontal_push", "machine", True),
    ("cable-fly", "Cable Fly", "chest", "isolation", "cable", False),
    ("pec-deck", "Pec Deck", "chest", "isolation", "machine", False),
    ("push-up", "Push-Up", "chest", "horizontal_push", "bodyweight", True),
    ("dip", "Chest Dip", "chest", "vertical_push", "bodyweight", True),
    # ---- Back ----
    ("barbell-row", "Barbell Row", "back", "horizontal_pull", "barbell", True),
    ("pendlay-row", "Pendlay Row", "back", "horizontal_pull", "barbell", True),
    ("dumbbell-row", "Dumbbell Row", "back", "horizontal_pull", "dumbbell", True),
    ("seated-cable-row", "Seated Cable Row", "back", "horizontal_pull", "cable", True),
    ("chest-supported-row", "Chest-Supported Row", "back", "horizontal_pull", "machine", True),
    ("lat-pulldown", "Lat Pulldown", "back", "vertical_pull", "cable", True),
    ("pull-up", "Pull-Up", "back", "vertical_pull", "bodyweight", True),
    ("chin-up", "Chin-Up", "back", "vertical_pull", "bodyweight", True),
    ("straight-arm-pulldown", "Straight-Arm Pulldown", "back", "isolation", "cable", False),
    ("face-pull", "Face Pull", "back", "horizontal_pull", "cable", False),
    # ---- Shoulders ----
    ("overhead-press", "Overhead Press", "shoulders", "vertical_push", "barbell", True),
    ("push-press", "Push Press", "shoulders", "vertical_push", "barbell", True),
    ("seated-dumbbell-press", "Seated Dumbbell Press", "shoulders", "vertical_push", "dumbbell", True),
    ("arnold-press", "Arnold Press", "shoulders", "vertical_push", "dumbbell", True),
    ("machine-shoulder-press", "Machine Shoulder Press", "shoulders", "vertical_push", "machine", True),
    ("lateral-raise", "Lateral Raise", "shoulders", "isolation", "dumbbell", False),
    ("cable-lateral-raise", "Cable Lateral Raise", "shoulders", "isolation", "cable", False),
    ("rear-delt-fly", "Rear Delt Fly", "shoulders", "isolation", "dumbbell", False),
    ("front-raise", "Front Raise", "shoulders", "isolation", "dumbbell", False),
    # ---- Quads ----
    ("back-squat", "Back Squat", "quads", "squat", "barbell", True),
    ("front-squat", "Front Squat", "quads", "squat", "barbell", True),
    ("hack-squat", "Hack Squat", "quads", "squat", "machine", True),
    ("leg-press", "Leg Press", "quads", "squat", "machine", True),
    ("goblet-squat", "Goblet Squat", "quads", "squat", "dumbbell", True),
    ("bulgarian-split-squat", "Bulgarian Split Squat", "quads", "lunge", "dumbbell", True),
    ("walking-lunge", "Walking Lunge", "quads", "lunge", "dumbbell", True),
    ("leg-extension", "Leg Extension", "quads", "isolation", "machine", False),
    # ---- Hamstrings ----
    ("deadlift", "Deadlift", "hamstrings", "hinge", "barbell", True),
    ("romanian-deadlift", "Romanian Deadlift", "hamstrings", "hinge", "barbell", True),
    ("sumo-deadlift", "Sumo Deadlift", "hamstrings", "hinge", "barbell", True),
    ("stiff-leg-deadlift", "Stiff-Leg Deadlift", "hamstrings", "hinge", "dumbbell", True),
    ("lying-leg-curl", "Lying Leg Curl", "hamstrings", "isolation", "machine", False),
    ("seated-leg-curl", "Seated Leg Curl", "hamstrings", "isolation", "machine", False),
    ("nordic-curl", "Nordic Curl", "hamstrings", "isolation", "bodyweight", False),
    # ---- Glutes ----
    ("hip-thrust", "Hip Thrust", "glutes", "hinge", "barbell", True),
    ("glute-bridge", "Glute Bridge", "glutes", "hinge", "barbell", True),
    ("cable-pull-through", "Cable Pull-Through", "glutes", "hinge", "cable", False),
    ("kettlebell-swing", "Kettlebell Swing", "glutes", "hinge", "dumbbell", True),
    # ---- Biceps ----
    ("barbell-curl", "Barbell Curl", "biceps", "isolation", "barbell", False),
    ("dumbbell-curl", "Dumbbell Curl", "biceps", "isolation", "dumbbell", False),
    ("hammer-curl", "Hammer Curl", "biceps", "isolation", "dumbbell", False),
    ("incline-dumbbell-curl", "Incline Dumbbell Curl", "biceps", "isolation", "dumbbell", False),
    ("preacher-curl", "Preacher Curl", "biceps", "isolation", "machine", False),
    ("cable-curl", "Cable Curl", "biceps", "isolation", "cable", False),
    # ---- Triceps ----
    ("close-grip-bench-press", "Close-Grip Bench Press", "triceps", "horizontal_push", "barbell", True),
    ("triceps-pushdown", "Triceps Pushdown", "triceps", "isolation", "cable", False),
    ("overhead-triceps-extension", "Overhead Triceps Extension", "triceps", "isolation", "dumbbell", False),
    ("skull-crusher", "Skull Crusher", "triceps", "isolation", "barbell", False),
    ("triceps-dip", "Triceps Dip", "triceps", "vertical_push", "bodyweight", True),
    # ---- Calves ----
    ("standing-calf-raise", "Standing Calf Raise", "calves", "isolation", "machine", False),
    ("seated-calf-raise", "Seated Calf Raise", "calves", "isolation", "machine", False),
    ("leg-press-calf-raise", "Leg Press Calf Raise", "calves", "isolation", "machine", False),
    # ---- Core ----
    ("hanging-leg-raise", "Hanging Leg Raise", "core", "core", "bodyweight", False),
    ("cable-crunch", "Cable Crunch", "core", "core", "cable", False),
    ("plank", "Plank", "core", "core", "bodyweight", False),
    ("ab-wheel-rollout", "Ab Wheel Rollout", "core", "core", "bodyweight", False),
    ("russian-twist", "Russian Twist", "core", "core", "bodyweight", False),
    # ---- Traps / forearms / carries ----
    ("barbell-shrug", "Barbell Shrug", "traps", "isolation", "barbell", False),
    ("dumbbell-shrug", "Dumbbell Shrug", "traps", "isolation", "dumbbell", False),
    ("farmers-carry", "Farmer's Carry", "traps", "carry", "dumbbell", True),
    ("wrist-curl", "Wrist Curl", "forearms", "isolation", "dumbbell", False),
    ("reverse-curl", "Reverse Curl", "forearms", "isolation", "barbell", False),
]

# Split templates. Each day lists (exercise_slug, target_sets, rep_low, rep_high).
TEMPLATES = {
    "full-body": {
        "name": "Full Body",
        "description": "One session hitting everything; run 2-3x/week.",
        "days": [
            ("Full Body", [
                ("back-squat", 3, 5, 8), ("bench-press", 3, 5, 8),
                ("barbell-row", 3, 6, 10), ("overhead-press", 3, 6, 10),
                ("romanian-deadlift", 3, 8, 12), ("barbell-curl", 2, 10, 15),
            ]),
        ],
    },
    "upper-lower": {
        "name": "Upper / Lower",
        "description": "Two days; run each twice a week for 4 sessions.",
        "days": [
            ("Upper", [
                ("bench-press", 3, 5, 8), ("barbell-row", 3, 6, 10),
                ("overhead-press", 3, 6, 10), ("lat-pulldown", 3, 8, 12),
                ("lateral-raise", 3, 12, 20), ("barbell-curl", 2, 10, 15),
            ]),
            ("Lower", [
                ("back-squat", 3, 5, 8), ("romanian-deadlift", 3, 6, 10),
                ("leg-press", 3, 10, 15), ("lying-leg-curl", 3, 10, 15),
                ("standing-calf-raise", 4, 10, 15),
            ]),
        ],
    },
    "ppl": {
        "name": "Push / Pull / Legs",
        "description": "Three days; run once or twice through per week.",
        "days": [
            ("Push", [
                ("bench-press", 3, 5, 8), ("overhead-press", 3, 6, 10),
                ("incline-dumbbell-press", 3, 8, 12), ("lateral-raise", 3, 12, 20),
                ("triceps-pushdown", 3, 10, 15),
            ]),
            ("Pull", [
                ("barbell-row", 3, 6, 10), ("lat-pulldown", 3, 8, 12),
                ("face-pull", 3, 12, 20), ("barbell-curl", 3, 10, 15),
                ("hammer-curl", 2, 10, 15),
            ]),
            ("Legs", [
                ("back-squat", 3, 5, 8), ("romanian-deadlift", 3, 6, 10),
                ("leg-press", 3, 10, 15), ("lying-leg-curl", 3, 10, 15),
                ("standing-calf-raise", 4, 10, 15),
            ]),
        ],
    },
    "ppl-ul": {
        "name": "Push / Pull / Legs / Upper / Lower",
        "description": "Five days: a PPL block plus an upper and a lower day.",
        "days": [
            ("Push", [
                ("bench-press", 4, 4, 6), ("overhead-press", 3, 6, 10),
                ("incline-dumbbell-press", 3, 8, 12), ("triceps-pushdown", 3, 10, 15),
            ]),
            ("Pull", [
                ("barbell-row", 4, 5, 8), ("pull-up", 3, 6, 10),
                ("face-pull", 3, 12, 20), ("barbell-curl", 3, 10, 15),
            ]),
            ("Legs", [
                ("back-squat", 4, 4, 6), ("romanian-deadlift", 3, 6, 10),
                ("leg-extension", 3, 12, 15), ("standing-calf-raise", 4, 10, 15),
            ]),
            ("Upper", [
                ("incline-bench-press", 3, 6, 10), ("seated-cable-row", 3, 8, 12),
                ("lateral-raise", 4, 12, 20), ("hammer-curl", 3, 10, 15),
            ]),
            ("Lower", [
                ("front-squat", 3, 6, 10), ("hip-thrust", 3, 8, 12),
                ("lying-leg-curl", 3, 10, 15), ("seated-calf-raise", 4, 12, 20),
            ]),
        ],
    },
    "classic-5": {
        "name": "Classic 5-Day",
        "description": "One muscle focus per day: chest, back, legs, shoulders, arms.",
        "days": [
            ("Chest", [
                ("bench-press", 4, 5, 8), ("incline-dumbbell-press", 3, 8, 12),
                ("cable-fly", 3, 12, 15), ("dip", 3, 8, 12),
            ]),
            ("Back", [
                ("barbell-row", 4, 5, 8), ("lat-pulldown", 3, 8, 12),
                ("seated-cable-row", 3, 10, 12), ("face-pull", 3, 12, 20),
            ]),
            ("Legs", [
                ("back-squat", 4, 5, 8), ("romanian-deadlift", 3, 6, 10),
                ("leg-press", 3, 10, 15), ("standing-calf-raise", 4, 10, 15),
            ]),
            ("Shoulders", [
                ("overhead-press", 4, 5, 8), ("lateral-raise", 4, 12, 20),
                ("rear-delt-fly", 3, 12, 20), ("barbell-shrug", 3, 10, 15),
            ]),
            ("Arms", [
                ("barbell-curl", 4, 8, 12), ("skull-crusher", 4, 8, 12),
                ("hammer-curl", 3, 10, 15), ("triceps-pushdown", 3, 10, 15),
            ]),
        ],
    },
}
