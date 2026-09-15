#!/usr/bin/env python3
"""Evaluate the gradient boosting classifier on the PADS dataset alone.

This is the open-data counterpart to ``train.py``. Nothing from ``dataset_a`` or
``dataset_b`` is used: the model is trained and tested only on PADS, so the
question it answers is "does this feature set and model separate real patient
tremor from healthy controls", not "does simulated tremor transfer".

Preprocessing is imported unchanged from ``scripts/run_baseline_analysis.py``
(50 Hz resampling, 3-second windows, recording-level aggregation), so the
features are exactly the ones used for the team's own recordings.

Two differences from ``train.py`` are forced by the dataset itself:

* With 160 participants, leave-one-subject-out would mean 160 refits per model.
  Subject-grouped stratified 5-fold cross-validation is the standard analogue and
  gives the same guarantee that no participant appears in both train and test.
* Parkinsonian tremor is frequently one-sided, and PADS labels the participant,
  not the wrist. Recording-level scoring therefore counts a non-shaking wrist of
  a patient as a miss. A participant-level view is reported alongside, taking the
  maximum probability over that participant's recordings, which matches the
  clinical reading "tremor present in at least one hand".

Usage:
    python experiments/euno/gradient_boosting/train_pads.py
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
# the fixed hyperparameters live in the sibling gradient boosting experiment
sys.path.insert(0, str(ROOT / "experiments" / "euno" / "gradient_boosting"))

import run_baseline_analysis as baseline  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PADS_DIR = ROOT / "data" / "processed" / "dataset_c_pads"
PADS_MANIFEST = PADS_DIR / "manifest_dataset_c.csv"
FEATURE_CACHE = RESULTS / "pads_recording_features_3s.csv"
FEATURE_SETS = ("B1_time", "B2_time_frequency")
CLASSIFIERS = ("LightGBM", "XGBoost")
N_SPLITS = 5
RANDOM_STATE = 42


def build_features(force: bool) -> pd.DataFrame:
    """Extract recording-level features, caching the result."""
    if FEATURE_CACHE.exists() and not force:
        return pd.read_csv(FEATURE_CACHE)
    if not PADS_MANIFEST.exists():
        raise SystemExit(
            f"{PADS_MANIFEST} not found. Run "
            "data_sources/euno/pads/download_or_prepare.py first."
        )
    manifest = pd.read_csv(PADS_MANIFEST)
    print(f"Extracting features from {len(manifest)} PADS recordings ...", flush=True)
    rows: list[dict[str, object]] = []
    for position, (_, row) in enumerate(manifest.iterrows(), start=1):
        features = baseline.recording_features(row)
        features["pads_task"] = row["pads_task"]
        features["pads_wrist"] = row["pads_wrist"]
        features["pads_condition"] = row["pads_condition"]
        rows.append(features)
        if position % 200 == 0 or position == len(manifest):
            print(f"  {position}/{len(manifest)}", flush=True)
    frame = pd.DataFrame(rows)
    RESULTS.mkdir(exist_ok=True)
    frame.to_csv(FEATURE_CACHE, index=False)
    return frame


def evaluate(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Subject-grouped stratified 5-fold cross-validation."""
    import train as gb  # the sibling script holds the fixed hyperparameters

    subjects = frame["subject_id"].to_numpy()
    targets = frame["target"].to_numpy()
    splitter = StratifiedGroupKFold(
        n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE
    )

    metrics: list[dict[str, object]] = []
    predictions: list[dict[str, object]] = []

    for fold, (train_index, test_index) in enumerate(
        splitter.split(frame, targets, groups=subjects), start=1
    ):
        train_mask = np.zeros(len(frame), dtype=bool)
        train_mask[train_index] = True
        test_mask = ~train_mask
        for feature_set in FEATURE_SETS:
            columns = baseline.feature_columns(frame, feature_set)
            for classifier_name in CLASSIFIERS:
                model = gb.build_classifier(classifier_name)
                model.fit(
                    frame.loc[train_mask, columns], frame.loc[train_mask, "target"]
                )
                probability = model.predict_proba(frame.loc[test_mask, columns])[:, 1]
                score = baseline.score_predictions(
                    frame.loc[test_mask, "target"].to_numpy(), probability
                )
                metrics.append(
                    {
                        "level": "recording",
                        "fold": fold,
                        "classifier": classifier_name,
                        "feature_set": feature_set,
                        "n_train_subjects": int(
                            frame.loc[train_mask, "subject_id"].nunique()
                        ),
                        "n_test_subjects": int(
                            frame.loc[test_mask, "subject_id"].nunique()
                        ),
                        **score,
                    }
                )
                for index, value in zip(frame.index[test_mask], probability):
                    predictions.append(
                        {
                            "fold": fold,
                            "classifier": classifier_name,
                            "feature_set": feature_set,
                            "recording_id": frame.at[index, "recording_id"],
                            "subject_id": frame.at[index, "subject_id"],
                            "pads_task": frame.at[index, "pads_task"],
                            "pads_wrist": frame.at[index, "pads_wrist"],
                            "pads_condition": frame.at[index, "pads_condition"],
                            "target": int(frame.at[index, "target"]),
                            "probability": float(value),
                        }
                    )
        print(f"  fold {fold}/{N_SPLITS} done", flush=True)

    return pd.DataFrame(metrics), pd.DataFrame(predictions)


def participant_level(predictions: pd.DataFrame) -> pd.DataFrame:
    """Score one prediction per participant: the maximum over their recordings.

    Parkinsonian tremor is often unilateral and can be intermittent, so a patient
    is counted as detected when any of their recordings crosses the threshold.
    """
    rows: list[dict[str, object]] = []
    grouped = predictions.groupby(["fold", "classifier", "feature_set"])
    for (fold, classifier, feature_set), group in grouped:
        aggregated = group.groupby("subject_id").agg(
            target=("target", "first"), probability=("probability", "max")
        )
        score = baseline.score_predictions(
            aggregated["target"].to_numpy(), aggregated["probability"].to_numpy()
        )
        rows.append(
            {
                "level": "participant",
                "fold": fold,
                "classifier": classifier,
                "feature_set": feature_set,
                **score,
            }
        )
    return pd.DataFrame(rows)


def per_task(predictions: pd.DataFrame) -> pd.DataFrame:
    """Recording-level performance split by movement task."""
    rows: list[dict[str, object]] = []
    grouped = predictions.groupby(["classifier", "feature_set", "pads_task"])
    for (classifier, feature_set, task), group in grouped:
        score = baseline.score_predictions(
            group["target"].to_numpy(), group["probability"].to_numpy()
        )
        rows.append(
            {
                "classifier": classifier,
                "feature_set": feature_set,
                "pads_task": task,
                **score,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["classifier", "feature_set", "balanced_accuracy"], ascending=[True, True, False]
    )


def by_condition(predictions: pd.DataFrame) -> pd.DataFrame:
    """Detection rate per clinical condition, for the best configuration."""
    best = predictions[
        (predictions["classifier"] == "LightGBM")
        & (predictions["feature_set"] == "B2_time_frequency")
    ]
    aggregated = best.groupby(["subject_id", "pads_condition", "target"])[
        "probability"
    ].max().reset_index()
    aggregated["detected"] = (aggregated["probability"] >= 0.5).astype(int)
    summary = aggregated.groupby(["pads_condition", "target"]).agg(
        participants=("subject_id", "nunique"),
        flagged_as_tremor=("detected", "sum"),
        median_probability=("probability", "median"),
    ).reset_index()
    summary["rate"] = (summary["flagged_as_tremor"] / summary["participants"]).round(3)
    return summary


def plot_summary(recording: pd.DataFrame, participant: pd.DataFrame) -> None:
    combined = pd.concat([recording, participant], ignore_index=True)
    summary = (
        combined.groupby(["level", "classifier", "feature_set"])["balanced_accuracy"]
        .mean()
        .reset_index()
    )
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    width = 0.36
    for axis, level, title in zip(
        axes,
        ("recording", "participant"),
        ("Recording level", "Participant level (max over recordings)"),
    ):
        subset = summary[summary["level"] == level].set_index(
            ["classifier", "feature_set"]
        )
        x = np.arange(len(CLASSIFIERS))
        for offset, feature_set in zip((-width / 2, width / 2), FEATURE_SETS):
            values = [
                subset.loc[(classifier, feature_set), "balanced_accuracy"]
                for classifier in CLASSIFIERS
            ]
            bars = axis.bar(x + offset, values, width=width, label=feature_set)
            axis.bar_label(bars, fmt="%.3f", fontsize=8, padding=2)
        axis.set_xticks(x, list(CLASSIFIERS))
        axis.set_ylim(0.5, 1.02)
        axis.axhline(0.5, color="black", linestyle="--", linewidth=1)
        axis.set_title(title)
        axis.set_ylabel("Balanced accuracy")
        axis.legend(loc="lower left", fontsize=9)
    fig.suptitle(
        "PADS only — subject-grouped 5-fold cross-validation (160 participants)",
        fontsize=13,
    )
    fig.tight_layout()
    fig.savefig(HERE / "pads_only_results.png", dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rebuild-features", action="store_true", help="Ignore the feature cache."
    )
    arguments = parser.parse_args()
    warnings.filterwarnings("ignore", message=".*valid feature names.*")

    frame = build_features(arguments.rebuild_features)
    print(
        f"\n{len(frame)} recordings, {frame['subject_id'].nunique()} participants, "
        f"{int(frame['valid_windows'].sum())} valid windows, "
        f"{int(frame['rejected_windows'].sum())} rejected"
    )
    print(frame.groupby("label")["recording_id"].count().to_string())

    recording_metrics, predictions = evaluate(frame)
    participant_metrics = participant_level(predictions)

    all_metrics = pd.concat([recording_metrics, participant_metrics], ignore_index=True)
    all_metrics.to_csv(HERE / "pads_only_results.csv", index=False)
    predictions.to_csv(HERE / "pads_only_predictions.csv", index=False)

    task_table = per_task(predictions)
    task_table.to_csv(HERE / "pads_only_by_task.csv", index=False)
    condition_table = by_condition(predictions)
    condition_table.to_csv(HERE / "pads_only_by_condition.csv", index=False)

    summary = (
        all_metrics.groupby(["level", "classifier", "feature_set"])
        .agg(
            balanced_accuracy_mean=("balanced_accuracy", "mean"),
            balanced_accuracy_std=("balanced_accuracy", "std"),
            sensitivity_mean=("sensitivity", "mean"),
            specificity_mean=("specificity", "mean"),
            macro_f1_mean=("macro_f1", "mean"),
            auroc_mean=("auroc", "mean"),
        )
        .reset_index()
        .round(4)
    )
    summary.to_csv(HERE / "pads_only_summary.csv", index=False)
    plot_summary(recording_metrics, participant_metrics)

    (HERE / "pads_only_summary.json").write_text(
        json.dumps(
            {
                "n_recordings": int(len(frame)),
                "n_participants": int(frame["subject_id"].nunique()),
                "cv": f"StratifiedGroupKFold(n_splits={N_SPLITS}) grouped by participant",
                "results": summary.to_dict(orient="records"),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print("\n=== Summary ===")
    print(summary.to_string(index=False))
    print("\n=== Per movement task (recording level) ===")
    print(
        task_table[
            ["classifier", "feature_set", "pads_task", "balanced_accuracy",
             "sensitivity", "specificity", "auroc"]
        ].round(4).to_string(index=False)
    )
    print("\n=== Per clinical condition (LightGBM B2, participant level) ===")
    print(condition_table.to_string(index=False))
    print(f"\nArtefacts written to {HERE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
