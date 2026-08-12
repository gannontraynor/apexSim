"""Export one driver's lap telemetry in ApexSim's canonical units."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import fastf1
import pandas as pd

from pipelines.ingestion.load_session import CACHE_DIR, PROCESSED_DATA_DIR, slugify


TELEMETRY_COLUMNS: Final[list[str]] = [
    "time_s",
    "distance_m",
    "speed_mps",
    "throttle",
    "brake",
    "gear",
    "rpm",
    "drs",
]


@dataclass(frozen=True)
class ExportedLap:
    driver_code: str
    lap_number: int
    lap_time_s: float
    parquet_path: Path
    csv_path: Path
    samples: int


def normalize_telemetry(telemetry: pd.DataFrame) -> pd.DataFrame:
    """Convert FastF1 telemetry into ApexSim units and column names."""

    required_columns = {
        "Time",
        "Distance",
        "Speed",
        "Throttle",
        "Brake",
        "nGear",
        "RPM",
        "DRS",
    }
    missing_columns = sorted(required_columns - set(telemetry.columns))
    if missing_columns:
        raise ValueError(f"Telemetry is missing columns: {missing_columns}")

    normalized = pd.DataFrame(
        {
            "time_s": telemetry["Time"].dt.total_seconds(),
            "distance_m": pd.to_numeric(telemetry["Distance"], errors="coerce"),
            "speed_mps": pd.to_numeric(telemetry["Speed"], errors="coerce")
            / 3.6,
            "throttle": pd.to_numeric(telemetry["Throttle"], errors="coerce")
            / 100.0,
            "brake": telemetry["Brake"].astype(float),
            "gear": pd.to_numeric(telemetry["nGear"], errors="coerce"),
            "rpm": pd.to_numeric(telemetry["RPM"], errors="coerce"),
            "drs": pd.to_numeric(telemetry["DRS"], errors="coerce").ge(10),
        }
    )

    normalized = normalized.dropna(subset=TELEMETRY_COLUMNS).copy()
    normalized = normalized.loc[normalized["distance_m"] >= 0.0]
    normalized = normalized.sort_values("distance_m")
    normalized = normalized.drop_duplicates("distance_m", keep="last")
    normalized["time_s"] -= normalized["time_s"].iloc[0]
    normalized["gear"] = normalized["gear"].astype(int)
    normalized["drs"] = normalized["drs"].astype(bool)

    if len(normalized) < 2:
        raise ValueError("Telemetry must contain at least two usable samples.")

    return normalized.loc[:, TELEMETRY_COLUMNS].reset_index(drop=True)


def export_driver_lap(
    *,
    session: fastf1.core.Session,
    year: int,
    event_name: str,
    session_type: str,
    driver_code: str,
    lap_number: int | None,
) -> ExportedLap:
    """Export a requested lap, or the driver's fastest lap when unspecified."""

    normalized_driver = driver_code.strip().upper()
    driver_laps = session.laps.pick_drivers(normalized_driver)
    if driver_laps.empty:
        raise ValueError(f"Driver '{normalized_driver}' was not found.")

    if lap_number is None:
        lap = driver_laps.pick_fastest()
    else:
        requested_laps = driver_laps.loc[driver_laps["LapNumber"] == lap_number]
        if requested_laps.empty:
            raise ValueError(
                f"Lap {lap_number} was not found for {normalized_driver}."
            )
        lap = requested_laps.iloc[0]

    telemetry = normalize_telemetry(lap.get_telemetry())
    selected_lap_number = int(lap["LapNumber"])
    lap_time_s = float(lap["LapTime"].total_seconds())

    output_directory = (
        PROCESSED_DATA_DIR
        / f"year={year}"
        / f"event={slugify(event_name)}"
        / f"session={session_type.lower()}"
        / "telemetry"
        / f"driver={normalized_driver.lower()}"
        / f"lap={selected_lap_number}"
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    parquet_path = output_directory / "samples.parquet"
    csv_path = output_directory / "samples.csv"
    telemetry.to_parquet(parquet_path, index=False)
    csv_telemetry = telemetry.copy()
    csv_telemetry["drs"] = csv_telemetry["drs"].astype(int)
    csv_telemetry.to_csv(csv_path, index=False)

    return ExportedLap(
        driver_code=normalized_driver,
        lap_number=selected_lap_number,
        lap_time_s=lap_time_s,
        parquet_path=parquet_path,
        csv_path=csv_path,
        samples=len(telemetry),
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export canonical telemetry for one or more driver laps."
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--session", required=True, type=str.upper)
    parser.add_argument(
        "--driver",
        action="append",
        required=True,
        help="Driver code; repeat to export multiple drivers.",
    )
    parser.add_argument(
        "--lap",
        type=int,
        help="Specific lap number. By default each driver's fastest lap is used.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    try:
        event: str | int = (
            int(arguments.event) if arguments.event.isdigit() else arguments.event
        )
        session = fastf1.get_session(arguments.year, event, arguments.session)
        session.load(
            laps=True,
            telemetry=True,
            weather=False,
            messages=False,
        )
        event_name = str(session.event["EventName"])

        for driver in arguments.driver:
            exported = export_driver_lap(
                session=session,
                year=arguments.year,
                event_name=event_name,
                session_type=arguments.session,
                driver_code=driver,
                lap_number=arguments.lap,
            )
            print(
                f"{exported.driver_code} lap {exported.lap_number} "
                f"({exported.lap_time_s:.3f}s): {exported.samples} samples\n"
                f"  Parquet: {exported.parquet_path}\n"
                f"  CSV: {exported.csv_path}"
            )
    except Exception:
        logging.exception("Telemetry export failed.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
