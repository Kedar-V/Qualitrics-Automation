import os
import sys
sys.path.append("src/")

import argparse
import json
import pandas as pd
from Survey import SURVEY
from Templates import TEMPLATES
from Constants import Constants


def build_client_survey(input_csv: str, output_qsf: str):
    # --- Load and prepare data ---
    df = pd.read_csv(input_csv)
    df = df.dropna(subset=["group_name"])

    # Validate required columns
    required_cols = {"group_name", "name"}
    missing = required_cols.difference(df.columns)
    if missing:
        raise ValueError(f"Input CSV must contain columns: {required_cols}. Missing: {missing}")

    # team -> members mapping
    team_members = df.groupby("group_name")["name"].apply(list).to_dict()

    # Save for reference
    with open("debug/client_teams.json", "w") as f:
        json.dump({"teams": team_members}, f, indent=4)

    # --- Build dropdown choices ---
    choices, choiceOrder, team_to_order = {}, [], {}
    for i, team in enumerate(sorted(team_members.keys())):
        idx = str(i + 1)
        choices[idx] = {"Display": team}
        choiceOrder.append(idx)
        team_to_order[team] = idx

    # --- Initialize template and survey ---
    Template = TEMPLATES(Constants.SURVEY_ID, Constants.SURVEY_NAME)
    Survey = SURVEY(Constants.SURVEY_ID)
    Survey.BASE_TEMPLATE["SurveyEntry"] = Template.SURVEY_ENTRY

    question_blocks = []
    q_counter = 1  # QID counter

    # =====================================================
    # INTRO BLOCK
    # =====================================================
    Intro_Block, Intro_ID = Template.get_standard_block("Intro and Project Selection")
    Intro_Block["Type"] = "Default"

    intro_text = (
        "Thank you for collaborating with our students! We are thrilled to see their growth and "
        "achievements this semester. This survey asks for your feedback on the students, which will "
        "be incorporated into their Capstone course grade. If you supervised more than one project, "
        "please complete a separate form for each team."
    )

    # DISPLAY intro
    Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
    Intro_Block["BlockElements"].append(Question_Element)
    question_blocks.append(
        Template.get_question("DISPLAY", intro_text, "", Question_ID)
    )
    q_counter += 1

    # TEXT: Organization (optional)
    Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
    Intro_Block["BlockElements"].append(Question_Element)
    question_blocks.append(
        Template.get_question(
            "TEXT",
            "Please state your organization.",
            {"DataExportTag": "Organization", "Required": True},
            Question_ID,
        )
    )
    q_counter += 1

    # TEXT: Name (optional)
    Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
    Intro_Block["BlockElements"].append(Question_Element)
    question_blocks.append(
        Template.get_question(
            "TEXT",
            "Please state your name.",
            {"DataExportTag": "ClientName", "Required": True},
            Question_ID,
        )
    )
    q_counter += 1

    # MCQ: Project Team (required)
    team_meta = {
        "QuestionJS": "",
        "choices": choices,
        "choiceOrder": choiceOrder,
        "DataExportTag": "ProjectTeam",
        "Required": True,
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
    # TEAM-SPECIFIC BLOCKS
    # =====================================================
    team_blocks = {}

    for team in sorted(team_members.keys()):
        members = team_members[team]
        curr_blocks = []

        # ----------------------------------------
        # BLOCK 1: Overall performance
        # ----------------------------------------
        Perf_Block, Perf_Block_ID = Template.get_standard_block(f"{team} - Overall Performance")

        # DISPLAY header
        Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
        Perf_Block["BlockElements"].append(Question_Element)
        question_blocks.append(
            Template.get_question("DISPLAY", "Team overall performance", "", Question_ID)
        )
        q_counter += 1

        # SLIDER rating
        Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
        Perf_Block["BlockElements"].append(Question_Element)
        question_blocks.append(
            Template.get_question(
                "SLIDER",
                (
                    "Please rate the team’s overall productivity and your satisfaction with their "
                    "performance on a scale of 1 to 10 (10 = very satisfied; scores of 7 or below "
                    "indicate some level of concern)."
                ),
                {"DataExportTag": f"{team}_OverallSatisfaction", "Required": True},
                Question_ID,
            )
        )
        q_counter += 1

        curr_blocks.append(Perf_Block)

        # ----------------------------------------
        # BLOCK 2: Technical readiness + collaboration
        # ----------------------------------------
        Qual_Block, Qual_Block_ID = Template.get_standard_block(f"{team} - Technical & Collaboration")

        # DISPLAY header
        Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
        Qual_Block["BlockElements"].append(Question_Element)
        question_blocks.append(
            Template.get_question(
                "DISPLAY",
                "Team technical readiness and collaboration experience",
                "",
                Question_ID
            )
        )
        q_counter += 1

        section_questions = [
            (
                "Is the team technically well-equipped to handle the project? Do they possess the "
                "necessary skills and knowledge to successfully complete their tasks?",
                "TechnicalEquipped",
            ),
            (
                "To what extent did the students independently propose solutions (score = 10) "
                "versus relying on your guidance to determine detailed next steps (score = 0)?",
                "Independence",
            ),
            (
                "How effectively did the students use the meetings with you? How well prepared were they, "
                "and did they make efficient use of your time and expertise?",
                "MeetingUse",
            ),
            (
                "Are you looking forward to the spring semester? Would you be interested in collaborating "
                "on the MIDS Capstone again in the future?",
                "FutureCollab",
            ),
        ]

        for qtext, tag in section_questions:
            Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
            Qual_Block["BlockElements"].append(Question_Element)
            question_blocks.append(
                Template.get_question(
                    "SLIDER",
                    qtext,
                    {"DataExportTag": f"{team}_{tag}", "Required": True},
                    Question_ID,
                )
            )
            q_counter += 1

        curr_blocks.append(Qual_Block)

        # ----------------------------------------
        # BLOCK 3: Individual member evaluations
        # ----------------------------------------
        Members_Block, Members_Block_ID = Template.get_standard_block(f"{team} - Member Ratings")

        # DISPLAY header
        Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
        Members_Block["BlockElements"].append(Question_Element)
        question_blocks.append(
            Template.get_question(
                "DISPLAY",
                "Individual student evaluations",
                "",
                Question_ID
            )
        )
        q_counter += 1

        for member in members:
            Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
            Members_Block["BlockElements"].append(Question_Element)
            question_blocks.append(
                Template.get_question(
                    "SLIDER",
                    (
                        f"Please provide an overall assessment for {member} on a scale of 1 to 10, "
                        "with 10 indicating complete satisfaction."
                    ),
                    {"DataExportTag": f"{member}_Overall", "Required": True},
                    Question_ID,
                )
            )
            q_counter += 1

        curr_blocks.append(Members_Block)

        # ----------------------------------------
        # BLOCK 4: Additional feedback
        # ----------------------------------------
        Feedback_Block, Feedback_Block_ID = Template.get_standard_block(f"{team} - Additional Feedback")

        Question_Element, Question_ID = Template.get_question_element(f"QID{q_counter}")
        Feedback_Block["BlockElements"].append(Question_Element)
        question_blocks.append(
            Template.get_question(
                "TEXT",
                "Do you have any additional feedback that you would like to share with us?",
                {"DataExportTag": f"{team}_AdditionalFeedback"},
                Question_ID,
            )
        )
        # print(Question_ID)
        q_counter += 1

        curr_blocks.append(Feedback_Block)

        team_blocks[team] = curr_blocks

    # =====================================================
    # ASSEMBLE SURVEY PAYLOAD
    # =====================================================
    Survey.BASE_TEMPLATE["SurveyElements"].append(Template.BLOCK_ELEMENT)

    all_team_blocks_flat = []
    for blocks in team_blocks.values():
        all_team_blocks_flat.extend(blocks)

    Survey.BASE_TEMPLATE["SurveyElements"][0]["Payload"].extend(
        [Intro_Block, *all_team_blocks_flat]
    )

    # =====================================================
    # FLOW LOGIC
    # =====================================================
    FLOW = Template.FLOW

    # Intro always appears
    FLOW["Payload"]["Flow"].append(
        Template.get_flow_element("Block", Intro_ID)[0]
    )

    # Branch per team
    for team in sorted(team_members.keys()):
        order = team_to_order[team]
        blocks = team_blocks[team]

        BR, BR_ID = Template.get_branch(order, blocks[0], team, Question_ID_Team)

        for block in blocks[1:]:
            BR["Flow"].append(
                Template.get_flow_element("Block", block["ID"])[0]
            )

        FLOW["Payload"]["Flow"].append(BR)

    # Final survey elements appended
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

    # =====================================================
    # SAVE FILE
    # =====================================================
    json_str = json.dumps(Survey.BASE_TEMPLATE, ensure_ascii=False, indent=4)
    json_str = json_str.replace("\\\\/", "\\/").replace("\\\\\"", "\\\"")
    with open(output_qsf, "w", encoding="utf-8") as f:
        f.write(json_str)

    print(f"✅ Client evaluation QSF survey file generated successfully at: {output_qsf}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate Client Evaluation Qualtrics QSF from a project team CSV."
    )
    parser.add_argument("--input", required=True, help="Path to input CSV")
    parser.add_argument("--output", required=True, help="Path to output QSF file")
    args = parser.parse_args()
    build_client_survey(args.input, args.output)
