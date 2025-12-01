import argparse
import pandas as pd
import copy
import json
import os
import matplotlib.pyplot as plt


# -------------------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------------------
METADATA_COLS = [
    'StartDate', 'EndDate', 'Status', 'IPAddress', 'Progress',
    'Duration (in seconds)', 'Finished', 'RecordedDate', 'ResponseId',
    'RecipientLastName', 'RecipientFirstName', 'RecipientEmail',
    'ExternalReference', 'LocationLatitude', 'LocationLongitude',
    'DistributionChannel', 'UserLanguage'
]

DETAILS_COLS = ['Name', 'DukeID', 'Email', 'Team', 'DirectorComment']

MEMBER_TEMPLATE = {
    'Name': '',
    'Team': '',
    'Communication': '',
    'Technical': '',
    'Reliability': '',
    'Feedback': '',
    'Reviewer': '',
    'DirectorComment': '',
    'RecordedDate': ''
}


class SurveySummarizer:
    """Transforms Qualtrics data and computes per-member summary statistics."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.fillna("")

    def expand_responses(self) -> pd.DataFrame:
        """Convert wide Qualtrics data to long format, where each row is a (reviewer, member) record."""
        members = []

        for i, row in self.df.iterrows():
            if i < 2:
                continue

            curr_name = None
            member_data = copy.deepcopy(MEMBER_TEMPLATE)

            for col in self.df.columns:
                if col in METADATA_COLS + DETAILS_COLS:
                    continue

                parts = col.split("_")
                if len(parts) < 2:
                    continue

                member, skill = parts[0], parts[1]
                val = row[col]

                if val not in [0, "", None]:
                    if member != curr_name:
                        if curr_name:
                            members.append(member_data)

                        curr_name = member
                        member_data = copy.deepcopy(MEMBER_TEMPLATE)
                        member_data["Reviewer"] = row.get("Name", "")
                        member_data["Name"] = curr_name
                        member_data["Team"] = row.get("Team", "")
                        member_data["DirectorComment"] = row.get("DirectorComment", "")
                        member_data["RecordedDate"] = pd.to_datetime(
                            row.get("RecordedDate", ""), errors="coerce"
                        )

                    member_data[skill] = val

            if member_data["Name"]:
                members.append(member_data)

        long_df = pd.DataFrame(members).fillna("")
        return long_df

    def summarize(self, long_df: pd.DataFrame) -> pd.DataFrame:
        """Compute per-member weighted averages excluding self-evaluations."""

        # ✅ REMOVE SELF EVALUATIONS FIRST
        filtered = long_df[long_df["Reviewer"] != long_df["Name"]].copy()

        def weighted_scores(group):
            group = group.sort_values("RecordedDate")

            score_cols = ["Communication", "Technical", "Reliability"]
            for col in score_cols:
                group[col] = pd.to_numeric(group[col], errors="coerce")

            if len(group) == 1:
                return group.iloc[0][score_cols]

            latest = group.iloc[-1][score_cols]
            previous = group.iloc[:-1][score_cols].mean()

            return 0.7 * latest + 0.3 * previous

        # ✅ Apply weighting per (Member, Reviewer)
        weighted = (
            filtered
            .groupby(["Name", "Reviewer"], group_keys=False)
            .apply(weighted_scores)
            .reset_index()
        )

        weighted_long = pd.merge(
            weighted,
            filtered[["Name", "Team"]].drop_duplicates(),
            on="Name",
            how="left"
        )

    def summarize_member(group: pd.DataFrame) -> pd.Series:
        score_vals = group[["Communication", "Technical", "Reliability"]] \
            .to_numpy(dtype=float).flatten()

        avg_score = round(score_vals.mean(), 2)
        above_8 = (score_vals > 8).sum() / len(score_vals) * 100
        below_5 = (score_vals < 5).sum() / len(score_vals) * 100

        raw_dict = {
            row["Reviewer"]: {
                "Communication": float(row["Communication"]),
                "Technical": float(row["Technical"]),
                "Reliability": float(row["Reliability"]),
            }
            for _, row in group.iterrows()
        }

        return pd.Series({
            "Team": group["Team"].iloc[0],
            "Avg Score": avg_score,
            "% Above 8": f"{above_8:.1f}%",
            "% Below 5": f"{below_5:.1f}%",
            "Raw Evaluations": raw_dict
        })

    summarized = (
        weighted_long
        .groupby("Name", group_keys=False)
        .apply(summarize_member)
        .reset_index()
    )

    return summarized


        def summarize_member(group: pd.DataFrame) -> pd.Series:
            score_vals = group[["Communication", "Technical", "Reliability"]] \
                            .to_numpy(dtype=float).flatten()

            avg_score = round(score_vals.mean(), 2)
            above_8 = (score_vals > 8).sum() / len(score_vals) * 100
            below_5 = (score_vals < 5).sum() / len(score_vals) * 100

            raw_dict = {
                row["Reviewer"]: {
                    "Communication": float(row["Communication"]),
                    "Technical": float(row["Technical"]),
                    "Reliability": float(row["Reliability"]),
                }
                for _, row in group.iterrows()
            }

            return pd.Series({
                "Team": group["Team"].iloc[0],
                "Avg Score": avg_score,
                "% Above 8": f"{above_8:.1f}%",
                "% Below 5": f"{below_5:.1f}%",
                "Raw Evaluations": raw_dict
            })

        summarized = (
            weighted_long
            .groupby("Name", group_keys=False)
            .apply(summarize_member)
            .reset_index()
        )

        return summarized


class Plotter:
    """Generates per-skill bar charts for each member."""

    def __init__(self, output_dir="plots"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def plot_per_skill(self, long_df: pd.DataFrame):
        """Generate one vertical bar chart per skill, showing average per member."""
        skills = ["Communication", "Technical", "Reliability"]

        for skill in skills:
            if skill not in long_df.columns:
                print(f"Skipping {skill}, not found in dataset.")
                continue

            df_skill = long_df.copy()
            df_skill[skill] = pd.to_numeric(df_skill[skill], errors="coerce")

            avg_per_member = (
                df_skill.groupby("Name")[skill]
                .mean()
                .sort_values(ascending=False)
                .dropna()
            )

            plt.figure(figsize=(8, 5))
            plt.bar(avg_per_member.index, avg_per_member.values)
            plt.title(f"Average {skill} Score per Member")
            plt.ylabel("Average Score")
            plt.xlabel("Member")
            plt.ylim(0, 10)
            plt.xticks(rotation=45, ha="right")
            plt.grid(axis="y", linestyle="--", alpha=0.6)
            plt.tight_layout()

            output_path = os.path.join(self.output_dir, f"{skill}_Scores.png")
            plt.savefig(output_path)
            plt.close()
            print(f"Saved {skill} chart to {output_path}")


def process_survey(input_csv: str, output_csv: str,
                   output_json: str = None, plot_dir: str = "plots"):
    """Full pipeline: load, transform, summarize, export, and plot."""
    df = pd.read_csv(input_csv)
    print(f"Loaded {len(df)} survey responses from {input_csv}")

    summarizer = SurveySummarizer(df)
    long_df = summarizer.expand_responses()
    print(f"Expanded into {len(long_df)} (reviewer, member) pairs")

    summarized = summarizer.summarize(long_df)
    summarized.to_csv(output_csv, index=False)
    print(f"Saved summary CSV to {output_csv}")

    if output_json:
        json_output = summarized.to_json(
            orient="records", indent=2, force_ascii=False
        )
        with open(output_json, "w", encoding="utf-8") as f:
            f.write(json_output)
        print(f"Saved JSON summary to {output_json}")

    plotter = Plotter(plot_dir)
    plotter.plot_per_skill(long_df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate summarized peer-evaluation report from Qualtrics survey CSV."
    )
    parser.add_argument("--input", required=True,
                        help="Path to Qualtrics survey CSV file.")
    parser.add_argument("--output", required=True,
                        help="Path to save summarized CSV report.")
    parser.add_argument("--json", required=False,
                        help="Optional path to save JSON output.")
    parser.add_argument("--plots", required=False, default="plots",
                        help="Directory to save generated plots.")

    args = parser.parse_args()

    process_survey(args.input, args.output, args.json, args.plots)
