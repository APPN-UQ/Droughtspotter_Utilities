#!/usr/bin/env python3
import sys
import zipfile
from pathlib import Path
import os
os.environ.setdefault("MPLBACKEND", "Agg")
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.cm as cm
from weather_summary import read_climate_from_zip

_STYLE = {
    "axes.facecolor": "white", "figure.facecolor": "white",
    "axes.edgecolor": "#cccccc", "axes.grid": True,
    "grid.color": "#e5e5e5", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 11,
}


def read_droughtspotter_from_zip(zip_path):
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path) as zf:
        name = next((n for n in zf.namelist() if "DroughtSpotter" in n), None)
        if name is None:
            raise FileNotFoundError("No DroughtSpotter CSV found in zip.")
        with zf.open(name) as f:
            df = pd.read_csv(f, dtype={"unit": str}, parse_dates=["timestamp"])
    df = df.rename(columns={"Weight g": "weight_g", "Irrigation g": "irrigation_g"})
    df = df.dropna(subset=["timestamp"])
    med = df.groupby("unit")["weight_g"].transform("median")
    off = df["weight_g"] < 0.5 * med
    if off.sum():
        print(f"  Detected {int(off.sum())} off-scale reading(s) — kept in data, excluded from y-axis scaling")
    df["off_scale"] = off
    return df


def read_targets(exp_path):
    exp_path = Path(exp_path)
    raw = exp_path.read_text(encoding="utf-8", errors="replace").splitlines()
    idx = next((i for i, line in enumerate(raw) if "block:column:row" in line.lower()), None)
    if idx is None:
        raise ValueError("Could not find unit header row in experiment file.")
    df = pd.read_csv(exp_path, skiprows=idx, header=0,
                     usecols=[0, 1], names=["unit", "target_g"])
    df = df[df["unit"].str.contains(":", na=False)].copy()
    df["target_g"] = pd.to_numeric(df["target_g"], errors="coerce")
    return df.dropna(subset=["target_g"])


def parse_experiment_name(zip_path):
    return Path(zip_path).stem.removeprefix("Tabular-data_")


def check_irrigation(df, fold_upper=3.0, min_irr_g=10.0):
    totals = (
        df.groupby(["unit", "treatment", "genotype", "g_alias"])
        .agg(total_irr_g=("irrigation_g", "sum"))
        .reset_index()
    )
    trt_med = (
        totals.groupby("treatment")["total_irr_g"]
        .median().rename("trt_median_g").reset_index()
    )
    flags = totals.merge(trt_med, on="treatment")

    def _flag(r):
        if r.total_irr_g < min_irr_g and r.trt_median_g >= min_irr_g * 2:
            return "no_irrigation"
        if r.total_irr_g > r.trt_median_g * fold_upper:
            return "excess_irrigation"
        return "ok"

    flags["flag"] = flags.apply(_flag, axis=1)
    flags = flags.sort_values(["flag", "treatment", "unit"])

    n_none = (flags["flag"] == "no_irrigation").sum()
    n_exc  = (flags["flag"] == "excess_irrigation").sum()
    print(f"Irrigation QC  |  fold_upper={fold_upper:.1f}x  |  min_irr={min_irr_g:.0f} g")
    print(f"  No irrigation: {n_none}  |  Excess: {n_exc}")

    for lbl, fv in [("No irrigation", "no_irrigation"),
                    ("Excess irrigation", "excess_irrigation")]:
        sub = flags[flags["flag"] == fv]
        if not sub.empty:
            print(f"  {lbl}:")
            for _, r in sub.iterrows():
                if fv == "no_irrigation":
                    print(f"    {r.unit:<10}  trt={r.treatment:<4}  "
                          f"total={r.total_irr_g:.0f} g  (trt median={r.trt_median_g:.0f} g)")
                else:
                    print(f"    {r.unit:<10}  trt={r.treatment:<4}  "
                          f"total={r.total_irr_g:.0f} g  "
                          f"({r.total_irr_g / r.trt_median_g:.1f}x trt median={r.trt_median_g:.0f} g)")

    excluded = flags.loc[flags["flag"] != "ok", "unit"].tolist()
    return {"flags": flags, "excluded_units": excluded}


def filter_irrigation_outliers(df, fold_upper=3.0, min_irr_g=10.0):
    qc = check_irrigation(df, fold_upper=fold_upper, min_irr_g=min_irr_g)
    excl = qc["excluded_units"]
    if not excl:
        print("  No units removed.")
        return df
    print(f"  Removing {len(excl)} unit(s) from data.")
    return df[~df["unit"].isin(excl)].copy()


def _fmt_xaxis(ax):
    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b\n%H:%M"))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=9)


def _normal_ylim(weights, margin_frac=0.05, min_margin=10):
    """Y limits derived from on-scale data only, with a small margin."""
    lo, hi = weights.min(), weights.max()
    margin = max((hi - lo) * margin_frac, min_margin)
    return (lo - margin, hi + margin)


def make_overview_plot(df, experiment_name, ylim=None):
    treatments = sorted(df["treatment"].unique())
    palette = cm.tab20.resampled(len(treatments))
    cmap = {t: palette(i) for i, t in enumerate(treatments)}

    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=(14, 7), constrained_layout=True)
        fig.suptitle(f"{experiment_name} -- all units", fontsize=12, fontweight="bold")
        seen = {}
        for unit, grp in df.groupby("unit"):
            trt = grp["treatment"].iloc[0]
            line, = ax.plot(grp["timestamp"], grp["weight_g"],
                            color=cmap[trt], linewidth=0.35, alpha=0.7,
                            label=trt if trt not in seen else "_")
            seen[trt] = line
        ax.legend(list(seen.values()), list(seen.keys()),
                  title="Treatment", loc="upper right", fontsize=8, title_fontsize=9)
        ax.set_ylabel("Weight (g)")
        _fmt_xaxis(ax)
        if ylim is not None:
            ax.set_ylim(ylim)
    return fig


def _draw_unit_ax(ax, df_unit, target_g, ylabel=True):
    ax.plot(df_unit["timestamp"], df_unit["weight_g"],
            color="#2166ac", linewidth=0.6)
    if ylabel:
        ax.set_ylabel("Weight (g)")
    _fmt_xaxis(ax)
    if pd.notna(target_g):
        ax.axhline(target_g, linestyle="--", color="#d62728", linewidth=0.8)
        ax.text(df_unit["timestamp"].min(), target_g,
                f" target: {target_g:.0f} g",
                va="bottom", ha="left", fontsize=8, color="#d62728")


_TEMP_COLOUR = "#ff7f0e"


def make_unit_plot(df_unit, target_g, experiment_name, global_ylim=None, temp_df=None):
    r = df_unit.iloc[0]
    title = (f"{experiment_name} | unit {r['unit']} | "
             f"{r['genotype']} ({r['g_alias']}) | {r['treatment']}")

    normal = df_unit[~df_unit["off_scale"]] if "off_scale" in df_unit.columns else df_unit
    local_ylim  = _normal_ylim(normal["weight_g"])

    temp_sub = None
    if temp_df is not None and not temp_df.empty:
        t_min, t_max = df_unit["timestamp"].min(), df_unit["timestamp"].max()
        temp_sub = temp_df[
            (temp_df["timestamp"] >= t_min) & (temp_df["timestamp"] <= t_max)
        ]
        if temp_sub.empty:
            temp_sub = None

    with plt.rc_context(_STYLE):
        fig, (ax_local, ax_global) = plt.subplots(
            1, 2, figsize=(14, 5), constrained_layout=True, sharey=False
        )
        fig.suptitle(title, fontsize=10)

        # left: local scale — y range from this unit's normal data
        _draw_unit_ax(ax_local, df_unit, target_g, ylabel=True)
        ax_local.set_ylim(local_ylim)
        ax_local.set_title("local scale", fontsize=9, color="grey")

        # right: experiment scale — y range from all units' normal data
        _draw_unit_ax(ax_global, df_unit, target_g, ylabel=False)
        ax_global.set_title("experiment scale", fontsize=9, color="grey")
        if global_ylim is not None:
            ax_global.set_ylim(global_ylim)

        if temp_sub is not None:
            for ax in (ax_local, ax_global):
                ax2 = ax.twinx()
                ax2.plot(temp_sub["timestamp"], temp_sub["value"],
                         color=_TEMP_COLOUR, linewidth=0.5, alpha=0.6)
                ax2.set_ylabel("Temp (°C)", color=_TEMP_COLOUR, fontsize=8)
                ax2.tick_params(axis="y", colors=_TEMP_COLOUR, labelsize=7)
                ax2.spines["right"].set_visible(True)
                ax2.spines["right"].set_color(_TEMP_COLOUR)
                ax2.spines["top"].set_visible(False)

    return fig


def plot_weights(zip_path, exp_path, out_dir=None, show=True, days=None):
    zip_path  = Path(zip_path)
    exp_path  = Path(exp_path)
    experiment = parse_experiment_name(zip_path)
    out_dir   = Path(out_dir) if out_dir else zip_path.parent / "outputs" / experiment
    units_dir = out_dir / "unit_plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    units_dir.mkdir(parents=True, exist_ok=True)

    print(f"Reading DroughtSpotter data from {zip_path.name} ...")
    df = read_droughtspotter_from_zip(zip_path)
    print(f"  {len(df):,} records | {df['unit'].nunique()} units | "
          f"{df['timestamp'].min()} to {df['timestamp'].max()}")

    try:
        climate = read_climate_from_zip(zip_path)
        temp_df = climate[climate["variable"].str.contains("Temperature", na=False)].copy()
    except Exception:
        temp_df = None

    if days is not None:
        cutoff = df["timestamp"].max() - pd.Timedelta(days=days)
        df = df[df["timestamp"] >= cutoff].copy()
        if temp_df is not None:
            temp_df = temp_df[temp_df["timestamp"] >= cutoff].copy()
        print(f"  Filtered to last {days} days: {df['timestamp'].min()} to {df['timestamp'].max()}")

    print(f"Reading target weights from {exp_path.name} ...")
    targets = read_targets(exp_path)
    tgt = targets.set_index("unit")["target_g"]
    print(f"  {len(targets)} units with target weights")

    # y limits from on-scale data only — off-scale dips will go out of view
    normal_weights = df.loc[~df["off_scale"], "weight_g"]
    global_ylim = _normal_ylim(normal_weights)

    print("Building overview plot ...")
    fig_ov = make_overview_plot(df, experiment, ylim=global_ylim)
    ov_file = out_dir / f"{experiment}_weights_overview.png"
    fig_ov.savefig(ov_file, dpi=150, bbox_inches="tight")
    plt.close(fig_ov)
    print(f"  Saved: {ov_file}")

    units = sorted(df["unit"].unique())
    w_min, w_max = normal_weights.min(), normal_weights.max()
    print(f"Building {len(units)} unit plots (shared y-axis: {w_min:.0f}–{w_max:.0f} g) ...")
    for u in units:
        fig_u = make_unit_plot(df[df["unit"] == u], tgt.get(u, float("nan")), experiment,
                               global_ylim=global_ylim, temp_df=temp_df)
        fig_u.savefig(units_dir / f"{experiment}_unit_{u.replace(':', '_')}.png",
                      dpi=150, bbox_inches="tight")
        plt.close(fig_u)
    print(f"  Saved {len(units)} plots to: {units_dir}")

    if show:
        plt.show()
    return {"data": df, "targets": targets}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python weight_summary.py <zip_path> <experiment_csv> [out_dir]")
        sys.exit(1)
    plot_weights(
        zip_path=sys.argv[1],
        exp_path=sys.argv[2],
        out_dir=sys.argv[3] if len(sys.argv) >= 4 else None,
        show=False,
    )
