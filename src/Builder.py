import sys
sys.path.append('../')
import copy
from utils import _FlowIds, _Utils

class _Builder:

    def __init__(self, survey_id, survey_name):
        self.survey_id = survey_id
        self.survey_name = survey_name
        self.flow = _FlowIds()

        self.BLOCK_ELEMENT = {
            "SurveyID": survey_id,
            "Element": "BL",
            "PrimaryAttribute": "Survey Blocks",
            "SecondaryAttribute": None,
            "TertiaryAttribute": None,
            "Payload": []
        }
        self.STANDARD_ELEMENT = {
            "Type": "Standard",
            "Description": "",
            "ID": "",
            "BlockElements": []
        }
        self.FLOW_ROOT = {
            "SurveyID": survey_id,
            "Element": "FL",
            "PrimaryAttribute": "Survey Flow",
            "SecondaryAttribute": None,
            "TertiaryAttribute": None,
            "Payload": {
                "Type": "Root",
                "FlowID": "FL_1",
                "Flow": []
            }
        }
        self.SURVEY_ENTRY = {
            "SurveyID": survey_id,
            "SurveyName": survey_name,
            "SurveyDescription": None,
            "SurveyOwnerID": "UR_6XPnXwY9ovrE2uG",
            "SurveyBrandID": "duke",
            "DivisionID": None,
            "SurveyLanguage": "EN",
            "SurveyActiveResponseSet": "RS_cvbqrPWfwXcKHL8",
            "SurveyStatus": "Inactive",
            "SurveyStartDate": "0000-00-00 00:00:00",
            "SurveyExpirationDate": "0000-00-00 00:00:00",
            "SurveyCreationDate": "2025-10-22 17:00:52",
            "CreatorID": "UR_6XPnXwY9ovrE2uG",
            "LastModified": "2025-10-23 18:23:16",
            "LastAccessed": "0000-00-00 00:00:00",
            "LastActivated": "0000-00-00 00:00:00",
            "Deleted": None
        }
        self.PROJ = {
            "SurveyID": survey_id,
            "Element": "PROJ",
            "PrimaryAttribute": "CORE",
            "SecondaryAttribute": None,
            "TertiaryAttribute": "1.1.0",
            "Payload": {"ProjectCategory": "CORE", "SchemaVersion": "1.1.0"}
        }
        self.SCO = {
            "SurveyID": survey_id,
            "Element": "SCO",
            "PrimaryAttribute": "Scoring",
            "SecondaryAttribute": None,
            "TertiaryAttribute": None,
            "Payload": {
                "ScoringCategories": [],
                "ScoringCategoryGroups": [],
                "ScoringSummaryCategory": None,
                "ScoringSummaryAfterQuestions": 0,
                "ScoringSummaryAfterSurvey": 0,
                "DefaultScoringCategory": None,
                "AutoScoringCategory": None
            }
        }
        self.QC = {
            "SurveyID": survey_id,
            "Element": "QC",
            "PrimaryAttribute": "Survey Question Count",
            "SecondaryAttribute": "26",
            "TertiaryAttribute": None,
            "Payload": None
        }
        self.RS = {
            "SurveyID": survey_id,
            "Element": "RS",
            "PrimaryAttribute": "RS_cvbqrPWfwXcKHL8",
            "SecondaryAttribute": "Default Response Set",
            "TertiaryAttribute": None,
            "Payload": None
        }
        self.SO = {
            "SurveyID": "SV_ehV7YlbNWr2IMuO",
            "Element": "SO",
            "PrimaryAttribute": "Survey Options",
            "SecondaryAttribute": None,
            "TertiaryAttribute": None,
            "Payload": {
                "BackButton": "true",
                "SaveAndContinue": "false",
                "SurveyProtection": "PublicSurvey",
                "BallotBoxStuffingPrevention": "false",
                "NoIndex": "Yes",
                "SecureResponseFiles": "true",
                "SurveyExpiration": "None",
                "SurveyTermination": "DefaultMessage",
                "Header": "",
                "Footer": "",
                "ProgressBarDisplay": "None",
                "PartialData": "No",
                "ValidationMessage": None,
                "PreviousButton": "",
                "NextButton": "",
                "SurveyTitle": "Qualtrics Survey | Qualtrics Experience Management",
                "SkinLibrary": "duke",
                "SkinType": "templated",
                "Skin": {
                    "brandingId": "1852927161",
                    "templateId": "*base",
                    "overrides": None
                },
                "NewScoring": 1,
                "SurveyMetaDescription": "The most powerful, simple and trusted way to gather experience data. Start your journey to experience management and try a free account today.",
                "EOSMessage": None,
                "ShowExportTags": "false",
                "CollectGeoLocation": "false",
                "PasswordProtection": "No",
                "AnonymizeResponse": "No",
                "RefererCheck": "No",
                "BallotBoxStuffingPreventionBehavior": None,
                "BallotBoxStuffingPreventionMessage": None,
                "BallotBoxStuffingPreventionMessageLibrary": None,
                "BallotBoxStuffingPreventionURL": None,
                "RecaptchaV3": "false",
                "ConfirmStart": False,
                "AutoConfirmStart": False,
                "RelevantID": "false",
                "RelevantIDLockoutPeriod": "+30 days",
                "UseCustomSurveyLinkCompletedMessage": None,
                "SurveyLinkCompletedMessage": None,
                "SurveyLinkCompletedMessageLibrary": None,
                "ResponseSummary": "No",
                "EOSMessageLibrary": None,
                "EOSRedirectURL": None,
                "EmailThankYou": "false",
                "ThankYouEmailMessageLibrary": None,
                "ThankYouEmailMessage": None,
                "ValidateMessage": "false",
                "ValidationMessageLibrary": None,
                "InactiveSurvey": "DefaultMessage",
                "PartialDeletion": "+1 hour",
                "PartialDataCloseAfter": "SurveyStart",
                "InactiveMessageLibrary": None,
                "InactiveMessage": None,
                "AvailableLanguages": {
                    "EN": []
                }
            }
        }
        self.STAT = {
            "SurveyID": survey_id,
            "Element": "STAT",
            "PrimaryAttribute": "Survey Statistics",
            "SecondaryAttribute": None,
            "TertiaryAttribute": None,
            "Payload": {"MobileCompatible": True, "ID": "Survey Statistics"}
        }
        self.QUESTION_ELEMENT = {"Type": "Question", "QuestionID": ""}
        self.BRANCH_LOGIC = {
            "0": {
                "0": {
                    "LogicType": "Question",
                    "QuestionID": "PH",
                    "QuestionIsInLoop": "no",
                    "ChoiceLocator": "q:\/\/PH\/SelectableChoice\/Placeholder",
                    "Operator": "Selected",
                    "QuestionIDFromLocator": "PH",
                    "LeftOperand": "q:\/\/PH\/SelectableChoice\/Placeholder",
                    "Type": "Expression",
                    "Description": "<span class=\"ConjDesc\">If<\/span> <span class=\"QuestionDesc\">Select your Project Team<\/span> <span class=\"LeftOpDesc\">Placeholder<\/span> <span class=\"OpDesc\">Is Selected<\/span> "
                },
                "Type": "If"
            },
            "Type": "BooleanExpression"
        }
        self.FLOW_ELEMENTS = {
            "Block": {"Type": "Block", "ID": "", "FlowID": ""},
            "Standard": {"Type": "Standard", "ID": "", "FlowID": ""},
            "Branch": {"Type": "Branch", "FlowID": "FL_14", "Description": "New Branch", "BranchLogic": [], "Flow": []}
        }
        self.EMAIL_VALIDATION = {
            "Settings": {
                "ForceResponse": "ON",
                "ForceResponseType": "ON",
                "Type": "CustomValidation",
                "MinChars": "1",
                "CustomValidation": {
                    "Logic": {
                        "0": {
                            "0": {
                                "QuestionID": "QID3",
                                "QuestionIsInLoop": "no",
                                "ChoiceLocator": "q:\/\/QID3\/ChoiceTextEntryValue",
                                "Operator": "Contains",
                                "QuestionIDFromLocator": "QID3",
                                "LeftOperand": "q:\/\/QID3\/ChoiceTextEntryValue",
                                "RightOperand": "@",
                                "Type": "Expression",
                                "LogicType": "Question",
                                "Description": "<span class=\"ConjDesc\">If<\/span> <span class=\"QuestionDesc\">Enter Email<\/span> <span class=\"LeftOpDesc\">Text Response<\/span> <span class=\"OpDesc\">Is Equal to<\/span> <span class=\"RightOpDesc\"> @ <\/span>"
                            },
                            "Type": "If"
                        },
                        "Type": "BooleanExpression"
                    },
                    "Message": {"messageID": None, "subMessageID": "VE_VALIDEMAIL", "libraryID": None, "description": "Require valid email address"}
                }
            }
        }
        self.Q_TEMPLATES = {
            "MCQ": {
                "SurveyID": survey_id,
                "Element": "SQ",
                "PrimaryAttribute": "",
                "SecondaryAttribute": "",
                "TertiaryAttribute": None,
                "Payload": {
                    "QuestionText": "",
                    "DataExportTag": "",
                    "QuestionType": "MC",
                    "Selector": "SAVR",
                    "SubSelector": "TX",
                    "DataVisibility": {"Private": False, "Hidden": False},
                    "Configuration": {"QuestionDescriptionOption": "UseText"},
                    "QuestionDescription": "",
                    "Choices": {"1": {"Display": "A"}, "2": {"Display": "B"}, "3": {"Display": "C"}},
                    "ChoiceOrder": ["1", "2", "3"],
                    "Validation": {"Settings": {"ForceResponse": "ON", "ForceResponseType": "ON", "Type": "None"}},
                    "Language": [],
                    "QuestionID": "",
                    "QuestionJS": ""
                }
            },
            "SLIDER": {
                "SurveyID": survey_id,
                "Element": "SQ",
                "PrimaryAttribute": "",
                "SecondaryAttribute": "Description",
                "TertiaryAttribute": None,
                "Payload": {
                    "QuestionText": "Description",
                    "DefaultChoices": False,
                    "QuestionType": "Slider",
                    "Selector": "STAR",
                    "DataVisibility": {"Private": False, "Hidden": False},
                    "Configuration": {
                        "QuestionDescriptionOption": "UseText",
                        "CSSliderMin": 0,
                        "CSSliderMax": 100,
                        "GridLines": 10,
                        "NumDecimals": "0",
                        "ShowValue": False,
                        "SliderStartPositions": {"1": 0},
                        "StarCount": 10,
                        "StarType": "discrete",
                        "MobileFirst": False
                    },
                    "QuestionDescription": "Description",
                    "Choices": {"1": {"Display": "Rate"}},
                    "ChoiceOrder": [1],
                    "Validation": {},
                    "GradingData": [],
                    "Language": [],
                    "Labels": [],
                    "QuestionJS": "",
                    "DataExportTag": "Q22",
                    "QuestionID": "QID22"
                }
            },
            "DISPLAY": {
                "SurveyID": survey_id,
                "Element": "SQ",
                "PrimaryAttribute": "",
                "SecondaryAttribute": "",
                "TertiaryAttribute": None,
                "Payload": {
                    "QuestionText": "",
                    "DefaultChoices": False,
                    "DataExportTag": "",
                    "QuestionType": "DB",
                    "Selector": "TB",
                    "DataVisibility": {"Private": False, "Hidden": False},
                    "Configuration": {"QuestionDescriptionOption": "UseText"},
                    "QuestionDescription": "",
                    "ChoiceOrder": [],
                    "Validation": {"Settings": {}},
                    "GradingData": [],
                    "Language": [],
                    "NextChoiceId": 4,
                    "NextAnswerId": 1,
                    "QuestionID": ""
                }
            },
            "TEXT": {
                "SurveyID": survey_id,
                "Element": "SQ",
                "PrimaryAttribute": "",
                "SecondaryAttribute": "",
                "TertiaryAttribute": None,
                "Payload": {
                    "QuestionText": "",
                    "DefaultChoices": False,
                    "DataExportTag": "Q2",
                    "QuestionType": "TE",
                    "Selector": "ML",
                    "DataVisibility": {"Private": False, "Hidden": False},
                    "Configuration": {"QuestionDescriptionOption": "UseText", "InputWidth": 680, "InputHeight": 29},
                    "QuestionDescription": "",
                    "Validation": {"Settings": {}},
                    "GradingData": [],
                    "Language": [],
                    "SearchSource": {"AllowFreeResponse": "false"},
                    "QuestionID": ""
                }
            }
        }

    # helper ops
    def branch(self, member, block, team, Question_ID_Team):
        br = copy.deepcopy(self.FLOW_ELEMENTS['Branch'])
        logic = copy.deepcopy(self.BRANCH_LOGIC)
        logic['0']['0']['ChoiceLocator'] = logic['0']['0']['ChoiceLocator'].replace('Placeholder', member)
        logic['0']['0']['LeftOperand'] = logic['0']['0']['LeftOperand'].replace('Placeholder', member)
        logic['0']['0']['Description'] = logic['0']['0']['Description'].replace('Placeholder', team)

        logic['0']['0']['QuestionID'] = Question_ID_Team
        logic['0']['0']['ChoiceLocator'] = logic['0']['0']['ChoiceLocator'].replace('PH', Question_ID_Team)
        logic['0']['0']['QuestionIDFromLocator'] = Question_ID_Team
        logic['0']['0']['LeftOperand'] = logic['0']['0']['LeftOperand'].replace('PH', Question_ID_Team)

        Question_ID_Team
        br['BranchLogic'] = logic
        br['FlowID'] = self.flow.next()
        std = copy.deepcopy(self.FLOW_ELEMENTS['Standard'])
        std['ID'] = block['ID']
        std['FlowID'] = self.flow.next()
        br['Flow'].append(std)
        return br, br['FlowID']

    def block(self, desc, type_='Standard'):
        blk = copy.deepcopy(self.STANDARD_ELEMENT)
        blk['Type'] = type_
        blk['Description'] = desc
        blk['ID'] = _Utils.get_random_id('BL')
        return blk, blk['ID']

    def q_element(self, qid):
        q = copy.deepcopy(self.QUESTION_ELEMENT)
        q['QuestionID'] = qid
        return q, qid

    def flow_element(self, kind, ID):
        obj = copy.deepcopy(self.FLOW_ELEMENTS[kind])
        if kind in ('Block', 'Standard') and not ID:
            obj['ID'] = _Utils.get_random_id('BL')
        else:
            obj['ID'] = ID
        obj['FlowID'] = self.flow.next()
        return obj, obj['FlowID']

    def question(self, kind, text, metadata, qid):
        q = copy.deepcopy(self.Q_TEMPLATES[kind])
        q['PrimaryAttribute'] = qid
        q['SecondaryAttribute'] = ''
        p = q['Payload']
        p['QuestionText'] = text
        p['QuestionDescription'] = text
        p['DataExportTag'] = qid.replace('QID', 'Q')
        p['QuestionID'] = qid
        if 'email' in text.lower():
            p['Validation'] = copy.deepcopy(self.EMAIL_VALIDATION)
            cv = p['Validation']['Settings']['CustomValidation']['Logic']['0']['0']
            cv['QuestionID'] = qid
            cv['QuestionIDFromLocator'] = qid
        if metadata:
            if kind == 'MCQ':
                p['QuestionJS'] = metadata.get('QuestionJS', '')
                p['Choices'] = metadata['choices']
                p['ChoiceOrder'] = metadata['choiceOrder']
            if 'DataExportTag' in metadata:
                p['DataExportTag'] = metadata['DataExportTag']
            if 'Required' in metadata and metadata['Required']:
                p['Validation'] = {
                    "Settings": {
                        "ForceResponse": "ON", 
                        "ForceResponseType": "ON", 
                        "Type": "None"
                        }
                    }
                
            if 'Numeric' in metadata and metadata['Numeric']:
                p['Selector'] = 'SL'
                p['Validation'] = {
                    "Settings": {
                        "ForceResponse": "ON",
                        "ForceResponseType": "ON",
                        "Type": "ContentType",
                        "MinChars": "1",
                        "TotalChars": "1",
                        "ContentType": "ValidNumber",
                        "ValidDateType": "DateWithFormat",
                        "ValidPhoneType": "ValidUSPhone",
                        "ValidZipType": "ValidUSZip",
                        "ValidNumber": {
                            "Min": "1",
                            "Max": "10000",
                            "NumDecimals": ""
                        }
                    }
                }
        return q
