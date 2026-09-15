#!/usr/bin/env python3
"""Helper notes for preparing the PADS smartwatch dataset locally.

The raw dataset is large and licensed CC BY-NC-SA 4.0, so this script does not
download or commit data automatically. It prints reproducible commands and
summarises the planned conversion into the repository's common IMU schema.
"""

from __future__ import annotations

import argparse
from pathlib import Path


PHYSIONET_URL = "https://physionet.org/files/parkinsons-disease-smartwatch/1.0.0/"
S3_URL = "s3://physionet-open/parkinsons-disease-smartwatch/1.0.0/"
ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"
PREPARED_DIR = ROOT / "prepared"


def print_download_commands() -> None:
    print("Raw PADS files are intentionally not committed to git.")
    print()
    print("wget:")
    print(f"  mkdir -p {RAW_DIR}")
    print(f"  wget -r -N -c -np -P {RAW_DIR} {PHYSIONET_URL}")
    print()
    print("AWS CLI:")
    print(f"  mkdir -p {RAW_DIR}")
    print(f"  aws s3 sync --no-sign-request {S3_URL} {RAW_DIR}/")


def print_summary() -> None:
    print("Dataset: PADS - Parkinsons Disease Smartwatch dataset v1.0.0")
    print("Source: https://physionet.org/content/parkinsons-disease-smartwatch/1.0.0/")
    print("License: CC BY-NC-SA 4.0")
    print("Participants: 469")
    print("Device: Apple Watch Series 4 on both wrists")
    print("Signals: 3-axis accelerometer in g, 3-axis gyroscope in rad/s")
    print("Sampling: 100 Hz")
    print("Tasks: 11 neurological assessment tasks, 10-20 seconds each")
    print()
    print("Planned common-schema mapping:")
    print("  elapsed_ms = sample_index * 10")
    print("  Accelerometer_X/Y/Z -> acc_x_g/acc_y_g/acc_z_g")
    print("  Gyroscope_X/Y/Z rad/s -> gyro_x_dps/gyro_y_dps/gyro_z_dps")
    print("  no orientation channels -> leave angle_* empty or exclude")
    print("  participant/task/wrist/condition -> manifest metadata")
    print()
    print(f"Local raw directory: {RAW_DIR}")
    print(f"Local prepared directory: {PREPARED_DIR}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PADS dataset preparation helper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("download-commands", help="print local download commands")
    subparsers.add_parser("summary", help="print dataset and conversion summary")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "download-commands":
        print_download_commands()
    elif args.command == "summary":
        print_summary()


if __name__ == "__main__":
    main()
