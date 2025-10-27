# Qualitrics-Automation

A small toolkit to build Qualtrics survey files from team CSVs and produce evaluation reports from survey results.

This repository contains two primary scripts:

- `main.py` — build a Qualtrics `.qsf` survey template from a team/member CSV.
- `report.py` — generate summary CSVs and plots from survey response data.

## Features

- Generate a ready-to-import Qualtrics `.qsf` file from a team-members CSV.
- Produce per-member statistics and skill-level plots from survey results.

## Prerequisites

- Python 3.8 or newer
- Install dependencies:

```sh
python -m pip install -r requirements.txt
```

## Usage

1) Generate a Qualtrics survey template

```sh
python main.py --input Project_Groups_Synthetic_data.csv --output generated.qsf
```

- `--input`: CSV containing team/member information (see `data.csv` as an example).
- `--output`: Path to write the generated `.qsf` file.

2) Generate evaluation reports from survey results

```sh
python report.py --input survey_data.csv --output SurveySummary.csv
```

- `--input`: CSV of survey responses (exported from Qualtrics or your collection pipeline).
- `--output`: CSV file to write summarized statistics (per-member) and to drive plots.

## Project layout

- `main.py` — builder for `.qsf` templates.
- `report.py` — report generation and plotting.
- `src/Builder.py`, `src/Survey.py`, `src/Templates.py` — core code that constructs the survey and templates.
- `data.csv`, `survey_data.csv`, `SurveySummary.csv` — example data and outputs.
- `plots/` — directory where generated plots are stored.
- `requirements.txt` — Python dependencies.

## Tips
- Check `data.csv` or `teams.json` for expected input fields and format before running `main.py`.



