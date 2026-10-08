"""Regenerate offline golden vectors by executing the pinned OFF Perl algorithm.

Run from any directory with Python and Perl installed. Downloads only source at
an immutable revision; application code is never imported to produce expectations.
OFF Product Opener is AGPL-3.0-or-later, Copyright Association Open Food Facts.
"""

import json
from pathlib import Path
import random
import subprocess
import urllib.request

REVISION = "b1af9a0b17e3db046b088a4e04f8daebc2594772"
BASE = f"https://raw.githubusercontent.com/openfoodfacts/openfoodfacts-server/{REVISION}"
TARGET = Path(__file__).resolve().parents[1] / "tests/fixtures/nutriscore/local-2023.json"


def generate():
    """Run the actual upstream 2023 functions, with only their module imports removed."""
    source = (
        urllib.request.urlopen(f"{BASE}/lib/ProductOpener/Nutriscore.pm", timeout=30)
        .read()
        .decode()
    )
    numbers = (
        urllib.request.urlopen(f"{BASE}/lib/ProductOpener/Numbers.pm", timeout=30).read().decode()
    )
    algorithm = source[
        source.index("sub compute_nutriscore_score_and_grade_2023 (") : source.index(
            "%points_thresholds ="
        )
    ]
    rounding = numbers[numbers.index("sub round_to_max_decimal_places (") : numbers.rindex("1;")]
    runner = (
        "use v5.36;\n"
        + rounding
        + algorithm
        + """
my $cases = CASES;
foreach my $data (@$cases) {
    my ($score, $grade) = compute_nutriscore_score_and_grade_2023($data);
    print join("\\t", $score, uc($grade), map {
        join(",", map { join(":", @{$_}{qw(id value unit points points_max)}) } @{$data->{components}{$_}})
    } qw(negative positive)), "\\n";
}
"""
    )
    rows = []
    rng = random.Random(2023)
    for category in ("en:meals", "en:cheeses", "en:fats"):
        for index in range(40):
            fat = rng.uniform(1, 100)
            rows.append(
                {
                    "nutrients": {
                        "energy_kj": rng.uniform(0, 4000),
                        "sugars": rng.uniform(0, 60),
                        "saturated_fat": rng.uniform(0, fat),
                        "fat": fat,
                        "salt": rng.uniform(0, 5),
                        "fiber": rng.uniform(0, 12),
                        "proteins": rng.uniform(0, 25),
                    },
                    "category": category,
                    "plant_percent": rng.uniform(0, 100),
                    "red_meat_percent": (0, 10, 10.01, 100)[index % 4],
                }
            )
    # Exact thresholds and their immediate neighbours, including the protein gate.
    base = {
        "energy_kj": 335,
        "sugars": 3.4,
        "saturated_fat": 1,
        "fat": 10,
        "salt": 0.2,
        "fiber": 3,
        "proteins": 2.4,
    }
    boundaries = {
        "energy_kj": [335, 3350],
        "sugars": [3.4, 6.8, 51],
        "saturated_fat": [1, 10],
        "salt": [0.2, 4],
        "fiber": [3, 4.1, 7.4],
        "proteins": [2.4, 17],
        "plant_percent": [40, 60, 80],
        "red_meat_percent": [10],
    }
    for key, values in boundaries.items():
        for value in values:
            for delta in (-0.001, 0, 0.001):
                row = {
                    "nutrients": base.copy(),
                    "category": "en:meals",
                    "plant_percent": 0,
                    "red_meat_percent": 0,
                }
                (row if key.endswith("percent") else row["nutrients"])[key] = value + delta
                rows.append(row)
    for ratio in (0, 9.94, 9.95, 10, 15.94, 15.95, 16, 64, 100):
        rows.append(
            {
                "nutrients": {**base, "fat": 100, "saturated_fat": ratio},
                "category": "en:fats",
                "plant_percent": 0,
                "red_meat_percent": 0,
            }
        )
    inputs = []
    for row in rows:
        nutrients = row["nutrients"]
        # Food.pm category preprocessing; our oracle executes the upstream core.
        inputs.append(
            {
                **nutrients,
                "energy": nutrients["energy_kj"],
                "fruits_vegetables_legumes": row["plant_percent"],
                "is_cheese": int(row["category"] == "en:cheeses"),
                "is_fat_oil_nuts_seeds": int(row["category"] == "en:fats"),
                "is_red_meat_product": int(row["red_meat_percent"] > 10),
                "energy_from_saturated_fat": nutrients["saturated_fat"] * 37,
                "saturated_fat_ratio": round(
                    nutrients["saturated_fat"] / nutrients["fat"] * 100, 1
                ),
            }
        )
    literals = (
        "["
        + ",".join(
            "{" + ",".join(f'"{key}"=>{value}' for key, value in row.items()) + "}"
            for row in inputs
        )
        + "]"
    )
    output = subprocess.run(
        ["perl", "-e", runner.replace("CASES", literals)], text=True, capture_output=True
    )
    if output.returncode:
        raise RuntimeError(output.stderr)
    expected = []
    for line in output.stdout.splitlines():
        score, grade, negative, positive = line.split("\t")
        components = {}
        for kind, raw in (("negative", negative), ("positive", positive)):
            components[kind] = []
            for part in raw.split(","):
                name, value, unit, points, maximum = part.split(":")
                components[kind].append(
                    {
                        "id": name,
                        "value": float(value),
                        "unit": unit,
                        "points": int(points),
                        "points_max": int(maximum),
                    }
                )
        expected.append({"score": int(score), "grade": grade, "components": components})
    artifact = {
        "source": f"{BASE}/lib/ProductOpener/Nutriscore.pm",
        "revision": REVISION,
        "cases": [
            {"input": row, "expected": result} for row, result in zip(rows, expected, strict=True)
        ],
    }
    TARGET.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    print(f"Generated {len(rows)} reference cases in {TARGET}")


if __name__ == "__main__":
    generate()
