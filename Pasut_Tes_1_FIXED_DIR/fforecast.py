# Generated from: fforecast.ipynb
# Converted at: 2026-08-24T07:29:29.967Z
# Next step (optional): refactor into modules & generate tests with RunCell
# Quick start: pip install runcell


import pandas as pd
import numpy as np

try:
    import utide
except ImportError as exc:
    utide = None
    _UTIDE_IMPORT_ERROR = exc
else:
    _UTIDE_IMPORT_ERROR = None

def _require_utide():
    if utide is None:
        raise ImportError(
            "UTide belum terpasang. Jalankan: python -m pip install utide"
        ) from _UTIDE_IMPORT_ERROR

# KONFIGURASI
# ============================================================

COL_TIME = "time"
COL_WL_PREDICTED = "water_level_predicted"

# 1. CEK DATA INPUT
# ============================================================

def validate_forecast_input(coef, df):
    """
    Memastikan input untuk forecasting tersedia dan valid.

    Parameters
    ----------
    coef : object
        Hasil UTide.solve() dari tidal_analysis.py

    df : pandas.DataFrame
        DataFrame data pasut historis.
        Minimal memiliki kolom 'time'.

    Returns
    -------
    None
    """

    if coef is None:
        raise ValueError(
            "Hasil harmonic analysis (coef) tidak tersedia."
        )

    if not isinstance(df, pd.DataFrame):
        raise TypeError(
            "df harus berupa pandas DataFrame."
        )

    if COL_TIME not in df.columns:
        raise ValueError(
            f"DataFrame harus memiliki kolom '{COL_TIME}'."
        )

    if df.empty:
        raise ValueError(
            "DataFrame kosong. Forecast tidak dapat dilakukan."
        )

# 2. MENENTUKAN WAKTU TERAKHIR DATA
# ============================================================

def get_last_time(df):
    """
    Mengambil waktu observasi terakhir dari DataFrame.

    Returns
    -------
    pandas.Timestamp
    """

    time = pd.to_datetime(
        df[COL_TIME],
        errors="coerce"
    )

    time = time.dropna()

    if time.empty:
        raise ValueError(
            "Tidak terdapat timestamp yang valid."
        )

    return time.max()

# 3. MEMBUAT WAKTU FORECAST
# ============================================================

def create_forecast_times(
    last_time,
    forecast_days=30,
    interval="1h"
):
    """
    Membuat timestamp untuk periode forecast.

    Forecast dimulai setelah waktu observasi terakhir.

    Parameters
    ----------
    last_time : pandas.Timestamp
        Waktu terakhir data observasi.

    forecast_days : int
        Lama forecast dalam hari.

    interval : str
        Interval waktu forecast.
        Default = 1 jam.

    Returns
    -------
    pandas.DatetimeIndex
    """

    if forecast_days <= 0:
        raise ValueError(
            "forecast_days harus lebih besar dari 0."
        )

    # Mulai forecast setelah data terakhir
    forecast_start = (
        last_time + pd.Timedelta(interval)
    )

    # Akhir periode forecast
    forecast_end = (
        last_time + pd.Timedelta(days=forecast_days)
    )

    future_times = pd.date_range(
        start=forecast_start,
        end=forecast_end,
        freq=interval
    )

    if len(future_times) == 0:
        raise ValueError(
            "Tidak berhasil membuat waktu forecast."
        )

    return future_times

# 4. MELAKUKAN TIDAL PREDICTION
# ============================================================

def predict_tide(
    coef,
    future_times
):
    _require_utide()
    """
    Melakukan prediksi pasut menggunakan konstanta harmonik
    hasil UTide.

    Parameters
    ----------
    coef : object
        Hasil dari utide.solve().

    future_times : array-like
        Timestamp yang akan diprediksi.

    Returns
    -------
    pandas.DataFrame
        DataFrame hasil prediksi.
    """

    future_times = pd.to_datetime(
        future_times
    )

    # Rekonstruksi / prediksi pasut
    tide = utide.reconstruct(
        future_times,
        coef,
        verbose=False
    )

    forecast_df = pd.DataFrame({
        COL_TIME: future_times,
        COL_WL_PREDICTED: tide.h
    })

    return forecast_df

# 5. QUALITY CONTROL HASIL FORECAST
# ============================================================

def validate_forecast_output(
    forecast_df,
    last_time
):
    """
    Melakukan pengecekan sederhana terhadap hasil forecast.

    Pengecekan:
    1. DataFrame tidak kosong
    2. Tidak ada timestamp kosong
    3. Tidak ada water level NaN
    4. Waktu forecast harus setelah data observasi terakhir
    """

    if forecast_df.empty:
        raise ValueError(
            "Hasil forecast kosong."
        )

    # Pastikan waktu valid
    forecast_df[COL_TIME] = pd.to_datetime(
        forecast_df[COL_TIME],
        errors="coerce"
    )

    # Pastikan water level numerik
    forecast_df[COL_WL_PREDICTED] = pd.to_numeric(
        forecast_df[COL_WL_PREDICTED],
        errors="coerce"
    )

    # Cek timestamp kosong
    if forecast_df[COL_TIME].isna().any():
        raise ValueError(
            "Terdapat timestamp yang tidak valid pada hasil forecast."
        )

    # Cek nilai water level kosong
    if forecast_df[COL_WL_PREDICTED].isna().any():
        raise ValueError(
            "Terdapat nilai water level kosong pada hasil forecast."
        )

    # Pastikan forecast berada setelah observasi terakhir
    if (
        forecast_df[COL_TIME].min()
        <= last_time
    ):
        raise ValueError(
            "Terdapat waktu forecast yang tidak berada "
            "setelah waktu observasi terakhir."
        )

    # Urutkan
    forecast_df = (
        forecast_df
        .sort_values(COL_TIME)
        .reset_index(drop=True)
    )

    return forecast_df

# 6. FUNGSI UTAMA FORECAST
# ============================================================

def generate_forecast(
    coef,
    df,
    forecast_days=30,
    interval="1h"
):
    """
    Fungsi utama untuk menghasilkan forecast pasut.

    Parameters
    ----------
    coef : object
        Hasil UTide.solve() dari tidal_analysis.py.

    df : pandas.DataFrame
        Data pasut historis.
        Minimal memiliki kolom 'time'.

    forecast_days : int, default=30
        Lama prediksi dalam hari.

    interval : str, default="1h"
        Interval prediksi.

    Returns
    -------
    pandas.DataFrame
        DataFrame hasil forecast dengan kolom:

        time
        water_level_predicted
    """

    # --------------------------------------------------------
    # STEP 1: Validasi input
    # --------------------------------------------------------

    validate_forecast_input(
        coef,
        df
    )

    # --------------------------------------------------------
    # STEP 2: Ambil waktu terakhir data
    # --------------------------------------------------------

    last_time = get_last_time(df)

    # --------------------------------------------------------
    # STEP 3: Buat waktu masa depan
    # --------------------------------------------------------

    future_times = create_forecast_times(
        last_time=last_time,
        forecast_days=forecast_days,
        interval=interval
    )

    # --------------------------------------------------------
    # STEP 4: Prediksi pasut menggunakan UTide
    # --------------------------------------------------------

    forecast_df = predict_tide(
        coef=coef,
        future_times=future_times
    )

    # --------------------------------------------------------
    # STEP 5: Quality control
    # --------------------------------------------------------

    forecast_df = validate_forecast_output(
        forecast_df,
        last_time
    )

    return forecast_df

# 7. FUNGSI ALTERNATIF:
#    LANGSUNG MENGGUNAKAN RESULT DARI TIDAL ANALYSIS
# ============================================================

def generate_forecast_from_result(
    result,
    df,
    forecast_days=30,
    interval="1h"
):
    """
    Menghasilkan forecast langsung dari dictionary
    hasil tidal_analysis.py.

    Parameters
    ----------
    result : dict
        Dictionary hasil run_full_analysis().

        Contoh:
        {
            "coef": coef,
            "formzahl": formzahl,
            "classification": classification,
            "prediction": prediction
        }

    df : pandas.DataFrame
        Data pasut historis.

    forecast_days : int
        Lama forecast.

    interval : str
        Interval forecast.

    Returns
    -------
    pandas.DataFrame
        Hasil forecast.
    """

    if not isinstance(result, dict):
        raise TypeError(
            "result harus berupa dictionary."
        )

    if "coef" not in result:
        raise KeyError(
            "Key 'coef' tidak ditemukan dalam result."
        )

    coef = result["coef"]

    return generate_forecast(
        coef=coef,
        df=df,
        forecast_days=forecast_days,
        interval=interval
    )