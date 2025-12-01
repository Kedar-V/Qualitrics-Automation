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
    'StartDate', 'EndDate', 'Status', 'IPAddress', 'Progress', 'Duration (in seconds)',
    'Finished', 'RecordedDate', 'ResponseId', 'RecipientLastName', 'RecipientFirstName',
    'RecipientEmail', 'ExternalReference', 'LocationLatitude', 'LocationLongitude',
    'DistributionChannel', 'UserLanguage'
]

DETAILS_COLS = ['Name', 'DukeID', 'Email', 'Team', 'DirectorComment']

MEMBER_TEMPLATE = {
    'Name': '',
    'Communication': '',
    'Technical': '',
    'Reliability': '',
    'Feedback': '',
    'Reviewer': '',
    'DirectorComment': ''
}


class SurveySummarizer:
    """Transforms Qualtrics data and computes per-member summary statistics."""

    def __init__(self, df: pd.DataFrame, high_threshold: float, low_threshold: float):
        self.df = df.fillna("")
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold

    def expand_responses(self) -> pd.DataFrame:
        """Convert wide Qualtrics data to long format, where each row is a (reviewer, member) record."""
        members = []

        for i, row in self.df.iterrows():
            # Skip Qualtrics label/import rows if they still exist
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
                        member_data["DirectorComment"] = row.get("DirectorComment", "")

                    member_data[skill] = val

            if member_data["Name"]:
                members.append(member_data)

        long_df = pd.DataFrame(members).fillna("")
        return long_df

    def summarize(self, long_df: pd.DataFrame) -> pd.DataFrame:
        """Compute per-member averages, percentages, and feedback summaries."""
        def summarize_member(group: pd.DataFrame) -> pd.Series:
            score_cols = [c for c in ["Communication", "Technical", "Reliability"] if c in group.columns]

            for col in score_cols:
                group[col] = pd.to_numeric(group[col], errors="coerce")

            scores = group[score_cols].to_numpy(dtype=float).flatten()

            avg_score = round(scores.mean(), 2) if len(scores) > 0 else 0.0

            above_high = (
                (scores >= self.high_threshold).sum() / len(scores) * 100
                if len(scores) else 0
            )

            below_low = (
                (scores < self.low_threshold).sum() / len(scores) * 100
                if len(scores) else 0
            )

            feedback_summary = [
                str(f).strip()
                for f in group["Feedback"].tolist()
                if str(f).strip() not in ["", "0", "nan"]
            ]

            raw_dict = {
                str(row["Reviewer"]): {
                    "Communication": float(row["Communication"]),
                    "Technical": float(row["Technical"]),
                    "Reliability": float(row["Reliability"]),
                    "Feedback": str(row["Feedback"]),
                    "DirectorComment": str(row["DirectorComment"]),
                }
                for _, row in group.iterrows()
                if pd.notna(row["Reviewer"])
            }

            return pd.Series({
                "Avg Score": avg_score,
                f"% Above {self.high_threshold}": f"{above_high:.1f}%",
                f"% Below {self.low_threshold}": f"{below_low:.1f}%",
                "Feedback Summary": feedback_summary,
                "Raw Evaluations": raw_dict
            })

        summarized = long_df.groupby("Name", group_keys=False).apply(summarize_member).reset_index()
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


def process_survey(
    input_csv: str,
    output_csv: str,
    output_json: str = None,
    plot_dir: str = "plots",
    high_threshold: float = 8.0,
    low_threshold: float = 5.0
):
    """Full pipeline: load, transform, summarize, export, and plot."""
    df = pd.read_csv(input_csv)
    print(f"Loaded {len(df)} survey responses from {input_csv}")

    summarizer = SurveySummarizer(df, high_threshold, low_threshold)

    long_df = summarizer.expand_responses()
    print(f"Expanded into {len(long_df)} (reviewer, member) pairs")

    summarized = summarizer.summarize(long_df)
    summarized.to_csv(output_csv, index=False)
    print(f"Saved summary CSV to {output_csv}")

    if output_json:
        json_output = summarized.to_json(orient="records", indent=2, force_ascii=False)
        with open(output_json, "w", encoding="utf-8") as f:
            f.write(json_output)
        print(f"Saved JSON summary to {output_json}")

    plotter = Plotter(plot_dir)
    plotter.plot_per_skill(long_df)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate summarized peer-evaluation report from Qualtrics survey CSV."
    )
    
    parser.add_argument("--input", required=True, help="Path to Qualtrics survey CSV file.")
    parser.add_argument("--output", required=True, help="Path to save summarized CSV report.")
    parser.add_argument("--json", required=False, help="Optional path to save JSON output.")
    parser.add_argument("--plots", required=False, default="plots", help="Directory to save generated plots.")

    parser.add_argument("--high-threshold", type=float, default=8.0,
                        help="High score threshold (default: 8)")
    parser.add_argument("--low-threshold", type=float, default=5.0,
                        help="Low score threshold (default: 5)")

    args = parser.parse_args()

    process_survey(
        args.input,
        args.output,
        args.json,
        args.plots,
        args.high_threshold,
        args.low_threshold
    )
