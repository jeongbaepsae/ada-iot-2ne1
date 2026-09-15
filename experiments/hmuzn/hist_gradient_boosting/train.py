#!/usr/bin/env python3
"""Leakage-safe LOSO evaluation of a histogram gradient boosting classifier."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import run_baseline_analysis as baseline  # noqa: E402

FEATURES = ROOT / "results" / "recording_features_3s.csv"
OUTPUT = Path(__file__).with_name("results.csv")
PREDICTIONS = Path(__file__).with_name("predictions.csv")


def make_model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        learning_rate=0.05,
        max_iter=200,
        max_leaf_nodes=15,
        min_samples_leaf=10,
        l2_regularization=1.0,
        class_weight="balanced",
        random_state=42,
    )


def main() -> None:
    frame = pd.read_csv(FEATURES)
    columns = baseline.feature_columns(frame, "B2_time_frequency")
    metrics: list[dict[str, object]] = []
    predictions: list[dict[str, object]] = []

    # Each row is one recording. Holding out subject_id therefore also keeps every
    # recording (and all windows aggregated into it) wholly within one fold.
    for subject in sorted(frame["subject_id"].unique()):
        test = (frame["subject_id"] == subject).to_numpy()
        model = make_model()
        model.fit(frame.loc[~test, columns], frame.loc[~test, "target"])
        probability = model.predict_proba(frame.loc[test, columns])[:, 1]
        score = baseline.score_predictions(
            frame.loc[test, "target"].to_numpy(dtype=int), probability
        )
        metrics.append({"fold": subject, "model": "HistGradientBoosting", **score})
        for index, value in zip(frame.index[test], probability):
            predictions.append(
                {
                    "fold": subject,
                    "recording_id": frame.at[index, "recording_id"],
                    "subject_id": frame.at[index, "subject_id"],
                    "target": int(frame.at[index, "target"]),
                    "probability": float(value),
                    "prediction": int(value >= 0.5),
                }
            )

    result = pd.DataFrame(metrics)
    mean = {
        "fold": "MEAN",
        "model": "HistGradientBoosting",
        **{
            column: result[column].mean()
            for column in ("n_test", "balanced_accuracy", "sensitivity", "specificity", "macro_f1", "auroc", "auprc")
        },
        **{column: result[column].sum() for column in ("tn", "fp", "fn", "tp")},
    }
    pd.concat([result, pd.DataFrame([mean])], ignore_index=True).to_csv(OUTPUT, index=False)
    pd.DataFrame(predictions).to_csv(PREDICTIONS, index=False)
    print(pd.concat([result, pd.DataFrame([mean])], ignore_index=True).to_string(index=False))


if __name__ == "__main__":
    main()
