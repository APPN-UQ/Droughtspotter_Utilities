# DroughtSpotter Utilities

Analysis pipeline for Phenospex DroughtSpotter data exported from TraitFinder. Produces weather and weight summary plots from a single zip file.

## Setup

Create and activate the conda environment:

```
conda env create -f environment.yml
conda activate DroughtspotterUtilities
```

## Folder layout

Place these files together in one folder before running:

```
my_experiment/
  Tabular-data_Experiment_20260701.zip   ← TraitFinder zip export
  experimentFile.csv                      ← experiment program CSV (target weights)
```

## Running the pipeline

```
python run_pipeline.py "Tabular-data_Experiment_20260701.zip"
```

To change the number of days shown in the recent-data view (default is 5):

```
python run_pipeline.py "Tabular-data_Experiment_20260701.zip" --days 7
```

Always quote the zip path if it contains spaces.

## Output structure

Each run creates a datetime-stamped folder inside `outputs/` next to the zip:

```
my_experiment/
  outputs/
    2026-07-01_143210/
      pipeline_metadata.json
      most_recent/                         ← last N days
        *_weather_timeseries.png
        *_weather_daily.png
        *_weights_overview.png
        unit_plots/
          *_unit_*.png
      entire_dataset/                      ← full experiment duration
        *_weather_timeseries.png
        *_weather_daily.png
        *_weights_overview.png
        unit_plots/
          *_unit_*.png
```

### Plot descriptions

| File | Contents |
|---|---|
| `*_weather_timeseries.png` | Temperature, relative humidity, and PAR (flux density) at 10-min intervals |
| `*_weather_daily.png` | Daily mean ± min/max ribbon for each weather variable |
| `*_weights_overview.png` | All 120 unit weights on one chart, coloured by treatment |
| `unit_plots/*_unit_*.png` | Per-unit weight trace (blue) with target weight (red dashed) and air temperature overlay (orange, secondary axis) |

### Off-scale readings

When a balance is removed from the scale mid-experiment, the resulting near-zero weight reading is kept in the data but excluded from y-axis scaling — it will appear as a dip out of view rather than distorting the chart.

### Per-unit plots — two panels

Each unit plot has two side-by-side panels:
- **Local scale** — y-axis fitted to this unit's own weight range, for pattern detail
- **Experiment scale** — y-axis shared across all units, for cross-unit comparison

## experimentFile.csv format

The experiment CSV must contain a section with a header row that includes `block:column:row`. The first column is the unit ID and the second column is the target weight in grams. All rows above the header are ignored.

Example:

```
... (global settings) ...
unit (block:column:row),h,Irrigation_mode,...
1:1:1,25400,...
2:1:1,25800,...
```


