# Generated from: ggrafik (1).ipynb
# Converted at: 2026-08-24T07:33:52.042Z
# Next step (optional): refactor into modules & generate tests with RunCell
# Quick start: pip install runcell

import pandas as pd
import matplotlib.pyplot as plt

# KONFIGURASI
# ============================================================

COL_TIME = "time"
COL_WL = "water_level"
COL_PREDICTED = "water_level_predicted"

THRESHOLD = 1.25

# 1. VALIDASI DATA
# ============================================================

def validate_visualization_input(df: pd.DataFrame):

    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            "Input harus berupa pandas DataFrame."
        )

    if df.empty:
        raise ValueError(
            "DataFrame kosong."
        )

    required_columns = [
        COL_TIME,
        COL_WL
    ]

    missing_columns = [
        col
        for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom berikut tidak ditemukan: {missing_columns}"
        )

# 2. PREPARE DATA VISUALISASI
# ============================================================

def prepare_visualization_data(
    df: pd.DataFrame
) -> pd.DataFrame:

    validate_visualization_input(df)

    data = df.copy()

    data[COL_TIME] = pd.to_datetime(
        data[COL_TIME],
        errors="coerce"
    )

    data[COL_WL] = pd.to_numeric(
        data[COL_WL],
        errors="coerce"
    )

    if COL_PREDICTED in data.columns:
        data[COL_PREDICTED] = pd.to_numeric(
            data[COL_PREDICTED],
            errors="coerce"
        )

    data = (
        data
        .dropna(subset=[COL_TIME])
        .sort_values(COL_TIME)
        .reset_index(drop=True)
    )

    return data

# 3. GRAFIK PASANG SURUT
# ============================================================

def plot_tide(
    df: pd.DataFrame,
    threshold: float = THRESHOLD,
    title: str = "Grafik Pasang Surut"
):
    """
    Membuat grafik tinggi muka air terhadap waktu.

    Jika tersedia kolom water_level_predicted,
    grafik juga menampilkan hasil prediksi/rekonstruksi.
    """

    data = prepare_visualization_data(df)

    plt.figure(figsize=(14, 5))

    # --------------------------------------------------------
    # Data observasi
    # --------------------------------------------------------

    plt.plot(
        data[COL_TIME],
        data[COL_WL],
        label="Water Level"
    )

    # --------------------------------------------------------
    # Data predicted / reconstructed
    # --------------------------------------------------------

    if COL_PREDICTED in data.columns:

        plt.plot(
            data[COL_TIME],
            data[COL_PREDICTED],
            label="Predicted Water Level"
        )

    # --------------------------------------------------------
    # Threshold
    # --------------------------------------------------------

    plt.axhline(
        y=threshold,
        linestyle="--",
        label=f"Threshold {threshold} m"
    )

    # --------------------------------------------------------
    # Label
    # --------------------------------------------------------

    plt.xlabel("Waktu")

    plt.ylabel(
        "Water Level (m)"
    )

    plt.title(title)

    plt.legend()

    plt.grid(
        True,
        alpha=0.3
    )

    plt.tight_layout()

    plt.show()