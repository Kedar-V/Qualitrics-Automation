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

1) Generate a client evaluation survey template

```sh
python3 client_eval.py \
  --students data/data.csv \
  --output generated/client_evaluation.qsf
```

- `--students`: CSV containing team/member  information (see data/data.csv as an example).
- `--output`: Path to write the generated `.qsf` file for client evaluations.

2) Generate a mentor evaluation survey template

```sh
python3 mentor_eval.py \
  --students data/data.csv \
  --mentors data/mentor.csv \
  --output generated/mentor_evaluation.qsf
```

- `--students`: CSV containing student/mentee information (see `data/data.csv` as an example).
- `--mentors`: CSV containing mentor information (see data/mentor.csv as an example).
- `--output`: Path to write the generated `.qsf` file for mentor evaluations.

3) Generate a Student Eval Qualtrics survey

```sh
python main.py --input data/data.csv --output generated.qsf
```

- `--input`: CSV containing team/member information (see `data/data.csv` as an example).
- `--output`: Path to write the generated `.qsf` file.

4) Generate grades per student from peer evaluations

```sh
python3 grade.py \
  --input data/survey_data.csv \
  --output data/grade_per_student.csv \
  --high-threshold 8 \
  --low-threshold 7 \
  --last-weight 0.7 \
  --prev-weight 0.3
```

- `--input`: CSV of survey responses (exported from Qualtrics peer evaluation).
- `--output`: CSV file to write grade summaries per student.
- `--high-threshold`: Score threshold for "above threshold" classification (default: 8).
- `--low-threshold`: Score threshold for "below threshold" / "Attention" action (default: 5).
- `--last-weight`: Weight for the most recent submission (default: 0.7).
- `--prev-weight`: Weight for previous submissions combined (default: 0.3).

5) Generate evaluation reports from survey results (legacy)

```sh
python report.py --input data/survey_data.csv --output data/SurveySummary.csv
```

- `--input`: CSV of survey responses (exported from Qualtrics or your collection pipeline).
- `--output`: CSV file to write summarized statistics (per-member) and to drive plots.

## Project layout

- `main.py` — builder for `.qsf` templates (legacy).
- `client_eval.py` — generates client evaluation survey templates.
- `mentor_eval.py` — generates mentor evaluation survey templates.
- `grade.py` — generates grade summaries and action flags per student from peer evaluation responses.
- `report.py` — report generation and plotting (legacy).
- `src/Builder.py`, `src/Survey.py`, `src/Templates.py` — core code that constructs the survey and templates.
- `data.csv`, `survey_data.csv`, `SurveySummary.csv` — example data and outputs.
- `plots/` — directory where generated plots are stored.
- `requirements.txt` — Python dependencies.

## Tips
- Check `data.csv` or `teams.json` for expected input fields and format before running `main.py`.



