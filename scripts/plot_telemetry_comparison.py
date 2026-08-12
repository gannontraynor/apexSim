"""Plot comparable ApexSim telemetry CSV files."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/apexsim-matplotlib")
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "time_s",
    "distance_m",
    "speed_mps",
    "throttle",
    "brake",
    "gear",
    "rpm",
    "drs",
}


def parse_series(value: str) -> tuple[str, Path]:
    label, separator, path = value.partition("=")
    if not separator or not label or not path:
        raise argparse.ArgumentTypeError("series must use LABEL=PATH format")
    return label, Path(path)


def load_series(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Telemetry CSV does not exist: {path}")
    telemetry = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(telemetry.columns))
    if missing:
        raise ValueError(f"{path} is missing columns: {missing}")
    if telemetry.empty:
        raise ValueError(f"Telemetry CSV is empty: {path}")
    return telemetry.sort_values("distance_m").reset_index(drop=True)


def plot_comparison(
    series: list[tuple[str, pd.DataFrame]],
    output_path: Path,
    title: str,
) -> None:
    if len(series) < 2:
        raise ValueError("At least two telemetry series are required.")

    figure, axes = plt.subplots(
        4,
        1,
        figsize=(14, 11),
        sharex=True,
        gridspec_kw={"height_ratios": [2.2, 1.4, 1.0, 1.4]},
    )
    figure.suptitle(title, fontsize=16, fontweight="bold")

    for label, telemetry in series:
        distance = telemetry["distance_m"]
        axes[0].plot(distance, telemetry["speed_mps"] * 3.6, label=label)
        axes[1].plot(distance, telemetry["throttle"] * 100.0, label=f"{label} throttle")
        axes[1].plot(
            distance,
            telemetry["brake"] * 100.0,
            linestyle="--",
            alpha=0.8,
            label=f"{label} brake",
        )
        axes[2].step(distance, telemetry["gear"], where="post", label=label)

    label_a, telemetry_a = series[0]
    label_b, telemetry_b = series[1]
    start_distance = max(
        float(telemetry_a["distance_m"].min()),
        float(telemetry_b["distance_m"].min()),
    )
    end_distance = min(
        float(telemetry_a["distance_m"].max()),
        float(telemetry_b["distance_m"].max()),
    )
    comparison_axis = np.linspace(start_distance, end_distance, 1_000)
    time_a = np.interp(
        comparison_axis,
        telemetry_a["distance_m"],
        telemetry_a["time_s"],
    )
    time_b = np.interp(
        comparison_axis,
        telemetry_b["distance_m"],
        telemetry_b["time_s"],
    )
    axes[3].plot(comparison_axis, time_a - time_b, color="black")
    axes[3].axhline(0.0, color="gray", linewidth=0.8)

    axes[0].set_ylabel("Speed (km/h)")
    axes[1].set_ylabel("Pedal (%)")
    axes[2].set_ylabel("Gear")
    axes[3].set_ylabel(f"Δ time (s)\n{label_a} − {label_b}")
    axes[3].set_xlabel("Distance (m)")
    axes[0].legend(ncol=len(series), loc="upper right")
    axes[1].legend(ncol=2, fontsize="small", loc="upper right")
    axes[2].legend(ncol=len(series), loc="upper right")

    for axis in axes:
        axis.grid(True, alpha=0.25)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.tight_layout()
    figure.savefig(output_path, dpi=160)
    plt.close(figure)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot an ApexSim telemetry comparison.")
    parser.add_argument(
        "--series",
        action="append",
        required=True,
        type=parse_series,
        help="Telemetry series as LABEL=PATH; repeat at least twice.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", default="ApexSim telemetry comparison")
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    try:
        series = [(label, load_series(path)) for label, path in arguments.series]
        plot_comparison(series, arguments.output, arguments.title)
    except Exception as error:
        print(f"Plotting failed: {error}", file=sys.stderr)
        return 1

    print(f"Wrote telemetry comparison to {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
