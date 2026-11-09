# Generated from: calender.ipynb
# Converted at: 2026-08-24T07:29:03.702Z
# Next step (optional): refactor into modules & generate tests with RunCell
# Quick start: pip install runcell

import pandas as pd

# KONFIGURASI
# ============================================================

COL_TIME = "time"
COL_WL = "water_level_predicted"
COL_STATUS = "status"


# 1. VALIDASI INPUT
# ============================================================

def validate_calendar_input(df: pd.DataFrame):
    """
    Memastikan DataFrame memiliki kolom yang diperlukan.
    """

    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            "Input harus berupa pandas DataFrame."
        )

    if df.empty:
        raise ValueError(
            "DataFrame kosong. Kalender tidak dapat dibuat."
        )

    required_columns = [
        COL_TIME,
        COL_WL,
        COL_STATUS
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

# 2. GENERATE HOURLY CALENDAR
# ============================================================

def generate_hourly_calendar(
    df: pd.DataFrame
) -> pd.DataFrame:
    """
    Membuat kalender pasut berdasarkan data forecast per jam.

    Input:
        DataFrame hasil threshold.py

    Kolom:
        time
        water_level_predicted
        status

    Output:
        DataFrame kalender per jam.
    """

    # --------------------------------------------------------
    # Validasi input
    # --------------------------------------------------------

    validate_calendar_input(df)

    # --------------------------------------------------------
    # Copy data
    # --------------------------------------------------------

    calendar = df.copy()

    # --------------------------------------------------------
    # Pastikan format waktu
    # --------------------------------------------------------

    calendar[COL_TIME] = pd.to_datetime(
        calendar[COL_TIME],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Pastikan water level numerik
    # --------------------------------------------------------

    calendar[COL_WL] = pd.to_numeric(
        calendar[COL_WL],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Hapus data yang tidak valid
    # --------------------------------------------------------

    calendar = calendar.dropna(
        subset=[
            COL_TIME
        ]
    ).copy()

    # --------------------------------------------------------
    # Urutkan berdasarkan waktu
    # --------------------------------------------------------

    calendar = (
        calendar
        .sort_values(COL_TIME)
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Tambahkan tanggal
    # --------------------------------------------------------

    calendar["date"] = (
        calendar[COL_TIME]
        .dt.strftime("%d-%m-%Y")
    )

    # --------------------------------------------------------
    # Tambahkan waktu
    # --------------------------------------------------------

    calendar["hour"] = (
        calendar[COL_TIME]
        .dt.strftime("%H:%M")
    )

    # --------------------------------------------------------
    # Susun kolom output
    # --------------------------------------------------------

    calendar = calendar[
        [
            "date",
            "hour",
            COL_WL,
            COL_STATUS
        ]
    ]

    # --------------------------------------------------------
    # Rename kolom agar lebih mudah digunakan di web
    # --------------------------------------------------------

    calendar = calendar.rename(
        columns={
            "date": "date",
            "hour": "time",
            COL_WL: "water_level",
            COL_STATUS: "status"
        }
    )

    return calendar

# 3. GENERATE CALENDAR PER BULAN
# ============================================================

def generate_monthly_calendar(
    df: pd.DataFrame,
    year: int,
    month: int
) -> pd.DataFrame:
    """
    Mengambil kalender hanya untuk bulan tertentu.

    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame hasil threshold.py.

    year : int
        Tahun kalender.

    month : int
        Bulan kalender.

    Returns
    -------
    pandas.DataFrame
        Kalender pasut per jam untuk bulan yang dipilih.
    """

    validate_calendar_input(df)

    data = df.copy()

    data[COL_TIME] = pd.to_datetime(
        data[COL_TIME],
        errors="coerce"
    )

    # Filter tahun dan bulan
    data = data[
        (data[COL_TIME].dt.year == year)
        &
        (data[COL_TIME].dt.month == month)
    ].copy()

    if data.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "time",
                "water_level",
                "status"
            ]
        )

    return generate_hourly_calendar(data)

# 4. SUMMARY KALENDER
# ============================================================

def get_calendar_summary(
    calendar_df: pd.DataFrame
) -> dict:
    """
    Menghasilkan ringkasan kalender.

    Returns
    -------
    dict
        Jumlah data dan jumlah status TINGGI/NORMAL.
    """

    if calendar_df.empty:
        return {
            "total_hours": 0,
            "normal": 0,
            "tinggi": 0,
            "data_kosong": 0
        }

    summary = {
        "total_hours": int(
            len(calendar_df)
        ),

        "normal": int(
            (
                calendar_df["status"]
                == "NORMAL"
            ).sum()
        ),

        "tinggi": int(
            (
                calendar_df["status"]
                == "TINGGI"
            ).sum()
        ),

        "data_kosong": int(
            (
                calendar_df["status"]
                == "DATA KOSONG"
            ).sum()
        )
    }

    return summary