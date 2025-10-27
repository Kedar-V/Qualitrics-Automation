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
    team_dict = df.groupby("group_name")["name"].apply(list).to_dict()

    # Save team data for reference
    with open("teams.json", "w") as f:
        json.dump(team_dict, f, indent=4)

    # --- Build team/choice mappings ---
    choices, choiceOrder, team_to_order = {}, [], {}
    for i, team in enumerate(sorted(team_dict.keys())):
        idx = str(i + 1)
        choices[idx] = {"Display": team}
        choiceOrder.append(idx)
        team_to_order[team] = idx

    reverse_map = {mem: team for team, members in team_dict.items() for mem in members}
    all_members = list(reverse_map.keys())

    # --- Initialize templates ---
    Template = TEMPLATES(Constants.SURVEY_ID, Constants.SURVEY_NAME)
    Survey = SURVEY(Constants.SURVEY_ID)
    Survey.BASE_TEMPLATE["SurveyEntry"] = Template.SURVEY_ENTRY

    # --- Section 1: participant info ---
    Default_Block, Default_ID = Template.get_standard_block("Default")
    Default_Block["Type"] = "Default"
    i = 1
    metadata = {"QuestionJS": "", "choices": choices, "choiceOrder": choiceOrder, "DataExportTag": "Team"}
    questions = [
        ("TEXT", "Enter Name", {"DataExportTag": "Name"}),
        ("TEXT", "Enter Duke ID", {"DataExportTag": "DukeID"}),
        ("TEXT", "Enter Email", {"DataExportTag": "Email"}),
        ("MCQ", "Select your Project Team", metadata),
    ]
    question_blocks = []
    for qtype, qtext, qmeta in questions:
        Question_Element, Question_ID = Template.get_question_element(f"QID{i}")
        question_blocks.append(Template.get_question(qtype, qtext, qmeta, Question_ID))
        Default_Block["BlockElements"].append(Question_Element)
        i += 1

    # --- Section 2: display intro ---
    Section_2_Block, SECTION_2_ID = Template.get_standard_block("Section 2")
    Question_Element, Question_ID = Template.get_question_element(f"QID{i}")
    Section_2_Block["BlockElements"].append(Question_Element)
    question_blocks.append(
        Template.get_question(
            "DISPLAY",
            "In the next section please rate your team mates on a scale of 1–10 for their technical and communication skills",
            "",
            Question_ID,
        )
    )
    i += 1

    # --- Section 3: team evaluations ---
    Members = []
    slider_questions = [
        ("SLIDER", "Communication skills", {"DataExportTag": "Communication"}),
        ("SLIDER", "Technical contribution", {"DataExportTag": "Technical"}),
        ("SLIDER", "Reliability and accountability", {"DataExportTag": "Reliability"}),
        ("TEXT", "Open-ended feedback", {"DataExportTag": "Feedback"}),
    ]
    for member in all_members:
        Member_Block, _ = Template.get_standard_block(f"Member Block – {member}")
        for qtype, qtext, qmeta in slider_questions:
            tag = qmeta["DataExportTag"]
            qmeta["DataExportTag"] = f"{member}_{tag}"
            Question_Element, Question_ID = Template.get_question_element(f"QID{i}")
            question_blocks.append(
                Template.get_question(qtype, f"Rate {member}: {qtext}", qmeta, Question_ID)
            )
            Member_Block["BlockElements"].append(Question_Element)
            qmeta["DataExportTag"] = tag
            i += 1
        Members.append(Member_Block)

    # --- Section 4: instructor comment ---
    Section_4_Block, SECTION_4_ID = Template.get_standard_block("Instructor Feedback")
    Question_Element, Question_ID = Template.get_question_element(f"QID{i}")
    Section_4_Block["BlockElements"].append(Question_Element)
    question_blocks.append(
        Template.get_question(
            "TEXT",
            "Additional comment to Instructor or Capstone Director only",
            {"DataExportTag": "DirectorComment"},
            Question_ID,
        )
    )

    # --- Build full survey ---
    Survey.BASE_TEMPLATE["SurveyElements"].append(Template.BLOCK_ELEMENT)
    Survey.BASE_TEMPLATE["SurveyElements"][0]["Payload"].extend(
        [Default_Block, Section_2_Block, *Members, Section_4_Block]
    )

    # --- Define flow ---
    FLOW = Template.FLOW
    FLOW["Payload"]["Flow"].append(Template.get_flow_element("Block", Default_ID)[0])
    FLOW["Payload"]["Flow"].append(Template.get_flow_element("Block", SECTION_2_ID)[0])
    for mem, block in zip(all_members, Members):
        team = reverse_map[mem]
        order = team_to_order[team]
        BR, _ = Template.get_branch(order, block, team)
        FLOW["Payload"]["Flow"].append(BR)
    FLOW["Payload"]["Flow"].append(Template.get_flow_element("Block", SECTION_4_ID)[0])

    # --- Final structure ---
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

    # --- Save output ---
    json_str = json.dumps(Survey.BASE_TEMPLATE, ensure_ascii=False, indent=4)
    json_str = json_str.replace("\\\\/", "\\/").replace("\\\\\"", "\\\"")
    with open(output_qsf, "w", encoding="utf-8") as f:
        f.write(json_str)

    print(f"✅ QSF survey file generated successfully at: {output_qsf}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Qualtrics QSF from a project team CSV.")
    parser.add_argument("--input", required=True, help="Path to input CSV (team data)")
    parser.add_argument("--output", required=True, help="Path to output QSF file")
    args = parser.parse_args()
    build_survey(args.input, args.output)
