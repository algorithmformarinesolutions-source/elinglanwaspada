# Generated from: testthreshold.ipynb
# Converted at: 2026-08-24T07:29:41.637Z
# Next step (optional): refactor into modules & generate tests with RunCell
# Quick start: pip install runcell

import pandas as pd

# KONFIGURASI
# ============================================================

COL_TIME = "time"
COL_WL = "water_level_predicted"
COL_STATUS = "status"

DEFAULT_THRESHOLD = 1.25

# 1. VALIDASI INPUT
# ============================================================

def validate_threshold_input(df: pd.DataFrame):
    """
    Memastikan DataFrame yang masuk memiliki
    kolom yang diperlukan.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            "Input harus berupa pandas DataFrame."
        )

    if df.empty:
        raise ValueError(
            "DataFrame kosong. Threshold tidak dapat diterapkan."
        )

    required_columns = [
        COL_TIME,
        COL_WL
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Kolom berikut tidak ditemukan: {missing_columns}"
        )

# 2. APPLY THRESHOLD
# ============================================================

def apply_threshold(
    df: pd.DataFrame,
    threshold: float = DEFAULT_THRESHOLD
) -> pd.DataFrame:
    """
    Mengklasifikasikan tinggi muka air berdasarkan threshold.

    Kategori:
        water level <= 1.25 m  -> NORMAL
        water level > 1.25 m   -> TINGGI
        data kosong             -> DATA KOSONG

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame hasil forecast.

    threshold : float
        Batas ketinggian pasut.
        Default = 1.25 m.

    Returns
    -------
    pandas.DataFrame
        DataFrame dengan kolom status.
    """

    # --------------------------------------------------------
    # Validasi
    # --------------------------------------------------------

    validate_threshold_input(df)

    if threshold < 0:
        raise ValueError(
            "Nilai threshold tidak boleh negatif."
        )

    # --------------------------------------------------------
    # Copy data
    # --------------------------------------------------------

    result = df.copy()

    # --------------------------------------------------------
    # Pastikan waktu datetime
    # --------------------------------------------------------

    result[COL_TIME] = pd.to_datetime(
        result[COL_TIME],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Pastikan water level numerik
    # --------------------------------------------------------

    result[COL_WL] = pd.to_numeric(
        result[COL_WL],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Klasifikasi
    # --------------------------------------------------------

    result[COL_STATUS] = result[COL_WL].apply(
        lambda x:
            "DATA KOSONG"
            if pd.isna(x)
            else "TINGGI"
            if x > threshold
            else "NORMAL"
    )

    return result

# 3. RINGKASAN THRESHOLD
# ============================================================

def get_threshold_summary(
    df: pd.DataFrame
) -> dict:
    """
    Menghasilkan ringkasan hasil klasifikasi threshold.

    Returns
    -------
    dict
        Jumlah data berdasarkan status.
    """

    if COL_STATUS not in df.columns:
        raise ValueError(
            "Kolom status belum tersedia. "
            "Jalankan apply_threshold() terlebih dahulu."
        )

    summary = {
        "total_data": int(len(df)),
        "normal": int(
            (df[COL_STATUS] == "NORMAL").sum()
        ),
        "tinggi": int(
            (df[COL_STATUS] == "TINGGI").sum()
        ),
        "data_kosong": int(
            (df[COL_STATUS] == "DATA KOSONG").sum()
        )
    }

    return summary