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
        description="Generate Client Grade Report from Qualtrics Client Survey"
    )
    p.add_argument("--input", required=True, help="Input Qualtrics Client CSV")
    p.add_argument("--output", required=True, help="Output Client Grade CSV")
    p.add_argument("--high-threshold", type=float, default=8)
    p.add_argument("--low-threshold", type=float, default=5)    

    return p.parse_args()


# -----------------------------
# MAIN
# -----------------------------
def main():
    args = parse_args()
    HIGH = args.high_threshold
    LOW = args.low_threshold

    # -----------------------------
    # LOAD CSV
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

    team_col = "ProjectTeam"
    client_name_col = "ClientName"
    ts_col = "RecordedDate"

    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")

    # -----------------------------
    # DETECT TEAM METRICS & FEEDBACK
    # -----------------------------
    team_metric_re = re.compile(r"^([A-Z])_(.*?)_1$")
    feedback_re = re.compile(r"^([A-Z])_AdditionalFeedback$")

    metric_cols = {}
    feedback_cols = {}

    for col in df.columns:
        m = team_metric_re.match(col)
        if m:
            team = m.group(1)
            metric = m.group(2)
            metric_cols.setdefault(team, {})[metric] = col

        m = feedback_re.match(col)
        if m:
            feedback_cols[m.group(1)] = col

    # -----------------------------
    # DETECT CANDIDATE COLUMNS
    # -----------------------------
    candidate_cols = {
        col.replace("_Overall_1", ""): col
        for col in df.columns
        if col.endswith("_Overall_1")
    }

    # -----------------------------
    # BUILD LONG FORMAT
    # -----------------------------
    long_records = []

    for _, row in df.iterrows():

        evaluator = str(row.get(client_name_col, "")).strip()
        if evaluator == "" or evaluator.lower() == "nan":
            evaluator = f"Reviewer_{row.get('ResponseId', 'Unknown')}"

        ts = row[ts_col]

        for team, metrics in metric_cols.items():

            raw_values = []
            raw_metrics = {}

            for metric, col_name in metrics.items():
                val = row.get(col_name, None)
                if pd.notna(val):
                    try:
                        raw_metrics[metric] = float(val)
                        raw_values.append(float(val))
                    except ValueError:
                        pass

            if not raw_values:
                continue

            avg_score = sum(raw_values) / len(raw_values)

            fb_text = ""
            if team in feedback_cols:
                fb_val = row.get(feedback_cols[team], "")
                if pd.notna(fb_val):
                    fb_text = str(fb_val)

            candidate_scores = {}
            for cand, col in candidate_cols.items():
                val = row.get(col, None)
                if pd.notna(val):
                    try:
                        candidate_scores[cand] = float(val)
                    except ValueError:
                        pass

            long_records.append({
                "team": team,
                "evaluator": evaluator,
                "score": avg_score,
                "candidates": candidate_scores,
                "feedback": fb_text,
                "timestamp": ts,
                "Organization": row.get("Organization", None)
            })

    if not long_records:
        print("No valid client ratings found.")
        sys.exit(1)

    long_df = pd.DataFrame(long_records)

    # -----------------------------
    # ORGANIZATION PER TEAM (MODE)
    # -----------------------------
    org_map = (
        long_df[["team", "Organization"]]
        .dropna()
        .groupby("team")["Organization"]
        .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else x.iloc[0])
        .to_dict()
    )

    # -----------------------------
    # 70/30 WEIGHTING PER TEAM + CLIENT
    # -----------------------------
    long_df = long_df.sort_values(
        by=["team", "evaluator", "timestamp"]
    )

    def compute_weighted(group):
        scores = group["score"].tolist()

        if len(scores) == 1:
            w = scores[-1]
        else:
            last = scores[-1]
            prev_avg = sum(scores[:-1]) / len(scores[:-1])
            w = 0.7 * last + 0.3 * prev_avg

        return pd.Series({"Weighted_Score": w})

    weighted_df = (
        long_df.groupby(["team", "evaluator"])
        .apply(compute_weighted)
        .reset_index()
    )

    # -----------------------------
    # FINAL TEAM METRICS (FROM WEIGHTED)
    # -----------------------------
    grade_df = (
        weighted_df.groupby("team")
        .agg(
            Avg_Score=("Weighted_Score", "mean"),
            Pct_Above_Threshold=("Weighted_Score",
                lambda s: (s >= HIGH).mean() * 100),
            Pct_Below_Threshold=("Weighted_Score",
                lambda s: (s < LOW).mean() * 100),
            Reviewer_Count=("evaluator", "nunique"),
        )
        .reset_index()
    )

    grade_df["Organization"] = grade_df["team"].map(org_map)

    # -----------------------------
    # ACTION RULES
    # -----------------------------
    def classify_action(avg):
        if round(avg, 6) == 10:
            return "Bonus"
        if avg <= LOW:
            return "Attention"
        return "Normal"

    grade_df["Action"] = grade_df["Avg_Score"].apply(classify_action)

    # -----------------------------
    # CLIENT JSON COLUMNS (LIST OF ALL EVALS)
    # -----------------------------
    client_blocks = (
        long_df.sort_values("timestamp")
        .groupby(["team", "evaluator"])
        .apply(lambda x: {
            "weighted_overall": (
                x["score"].iloc[-1] if len(x) == 1
                else round(
                    0.7 * x["score"].iloc[-1]
                    + 0.3 * x["score"].iloc[:-1].mean(),
                    3
                )
            ),
            "evaluations": [
                {
                    "timestamp": str(ts) if pd.notna(ts) else None,
                    "overall": round(sc, 3),
                    "candidates": cand,
                    "feedback": fb
                }
                for ts, sc, cand, fb in zip(
                    x["timestamp"],
                    x["score"],
                    x["candidates"],
                    x["feedback"]
                )
            ]
        })
        .reset_index(name="client_block")
    )

    client_blocks["client_col"] = client_blocks["evaluator"].apply(
        lambda x: f"Client_{str(x).strip().replace(' ', '_')}"
    )

    client_wide = (
        client_blocks.pivot_table(
            index="team",
            columns="client_col",
            values="client_block",
            aggfunc="first"
        )
        .reset_index()
    )

    for col in client_wide.columns:
        if col != "team":
            client_wide[col] = client_wide[col].apply(
                lambda x: json.dumps(x, ensure_ascii=False)
                if isinstance(x, dict) else ""
            )

    # -----------------------------
    # MERGE EVERYTHING
    # -----------------------------
    final = grade_df.merge(client_wide, on="team", how="left")

    final["Avg_Score"] = final["Avg_Score"].round(2)
    final["Pct_Above_Threshold"] = final["Pct_Above_Threshold"].round(2)
    final["Pct_Below_Threshold"] = final["Pct_Below_Threshold"].round(2)

    cols = list(final.columns)
    if "Organization" in cols:
        cols.insert(1, cols.pop(cols.index("Organization")))
        final = final[cols]

    # -----------------------------
    # SAVE
    # -----------------------------
    final.to_csv(args.output, index=False)

    print("✅ Done")
    print("Teams graded:", len(final))
    print("Output written to:", args.output)
    print("High threshold:", HIGH, "Low threshold:", LOW)


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    main()
