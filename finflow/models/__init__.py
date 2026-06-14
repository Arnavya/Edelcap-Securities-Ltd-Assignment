"""Pure pydantic data contracts shared across the system."""

from .answer import Answer, AnswerVersion
from .evaluation import (
    EvaluationRun,
    EvidenceOverlapResult,
    GateResult,
    ImprovementResult,
    JudgeResult,
    QuestionScore,
    RunRecord,
)
from .evidence import EvidenceItem, SourceType
from .gap import GapAnalysis
from .human_answer import HumanAnswer, RubricElement
from .learning import (
    LearningEvent,
    LearningPattern,
    MetricSnapshot,
    PatternType,
    Sanitization,
)
from .question import Question, QuestionFamily
from .reasoning import ReasoningStep, ReasoningTrace
from .retrieval import (
    RetrievalDiagnostics,
    RetrievalSnapshot,
    RetrievedItem,
)

__all__ = [
    "Answer",
    "AnswerVersion",
    "EvidenceItem",
    "SourceType",
    "EvaluationRun",
    "EvidenceOverlapResult",
    "GateResult",
    "ImprovementResult",
    "JudgeResult",
    "QuestionScore",
    "RunRecord",
    "GapAnalysis",
    "HumanAnswer",
    "RubricElement",
    "LearningEvent",
    "LearningPattern",
    "MetricSnapshot",
    "PatternType",
    "Sanitization",
    "Question",
    "QuestionFamily",
    "ReasoningStep",
    "ReasoningTrace",
    "RetrievalDiagnostics",
    "RetrievalSnapshot",
    "RetrievedItem",
]
