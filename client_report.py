#!/usr/bin/env python3

import argparse
import pandas as pd
import json
import re
import sys

# -----------------------------
# CONSTANTS / METRIC NAME MAP
# -----------------------------
METRIC_DISPLAY_NAMES = {
    "OverallSatisfaction": "Team_OverallSatisfaction",
    "TechnicalEquipped": "Team_TechnicalEquipped",
    "Independence": "Team_Independence",
    "MeetingUse": "Team_MeetingUse",
    "FutureCollab": "Team_FutureCollaboration",
}


# -----------------------------
# CLI
# -----------------------------
def parse_args():
    p = argparse.ArgumentParser(
        description="Generate Client Grade Report from Qualtrics Client Survey"
    )
    p.add_argument("--input", required=True, help="Input Qualtrics Client CSV")
    p.add_argument("--output", required=True, help="Output Client Grade CSV")
    p.add_argument(
        "--team-output",
        required=False,
        help="Optional team-Level Output CSV",
    )
    p.add_argument("--high-threshold", type=float, default=8)
    p.add_argument("--low-threshold", type=float, default=5)

    p.add_argument(
        "--metric-agg-mode",
        choices=["mean", "weighted"],
        default="mean",
        help="Aggregation mode for evaluator scores and team metrics "
             "(mean or weighted)",
    )
    p.add_argument(
        "--latest-weight",
        type=float,
        default=0.7,
        help="Weight for the most recent evaluation when using "
             "metric-agg-mode=weighted",
    )
    p.add_argument(
        "--prev-weight",
        type=float,
        default=0.3,
        help="Weight for the average of previous evaluations when using "
             "metric-agg-mode=weighted",
    )

    # Bonus as PERCENT (5 means 5 percent bonus)
    p.add_argument(
        "--bonus-multiplier",
        type=float,
        default=5.0,
        help="Bonus percent for Bonus action (5 means 5 percent bonus)",
    )

    return p.parse_args()


# -----------------------------
# GENERIC AGGREGATION FUNCTION
# -----------------------------
def aggregate_metric(values, mode="mean",
                     latest_weight=0.7,
                     previous_weight=0.3):
    """
    Aggregates a list of numeric values.

    Parameters:
        values: list of floats
        mode: "mean" or "weighted"
        latest_weight: weight assigned to the most recent evaluation
        previous_weight: weight assigned to the average of previous evaluations

    Returns:
        float or None
    """

    # Clean invalid entries
    values = [v for v in values if v is not None and pd.notna(v)]

    if not values:
        return None

    if mode == "mean":
        return sum(values) / len(values)

    if mode == "weighted":
        if len(values) == 1:
            return values[-1]

        last = values[-1]
        prev_values = values[:-1]
        prev_avg = sum(prev_values) / len(prev_values)

        # normalise weights to avoid surprises
        w_sum = latest_weight + previous_weight
        if w_sum == 0:
            # fallback to simple mean if weights are degenerate
            return sum(values) / len(values)
        lw = latest_weight / w_sum
        pw = previous_weight / w_sum

        return lw * last + pw * prev_avg

    raise ValueError(f"Unknown aggregation mode: {mode}")


def compute_individual_final_score(row, bonus_multiplier):
    """
    Compute the final individual score from team and student metrics.

    bonus_multiplier is already converted to a true multiplier,
    e.g. 5 percent → 1.05.
    """
    team_score = row.get("Team_Avg_Score")
    individual_avg = row.get("Student_Overall_Avg")
    action = row.get("Action")

    if pd.isna(team_score) or pd.isna(individual_avg) or not action:
        return None

    if action == "Normal":
        return team_score * 10

    if action == "Attention":
        return team_score * individual_avg

    if action == "Bonus":
        return team_score * 10 * bonus_multiplier

    return None


# -----------------------------
# STUDENT-LEVEL OUTPUT
# -----------------------------
def build_student_level_output(
    long_df: pd.DataFrame,
    team_df: pd.DataFrame,
    LOW: float,
    metric_agg_mode: str,
    latest_weight: float,
    prev_weight: float,
    bonus_percent: float,
) -> pd.DataFrame:
    """
    Build student-level metrics.

    Steps:
    1) Expand each evaluator record into per-student rows.
    2) Apply chosen aggregation per evaluator per student
       (mean or weighted).
    3) Average weighted scores across evaluators.
    4) Aggregate feedback.
    5) Classify Action per student using Student_Overall_Avg & LOW threshold.
    6) Merge team-level metrics and dimensions onto each student.
    7) Compute Individual_Final_Score using team score, student score and bonus.
    8) Attach Raw_Scores (JSON list of all raw scores) at the end.
    """

    # Convert percent to true multiplier: 5 → 1.05
    bonus_multiplier = 1 + (bonus_percent / 100.0)

    records = []

    # Expand candidates to long format
    for _, row in long_df.iterrows():
        candidates = row.get("candidates", {})
        if not isinstance(candidates, dict):
            continue

        team = row.get("team")
        evaluator = row.get("evaluator")
        ts = row.get("timestamp")
        feedback = row.get("feedback", "")

        for student_name, score in candidates.items():
            try:
                score_val = float(score)
            except (TypeError, ValueError):
                continue

            records.append({
                "team": team,
                "evaluator": evaluator,
                "timestamp": ts,
                "Student_Name": student_name,
                "score": score_val,
                "feedback": feedback,
            })

    if not records:
        return pd.DataFrame()

    stu_long = pd.DataFrame(records)

    # Sort for deterministic aggregation
    stu_long = stu_long.sort_values(
        by=["team", "Student_Name", "evaluator", "timestamp"]
    )

    # Aggregation per evaluator per student
    def compute_student_weighted(group):
        values = group["score"].tolist()
        w = aggregate_metric(
            values,
            mode=metric_agg_mode,
            latest_weight=latest_weight,
            previous_weight=prev_weight,
        )
        return pd.Series({"Weighted_Student_Score": w})

    weighted_students = (
        stu_long.groupby(["team", "Student_Name", "evaluator"])
        .apply(compute_student_weighted)
        .reset_index()
    )

    # Aggregate across evaluators
    agg = (
        weighted_students.groupby(["team", "Student_Name"])
        .agg(
            Student_Overall_Avg=("Weighted_Student_Score", "mean"),
            Eval_Count=("evaluator", "nunique"),
        )
        .reset_index()
    )

    # Combine feedback
    fb_series = (
        stu_long[["team", "Student_Name", "feedback"]]
        .dropna(subset=["feedback"])
    )
    fb_map = (
        fb_series.groupby(["team", "Student_Name"])["feedback"]
        .agg(lambda x: [str(f).strip() for f in x if str(f).strip() != ""])
        .to_dict()
    )
    agg["Feedback_Combined"] = agg.apply(
        lambda r: fb_map.get((r["team"], r["Student_Name"]), ""),
        axis=1,
    )

    # STUDENT-LEVEL ACTION RULES
    def classify_student_action(avg):
        if pd.isna(avg):
            return ""
        if round(avg, 6) == 10:
            return "Bonus"
        if avg <= LOW:
            return "Attention"
        return "Normal"

    agg["Action"] = agg["Student_Overall_Avg"].apply(classify_student_action)

    # Merge team-level metrics & dimensions
    # Expected in team_df: team, Organization, Avg_Score, Pct_Above_Threshold,
    # Pct_Below_Threshold, Reviewer_Count, plus dimension columns and raw.
    team_metric_cols = [
        "team",
        "Organization",
        "Avg_Score",
        "Pct_Above_Threshold",
        "Pct_Below_Threshold",
        "Reviewer_Count",
    ] + list(METRIC_DISPLAY_NAMES.values()) + [
        name + "_Raw" for name in METRIC_DISPLAY_NAMES.values()
    ]

    available_team_cols = [c for c in team_metric_cols if c in team_df.columns]
    team_info = team_df[available_team_cols].copy()

    # Rename core team metrics for clarity in student-level CSV
    rename_map = {
        "Avg_Score": "Team_Avg_Score",
        "Pct_Above_Threshold": "Team_Pct_Above_Threshold",
        "Pct_Below_Threshold": "Team_Pct_Below_Threshold",
        "Reviewer_Count": "Team_Reviewer_Count",
    }
    team_info = team_info.rename(columns=rename_map)

    agg = agg.merge(team_info, on="team", how="left")

    # Compute individual final score
    agg["Student_Final_Score"] = agg.apply(
        lambda row: compute_individual_final_score(row, bonus_multiplier),
        axis=1
    )

    # Build Raw_Scores JSON arrays per student (all raw scores across evaluators)
    raw_map = (
        stu_long.groupby(["team", "Student_Name"])["score"]
        .agg(lambda x: json.dumps([float(v) for v in x if pd.notna(v)]))
        .to_dict()
    )

    agg["Raw_Scores"] = agg.apply(
        lambda r: raw_map.get((r["team"], r["Student_Name"]), "[]"),
        axis=1
    )

    # ROUND STUDENT-LEVEL NUMERIC VALUES TO 3 DECIMALS
    num_cols = agg.select_dtypes(include="number").columns
    agg[num_cols] = agg[num_cols].round(3)

    # Final column ordering
    dim_cols = list(METRIC_DISPLAY_NAMES.values())
    dim_raw_cols = [name + "_Raw" for name in dim_cols]

    final_cols = [
        "team",
        "Organization",
        "Student_Name",
        "Student_Final_Score",
        "Student_Overall_Avg",
        "Team_Avg_Score",
        # "Eval_Count",
        "Feedback_Combined",
        "Action",
    ] + dim_cols + [
        "Team_Pct_Above_Threshold",
        "Team_Pct_Below_Threshold",
        "Raw_Scores",
    ] + dim_raw_cols

    final_cols = [c for c in final_cols if c in agg.columns]
    agg = agg[final_cols]

    return agg


# -----------------------------
# MAIN
# -----------------------------
def main():
    args = parse_args()
    HIGH = args.high_threshold
    LOW = args.low_threshold
    metric_agg_mode = args.metric_agg_mode
    latest_weight = args.latest_weight
    prev_weight = args.prev_weight

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
    # BUILD LONG FORMAT (TEAM OVERALL SCORES)
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
    # TEAM DIMENSION METRICS (5 COLS + RAW)
    # -----------------------------
    # Compute per-team aggregated metrics (Overall Satisfaction, etc.)
    team_dim_records = []
    for team, metrics in metric_cols.items():
        # Filter rows for this team and sort by timestamp
        sub = df[df[team_col] == team].sort_values(ts_col)
        rec = {"team": team}
        for metric_name, col_name in metrics.items():
            vals = pd.to_numeric(sub[col_name], errors="coerce").dropna().tolist()

            if vals:
                agg_val = aggregate_metric(
                    vals,
                    mode=metric_agg_mode,
                    latest_weight=latest_weight,
                    previous_weight=prev_weight,
                )
            else:
                agg_val = None

            display_name = METRIC_DISPLAY_NAMES.get(metric_name, metric_name)
            rec[display_name] = agg_val
            rec[display_name + "_Raw"] = json.dumps(vals) if vals else "[]"

        team_dim_records.append(rec)

    team_dim_df = (
        pd.DataFrame(team_dim_records)
        if team_dim_records else pd.DataFrame(columns=["team"])
    )

    # -----------------------------
    #  AGGREGATED TEAM SCORE PER EVALUATOR
    # -----------------------------
    long_df = long_df.sort_values(
        by=["team", "evaluator", "timestamp"]
    )

    def compute_weighted(group):
        values = group["score"].tolist()
        w = aggregate_metric(
            values,
            mode=metric_agg_mode,
            latest_weight=latest_weight,
            previous_weight=prev_weight,
        )
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

    # Merge team dimension metrics (5 cols + raw) into team metrics
    if not team_dim_df.empty:
        grade_df = grade_df.merge(team_dim_df, on="team", how="left")

    # -----------------------------
    # TEAM ACTION RULES
    # -----------------------------
    def classify_action(avg):
        if pd.isna(avg):
            return ""
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
            "aggregated_overall": aggregate_metric(
                x["score"].tolist(),
                mode=metric_agg_mode,
                latest_weight=latest_weight,
                previous_weight=prev_weight,
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
    # MERGE EVERYTHING (TEAM-LEVEL)
    # -----------------------------
    final = grade_df.merge(client_wide, on="team", how="left")

    # ROUND TEAM-LEVEL NUMERIC VALUES TO 3 DECIMALS
    numeric_cols = final.select_dtypes(include="number").columns
    final[numeric_cols] = final[numeric_cols].round(3)

    # Reorder to put Organization after team
    cols = list(final.columns)
    if "Organization" in cols:
        cols.insert(1, cols.pop(cols.index("Organization")))
        final = final[cols]

    # -----------------------------
    # SAVE TEAM-LEVEL OUTPUT
    # -----------------------------
    if getattr(args, "team_output", None):
        final.to_csv(args.output, index=False)
        print("✅ Team-level report written to:", args.output)

    # -----------------------------
    # SAVE STUDENT-LEVEL OUTPUT
    # -----------------------------
    # if getattr(args, "student_output", None):
    student_df = build_student_level_output(
        long_df,
        grade_df,
        LOW,
        metric_agg_mode,
        latest_weight,
        prev_weight,
        args.bonus_multiplier,
    )
    student_df.to_csv(args.output, index=False)
    print("✅ Student-level report written to:", args.output)


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    main()
