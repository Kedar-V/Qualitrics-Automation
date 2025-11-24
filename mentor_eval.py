import os
import sys
sys.path.append('src/')

import argparse
import json
import pandas as pd
from Survey import SURVEY
from Templates import TEMPLATES
from Constants import Constants


def build_survey(input_csv: str, output_qsf: str):
    # --- Load and prepare data ---
    df = pd.read_csv(input_csv)
    df = df.dropna(subset=["group_name"])

    # Validate required columns
    required_cols = {"group_name", "name", "mentor_name"}
    missing = required_cols.difference(df.columns)
    if missing:
        raise ValueError(f"Input CSV must contain columns: {required_cols}. Missing: {missing}")

    # team -> members
    team_members = df.groupby("group_name")["name"].apply(list).to_dict()
    # team -> mentor
    team_mentors = df.groupby("group_name")["mentor_name"].first().to_dict()

    # Save for reference
    with open("teams_mentors.json", "w") as f:
        json.dump({"teams": team_members, "mentors": team_mentors}, f, indent=4)

    # --- Build team / choice mappings ---
    choices, choiceOrder, team_to_order = {}, [], {}
    for i, team in enumerate(sorted(team_members.keys())):
        idx = str(i + 1)
        choices[idx] = {"Display": team}
        choiceOrder.append(idx)
        team_to_order[team] = idx

    # --- Initialize templates ---
    Template = TEMPLATES(Constants.SURVEY_ID, Constants.SURVEY_NAME)
    Survey = SURVEY(Constants.SURVEY_ID)
    Survey.BASE_TEMPLATE["SurveyEntry"] = Template.SURVEY_ENTRY

    question_blocks = []
    q_counter = 1

    # =====================================================
    # BLOCK: Welcome + Team Selection
    # =====================================================
    Intro_Block, Intro_ID = Template.get_standard_block("Intro and Project Selection")
    Intro_Block["Type"] = "Default"

    welcome_text = (
        "Thank you for working with our students! This survey is designed to gather feedback on "
        "overall team performance as well as individual contributions. The results will be "
        "incorporated into each student’s grade for the Capstone course. If you are mentoring "
        "more than one project, please complete a separate survey for each project."
    )

    # Welcome DISPLAY
    Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
    Intro_Block["BlockElements"].append(Question_Element)
    question_blocks.append(
        Template.get_question("DISPLAY", welcome_text, "", Question_ID)
    )
    q_counter += 1

    # Team dropdown (required)
    team_meta = {
        "QuestionJS": "",
        "choices": choices,
        "choiceOrder": choiceOrder,
        "DataExportTag": "ProjectTeam",
        "Required": True
    }
    Question_Element, Question_ID_Team = Template.get_question_element(f"QID{q_counter}")
    Intro_Block["BlockElements"].append(Question_Element)
    question_blocks.append(
        Template.get_question(
            "MCQ",
            "Please select the project team you are evaluating today.",
            team_meta,
            Question_ID_Team,
        )
    )
    q_counter += 1

    # =====================================================
    # PER-TEAM BLOCKS
    # =====================================================

    team_blocks = {}

    for team in sorted(team_members.keys()):
        mentor_name = team_mentors.get(team, "")
        members = team_members[team]

        curr_blocks = []

        # ----------------------------------------
        # Block 1: Mentor confirmation
        # ----------------------------------------
        Mentor_Block, _ = Template.get_standard_block(f"{team} – Mentor Confirmation")

        # DISPLAY: confirmed mentor
        Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
        Mentor_Block["BlockElements"].append(Question_Element)
        question_blocks.append(
            Template.get_question(
                "DISPLAY",
                f"Our records show that you are the mentor for \"{team}\": \n {mentor_name}.",
                "",
                Question_ID,
            )
        )
        q_counter += 1

        # Optional correction (no “optional” text)
        Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
        Mentor_Block["BlockElements"].append(Question_Element)
        question_blocks.append(
            Template.get_question(
                "TEXT",
                "If this name is not correct, please enter your name here.",
                {"DataExportTag": f"{team}_MentorName"},
                Question_ID,
            )
        )
        q_counter += 1

        curr_blocks.append(Mentor_Block)

        # ----------------------------------------
        # Block 2: Overall team performance
        # ----------------------------------------
        Perf_Block, _ = Template.get_standard_block(f"{team} – Overall Performance")

        # Heading DISPLAY
        Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
        Perf_Block["BlockElements"].append(Question_Element)
        question_blocks.append(
            Template.get_question("DISPLAY", "Section 1: Overall team performance", "", Question_ID)
        )
        q_counter += 1

        # Revised text: No "(required)"
        qtexts_perf = [
            (
                "Please rate the team’s overall productivity and your satisfaction with their "
                "performance on a scale of 1–10 (10 = very satisfied; scores of 7 or below indicate some level of concern).",
                f"{team}_OverallSatisfaction",
            ),
            (
                "How many client meetings have you attended?",
                f"{team}_ClientMeetings",
            ),
            (
                "Approximately how many hours per week, on average, did you spend working with the team this semester?",
                f"{team}_HoursPerWeek",
            )
        ]

        for text, tag in qtexts_perf:
            Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
            Perf_Block["BlockElements"].append(Question_Element)
            qtype = "SLIDER" if "rate the team" in text else "TEXT"
            numeric = True if 'how many' in text.lower() else False

            question_blocks.append(
                Template.get_question(
                    qtype,
                    text,
                    {"DataExportTag": tag, "Required": True, "Numeric": numeric},
                    Question_ID,
                )
            )
            q_counter += 1

        curr_blocks.append(Perf_Block)

        # ----------------------------------------
        # Block 3: Client communication & critical thinking
        # ----------------------------------------
        Comm_Block, _ = Template.get_standard_block(f"{team} – Client Communication")

        Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
        Comm_Block["BlockElements"].append(Question_Element)
        question_blocks.append(
            Template.get_question(
                "DISPLAY",
                "Section 2: Communication with client and problem solving",
                "",
                Question_ID,
            )
        )
        q_counter += 1

        section2_questions = [
            (
                "How effectively did the students communicate their progress to the client(s) throughout the semester?",
                "CommWithClient",
            ),
            (
                "How well did the students’ work align with the clients’ interests, needs, and stated goals?",
                "AlignWithClient",
            ),
            (
                "To what extent did the students demonstrate critical thinking about their problem, for example, by asking thoughtful, clarifying questions or raising important issues?",
                "CriticalThinking",
            ),
            (
                "To what extent did the students independently propose solutions (score = 10) versus relying on your guidance to determine detailed next steps (score = 0)?",
                "Independence",
            ),
        ]

        for qtext, tag in section2_questions:
            Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
            Comm_Block["BlockElements"].append(Question_Element)
            question_blocks.append(
                Template.get_question(
                    "SLIDER",
                    qtext,
                    {"DataExportTag": f"{team}_{tag}", "Required": True},
                    Question_ID,
                )
            )
            q_counter += 1

        curr_blocks.append(Comm_Block)

        # ----------------------------------------
        # Blocks 4+: Member evaluations
        # ----------------------------------------
        for member in members:
            Member_Block, _ = Template.get_standard_block(f"{team} – Member – {member}")

            # DISPLAY heading for member
            Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
            Member_Block["BlockElements"].append(Question_Element)
            question_blocks.append(
                Template.get_question(
                    "DISPLAY",
                    f"Now thinking specifically about {member}:",
                    "",
                    Question_ID,
                )
            )
            q_counter += 1

            slider_qs = [
                (f"How would you rate {member}'s Communication skills", "Communication"),
                (f"How would you rate {member}'s Technical contribution", "Technical"),
                (f"How would you rate {member}'s Reliability and accountability", "Reliability"),
            ]

            for label, tag in slider_qs:
                Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
                Member_Block["BlockElements"].append(Question_Element)
                question_blocks.append(
                    Template.get_question(
                        "SLIDER",
                        label,
                        {"DataExportTag": f"{member}_{tag}", "Required": True},
                        Question_ID,
                    )
                )
                q_counter += 1

            # open-ended (not required)
            Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
            Member_Block["BlockElements"].append(Question_Element)
            question_blocks.append(
                Template.get_question(
                    "TEXT",
                    f"Open-ended feedback for {member}",
                    {"DataExportTag": f"{member}_Feedback"},
                    Question_ID,
                )
            )
            q_counter += 1

            curr_blocks.append(Member_Block)

        # ----------------------------------------
        # Director comment
        # ----------------------------------------
        Director_Block, _ = Template.get_standard_block(f"{team} – Director Comment")

        Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
        Director_Block["BlockElements"].append(Question_Element)
        question_blocks.append(
            Template.get_question(
                "TEXT",
                "Additional comment to Capstone Director only",
                {"DataExportTag": f"{team}_DirectorComment"},
                Question_ID,
            )
        )
        q_counter += 1

        curr_blocks.append(Director_Block)

        team_blocks[team] = curr_blocks

    # =====================================================
    # Build full survey + Flow
    # =====================================================
    Survey.BASE_TEMPLATE["SurveyElements"].append(Template.BLOCK_ELEMENT)

    all_team_blocks = []
    for blocks in team_blocks.values():
        all_team_blocks.extend(blocks)

    Survey.BASE_TEMPLATE["SurveyElements"][0]["Payload"].extend([Intro_Block, *all_team_blocks])

    FLOW = Template.FLOW

    FLOW["Payload"]["Flow"].append(Template.get_flow_element("Block", Intro_ID)[0])

    for team in sorted(team_members.keys()):
        order = team_to_order[team]
        blocks = team_blocks[team]

        BR, BR_ID = Template.get_branch(order, blocks[0], team, Question_ID_Team)

        for block in blocks[1:]:
            BR["Flow"].append(Template.get_flow_element("Block", block["ID"])[0])

        FLOW["Payload"]["Flow"].append(BR)

    Survey.BASE_TEMPLATE["SurveyElements"].extend(
        [
            FLOW,
            Template.get_element("PROJ"),
            Template.get_element("QC"),
            Template.get_element("RS"),
            Template.get_element("SCO"),
            Template.get_element("SO"),
            *question_blocks,
            Template.get_element("STAT"),
        ]
    )

    json_str = json.dumps(Survey.BASE_TEMPLATE, ensure_ascii=False, indent=4)
    json_str = json_str.replace("\\\\/", "\\/").replace("\\\\\"", "\\\"")

    with open(output_qsf, "w", encoding="utf-8") as f:
        f.write(json_str)

    print(f"✅ Mentor evaluation QSF survey file generated successfully at: {output_qsf}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Mentor Evaluation Qualtrics QSF from a project team CSV."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    build_survey(args.input, args.output)
