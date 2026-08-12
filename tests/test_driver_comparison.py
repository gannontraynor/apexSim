from __future__ import annotations

import pandas as pd
import pytest

from packages.analytics.driver_comparison import (
    compare_drivers,
    representative_lap_mask,
    summarize_driver,
    summarize_stints,
)


def build_test_laps() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "driver_code": [
                "NOR",
                "NOR",
                "NOR",
                "NOR",
                "LEC",
                "LEC",
                "LEC",
                "LEC",
            ],
            "lap_number": pd.Series(
                [1, 2, 3, 4, 1, 2, 3, 4],
                dtype="Int64",
            ),
            "stint": pd.Series(
                [1, 1, 1, 2, 1, 1, 1, 2],
                dtype="Int64",
            ),
            "lap_time_ms": pd.Series(
                [
                    80000,
                    79000,
                    81000,
                    90000,
                    80500,
                    80000,
                    81500,
                    91000,
                ],
                dtype="Int64",
            ),
            "compound": [
                "MEDIUM",
                "MEDIUM",
                "MEDIUM",
                "HARD",
                "MEDIUM",
                "MEDIUM",
                "MEDIUM",
                "HARD",
            ],
            "track_status": [
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
            ],
            "pit_in_ms": pd.Series(
                [pd.NA, pd.NA, pd.NA, 1000, pd.NA, pd.NA, pd.NA, 1000],
                dtype="Int64",
            ),
            "pit_out_ms": pd.Series(
                [pd.NA] * 8,
                dtype="Int64",
            ),
            "is_accurate": [
                True,
                True,
                True,
                True,
                True,
                True,
                True,
                True,
            ],
        }
    )


def test_representative_lap_mask_excludes_pit_laps() -> None:
    laps = build_test_laps()

    result = representative_lap_mask(laps)

    assert result.sum() == 6
    assert not result.iloc[3]
    assert not result.iloc[7]


def test_summarize_driver() -> None:
    laps = build_test_laps()

    result = summarize_driver(laps, "NOR")

    assert result.driver_code == "NOR"
    assert result.total_laps == 4
    assert result.representative_laps == 3
    assert result.excluded_laps == 1
    assert result.median_lap_time_ms == 80000
    assert result.fastest_lap_time_ms == 79000


def test_summarize_stints() -> None:
    laps = build_test_laps()

    result = summarize_stints(laps, "NOR")

    assert len(result) == 1
    assert result[0].stint == 1
    assert result[0].compound == "MEDIUM"
    assert result[0].representative_laps == 3
    assert result[0].median_lap_time_ms == 80000


def test_compare_drivers() -> None:
    laps = build_test_laps()

    result = compare_drivers(laps, "NOR", "LEC")

    assert result.driver_a.driver_code == "NOR"
    assert result.driver_b.driver_code == "LEC"
    assert result.median_pace_delta_ms == -500
    assert result.faster_driver == "NOR"


def test_compare_same_driver_rejected() -> None:
    laps = build_test_laps()

    with pytest.raises(ValueError, match="Two different drivers"):
        compare_drivers(laps, "NOR", "NOR")


def test_unknown_driver_rejected() -> None:
    laps = build_test_laps()

    with pytest.raises(ValueError, match="was not found"):
        summarize_driver(laps, "VER")
