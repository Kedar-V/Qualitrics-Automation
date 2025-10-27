class SURVEY:
    def __init__(self, SurveyID):
        self.BASE_TEMPLATE = {"SurveyEntry": "", "SurveyElements": []}
        self.FLOW_TEMPLATE = {
            "SurveyID": SurveyID,
            "Element": "FL",
            "PrimaryAttribute": "Survey Flow",
            "SecondaryAttribute": None,
            "TertiaryAttribute": None,
            "Payload": {"Type": "Root", "FlowID": "FL_1", "Flow": []}
        }