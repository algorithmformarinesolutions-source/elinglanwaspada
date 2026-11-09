"""Validation utilities for predicted/reconstructed and observed tide data."""
from __future__ import annotations

from dataclasses import dataclass
import os

import numpy as np
import pandas as pd

COL_TIME = "time"
COL_WL = "water_level"
COL_PREDICTED = "water_level_predicted"


@dataclass
class ValidationResult:
    metrics: dict
    merged: pd.DataFrame


def _normalize(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise TypeError("Input harus berupa pandas DataFrame.")
    data = df.copy()
    if "datetime" in data.columns and COL_TIME not in data.columns:
        data = data.rename(columns={"datetime": COL_TIME})
    if value_col not in data.columns:
        raise ValueError(f"Kolom '{value_col}' tidak ditemukan.")
    data[COL_TIME] = pd.to_datetime(data[COL_TIME], errors="coerce")
    data[value_col] = pd.to_numeric(data[value_col], errors="coerce")
    return data[[COL_TIME, value_col]].dropna().sort_values(COL_TIME).reset_index(drop=True)


def synchronize_time(prediction_df: pd.DataFrame, observed_df: pd.DataFrame, tolerance: str = "1min") -> pd.DataFrame:
    pred = _normalize(prediction_df, COL_PREDICTED)
    obs = _normalize(observed_df, COL_WL)
    return pd.merge_asof(
        obs, pred, on=COL_TIME, direction="nearest", tolerance=pd.Timedelta(tolerance)
    ).dropna(subset=[COL_PREDICTED, COL_WL])


def compute_residual(merged_df: pd.DataFrame) -> pd.DataFrame:
    out = merged_df.copy()
    out["residual"] = out[COL_WL] - out[COL_PREDICTED]
    return out


def compute_rmse(residual: pd.Series) -> float:
    return float(np.sqrt(np.mean(residual ** 2)))


def compute_mae(residual: pd.Series) -> float:
    return float(np.mean(np.abs(residual)))


def compute_bias(residual: pd.Series) -> float:
    return float(np.mean(residual))


def compute_correlation(merged_df: pd.DataFrame) -> float:
    return float(merged_df[COL_WL].corr(merged_df[COL_PREDICTED]))


def compute_r_squared(merged_df: pd.DataFrame) -> float:
    obs = merged_df[COL_WL]
    pred = merged_df[COL_PREDICTED]
    ss_res = np.sum((obs - pred) ** 2)
    ss_tot = np.sum((obs - obs.mean()) ** 2)
    if ss_tot == 0:
        return float("nan")
    return float(1 - ss_res / ss_tot)


def generate_validation_report(merged_df: pd.DataFrame) -> ValidationResult:
    merged = compute_residual(merged_df)
    residual = merged["residual"]
    metrics = {
        "n_matched": int(len(merged)),
        "rmse": compute_rmse(residual),
        "mae": compute_mae(residual),
        "bias": compute_bias(residual),
        "correlation": compute_correlation(merged),
        "r_squared": compute_r_squared(merged),
        "residual_max": float(residual.max()),
        "residual_min": float(residual.min()),
        "residual_std": float(residual.std()),
    }
    return ValidationResult(metrics=metrics, merged=merged)


def print_validation_report(result: ValidationResult) -> None:
    print("=== VALIDATION REPORT ===")
    for key, value in result.metrics.items():
        print(f"{key:>18}: {value:.4f}" if isinstance(value, float) else f"{key:>18}: {value}")


def save_validation_report(result: ValidationResult, output_dir: str = "output/validation", prefix: str = "validation"):
    os.makedirs(output_dir, exist_ok=True)
    metrics_path = os.path.join(output_dir, f"{prefix}_metrics.csv")
    detail_path = os.path.join(output_dir, f"{prefix}_detail.csv")
    pd.DataFrame([result.metrics]).to_csv(metrics_path, index=False)
    result.merged.to_csv(detail_path, index=False)
    return metrics_path, detail_path


def run_full_validation(prediction_df: pd.DataFrame, observed_df: pd.DataFrame, tolerance: str = "1min") -> ValidationResult:
    merged = synchronize_time(prediction_df, observed_df, tolerance=tolerance)
    return generate_validation_report(merged)
