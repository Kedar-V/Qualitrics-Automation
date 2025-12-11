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
    p.add_argument("--high-threshold", type=float, default=8)
    p.add_argument("--low-threshold", type=float, default=5)
    p.add_argument("--last-weight", type=float, default=0.7)
    p.add_argument("--prev-weight", type=float, default=0.3)
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
        df = pd.read_csv(args.input, skiprows=[1, 2])
    except Exception as e:
        print("Failed to load input file:", e)
        sys.exit(1)

    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    def find_col(part):
        matches = [c for c in df.columns if part.lower() in c.lower()]
        if not matches:
            raise KeyError(f"Required column not found containing: {part}")
        return matches[0]

    evaluator_col = "Name" if "Name" in df.columns else find_col("Name")
    team_col = "Team" if "Team" in df.columns else find_col("Team")
    ts_col = "RecordedDate" if "RecordedDate" in df.columns else find_col("Recorded")

    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")

    # -----------------------------
    # DETECT STUDENT RATING BLOCKS
    # -----------------------------
    comm_re = re.compile(r"^(.*)_Communication_1$")
    tech_re = re.compile(r"^(.*)_Technical_1$")
    reli_re = re.compile(r"^(.*)_Reliability_1$")
    fb_re   = re.compile(r"^(.*)_Feedback$")

    metric_cols = {}
    feedback_cols = {}

    for col in df.columns:
        for regex in [comm_re, tech_re, reli_re]:
            m = regex.match(col)
            if m:
                student = m.group(1).strip()
                metric_cols.setdefault(student, set()).add(col)

        m = fb_re.match(col)
        if m:
            student = m.group(1).strip()
            feedback_cols[student] = col

    long_records = []

    # -----------------------------
    # BUILD LONG FORMAT WITH TRUE METRICS
    # -----------------------------
    for _, row in df.iterrows():
        evaluator = str(row[evaluator_col]).strip()
        if evaluator == "" or evaluator.lower() in ["nan", "none"]:
            continue

        team = str(row.get(team_col, "")).strip()
        ts = row[ts_col]

        for student, cols in metric_cols.items():
            metric_map = {}
            raw_values = []

            for c in cols:
                val = row.get(c, None)
                if pd.notna(val):
                    try:
                        metric_name = c.split("_")[-2]   # Communication / Technical / Reliability
                        fval = float(val)
                        metric_map[metric_name] = fval
                        raw_values.append(fval)
                    except ValueError:
                        pass

            if not raw_values:
                continue

            avg_score = sum(raw_values) / len(raw_values)

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
                "raw_metrics": metric_map,
                "raw_values": raw_values,
                "feedback": fb_text,
                "timestamp": ts,
            })

    if not long_records:
        print("No valid rating records found.")
        sys.exit(1)

    long_df = pd.DataFrame(long_records)

    # -----------------------------
    # REMOVE SELF EVALS
    # -----------------------------
    long_df = long_df[
        long_df["evaluator"].str.lower() != long_df["student"].str.lower()
    ].copy()

    # -----------------------------
    # STABLE SORT FOR WEIGHTING
    # -----------------------------
    long_df["submission_order"] = range(len(long_df))

    long_df = long_df.sort_values(
        by=["evaluator", "student", "timestamp", "submission_order"]
    )

    # -----------------------------
    # WEIGHTING (AVG PER SUBMISSION)
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
    # RAW EVALUATIONS JSON (MULTI-SUBMISSION + WEIGHTED)
    # -----------------------------
    raw_grouped = (
        long_df.groupby(["student", "evaluator", "team"])
        .apply(lambda x: pd.Series({
            "scores": x["raw_metrics"].tolist(),
            "timestamps": x["timestamp"].astype(str).tolist(),
            "avg_scores": x["score"].round(3).tolist()
        }))
        .reset_index()
    )

    raw_grouped = raw_grouped.merge(
        weighted_df[["student", "evaluator", "Weighted_Score"]],
        on=["student", "evaluator"],
        how="left"
    )

    raw_eval_df = (
        raw_grouped.groupby("student")
        .apply(lambda x: json.dumps(
            [
                {
                    "team": r["team"],
                    "evaluator": r["evaluator"],
                    "scores": r["scores"],
                    "timestamps": r["timestamps"],
                    "avg_scores": r["avg_scores"],
                    "weighted_score": round(r["Weighted_Score"], 3)
                        if pd.notna(r["Weighted_Score"]) else None,
                }
                for _, r in x.iterrows()
            ],
            ensure_ascii=False
        ))
        .reset_index(name="Raw_Evaluations")
    )

    # -----------------------------
    # FEEDBACK SUMMARY AS DICT (JSON SAFE)
    # -----------------------------
    feedback_df = (
        long_df[long_df["feedback"].astype(str).str.strip() != ""]
        .groupby(["student", "evaluator"])["feedback"]
        .apply(list)
        .reset_index()
        .groupby("student")
        .apply(lambda x: json.dumps(
            {
                r["evaluator"]: r["feedback"]
                for _, r in x.iterrows()
            },
            ensure_ascii=False
        ))
        .reset_index(name="Feedback_Summary")
    )

    # -----------------------------
    # FINAL GRADE METRICS
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
    # ACTION (PERCENT BASED)
    # -----------------------------
    def classify_action(row):
        if row["Pct_Above_Threshold"] == 100:
            return "Bonus"
        if row["Pct_Below_Threshold"] >= 50:
            return "Attention"
        return "Normal"

    grade_df["Action"] = grade_df.apply(classify_action, axis=1)

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
