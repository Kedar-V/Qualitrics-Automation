import sys
sys.path.append('../')

import copy
from Builder import _Builder

class TEMPLATES:
    def __init__(self, SurveyID, SURVEY_NAME):
        self._b = _Builder(SurveyID, SURVEY_NAME)
        
        self.FLOW_COUNT = self._b.flow.count
        self.BLOCK_ELEMENT = self._b.BLOCK_ELEMENT
        self.STANDARD_ELEMENT = self._b.STANDARD_ELEMENT
        self.FLOW = copy.deepcopy(self._b.FLOW_ROOT)
        self.SURVEY_ENTRY = self._b.SURVEY_ENTRY
        self.PROJ = self._b.PROJ
        self.SCO = self._b.SCO
        self.QC = self._b.QC
        self.RS = self._b.RS
        self.SO = self._b.SO
        self.STAT = self._b.STAT
        self.QUESTION_ELEMENT = self._b.QUESTION_ELEMENT
        self.BRANCH_LOGIC = self._b.BRANCH_LOGIC
        self.PAGE_BREAK = {"Type": "Page Break"}
        self.FLOW_ELEMENTS = self._b.FLOW_ELEMENTS
        self.EMAIL_VALIDATION = self._b.EMAIL_VALIDATION
        self.QUESTIONS = {"SQ": self._b.Q_TEMPLATES}

    def get_branch(self, member, block, team, Question_ID_Team):
        return self._b.branch(member, block, team, Question_ID_Team)

    def get_standard_block(self, desc, TYPE='Standard'):
        return self._b.block(desc, TYPE)

    def get_question_element(self, QuestionID):
        return self._b.q_element(QuestionID)

    def get_flow_element(self, TYPE, ID):
        return self._b.flow_element(TYPE, ID)

    def get_question(self, TYPE, TEXT, metadata, QID):
        return self._b.question(TYPE, TEXT, metadata, QID)

    def get_element(self, TYPE):
        mapping = {
            'PROJ': self._b.PROJ,
            'QC': self._b.QC,
            'RS': self._b.RS,
            'SO': self._b.SO,
            'STAT': self._b.STAT,
            'SCO': self._b.SCO,
        }
        obj = mapping.get(TYPE)
        return copy.deepcopy(obj) if obj else None