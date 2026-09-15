#!/usr/bin/env python3
"""Download the PADS smartwatch dataset and convert it to this repository's CSV schema.

PADS (Parkinsons Disease Smartwatch dataset, PhysioNet v1.0.0) records both wrists
with an Apple Watch Series 4 at 100 Hz during 11 standardised movement tasks.

Source      https://physionet.org/content/parkinsons-disease-smartwatch/1.0.0/
DOI         https://doi.org/10.13026/m0w9-zx22
Paper       Varghese et al., npj Parkinsons Dis. 10, 9 (2024)
License     Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International

The raw dataset is about 1.4 GB and is CC BY-NC-SA, so it is NOT committed to this
repository. This script downloads only the files it needs and writes converted CSVs
into ``data/processed/`` which is git-ignored.

IMPORTANT LABEL CAVEAT
----------------------
PADS provides a *participant-level clinical diagnosis*, not a per-recording
tremor annotation. This script therefore derives a weak binary label from the
diagnosis plus the free-text ``disease_comment`` field, and restricts the export
to rest and postural tasks where pathological tremor is expected to dominate.
Every recording it writes carries that derivation in the manifest so the
assumption stays visible downstream. See README.md for the full argument.

Usage
-----
    # smoke test: four participants, downloads a few megabytes
    python data_sources/euno/pads/download_or_prepare.py --limit-subjects 4

    # full strict cohort (81 tremor + 79 healthy participants, rest/postural tasks)
    python data_sources/euno/pads/download_or_prepare.py

    # convert from an already downloaded local copy instead of fetching over HTTP
    python data_sources/euno/pads/download_or_prepare.py \
        --source-dir /path/to/parkinsons-disease-smartwatch/1.0.0

    # inspect the cohort without downloading any time series
    python data_sources/euno/pads/download_or_prepare.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE_URL = "https://physionet.org/files/parkinsons-disease-smartwatch/1.0.0"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "dataset_c_pads"

SAMPLING_RATE_HZ = 100.0
RAD_TO_DEG = 180.0 / math.pi

# The repository's immutable recording schema.
TARGET_COLUMNS = [
    "elapsed_ms",
    "acc_x_g",
    "acc_y_g",
    "acc_z_g",
    "gyro_x_dps",
    "gyro_y_dps",
    "gyro_z_dps",
    "angle_x_deg",
    "angle_y_deg",
    "angle_z_deg",
]

# PADS timeseries column order, confirmed from movement/observation_*.json:
# Time [s], Accelerometer_X/Y/Z [g], Gyroscope_X/Y/Z [rad/s].
PADS_COLUMNS = 7

# Rest and postural tasks. Pathological rest and postural tremor is expected here,
# and voluntary movement does not dominate the signal.
REST_POSTURAL_TASKS = (
    "Relaxed",
    "RelaxedTask",
    "StretchHold",
    "LiftHold",
    "HoldWeight",
)
KINETIC_TASKS = (
    "PointFinger",
    "DrinkGlas",
    "CrossArms",
    "TouchIndex",
    "TouchNose",
)
ALL_TASKS = REST_POSTURAL_TASKS + KINETIC_TASKS + ("Entrainment",)
WRISTS = ("LeftWrist", "RightWrist")

TREMOR_CONDITIONS = ("Parkinson's", "Essential Tremor")
CONTROL_CONDITIONS = ("Healthy",)
# Diagnoses whose tremor status cannot be asserted from the metadata alone.
AMBIGUOUS_CONDITIONS = (
    "Other Movement Disorders",
    "Atypical Parkinsonism",
    "Multiple Sclerosis",
)


def fetch(url: str, destination: Path, force: bool = False) -> Path:
    """Download ``url`` to ``destination`` unless it is already present."""
    if destination.exists() and destination.stat().st_size > 0 and not force:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url, headers={"User-Agent": "ada-iot-2ne1/pads-prepare"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    destination.write_bytes(payload)
    return destination


def load_patient_table(cache_dir: Path, source_dir: Path | None) -> list[dict[str, str]]:
    """Return the 469 participant metadata rows from preprocessed/file_list.csv."""
    relative = "preprocessed/file_list.csv"
    if source_dir is not None:
        path = source_dir / relative
        if not path.exists():
            raise SystemExit(f"Not found in --source-dir: {path}")
    else:
        path = fetch(f"{BASE_URL}/{relative}", cache_dir / "file_list.csv")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def derive_label(row: dict[str, str], cohort: str) -> str | None:
    """Map a PADS participant to ``tremor``, ``non_tremor`` or ``None`` (excluded).

    ``strict``  tremor requires a documented tremor phenotype in ``disease_comment``
                (for example "IPS tremordominant type" or "Essential Tremor").
    ``broad``   every Parkinson's disease and Essential Tremor participant counts
                as tremor, which is noisier because akinetic-rigid Parkinson's
                disease can present with little or no tremor.

    Healthy controls are the negative class in both cohorts. Other movement
    disorders, atypical Parkinsonism and multiple sclerosis are always excluded
    because their tremor status is not decidable from the released metadata.
    """
    condition = row["condition"]
    comment = row["disease_comment"].lower()
    if condition in CONTROL_CONDITIONS:
        return "non_tremor"
    if condition in AMBIGUOUS_CONDITIONS:
        return None
    if condition in TREMOR_CONDITIONS:
        if cohort == "broad":
            return "tremor"
        return "tremor" if "tremor" in comment else None
    return None


def select_cohort(
    patients: list[dict[str, str]], cohort: str, limit: int | None
) -> list[dict[str, str]]:
    selected: list[dict[str, str]] = []
    for row in patients:
        label = derive_label(row, cohort)
        if label is None:
            continue
        selected.append({**row, "derived_label": label})
    selected.sort(key=lambda row: row["id"])
    if limit is not None:
        tremor = [row for row in selected if row["derived_label"] == "tremor"][: limit // 2]
        control = [row for row in selected if row["derived_label"] == "non_tremor"][
            : limit - len(tremor)
        ]
        selected = sorted(tremor + control, key=lambda row: row["id"])
    return selected


def read_pads_timeseries(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            values = [float(value) for value in line.split(",")]
            if len(values) != PADS_COLUMNS:
                raise ValueError(
                    f"{path}:{line_number} has {len(values)} columns, expected {PADS_COLUMNS}"
                )
            rows.append(values)
    if len(rows) < 2:
        raise ValueError(f"{path} has fewer than two samples")
    return rows


def convert_recording(rows: list[list[float]], drop_initial_seconds: float) -> list[list[object]]:
    """Convert PADS samples to the repository schema.

    * ``Time`` seconds become ``elapsed_ms`` re-based to zero.
    * Acceleration is already in g and is copied unchanged.
    * Gyroscope rad/s is converted to deg/s.
    * PADS has no orientation estimate, so the three angle columns are written
      empty. The analysis pipeline only consumes the timestamp, accelerometer and
      gyroscope columns, so this is lossless for every current experiment.
    """
    kept = [row for row in rows if row[0] >= drop_initial_seconds]
    if len(kept) < 2:
        raise ValueError("Dropping the initial seconds left fewer than two samples")
    origin = kept[0][0]
    output: list[list[object]] = []
    for time_s, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z in kept:
        output.append(
            [
                round((time_s - origin) * 1000.0, 4),
                round(acc_x, 8),
                round(acc_y, 8),
                round(acc_z, 8),
                round(gyro_x * RAD_TO_DEG, 8),
                round(gyro_y * RAD_TO_DEG, 8),
                round(gyro_z * RAD_TO_DEG, 8),
                "",
                "",
                "",
            ]
        )
    return output


def write_csv(path: Path, rows: list[list[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(TARGET_COLUMNS)
        writer.writerows(rows)


def timestamp_quality(rows: list[list[object]]) -> dict[str, object]:
    times = [float(row[0]) for row in rows]
    deltas = [right - left for left, right in zip(times, times[1:])]
    positive = sorted(delta for delta in deltas if delta > 0)
    median = positive[len(positive) // 2] if positive else float("nan")
    return {
        "n_rows": len(times),
        "duration_s": round((times[-1] - times[0]) / 1000.0, 6),
        "median_dt_ms": round(median, 6),
        "min_dt_ms": round(min(positive), 6) if positive else "",
        "max_dt_ms": round(max(positive), 6) if positive else "",
        "non_increasing_steps": sum(delta <= 0 for delta in deltas),
        "gaps_over_100ms": sum(delta > 100 for delta in positive),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--cohort",
        choices=("strict", "broad"),
        default="strict",
        help="Label derivation rule (default: strict).",
    )
    parser.add_argument(
        "--tasks",
        choices=("rest_postural", "kinetic", "all"),
        default="rest_postural",
        help="Which PADS movement tasks to export (default: rest_postural).",
    )
    parser.add_argument(
        "--wrists",
        nargs="+",
        choices=WRISTS,
        default=list(WRISTS),
        help="Which wrist recordings to export (default: both).",
    )
    parser.add_argument(
        "--limit-subjects",
        type=int,
        default=None,
        help="Export at most this many participants, class-balanced. Useful for a smoke test.",
    )
    parser.add_argument(
        "--drop-initial-seconds",
        type=float,
        default=0.5,
        help="Drop the leading seconds affected by the watch notification vibration "
        "(default: 0.5, as recommended by the dataset authors).",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="Convert from a local PADS copy instead of downloading over HTTP.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Destination for converted CSVs (default: {DEFAULT_OUTPUT.relative_to(ROOT)}).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=ROOT / "data" / "processed" / "_pads_download_cache",
        help="Where downloaded PADS files are cached.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report the selected cohort and planned downloads, then exit.",
    )
    arguments = parser.parse_args()

    tasks = {
        "rest_postural": REST_POSTURAL_TASKS,
        "kinetic": KINETIC_TASKS,
        "all": ALL_TASKS,
    }[arguments.tasks]

    patients = load_patient_table(arguments.cache_dir, arguments.source_dir)
    cohort = select_cohort(patients, arguments.cohort, arguments.limit_subjects)
    tremor = sum(row["derived_label"] == "tremor" for row in cohort)
    control = len(cohort) - tremor
    planned = len(cohort) * len(tasks) * len(arguments.wrists)

    print(f"PADS cohort rule      : {arguments.cohort}")
    print(f"Participants selected : {len(cohort)} ({tremor} tremor / {control} non_tremor)")
    print(f"Tasks                 : {', '.join(tasks)}")
    print(f"Wrists                : {', '.join(arguments.wrists)}")
    print(f"Recordings to produce : {planned}")

    if arguments.dry_run:
        print("\nDry run, nothing downloaded or written.")
        return

    manifest_rows: list[dict[str, object]] = []
    failures: list[str] = []
    for index, patient in enumerate(cohort, start=1):
        subject_number = patient["id"]
        subject_id = f"pads_{subject_number}"
        label = patient["derived_label"]
        folder_suffix = "tremor" if label == "tremor" else "still"
        for task in tasks:
            for wrist in arguments.wrists:
                name = f"{subject_number}_{task}_{wrist}.txt"
                relative = f"movement/timeseries/{name}"
                try:
                    if arguments.source_dir is not None:
                        source = arguments.source_dir / relative
                        if not source.exists():
                            raise FileNotFoundError(source)
                    else:
                        source = fetch(
                            f"{BASE_URL}/{relative}",
                            arguments.cache_dir / "timeseries" / name,
                        )
                    rows = convert_recording(
                        read_pads_timeseries(source), arguments.drop_initial_seconds
                    )
                except (urllib.error.URLError, OSError, ValueError) as error:
                    failures.append(f"{name}: {error}")
                    continue

                stem = f"pads_{subject_number}_{task}_{wrist}"
                destination = (
                    arguments.output_dir / f"{subject_id}_{folder_suffix}" / f"{stem}.csv"
                )
                write_csv(destination, rows)
                manifest_rows.append(
                    {
                        "recording_id": f"dataset_c:{stem}",
                        "dataset_id": "dataset_c",
                        "subject_id": subject_id,
                        "label": label,
                        "relative_path": destination.relative_to(ROOT).as_posix(),
                        **timestamp_quality(rows),
                        "pads_condition": patient["condition"],
                        "pads_disease_comment": patient["disease_comment"],
                        "pads_task": task,
                        "pads_wrist": wrist,
                        "label_source": f"participant_diagnosis:{arguments.cohort}",
                    }
                )
        if index % 10 == 0 or index == len(cohort):
            print(f"  processed {index}/{len(cohort)} participants", flush=True)

    if not manifest_rows:
        raise SystemExit("No recordings were produced.")

    manifest_path = arguments.output_dir / "manifest_dataset_c.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"\nWrote {len(manifest_rows)} recordings to {arguments.output_dir.relative_to(ROOT)}")
    print(f"Manifest: {manifest_path.relative_to(ROOT)}")
    if failures:
        print(f"\n{len(failures)} file(s) failed:", file=sys.stderr)
        for failure in failures[:20]:
            print(f"  {failure}", file=sys.stderr)


if __name__ == "__main__":
    main()
