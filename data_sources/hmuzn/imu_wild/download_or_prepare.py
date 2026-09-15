#!/usr/bin/env python3
"""Convert the IMU-Wild pickle to the repository's per-recording CSV schema."""

from __future__ import annotations

import argparse
import csv
import pickle
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Official, trusted IMU-Wild pickle")
    parser.add_argument("output", type=Path, help="Output directory (keep outside git by default)")
    parser.add_argument("--time-unit", choices=("s", "ms"), required=True)
    parser.add_argument("--acc-unit", choices=("g", "m_s2"), required=True)
    args = parser.parse_args()
    if not args.input.is_file():
        parser.error(f"not a file: {args.input}")

    # Pickle can execute code while loading. Only accept the official file obtained
    # through the DOI; never run this converter on an unknown pickle.
    with args.input.open("rb") as handle:
        subjects = pickle.load(handle)  # noqa: S301

    manifest: list[dict[str, object]] = []
    for subject in subjects:
        subject_id = str(subject["subject_id"])
        annotation = subject["annotation"]
        label = "tremor" if int(annotation["sp_expert"]) == 1 else "non_tremor"
        for session_index, values in enumerate(subject["subject_sessions"]):
            values = np.asarray(values, dtype=float)
            if values.ndim != 2 or values.shape[1] != 4:
                raise ValueError(f"subject {subject_id}, session {session_index}: expected N x 4")
            relative = Path(label) / f"subject_{subject_id}_session_{session_index:04d}.csv"
            destination = args.output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            time = values[:, 0] - values[0, 0]
            if len(time) < 2 or np.any(np.diff(time) <= 0):
                raise ValueError(f"subject {subject_id}, session {session_index}: invalid timestamps")
            elapsed_ms = time * 1000.0 if args.time_unit == "s" else time
            acceleration_g = values[:, 1:4] / 9.80665 if args.acc_unit == "m_s2" else values[:, 1:4]
            with destination.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["elapsed_ms", "acc_x_g", "acc_y_g", "acc_z_g"])
                writer.writerows(np.column_stack([elapsed_ms, acceleration_g]))
            manifest.append(
                {
                    "dataset_id": "imu_wild",
                    "subject_id": subject_id,
                    "session_id": session_index,
                    "label": label,
                    "label_scope": "subject",
                    "relative_path": relative.as_posix(),
                    "n_samples": len(values),
                    "pd_status": annotation.get("pd_status", ""),
                    "updrs16": annotation.get("updrs16", ""),
                }
            )

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest[0]))
        writer.writeheader()
        writer.writerows(manifest)
    print(f"converted {len(manifest)} sessions from {len(subjects)} subjects into {args.output}")


if __name__ == "__main__":
    main()
