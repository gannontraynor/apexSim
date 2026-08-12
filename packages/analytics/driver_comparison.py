"""Deterministic driver pace comparison analytics."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final

import pandas as pd


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

GREEN_TRACK_STATUS: Final[str] = "1"


@dataclass(frozen=True)
class DriverPaceSummary:
    driver_code: str
    total_laps: int
    representative_laps: int
    excluded_laps: int
    median_lap_time_ms: int | None
    mean_lap_time_ms: int | None
    fastest_lap_time_ms: int | None
    pace_std_dev_ms: int | None


@dataclass(frozen=True)
class StintComparison:
    driver_code: str
    stint: int
    compound: str | None
    start_lap: int
    end_lap: int
    representative_laps: int
    median_lap_time_ms: int | None
    pace_std_dev_ms: int | None


@dataclass(frozen=True)
class DriverComparison:
    driver_a: DriverPaceSummary
    driver_b: DriverPaceSummary
    median_pace_delta_ms: int | None
    faster_driver: str | None
    consistency_advantage: str | None
    driver_a_stints: list[StintComparison]
    driver_b_stints: list[StintComparison]


def nullable_int(value: float | int | None) -> int | None:
    """Convert a numeric value into an integer, preserving missing values."""

    if value is None or pd.isna(value):
        return None

    return int(round(float(value)))


def validate_driver_exists(laps: pd.DataFrame, driver_code: str) -> None:
    available_drivers = set(laps["driver_code"].dropna().astype(str))

    if driver_code not in available_drivers:
        raise ValueError(
            f"Driver '{driver_code}' was not found. "
            f"Available drivers: {sorted(available_drivers)}"
        )


def representative_lap_mask(laps: pd.DataFrame) -> pd.Series:
    """
    Identify laps suitable for basic race-pace comparison.

    A representative lap must:
    - have a valid lap time
    - be marked accurate by FastF1
    - not be a pit-in lap
    - not be a pit-out lap
    - occur under green-flag track status
    """

    return (
        laps["lap_time_ms"].notna()
        & laps["is_accurate"].fillna(False)
        & laps["pit_in_ms"].isna()
        & laps["pit_out_ms"].isna()
        & laps["track_status"].astype("string").eq(GREEN_TRACK_STATUS)
    )


def select_driver_laps(
    laps: pd.DataFrame,
    driver_code: str,
) -> pd.DataFrame:
    """Return all laps for one driver."""

    normalized_code = driver_code.strip().upper()
    validate_driver_exists(laps, normalized_code)

    return (
        laps.loc[laps["driver_code"] == normalized_code]
        .sort_values("lap_number")
        .reset_index(drop=True)
    )


def select_representative_laps(driver_laps: pd.DataFrame) -> pd.DataFrame:
    """Return laps eligible for deterministic pace comparison."""

    return driver_laps.loc[representative_lap_mask(driver_laps)].copy()


def summarize_driver(
    laps: pd.DataFrame,
    driver_code: str,
) -> DriverPaceSummary:
    """Calculate race-level pace and consistency metrics for one driver."""

    driver_laps = select_driver_laps(laps, driver_code)
    representative_laps = select_representative_laps(driver_laps)

    lap_times = representative_laps["lap_time_ms"]

    return DriverPaceSummary(
        driver_code=driver_code.strip().upper(),
        total_laps=len(driver_laps),
        representative_laps=len(representative_laps),
        excluded_laps=len(driver_laps) - len(representative_laps),
        median_lap_time_ms=nullable_int(lap_times.median()),
        mean_lap_time_ms=nullable_int(lap_times.mean()),
        fastest_lap_time_ms=nullable_int(lap_times.min()),
        pace_std_dev_ms=nullable_int(lap_times.std(ddof=0)),
    )


def summarize_stints(
    laps: pd.DataFrame,
    driver_code: str,
) -> list[StintComparison]:
    """Calculate representative pace metrics for each driver stint."""

    driver_laps = select_driver_laps(laps, driver_code)
    representative_laps = select_representative_laps(driver_laps)

    if representative_laps.empty:
        return []

    grouped = representative_laps.dropna(subset=["stint", "lap_number"]).groupby(
        ["stint", "compound"], dropna=False
    )

    summaries: list[StintComparison] = []

    for (stint, compound), group in grouped:
        lap_times = group["lap_time_ms"]

        summaries.append(
            StintComparison(
                driver_code=driver_code.strip().upper(),
                stint=int(stint),
                compound=None if pd.isna(compound) else str(compound),
                start_lap=int(group["lap_number"].min()),
                end_lap=int(group["lap_number"].max()),
                representative_laps=len(group),
                median_lap_time_ms=nullable_int(lap_times.median()),
                pace_std_dev_ms=nullable_int(lap_times.std(ddof=0)),
            )
        )

    return sorted(summaries, key=lambda item: item.stint)


def compare_drivers(
    laps: pd.DataFrame,
    driver_a: str,
    driver_b: str,
) -> DriverComparison:
    """Compare two drivers using deterministic race-pace metrics."""

    normalized_a = driver_a.strip().upper()
    normalized_b = driver_b.strip().upper()

    if normalized_a == normalized_b:
        raise ValueError("Two different drivers are required.")

    summary_a = summarize_driver(laps, normalized_a)
    summary_b = summarize_driver(laps, normalized_b)

    median_delta: int | None = None
    faster_driver: str | None = None

    if (
        summary_a.median_lap_time_ms is not None
        and summary_b.median_lap_time_ms is not None
    ):
        median_delta = summary_a.median_lap_time_ms - summary_b.median_lap_time_ms

        if median_delta < 0:
            faster_driver = normalized_a
        elif median_delta > 0:
            faster_driver = normalized_b

    consistency_advantage: str | None = None

    if summary_a.pace_std_dev_ms is not None and summary_b.pace_std_dev_ms is not None:
        if summary_a.pace_std_dev_ms < summary_b.pace_std_dev_ms:
            consistency_advantage = normalized_a
        elif summary_b.pace_std_dev_ms < summary_a.pace_std_dev_ms:
            consistency_advantage = normalized_b

    return DriverComparison(
        driver_a=summary_a,
        driver_b=summary_b,
        median_pace_delta_ms=median_delta,
        faster_driver=faster_driver,
        consistency_advantage=consistency_advantage,
        driver_a_stints=summarize_stints(laps, normalized_a),
        driver_b_stints=summarize_stints(laps, normalized_b),
    )


def load_processed_laps(path: Path) -> pd.DataFrame:
    """Load and validate a processed lap dataset."""

    if not path.exists():
        raise FileNotFoundError(f"Lap dataset does not exist: {path}")

    laps = pd.read_parquet(path)

    required_columns = {
        "driver_code",
        "lap_number",
        "stint",
        "lap_time_ms",
        "compound",
        "track_status",
        "pit_in_ms",
        "pit_out_ms",
        "is_accurate",
    }

    missing_columns = sorted(required_columns - set(laps.columns))

    if missing_columns:
        raise ValueError(f"Processed lap dataset is missing columns: {missing_columns}")

    return laps


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two drivers from a processed F1 session."
    )

    parser.add_argument(
        "--laps",
        type=Path,
        required=True,
        help="Path to the processed laps.parquet file.",
    )
    parser.add_argument(
        "--driver-a",
        required=True,
        help="Three-letter driver code.",
    )
    parser.add_argument(
        "--driver-b",
        required=True,
        help="Three-letter driver code.",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        laps = load_processed_laps(arguments.laps)
        comparison = compare_drivers(
            laps,
            arguments.driver_a,
            arguments.driver_b,
        )
    except Exception as exc:
        print(f"Driver comparison failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(asdict(comparison), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
