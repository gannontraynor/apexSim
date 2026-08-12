# ApexSim

ApexSim is a motorsport telemetry, analytics, and simulation platform built
around a deterministic C++20 numerical core and Python data ingestion.

The project currently ingests real Formula 1 session and telemetry data,
normalizes it into stable units, compares driver race pace, resamples irregular
telemetry onto a common distance axis, and produces driver-comparison plots.

## Design principles

- Calculations are deterministic, testable, and explainable.
- Python owns ingestion, experimentation, and orchestration.
- C++ owns performance-sensitive numerical analytics and simulation logic.
- Parquet is the canonical persisted data format.
- APIs and user interfaces orchestrate analytics instead of reimplementing them.
- AI may explain calculated results, but it is not their source of truth.

## Architecture

```text
FastF1 / OpenF1
        ↓
Python ingestion and caching
        ↓
Canonical telemetry data (Parquet)
        ↓
C++20 ApexSim Core
  ├── telemetry domain types
  └── distance-based resampling
        ↓
Later: lap synchronization, delta, corner analytics, simulation
        ↓
FastAPI
        ↓
React / TypeScript dashboard
```

CSV is currently used only as a temporary bridge between Python and the C++
resampling executable. It is not intended to replace Parquet as the canonical
storage format.

## Current capabilities

- FastF1 session ingestion and local caching
- Normalized lap and stint datasets
- Deterministic Python driver pace comparison
- Canonical telemetry export using SI-oriented units
- C++20 `TelemetrySample` domain type
- C++ distance-based telemetry resampling
- Catch2 and CTest coverage
- Raw and resampled telemetry comparison plots

The telemetry resampler:

- creates a regular distance axis;
- linearly interpolates time, speed, throttle, brake, and RPM;
- holds the latest gear and DRS state between source samples;
- preserves the final source endpoint; and
- rejects invalid steps and non-increasing distance axes.

## Repository layout

```text
apexsim/
├── cpp/                         # C++20 numerical core and tests
├── data/                        # Ignored raw and processed datasets
├── docs/                        # Vision, architecture, principles, roadmap
├── packages/analytics/          # Python analytics reference implementations
├── pipelines/ingestion/         # FastF1 ingestion and telemetry export
├── scripts/                     # Development visualization commands
└── tests/                       # Python tests
```

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- CMake 3.20 or newer
- A C++20-capable compiler

Install the Python environment from the repository root:

```bash
uv sync
```

FastF1 needs network access when telemetry is requested for the first time.
Later runs use `.cache/fastf1/`.

## Build and test the C++ core

Use an out-of-source build:

```bash
cmake -S cpp -B build/cpp
cmake --build build/cpp
ctest --test-dir build/cpp --output-on-failure
```

This builds:

- `apexsim_core`: the reusable C++ library;
- `apexsim_core_tests`: the Catch2 test executable; and
- `apexsim_resample_csv`: the temporary CSV-to-C++ resampling bridge.

Run the Python checks separately:

```bash
uv run ruff check .
uv run python -m pytest
```

## Monaco telemetry walkthrough

The following workflow compares the fastest race laps completed by Lando
Norris and Charles Leclerc during the 2025 Monaco Grand Prix.

### 1. Export detailed telemetry

```bash
uv run python -m pipelines.ingestion.export_lap_telemetry \
  --year 2025 \
  --event Monaco \
  --session R \
  --driver NOR \
  --driver LEC
```

When `--lap` is omitted, the exporter selects each driver's fastest lap. A
specific common lap can be requested with `--lap 36`, provided both drivers
completed that lap.

Each export is written beneath:

```text
data/processed/year=2025/event=monaco-grand-prix/session=r/telemetry/
└── driver=<code>/lap=<number>/
    ├── samples.parquet           # Canonical data
    └── samples.csv               # Current C++ bridge input
```

Canonical telemetry columns are:

| Column | Meaning |
|---|---|
| `time_s` | Elapsed lap time in seconds |
| `distance_m` | Estimated lap distance in metres |
| `speed_mps` | Speed in metres per second |
| `throttle` | Normalized throttle from 0 to 1 |
| `brake` | Brake state represented as 0 or 1 |
| `gear` | Selected gear |
| `rpm` | Engine speed in revolutions per minute |
| `drs` | Normalized DRS state |

For the current Monaco cache, the fastest-lap selections are NOR lap 78 and
LEC lap 36.

### 2. Plot the original irregular samples

```bash
uv run python scripts/plot_telemetry_comparison.py \
  --series NOR=data/processed/year=2025/event=monaco-grand-prix/session=r/telemetry/driver=nor/lap=78/samples.csv \
  --series LEC=data/processed/year=2025/event=monaco-grand-prix/session=r/telemetry/driver=lec/lap=36/samples.csv \
  --output build/telemetry/monaco-raw.png \
  --title "Monaco 2025 race: fastest laps (raw)"
```

The plot contains speed, throttle/brake, gear, and an exploratory cumulative
time-delta trace against distance.

### 3. Resample both laps through C++

```bash
mkdir -p build/telemetry

build/cpp/apexsim_resample_csv \
  data/processed/year=2025/event=monaco-grand-prix/session=r/telemetry/driver=nor/lap=78/samples.csv \
  build/telemetry/nor-resampled.csv \
  1.0

build/cpp/apexsim_resample_csv \
  data/processed/year=2025/event=monaco-grand-prix/session=r/telemetry/driver=lec/lap=36/samples.csv \
  build/telemetry/lec-resampled.csv \
  1.0
```

The executable interface is:

```text
apexsim_resample_csv INPUT.csv OUTPUT.csv DISTANCE_STEP_METRES
```

Change `1.0` to `5.0` to experiment with a coarser five-metre grid.

### 4. Plot the C++ output

```bash
uv run python scripts/plot_telemetry_comparison.py \
  --series NOR=build/telemetry/nor-resampled.csv \
  --series LEC=build/telemetry/lec-resampled.csv \
  --output build/telemetry/monaco-resampled.png \
  --title "Monaco 2025 race: fastest laps (C++ 1 m resampling)"
```

In the delta panel, a value below zero means the first series is ahead of the
second at that estimated distance. This is currently an exploratory trace, not
an official lap delta: FastF1 estimates each lap's distance independently, and
the two laps can therefore have slightly different terminal distances.

## Generated files

The following are intentionally ignored by Git:

- `build/` and its CMake artifacts, CSV outputs, and plots;
- `.cache/fastf1/` downloaded API responses;
- generated files under `data/raw/` and `data/processed/`; and
- Python `__pycache__/` directories.

## Next milestone

The next C++ milestone is lap synchronization and a first-class delta
calculation. That work should explicitly define how independently estimated lap
distances are normalized before producing a comparison intended as an
analytics result rather than an exploratory visualization.

Additional project direction is documented in [`docs/`](docs/).
