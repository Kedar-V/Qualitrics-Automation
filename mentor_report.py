#!/usr/bin/env python3

import argparse
import pandas as pd
import re
import sys
import json
import numpy as np


# -----------------------------
# CONFIG: STUDENT WEIGHTING
# -----------------------------
# You can change these later to e.g. 0.7 / 0.3
STUDENT_LATEST_WEIGHT = 0.7
STUDENT_PREV_WEIGHT = 0.3

# -----------------------------
# CONFIG: TEAM DIMENSION WEIGHTING
# -----------------------------
TEAM_DIM_LATEST_WEIGHT = 0.5
TEAM_DIM_PREV_WEIGHT = 0.5

HIGH = None
LOW = None
BONUS = None
# -----------------------------
# CLI
# -----------------------------

def parse_args():
    global HIGH, LOW
    p = argparse.ArgumentParser(
        description="Generate Mentor Grade Report + Student-Level Expansion"
    )
    p.add_argument("--input", required=True, help="Input Qualtrics Mentor CSV")
    p.add_argument("--output", required=True, help="Output Mentor Grade CSV")
    p.add_argument("--mentor-output", required=False, help="Optional intermediate Mentor-Level Output CSV", default='./generated/mentor_report.csv')
    p.add_argument("--high-threshold", type=float, default=8)
    p.add_argument("--low-threshold", type=float, default=7)
    p.add_argument("--bonus", type=float, default=5)
    p.add_argument("--mentor-map", required=False, help="CSV with columns: group_name, mentor_name")
    return p.parse_args()


# -----------------------------
# LOAD + CLEAN CSV
# -----------------------------
def load_csv(path):
    try:
        df = pd.read_csv(path, skiprows=[1, 2])
    except Exception as e:
        print("Failed to load input file:", e)
        sys.exit(1)

    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    ts_col = "RecordedDate"
    df[ts_col] = pd.to_datetime(df[ts_col], errors="coerce")

    return df


# -----------------------------
# LOAD MENTOR MAP
# -----------------------------
def load_mentor_map(path):
    try:
        mdf = pd.read_csv(path)
    except Exception as e:
        print("❌ Failed to load mentor map:", e)
        sys.exit(1)

    required = {"group_name", "mentor_name"}
    if not required.issubset(set(mdf.columns)):
        print("❌ Mentor map must contain: group_name, mentor_name")
        sys.exit(1)

    return dict(zip(
        mdf["group_name"].astype(str).str.strip(),
        mdf["mentor_name"].astype(str).str.strip()
    ))


# -----------------------------
# DETECT TEAM + MENTOR COLUMNS
# -----------------------------
def detect_team_structure(df):
    mentor_name_re = re.compile(r"^([A-Z])_MentorName$")
    team_metric_re = re.compile(r"^([A-Z])_(.*?)_1$")

    team_metrics = {}
    mentor_name_cols = {}

    for col in df.columns:
        m = mentor_name_re.match(col)
        if m:
            mentor_name_cols[m.group(1)] = col

        m = team_metric_re.match(col)
        if m:
            team = m.group(1)
            metric = m.group(2)
            team_metrics.setdefault(team, {})[metric] = col

    if not team_metrics:
        print("❌ No mentor team blocks detected.")
        sys.exit(1)

    return team_metrics, mentor_name_cols


# -----------------------------
# DETECT RAW STUDENT BLOCK
# -----------------------------
def detect_student_metrics(df):
    candidate_metric_re = re.compile(
        r"^(.+?)_(Communication|Technical|Reliability)_1$"
    )
    candidate_feedback_re = re.compile(r"^(.+?)_Feedback$")

    candidate_metric_cols = {}
    candidate_feedback_cols = {}

    for col in df.columns:
        m = candidate_metric_re.match(col)
        if m:
            name = m.group(1)
            metric = m.group(2)
            candidate_metric_cols.setdefault(name, {})[metric] = col

        m = candidate_feedback_re.match(col)
        if m:
            candidate_feedback_cols[m.group(1)] = col

    return candidate_metric_cols, candidate_feedback_cols


def classify_action(avg):
    if round(avg, 6) == 10:
        return "Bonus"
    if avg <= LOW:
        return "Attention"
    return "Normal"

# -----------------------------
# BUILD LONG FORMAT
# -----------------------------
def build_long_df(df, team_metrics, mentor_name_cols,
                  candidate_metric_cols, candidate_feedback_cols):

    long_records = []
    ts_col = "RecordedDate"

    for _, row in df.iterrows():
        ts = row.get(ts_col)

        # ---- raw student metrics per submission ----
        raw_student_block = {}

        for student, metrics in candidate_metric_cols.items():
            s_block = {}

            for metric, col in metrics.items():
                v = row.get(col)
                if pd.notna(v):
                    try:
                        s_block[metric] = float(v)
                    except ValueError:
                        pass

            fb_col = candidate_feedback_cols.get(student)
            if fb_col:
                fb_val = row.get(fb_col)
                if pd.notna(fb_val) and str(fb_val).strip() != "":
                    s_block["Feedback"] = str(fb_val).strip()

            if s_block:
                raw_student_block[student] = s_block

        for team, metrics in team_metrics.items():
            vals = {}
            raw_scores = []

            for metric, col in metrics.items():
                v = row.get(col)
                if pd.notna(v):
                    try:
                        v = float(v)
                        vals[metric] = v
                        raw_scores.append(v)
                    except ValueError:
                        pass

            if not raw_scores:
                continue

            avg_score = sum(raw_scores) / len(raw_scores)

            mentor = ""
            if team in mentor_name_cols:
                mentor = str(row.get(mentor_name_cols[team], "")).strip()

            if mentor == "" or mentor.lower() == "nan":
                mentor = f"Mentor_{row.get('ResponseId', 'Unknown')}"

            long_records.append({
                "team": team,
                "mentor": mentor,
                "score": avg_score,
                "metrics": vals,
                "timestamp": ts,
                "raw_students": raw_student_block
            })

    return pd.DataFrame(long_records)


# -----------------------------
# 70 / 30 WEIGHTING (TEAM OVERALL)
# -----------------------------
def compute_team_weighting(long_df):
    long_df = long_df.sort_values(
        by=["team", "mentor", "timestamp"],
        ascending=[True, True, False]
    )

    def compute_weighted_score(group):
        scores = group["score"].tolist()
        if len(scores) == 1:
            return scores[-1]
        last = scores[-1]
        prev_avg = sum(scores[:-1]) / len(scores[:-1])
        return 0.7 * last + 0.3 * prev_avg

    weighted_df = (
        long_df.groupby(["team", "mentor"])
        .apply(lambda x: compute_weighted_score(x))
        .reset_index(name="Weighted_Score_Mentor")
    )

    team_weighted = (
        weighted_df.groupby("team")["Weighted_Score_Mentor"]
        .mean()
        .reset_index(name="Weighted_Score")
    )

    return weighted_df, team_weighted


# -----------------------------
# METRIC HISTORY LISTS
# -----------------------------
def build_metric_lists(long_df):
    metric_lists = {}

    for _, row in long_df.sort_values(["team", "mentor", "timestamp"]).iterrows():
        team = row["team"]
        metrics = row["metrics"]

        metric_lists.setdefault(team, {})

        for k, v in metrics.items():
            metric_lists[team].setdefault(k, [])
            metric_lists[team][k].append(round(float(v), 3))

    metric_lists_df = (
        pd.DataFrame.from_dict(metric_lists, orient="index")
        .reset_index()
        .rename(columns={"index": "team"})
    )

    for col in metric_lists_df.columns:
        if col != "team":
            metric_lists_df[col] = metric_lists_df[col].apply(
                lambda x: json.dumps(x, ensure_ascii=False)
                if isinstance(x, list) else json.dumps([])
            )

    return metric_lists_df


# -----------------------------
# RAW STUDENT JSON PER TEAM
# -----------------------------
def build_raw_json(long_df):
    return (
        long_df
        .sort_values(["team", "mentor", "timestamp"])
        .groupby("team")["raw_students"]
        .apply(lambda x: json.dumps(list(x), ensure_ascii=False))
        .reset_index(name="Raw_Evaluations")
    )


# -----------------------------
# GENERIC WEIGHTING (REUSABLE)
# -----------------------------
def compute_weighted_score_generic(values, latest_w, prev_w):
    """
    values: list[float] in chronological order.
    Returns latest * latest_w + mean(previous) * prev_w.
    """
    if latest_w == prev_w:
        return np.mean(values)
    if not values:
        return None
    if len(values) == 1:
        return values[-1]

    latest = values[-1]
    prev_avg = sum(values[:-1]) / len(values[:-1])
    return latest_w * latest + prev_w * prev_avg


# -----------------------------
# FINAL TEAM GRADING
# -----------------------------
def build_final_team_df(weighted_df, team_weighted, metric_lists_df,
                        raw_json, mentor_map=None):
    global LOW, HIGH

    grade_df = (
        weighted_df.groupby("team")
        .agg(
            Reviewer_Count=("mentor", "nunique"),
            Mentor=("mentor", lambda x: ", ".join(sorted(set(x))))
        )
        .reset_index()
    )

    # Add DB mentor name as a separate column, do not override
    if mentor_map:
        grade_df["Mentor_Name_DB"] = grade_df["team"].map(
            lambda t: mentor_map.get(str(t), "UNK")
        )
    else:
        grade_df["Mentor_Name_DB"] = "UNK"

    grade_df = grade_df.merge(team_weighted, on="team", how="left")
    grade_df["Avg_Score"] = grade_df["Weighted_Score"]

    grade_df["Pct_Above_Threshold"] = grade_df["Weighted_Score"].apply(
        lambda x: (x >= HIGH) * 100
    )

    grade_df["Pct_Below_Threshold"] = grade_df["Weighted_Score"].apply(
        lambda x: (x < LOW) * 100
    )

    final = (
        grade_df
        .merge(metric_lists_df, on="team", how="left")
        .merge(raw_json, on="team", how="left")
    )

    # -----------------------------
    # TEAM-LEVEL DIMENSION WEIGHTED AVERAGE (70/30)
    # -----------------------------
    def safe_weighted_metric(x):
        try:
            arr = json.loads(x)
            return compute_weighted_score_generic(
                arr, TEAM_DIM_LATEST_WEIGHT, TEAM_DIM_PREV_WEIGHT
            )
        except Exception:
            return None

    final["Dimension_Weighted_Avg"] = final.apply(
        lambda r: float(np.mean([
            m for m in [
                safe_weighted_metric(r["CommWithClient"]),
                safe_weighted_metric(r["AlignWithClient"]),
                safe_weighted_metric(r["CriticalThinking"]),
                safe_weighted_metric(r["Independence"]),
            ] if m is not None
        ])) if any([
            safe_weighted_metric(r["CommWithClient"]),
            safe_weighted_metric(r["AlignWithClient"]),
            safe_weighted_metric(r["CriticalThinking"]),
            safe_weighted_metric(r["Independence"]),
        ]) else None,
        axis=1
    )

    fixed_cols = [
        "team", "Mentor", "Mentor_Name_DB",
        "Weighted_Score", "Avg_Score",
        "Dimension_Weighted_Avg",
        "Pct_Above_Threshold", "Pct_Below_Threshold",
        "Reviewer_Count"
    ]

    dynamic_cols = [c for c in final.columns if c not in fixed_cols]
    return final[fixed_cols + dynamic_cols]


# -----------------------------
# STUDENT-LEVEL EXPANSION
# -----------------------------
def expand_to_student_level(team_df, student_output_path):
    global BONUS

    rows = []

    for _, row in team_df.iterrows():

        team = row["team"]
        mentor_name = row['Mentor']
        mentor_name_db = row['Mentor_Name_DB']

        if 'Mentor_R_' in mentor_name:
            mentor_name = mentor_name_db

        # Team-level dimension histories (JSON arrays)
        comm_hist = json.loads(row["CommWithClient"])
        align_hist = json.loads(row["AlignWithClient"])
        crit_hist = json.loads(row["CriticalThinking"])
        indep_hist = json.loads(row["Independence"])
        overall_hist = json.loads(row["OverallSatisfaction"])

        # 70/30 weighting per dimension, consistent with team logic
        comm_w = compute_weighted_score_generic(
            comm_hist, TEAM_DIM_LATEST_WEIGHT, TEAM_DIM_PREV_WEIGHT
        )
        align_w = compute_weighted_score_generic(
            align_hist, TEAM_DIM_LATEST_WEIGHT, TEAM_DIM_PREV_WEIGHT
        )
        crit_w = compute_weighted_score_generic(
            crit_hist, TEAM_DIM_LATEST_WEIGHT, TEAM_DIM_PREV_WEIGHT
        )
        indep_w = compute_weighted_score_generic(
            indep_hist, TEAM_DIM_LATEST_WEIGHT, TEAM_DIM_PREV_WEIGHT
        )
        overall_w = compute_weighted_score_generic(
            overall_hist, TEAM_DIM_LATEST_WEIGHT, TEAM_DIM_PREV_WEIGHT
        )

        dims = [x for x in [comm_w, align_w, crit_w, indep_w] if x is not None]
        team_avg_score = float(np.mean(dims)) if dims else None

        # Raw evaluations list (per submission)
        raw_blocks = json.loads(row["Raw_Evaluations"])

        # Build per-student time series from ordered raw_blocks
        student_map = {}

        # raw_blocks is a list of raw_students dicts in timestamp order
        for submission in raw_blocks:
            for student, metrics in submission.items():
                student_map.setdefault(student, {
                    "Communication": [],
                    "Technical": [],
                    "Reliability": [],
                    "Feedback": []
                })

                for k in ["Communication", "Technical", "Reliability"]:
                    if k in metrics:
                        student_map[student][k].append(float(metrics[k]))

                if "Feedback" in metrics:
                    student_map[student]["Feedback"].append(str(metrics["Feedback"]))

        # Team-level values needed for final score
        team_score = row.get("Weighted_Score", None)
        # action = row.get("Action", "Normal")

        for student, metrics in student_map.items():

            comm_series = metrics["Communication"]
            tech_series = metrics["Technical"]
            reliab_series = metrics["Reliability"]
            feedback_list = metrics["Feedback"]

            w_comm = compute_weighted_score_generic(
                comm_series, STUDENT_LATEST_WEIGHT, STUDENT_PREV_WEIGHT
            )
            w_tech = compute_weighted_score_generic(
                tech_series, STUDENT_LATEST_WEIGHT, STUDENT_PREV_WEIGHT
            )
            w_reliab = compute_weighted_score_generic(
                reliab_series, STUDENT_LATEST_WEIGHT, STUDENT_PREV_WEIGHT
            )

            # Individual weighted average from the three rubric dimensions
            indiv_dims = [x for x in [w_comm, w_tech, w_reliab] if x is not None]
            student_avg = float(np.mean(indiv_dims)) if indiv_dims else None

            action = classify_action(student_avg)

            # -----------------------------
            # FINAL INDIVIDUAL SCORE (FOR CANVAS)
            # -----------------------------
            final_score = None
            if team_avg_score is not None:
                if action == "Bonus":
                    # Bonus: team_score * 10 * 1.05
                    final_score = team_avg_score * 10.0 * (BONUS)

                elif action == "Attention":
                    # Below threshold: team_score * individual_avg
                    if student_avg is not None:
                        final_score = team_avg_score * student_avg
                    else:
                        # Fallback to normal behaviour if no individual data
                        final_score = team_avg_score * 10.0
                else:
                    # Normal: team_score * 10
                    final_score = team_avg_score * 10.0

            rows.append({
                "Team": team,
                "Student_Name": student,
                "Mentor": mentor_name,

                # Team-level satisfaction / dimensions
                "Team_Avg_Score": round(team_avg_score, 3) if team_avg_score is not None else None,
                "Student_Weighted_Avg": round(student_avg, 3) if student_avg is not None else None,
                "Action": action,
                "Final_Individual_Score": round(final_score, 3) if final_score is not None else None,

                # Individual weighted rubric
                "Student_Communication_Weighted": round(w_comm, 3) if w_comm is not None else None,
                "Student_Technical_Weighted": round(w_tech, 3) if w_tech is not None else None,
                "Student_Reliability_Weighted": round(w_reliab, 3) if w_reliab is not None else None,

                # Action + final combined score to send to Canvas
                "Team_CommWithClient_Weighted": round(comm_w, 3) if comm_w is not None else None,
                "Team_Overall_Satisfaction_Weighted": round(overall_w, 3) if overall_w is not None else None,
                "Team_AlignWithClient_Weighted": round(align_w, 3) if align_w is not None else None,
                "Team_CriticalThinking_Weighted": round(crit_w, 3) if crit_w is not None else None,
                "Team_Independence_Weighted": round(indep_w, 3) if indep_w is not None else None,

                "Team_CommWithClient_Raw": json.dumps(comm_hist),
                "Team_Overall_Satisfaction_Raw": json.dumps(overall_hist),
                "Team_AlignWithClient_Raw": json.dumps(align_hist),
                "Team_CriticalThinking_Raw": json.dumps(crit_hist),
                "Team_Independence_Raw": json.dumps(indep_hist),

                # Full history for auditability
                "Student_Communication_Raw": json.dumps(comm_series),
                "Student_Technical_Raw": json.dumps(tech_series),
                "Student_Reliability_Raw": json.dumps(reliab_series),
                "Student_Feedback_Raw": feedback_list,
            })

    pd.DataFrame(rows).to_csv(student_output_path, index=False)
    print("✅ Student-level file written to:", student_output_path)


# -----------------------------
# MAIN
# -----------------------------
def main():
    global LOW, HIGH, BONUS

    args = parse_args()
    LOW = args.low_threshold
    HIGH = args.high_threshold
    BONUS = args.bonus
    BONUS = (100 + BONUS) / 100

    df = load_csv(args.input)

    team_metrics, mentor_name_cols = detect_team_structure(df)
    candidate_metric_cols, candidate_feedback_cols = detect_student_metrics(df)

    long_df = build_long_df(
        df,
        team_metrics,
        mentor_name_cols,
        candidate_metric_cols,
        candidate_feedback_cols,
    )

    # Will be removed
    weighted_df, team_weighted = compute_team_weighting(long_df)

    metric_lists_df = build_metric_lists(long_df)
    raw_json = build_raw_json(long_df)

    mentor_map = None
    if args.mentor_map:
        mentor_map = load_mentor_map(args.mentor_map)

    final_team_df = build_final_team_df(
        weighted_df,
        team_weighted,
        metric_lists_df,
        raw_json,
        mentor_map
    )

    if args.mentor_output:
        final_team_df.to_csv(args.mentor_output, index=False)
        

    expand_to_student_level(final_team_df, args.output)
    print("✅ Student report written to:", args.output)


# -----------------------------
# ENTRY POINT
# -----------------------------
if __name__ == "__main__":
    main()
