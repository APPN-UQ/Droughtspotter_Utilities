#!/usr/bin/env python3
import sys
import zipfile
from pathlib import Path
import os
os.environ.setdefault("MPLBACKEND", "Agg")
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

_STYLE = {
    "axes.facecolor": "white", "figure.facecolor": "white",
    "axes.edgecolor": "#cccccc", "axes.grid": True,
    "grid.color": "#e5e5e5", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 11,
}
_VAR_COLOURS = {"Temperature": "#d62728", "Humidity": "#1f77b4", "Flux": "#ff7f0e"}
_VAR_LABELS  = {
    "Temperature": "Temperature (C)",
    "Humidity":    "Relative Humidity (%)",
    "Flux":        "PAR (umol/s/m2)",
}


def read_climate_from_zip(zip_path):
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        name = next((n for n in zf.namelist() if "Climate Datalogger" in n), None)
        if name is None:
            raise FileNotFoundError("No Climate Datalogger CSV found in zip.")
        with zf.open(name) as f:
            df = pd.read_csv(f, parse_dates=["timestamp"])
    return df.dropna(subset=["timestamp"])


def parse_experiment_name(zip_path):
    return Path(zip_path).stem.removeprefix("Tabular-data_")


def _daily_summary(df):
    d = df.copy()
    d["date"] = d["timestamp"].dt.normalize()
    return (
        d.groupby(["date", "variable"])["value"]
        .agg(mean="mean", min="min", max="max")
        .reset_index()
    )


def _fmt_xaxis(ax):
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=9)


def make_weather_plots(df, experiment_name):
    with plt.rc_context(_STYLE):
        fig, axes = plt.subplots(3, 1, figsize=(12, 9), sharex=True,
                                 constrained_layout=True)
        fig.suptitle(experiment_name, fontsize=12, fontweight="bold")
        for ax, key in zip(axes, ["Temperature", "Humidity", "Flux"]):
            sub = df[df["variable"].str.contains(key, na=False)]
            ax.plot(sub["timestamp"], sub["value"],
                    color=_VAR_COLOURS[key], linewidth=0.5)
            ax.set_ylabel(_VAR_LABELS[key], fontsize=10)
            if key == "Humidity":
                ax.set_ylim(0, 100)
        _fmt_xaxis(axes[-1])
    return fig


def make_daily_summary_plot(df, experiment_name):
    _DISPLAY = {
        "Temperature": "Temperature (C)",
        "Humidity":    "Relative Humidity (%)",
        "Flux":        "PAR (umol/s/m2)",
    }
    def _label(v):
        return next((lbl for k, lbl in _DISPLAY.items() if k in v), v)

    ds = _daily_summary(df)
    ds["label"] = ds["variable"].apply(_label)
    groups = sorted(ds["label"].unique())

    with plt.rc_context(_STYLE):
        fig, axes = plt.subplots(len(groups), 1, figsize=(8, 9),
                                 constrained_layout=True)
        fig.suptitle(f"{experiment_name} -- daily summary",
                     fontsize=12, fontweight="bold")
        for ax, grp in zip(axes, groups):
            sub = ds[ds["label"] == grp].sort_values("date")
            ax.fill_between(sub["date"], sub["min"], sub["max"],
                            color="steelblue", alpha=0.25)
            ax.plot(sub["date"], sub["mean"], color="steelblue", linewidth=0.8)
            ax.scatter(sub["date"], sub["mean"], color="steelblue", s=20, zorder=3)
            ax.set_ylabel(grp, fontsize=9)
            ax.xaxis.set_major_locator(mdates.DayLocator())
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
            plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=9)
        fig.text(0.5, 0.01, "Line = daily mean; ribbon = daily min-max",
                 ha="center", fontsize=9, color="grey")
    return fig


def plot_weather(zip_path, out_dir=None, show=True, days=None):
    zip_path = Path(zip_path)
    experiment = parse_experiment_name(zip_path)
    out_dir = Path(out_dir) if out_dir else zip_path.parent / "outputs" / experiment
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Reading climate data from {zip_path.name} ...")
    df = read_climate_from_zip(zip_path)
    print(f"  {len(df):,} records | {df['timestamp'].min()} to {df['timestamp'].max()}")
    if days is not None:
        cutoff = df["timestamp"].max() - pd.Timedelta(days=days)
        df = df[df["timestamp"] >= cutoff].copy()
        print(f"  Filtered to last {days} days: {df['timestamp'].min()} to {df['timestamp'].max()}")

    fig_ts  = make_weather_plots(df, experiment)
    fig_day = make_daily_summary_plot(df, experiment)

    ts_file  = out_dir / f"{experiment}_weather_timeseries.png"
    day_file = out_dir / f"{experiment}_weather_daily.png"
    fig_ts.savefig(ts_file,  dpi=150, bbox_inches="tight")
    fig_day.savefig(day_file, dpi=150, bbox_inches="tight")
    plt.close("all")
    print(f"Saved:\n  {ts_file}\n  {day_file}")

    if show:
        plt.show()
    return df


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python weather_summary.py <zip_path> [out_dir]")
        sys.exit(1)
    plot_weather(
        zip_path=sys.argv[1],
        out_dir=sys.argv[2] if len(sys.argv) >= 3 else None,
        show=False,
    )