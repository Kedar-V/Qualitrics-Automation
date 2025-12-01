#!/usr/bin/env python3

import argparse
import pandas as pd
import json
import re
import sys

# -----------------------------
# CLI
# -----------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description="Generate Grade per Student table from Qualtrics peer eval export"
    )
    p.add_argument("--input", required=True, help="Input Qualtrics CSV")
    p.add_argument("--output", required=True, help="Output grade-per-student CSV")
    p.add_argument("--high-threshold", type=float, default=8,
                   help="High threshold (default: 8)")
    p.add_argument("--low-threshold", type=float, default=5,
                   help="Low threshold (default: 5)")
    p.add_argument("--last-weight", type=float, default=0.7,
                   help="Weight for last submission (default: 0.7)")
    p.add_argument("--prev-weight", type=float, default=0.3,
                   help="Weight for previous submissions combined (default: 0.3)")
    return p.parse_args()


def main():
    args = parse_args()

    HIGH = args.high_threshold
    LOW = args.low_threshold
    W_LAST = args.last_weight
    W_PREV = args.prev_weight

    # -----------------------------
    # LOAD & CLEAN RAW CSV
    # -----------------------------
    try:
        # keep row 0 as header, skip Qualtrics label & ImportId rows (1 and 2)
        df = pd.read_csv(args.input, skiprows=[1, 2])
    except Exception as e:
        print("Failed to load input file:", e)
        sys.exit(1)

    # Normalise column names: strip, collapse spaces
    df.columns = (
        df.columns
          .astype(str)
          .str.strip()
          .str.replace(r"\s+", " ", regex=True)
    )

    # Helper to find a column by a substring (case insensitive)
    def find_col(part):
        matches = [c for c in df.columns if part.lower() in c.lower()]
        if not matches:
            raise KeyError(f"Required column not found containing: {part}")
        return matches[0]

    # Identify key metadata columns
    # In your header these are: Name, DukeID, Email, Team, RecordedDate
    if "Name" in df.columns:
        evaluator_col = "Name"
    else:
        evaluator_col = find_col("Name")

    if "Team" in df.columns:
        team_col = "Team"
    else:
        team_col = find_col("Team")

    if "RecordedDate" in df.columns:
        ts_col = "RecordedDate"
    else:
        # fallback if Qualtrics changes it
        ts_col = find_col("Recorded")

    # Parse timestamps robustly
    df[ts_col] = pd.to_datetime(
        df[ts_col],
        errors="coerce",
        infer_datetime_format=True
    )

    # -----------------------------
    # DETECT STUDENT RATING BLOCKS
    # -----------------------------
    comm_re = re.compile(r"^(.*)_Communication_1$")
    tech_re = re.compile(r"^(.*)_Technical_1$")
    reli_re = re.compile(r"^(.*)_Reliability_1$")
    fb_re   = re.compile(r"^(.*)_Feedback$")

    metric_cols = {}   # student -> [comm_col, tech_col, reli_col]
    feedback_cols = {} # student -> feedback_col

    for col in df.columns:
        m = comm_re.match(col)
        if m:
            student = m.group(1).strip()
            metric_cols.setdefault(student, set()).add(col)
            continue

        m = tech_re.match(col)
        if m:
            student = m.group(1).strip()
            metric_cols.setdefault(student, set()).add(col)
            continue

        m = reli_re.match(col)
        if m:
            student = m.group(1).strip()
            metric_cols.setdefault(student, set()).add(col)
            continue

        m = fb_re.match(col)
        if m:
            student = m.group(1).strip()
            feedback_cols[student] = col
            continue

    long_records = []

    for _, row in df.iterrows():
        evaluator = str(row[evaluator_col]).strip()
        if evaluator == "" or evaluator.lower() in ["nan", "none"]:
            continue 

        team = row.get(team_col, None)
        ts = row[ts_col]

        for student, cols in metric_cols.items():
            scores = []
            for c in cols:
                val = row.get(c, None)
                if pd.notna(val):
                    try:
                        scores.append(float(val))
                    except ValueError:
                        pass

            if not scores:
                continue

            avg_score = sum(scores) / len(scores)
            fb_text = ""
            if student in feedback_cols:
                fb_val = row.get(feedback_cols[student], "")
                if pd.notna(fb_val):
                    fb_text = str(fb_val)

            long_records.append({
                "team": team,
                "evaluator": evaluator,
                "student": student,
                "score": avg_score,
                "feedback": fb_text,
                "timestamp": ts,
            })

    if not long_records:
        print("No valid rating records found – check column patterns.")
        sys.exit(1)

    long_df = pd.DataFrame(long_records)

    # -----------------------------
    # REMOVE SELF-EVALUATIONS (simple name match, can refine later)
    # -----------------------------
    long_df = long_df[
        long_df["evaluator"].str.lower() != long_df["student"].str.lower()
    ].copy()

    # -----------------------------
    # SORT FOR MULTI-SUBMISSION WEIGHTING
    # -----------------------------
    long_df = long_df.sort_values(
        by=["evaluator", "student", "timestamp"]
    )

    # -----------------------------
    # APPLY WEIGHTING PER evaluator–student
    # -----------------------------
    def compute_weighted(group):
        scores = group["score"].tolist()
        times = group["timestamp"].astype(str).tolist()

        if len(scores) == 1:
            w = scores[-1]
        else:
            last = scores[-1]
            prev_avg = sum(scores[:-1]) / len(scores[:-1])
            w = W_LAST * last + W_PREV * prev_avg

        return pd.Series({
            "Weighted_Score": w,
            "Raw_Scores": scores,
            "Timestamps": times
        })

    weighted_df = (
        long_df.groupby(["evaluator", "student", "team"])
               .apply(compute_weighted)
               .reset_index()
    )

    # -----------------------------
    # RAW EVALUATIONS JSON PER STUDENT
    # -----------------------------
    raw_eval_df = (
        weighted_df.groupby("student")
        .apply(lambda x: json.dumps(
            [
                {
                    "evaluator": r["evaluator"],
                    "scores": r["Raw_Scores"],
                    "timestamps": r["Timestamps"],
                    "weighted_score": round(r["Weighted_Score"], 3),
                }
                for _, r in x.iterrows()
            ],
            ensure_ascii=False
        ))
        .reset_index(name="Raw_Evaluations")
    )

    # -----------------------------
    # CONSOLIDATED FEEDBACK PER STUDENT
    # -----------------------------

    # Placeholder for now
    feedback_df = (
        long_df.groupby("student")
               .apply(lambda x: " | ".join(
                   f"{r['evaluator']}: {str(r['feedback'])}"
                   for _, r in x.iterrows()
                   if str(r["feedback"]).strip() != ""
               ))
               .reset_index(name="Feedback_Summary")
    )

    # -----------------------------
    # FINAL GRADE METRICS PER STUDENT
    # -----------------------------
    grade_df = (
        weighted_df.groupby(["team", "student"])
        .agg(
            Avg_Score=("Weighted_Score", "mean"),
            Pct_Above_Threshold=("Weighted_Score",
                lambda s: (s >= HIGH).mean() * 100),
            Pct_Below_Threshold=("Weighted_Score",
                lambda s: (s < LOW).mean() * 100),
        )
        .reset_index()
    )

    # -----------------------------
    # ACTION COLUMN
    # -----------------------------
    def classify_action(avg):
        if round(avg, 6) == 10:
            return "Bonus"
        if avg <= LOW:
            return "Attention"
        return "Normal"

    grade_df["Action"] = grade_df["Avg_Score"].apply(classify_action)

    # -----------------------------
    # MERGE EVERYTHING
    # -----------------------------
    final = grade_df.merge(raw_eval_df, on="student", how="left")
    final = final.merge(feedback_df, on="student", how="left")

    final["Avg_Score"] = final["Avg_Score"].round(2)
    final["Pct_Above_Threshold"] = final["Pct_Above_Threshold"].round(2)
    final["Pct_Below_Threshold"] = final["Pct_Below_Threshold"].round(2)

    # -----------------------------
    # SAVE
    # -----------------------------
    final.to_csv(args.output, index=False)

    print("Done")
    print("Students graded:", len(final))
    print("Output written to:", args.output)
    print("High threshold:", HIGH, "Low threshold:", LOW)
    print("Weights last/prev:", W_LAST, "/", W_PREV)


if __name__ == "__main__":
    main()
