#!/usr/bin/env python3
"""Gradient boosting baselines (LightGBM, XGBoost) for simulated-tremor detection.

The preprocessing and evaluation rules are inherited unchanged from
``scripts/run_baseline_analysis.py`` so that this model is directly comparable to
the existing Logistic Regression, RBF-SVM and Random Forest baselines:

* 50 Hz linear resampling of every recording;
* 3-second windows with 50 percent overlap, windows containing an original
  timestamp gap above 100 ms are rejected;
* per-window accelerometer and gyroscope time and spectral features, aggregated
  to recording level as median and IQR;
* recording-level classification, so windows of one recording are never split
  across train and test;
* Leave-One-Subject-Out over the six participants, plus both cross-dataset
  directions.

Hyperparameters are fixed a priori and are never tuned on a test fold.
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
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import run_baseline_analysis as baseline  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
FEATURES = RESULTS / "recording_features_3s.csv"
FEATURE_SETS = ("B1_time", "B2_time_frequency")
CLASSIFIERS = ("LightGBM", "XGBoost")
RANDOM_STATE = 42


def build_classifier(name: str):
    """Return a fixed, untuned gradient boosting pipeline.

    The parameters are deliberately conservative: with 220 recordings and only
    about 183 training recordings per LOSO fold, shallow trees with a low
    learning rate and column/row subsampling are the defensible default.
    """
    if name == "LightGBM":
        from lightgbm import LGBMClassifier

        return make_pipeline(
            StandardScaler(),
            LGBMClassifier(
                n_estimators=300,
                learning_rate=0.05,
                num_leaves=15,
                max_depth=4,
                min_child_samples=5,
                subsample=0.8,
                subsample_freq=1,
                colsample_bytree=0.8,
                reg_lambda=1.0,
                class_weight="balanced",
                random_state=RANDOM_STATE,
                n_jobs=-1,
                verbose=-1,
            ),
        )
    if name == "XGBoost":
        from xgboost import XGBClassifier

        return make_pipeline(
            StandardScaler(),
            XGBClassifier(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=3,
                min_child_weight=1.0,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_lambda=1.0,
                objective="binary:logistic",
                eval_metric="logloss",
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
        )
    raise ValueError(f"Unknown classifier: {name}")


def ensure_features() -> pd.DataFrame:
    """Load recording-level features, regenerating them from raw data if needed."""
    if not FEATURES.exists():
        print(f"{FEATURES.name} not found, rebuilding features from data/raw ...")
        manifest = pd.read_csv(ROOT / "data" / "manifest.csv")
        frame = pd.DataFrame(
            [baseline.recording_features(row) for _, row in manifest.iterrows()]
        )
        RESULTS.mkdir(exist_ok=True)
        frame.to_csv(FEATURES, index=False)
        return frame
    return pd.read_csv(FEATURES)


def fit_and_score(
    frame: pd.DataFrame,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    feature_set: str,
    classifier_name: str,
) -> tuple[dict[str, float | int], np.ndarray, pd.Series]:
    columns = baseline.feature_columns(frame, feature_set)
    classifier = build_classifier(classifier_name)
    classifier.fit(frame.loc[train_mask, columns], frame.loc[train_mask, "target"])
    probability = classifier.predict_proba(frame.loc[test_mask, columns])[:, 1]
    score = baseline.score_predictions(
        frame.loc[test_mask, "target"].to_numpy(), probability
    )
    estimator = classifier[-1]
    importance = pd.Series(
        estimator.feature_importances_, index=columns, dtype=float
    )
    return score, probability, importance


def evaluate(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metrics: list[dict[str, object]] = []
    predictions: list[dict[str, object]] = []
    importances: list[dict[str, object]] = []

    folds: list[tuple[str, str, np.ndarray, np.ndarray]] = []
    for subject in sorted(frame["subject_id"].unique()):
        test_mask = (frame["subject_id"] == subject).to_numpy()
        folds.append(("LOSO", subject, ~test_mask, test_mask))
    for train_dataset, test_dataset in (
        ("dataset_a", "dataset_b"),
        ("dataset_b", "dataset_a"),
    ):
        folds.append(
            (
                "cross_dataset",
                f"{train_dataset}_to_{test_dataset}",
                (frame["dataset_id"] == train_dataset).to_numpy(),
                (frame["dataset_id"] == test_dataset).to_numpy(),
            )
        )

    for evaluation, fold, train_mask, test_mask in folds:
        for feature_set in FEATURE_SETS:
            for classifier_name in CLASSIFIERS:
                score, probability, importance = fit_and_score(
                    frame, train_mask, test_mask, feature_set, classifier_name
                )
                metrics.append(
                    {
                        "evaluation": evaluation,
                        "fold": fold,
                        "classifier": classifier_name,
                        "feature_set": feature_set,
                        "n_train": int(train_mask.sum()),
                        **score,
                    }
                )
                for index, value in zip(frame.index[test_mask], probability):
                    predictions.append(
                        {
                            "evaluation": evaluation,
                            "fold": fold,
                            "classifier": classifier_name,
                            "feature_set": feature_set,
                            "recording_id": frame.at[index, "recording_id"],
                            "dataset_id": frame.at[index, "dataset_id"],
                            "subject_id": frame.at[index, "subject_id"],
                            "target": int(frame.at[index, "target"]),
                            "probability": float(value),
                            "prediction": int(value >= 0.5),
                            "correct": int((value >= 0.5) == frame.at[index, "target"]),
                        }
                    )
                total = importance.sum()
                if total > 0:
                    importance = importance / total
                for name, value in importance.items():
                    importances.append(
                        {
                            "evaluation": evaluation,
                            "fold": fold,
                            "classifier": classifier_name,
                            "feature_set": feature_set,
                            "feature": name,
                            "normalised_importance": float(value),
                        }
                    )

    return (
        pd.DataFrame(metrics),
        pd.DataFrame(predictions),
        pd.DataFrame(importances),
    )


def load_reference_metrics() -> pd.DataFrame:
    """Collect the existing Logistic Regression / SVM / Random Forest results."""
    frames: list[pd.DataFrame] = []
    logistic_path = RESULTS / "baseline_metrics.csv"
    if logistic_path.exists():
        logistic = pd.read_csv(logistic_path)
        logistic = logistic[logistic["model"].isin(FEATURE_SETS)].copy()
        logistic["classifier"] = "Logistic_Regression"
        logistic["feature_set"] = logistic["model"]
        frames.append(logistic.drop(columns=["model"]))
    nonlinear_path = RESULTS / "nonlinear_metrics.csv"
    if nonlinear_path.exists():
        frames.append(pd.read_csv(nonlinear_path))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def summarise(metrics: pd.DataFrame) -> pd.DataFrame:
    aggregated = (
        metrics.groupby(["evaluation", "classifier", "feature_set"])
        .agg(
            balanced_accuracy_mean=("balanced_accuracy", "mean"),
            balanced_accuracy_std=("balanced_accuracy", "std"),
            sensitivity_mean=("sensitivity", "mean"),
            specificity_mean=("specificity", "mean"),
            macro_f1_mean=("macro_f1", "mean"),
            auroc_mean=("auroc", "mean"),
            folds=("fold", "count"),
        )
        .reset_index()
    )
    return aggregated.round(4)


def misclassified(predictions: pd.DataFrame) -> pd.DataFrame:
    errors = predictions[predictions["correct"] == 0].copy()
    errors["error_type"] = np.where(
        errors["target"] == 1, "false_negative", "false_positive"
    )
    errors["margin"] = (errors["probability"] - 0.5).abs()
    return errors.sort_values(
        ["evaluation", "classifier", "feature_set", "margin"], ascending=True
    )


def plot_comparison(summary: pd.DataFrame) -> None:
    order = ["Logistic_Regression", "RBF_SVM", "Random_Forest", "LightGBM", "XGBoost"]
    labels = ["Logistic", "RBF-SVM", "Random Forest", "LightGBM", "XGBoost"]
    available = [name for name in order if name in set(summary["classifier"])]
    labels = [labels[order.index(name)] for name in available]

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    width = 0.36
    for axis, evaluation, title in zip(
        axes,
        ("LOSO", "cross_dataset"),
        ("LOSO mean (6 subjects)", "Cross-dataset directional mean"),
    ):
        subset = summary[summary["evaluation"] == evaluation].set_index(
            ["classifier", "feature_set"]
        )
        x = np.arange(len(available))
        for offset, feature_set in zip((-width / 2, width / 2), FEATURE_SETS):
            values = [
                subset.loc[(classifier, feature_set), "balanced_accuracy_mean"]
                if (classifier, feature_set) in subset.index
                else np.nan
                for classifier in available
            ]
            bars = axis.bar(x + offset, values, width=width, label=feature_set)
            axis.bar_label(bars, fmt="%.3f", fontsize=7, padding=2)
        axis.set_xticks(x, labels, rotation=15)
        axis.set_ylim(0.9, 1.02)
        axis.set_title(title)
        axis.set_ylabel("Balanced accuracy")
        axis.legend(loc="lower left", fontsize=9)
    fig.suptitle("Gradient boosting versus existing baselines", fontsize=13)
    fig.tight_layout()
    fig.savefig(HERE / "model_comparison.png", dpi=180)
    plt.close(fig)


def plot_loso_folds(metrics: pd.DataFrame) -> None:
    loso = metrics[
        (metrics["evaluation"] == "LOSO")
        & (metrics["feature_set"] == "B2_time_frequency")
    ]
    subjects = sorted(loso["fold"].unique())
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axis = plt.subplots(figsize=(9, 5))
    width = 0.38
    for offset, classifier in zip((-width / 2, width / 2), CLASSIFIERS):
        subset = loso[loso["classifier"] == classifier].set_index("fold")
        values = [subset.loc[subject, "balanced_accuracy"] for subject in subjects]
        bars = axis.bar(np.arange(len(subjects)) + offset, values, width=width,
                        label=classifier)
        axis.bar_label(bars, fmt="%.2f", fontsize=8, padding=2)
    axis.axhline(0.5, color="black", linestyle="--", linewidth=1, label="chance")
    axis.set_xticks(np.arange(len(subjects)), subjects)
    axis.set_ylim(0.0, 1.08)
    axis.set_ylabel("Balanced accuracy")
    axis.set_title("Per-subject LOSO performance (B2 time + frequency features)")
    axis.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    fig.savefig(HERE / "loso_per_subject.png", dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-plots", action="store_true", help="Skip figure generation."
    )
    arguments = parser.parse_args()

    warnings.filterwarnings("ignore", message=".*valid feature names.*")

    frame = ensure_features()
    metrics, predictions, importances = evaluate(frame)

    metrics.to_csv(HERE / "results.csv", index=False)
    predictions.to_csv(HERE / "predictions.csv", index=False)

    errors = misclassified(predictions)
    errors.to_csv(HERE / "misclassified.csv", index=False)

    gain = (
        importances[importances["feature_set"] == "B2_time_frequency"]
        .groupby(["classifier", "feature"])["normalised_importance"]
        .mean()
        .reset_index()
        .sort_values(["classifier", "normalised_importance"], ascending=[True, False])
    )
    gain.to_csv(HERE / "feature_importance.csv", index=False)

    combined = pd.concat([load_reference_metrics(), metrics], ignore_index=True)
    summary = summarise(combined)
    summary.to_csv(HERE / "summary_comparison.csv", index=False)

    if not arguments.no_plots:
        plot_comparison(summary)
        plot_loso_folds(metrics)

    own = summary[summary["classifier"].isin(CLASSIFIERS)]
    (HERE / "summary.json").write_text(
        json.dumps(
            {
                "n_recordings": int(len(frame)),
                "n_subjects": int(frame["subject_id"].nunique()),
                "classifiers": list(CLASSIFIERS),
                "feature_sets": list(FEATURE_SETS),
                "results": own.to_dict(orient="records"),
                "n_misclassified_recording_folds": int(len(errors)),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Fold-level metrics")
    print(
        metrics[
            [
                "evaluation", "fold", "classifier", "feature_set",
                "balanced_accuracy", "sensitivity", "specificity", "macro_f1",
            ]
        ].round(4).to_string(index=False)
    )
    print("\nComparison against existing baselines")
    print(summary.to_string(index=False))
    print(f"\nMisclassified recording-fold pairs: {len(errors)}")
    if not errors.empty:
        print(
            errors[
                [
                    "evaluation", "fold", "classifier", "feature_set",
                    "recording_id", "error_type", "probability",
                ]
            ].round(4).to_string(index=False)
        )
    print(f"\nArtefacts written to {HERE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
