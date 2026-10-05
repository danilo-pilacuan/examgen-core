"""Pydantic INPUT schemas for the conversational agent's tools.

Complements the LLM OUTPUT validation (already done with
`with_structured_output(GeneratedItem)` in `src/agents/nodes.py`,
`src/agents/verifier.py` and `src/agents/conversational/tools.py`).

Here we validate what the LLM passes as tool ARGUMENTS (tool-calling).
Without this, the LLM could pass invalid values (e.g. `difficulty="super_hard"`,
`limit=0`, `num_versions=1000`) that used to be stored as-is in the database.

Mechanism: LangChain's `@tool(args_schema=...)`. The Pydantic model's JSON
schema travels to the LLM (guiding tool-calling) and Pydantic validates the
args on every invocation, raising `pydantic.ValidationError` when they don't
comply. That error is caught in `_call_tools_node`
(`src/agents/conversational/graph.py`) and returned to the LLM as a friendly
ToolMessage so it can correct and retry.

Reuses the enums and models from `src/schemas/exam.py` (single source of
truth of the domain).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from core.domain.schemas.exam import AnswerOption, Difficulty, QuestionType


# ---------------------------------------------------------------------------
# Description helpers (travel to the LLM in the tool's JSON schema)
# ---------------------------------------------------------------------------
_TOPIC_DESC = (
    "Topic of the question (e.g. 'Linear Regression', 'Law of Demand'). "
    "Must be an academic topic from the subjects' material."
)
_DIFFICULTY_DESC = "Difficulty of the question: 'easy', 'medium' or 'hard'."


# ---------------------------------------------------------------------------
# Table output format (list questions)
# ---------------------------------------------------------------------------
class TableColumn(str, Enum):
    """Columns available to display questions in table format.

    The LLM chooses which ones to include with `columns`; if none are given,
    the default set is used. Names match the fields of `GeneratedQuestion`
    (src/database/models.py).
    """

    N = "n"                          # row number
    ID = "id"                        # question id (UUID)
    TOPIC = "topic"                  # topic
    SUBTOPIC = "subtopic"            # subtopic
    BLOOM_LEVEL = "bloom_level"      # Bloom level
    DIFFICULTY = "difficulty"        # difficulty
    QUESTION_TYPE = "question_type"  # question type
    QUESTION_TEXT = "question_text"  # statement
    EXPECTED_ANSWER = "expected_answer"  # expected answer
    OPTIONS = "options"              # answer options (multiple_choice, etc.)
    SOLUTION_EXPLANATION = "solution_explanation"  # solution / justification
    POINTS = "points"                # score
    VERIFIED_BY_HUMAN = "verified_by_human"  # verified by human
    VERIFIED_BY_AI = "verified_by_ai"        # verified by AI
    AI_REVIEW_PRIORITY = "ai_review_priority"  # AI review priority
    SOURCE = "source"                # provenance (generated|chat|bank)
    CREATED_AT = "created_at"        # creation date


# Default set if the LLM doesn't specify columns.
DEFAULT_TABLE_COLUMNS: list[TableColumn] = [
    TableColumn.N,
    TableColumn.TOPIC,
    TableColumn.DIFFICULTY,
    TableColumn.QUESTION_TYPE,
    TableColumn.QUESTION_TEXT,
    TableColumn.VERIFIED_BY_HUMAN,
]

# Human-readable labels for each column (table headers).
COLUMN_LABELS: dict[TableColumn, str] = {
    TableColumn.N: "#",
    TableColumn.ID: "Id",
    TableColumn.TOPIC: "Topic",
    TableColumn.SUBTOPIC: "Subtopic",
    TableColumn.BLOOM_LEVEL: "Bloom",
    TableColumn.DIFFICULTY: "Difficulty",
    TableColumn.QUESTION_TYPE: "Type",
    TableColumn.QUESTION_TEXT: "Question",
    TableColumn.EXPECTED_ANSWER: "Answer",
    TableColumn.OPTIONS: "Options",
    TableColumn.SOLUTION_EXPLANATION: "Solution",
    TableColumn.POINTS: "Points",
    TableColumn.VERIFIED_BY_HUMAN: "Human verif.",
    TableColumn.VERIFIED_BY_AI: "AI verif.",
    TableColumn.AI_REVIEW_PRIORITY: "AI priority",
    TableColumn.SOURCE: "Source",
    TableColumn.CREATED_AT: "Created",
}


class _StrictModel(BaseModel):
    """Common base: rejects extra fields the LLM may invent."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
class ListSubjectsInput(_StrictModel):
    """Input of `list_subjects` (no arguments)."""


class SearchQuestionsInput(_StrictModel):
    """Input of `search_questions`."""

    subject_id: str = Field(..., description="Subject id (UUID)")
    topic: str | None = Field(
        default=None, description="Optional filter by exact topic"
    )
    limit: int = Field(
        default=20, ge=1, le=100, description="Max number of questions to return (1-100)"
    )
    columns: list[TableColumn] | None = Field(
        default=None,
        description=(
            "Columns to show in the table (optional). Values: 'n', 'id', "
            "'topic', 'subtopic', 'bloom_level', 'difficulty', 'question_type', "
            "'question_text', 'expected_answer', 'points', 'verified_by_human', "
            "'verified_by_ai', 'ai_review_priority', 'source', 'created_at'. "
            "If omitted the default set is used. Choose the columns the "
            "professor asks for (e.g. 'give me id, topic and difficulty in a table')."
        ),
    )


class ListMaterialInput(_StrictModel):
    """Input of `list_subject_material`."""

    subject_id: str = Field(..., description="Subject id (UUID)")


# ---------------------------------------------------------------------------
# Question generation / saving
# ---------------------------------------------------------------------------
class GenerateQuestionInput(_StrictModel):
    """Input of `generate_question`."""

    subject_id: str = Field(..., description="Subject id (UUID)")
    subject_name: str = Field(..., description="Name of the subject")
    topic: str = Field(..., description=_TOPIC_DESC)
    difficulty: Difficulty = Field(
        default=Difficulty.MEDIUM, description=_DIFFICULTY_DESC
    )


class AnswerOptionIn(AnswerOption):
    """Answer option arriving from the LLM via tool-calling.

    Inherits `text` and `is_correct` from `AnswerOption` (src/schemas/exam.py).
    """

    model_config = ConfigDict(extra="forbid")


class SaveQuestionInput(_StrictModel):
    """Input of `save_question`.

    Validates against the domain enums: the LLM cannot save
    `bloom_level="super_hard"` nor options without exactly one correct one
    (for multiple_choice) — same rules as `GeneratedItem`.
    """

    subject_id: str = Field(..., description="Subject id (UUID)")
    topic: str = Field(..., description=_TOPIC_DESC)
    bloom_level: str = Field(
        ...,
        description=(
            "Bloom level: 'remember', 'understand', 'apply', "
            "'analyze', 'evaluate' or 'create'"
        ),
    )
    difficulty: Difficulty = Field(..., description=_DIFFICULTY_DESC)
    question_text: str = Field(..., min_length=5, description="Question statement")
    question_type: QuestionType = Field(
        ...,
        description=(
            "Type: 'multiple_choice', 'true_false', 'short_answer', "
            "'essay', 'fill_in_blank' or 'select_all'"
        ),
    )
    options: list[AnswerOptionIn] | None = Field(
        default=None,
        description=(
            "Options (only multiple_choice/true_false/select_all). "
            "Each one: {'text': str, 'is_correct': bool}"
        ),
    )
    expected_answer: str | None = Field(
        default=None, description="Expected answer or reference solution"
    )
    solution_explanation: str | None = Field(
        default=None, description="Justification / step-by-step solution"
    )
    subtopic: str | None = Field(default=None, description="Optional subtopic")
    points: float = Field(default=1.0, gt=0, le=100, description="Score (> 0)")

    def to_review_dict(self) -> dict:
        """Flat dict for `review_question` (AI verifier)."""
        return {
            "topic": self.topic,
            "bloom_level": self.bloom_level,
            "difficulty": self.difficulty.value,
            "question_type": self.question_type.value,
            "statement": self.question_text,
            "options": [o.model_dump() for o in self.options] if self.options else None,
            "expected_answer": self.expected_answer,
            "solution_explanation": self.solution_explanation,
        }


class SavePendingQuestionInput(_StrictModel):
    """Input of `save_pending_question`."""

    verify_human: bool = Field(
        default=False,
        description=(
            "True only if the professor explicitly confirmed marking the "
            "question as verified by human"
        ),
    )


class ConfirmVerificationInput(_StrictModel):
    """Input of `confirm_human_verification`."""

    question_id: str = Field(..., description="Id (UUID) of the question to verify")


# ---------------------------------------------------------------------------
# Exams
# ---------------------------------------------------------------------------
class GenerateExamPdfInput(_StrictModel):
    """Input of `generate_exam_pdf`."""

    subject_id: str = Field(..., description="Subject id (UUID)")
    subject_name: str = Field(..., description="Name of the subject")
    total_questions: int = Field(
        default=5, ge=1, le=30, description="Number of exam questions (1-30)"
    )
    use_bank: bool = Field(
        default=True,
        description="True to build the exam with questions ALREADY in the bank",
    )
    num_versions: int = Field(
        default=1, ge=1, le=10, description="Number of shuffled exam versions (1-10)"
    )


# ---------------------------------------------------------------------------
# Bank export
# ---------------------------------------------------------------------------
class ExportQuestionsInput(_StrictModel):
    """Input of `export_questions`."""

    subject_id: str = Field(..., description="Subject id (UUID)")
    format: str = Field(
        default="csv",
        description="Export file format: 'csv' or 'xlsx' (Excel)",
    )
    topic: str | None = Field(
        default=None, description="Optional filter by exact topic"
    )
    limit: int = Field(
        default=100, ge=1, le=500, description="Max number of questions to export (1-500)"
    )


# ---------------------------------------------------------------------------
# Material and subjects
# ---------------------------------------------------------------------------
class AddMaterialFileInput(_StrictModel):
    """Input of `add_material_file`."""

    file_id: str = Field(
        ..., description="Id of the file attached in Open WebUI (tag <file id='...'/> )"
    )
    subject_id: str = Field(..., description="Subject id (UUID)")
    subject_name: str = Field(..., description="Name of the subject")
    clear_previous: bool = Field(
        default=False,
        description="True to replace the previous material of that file",
    )


class RegisterSubjectInput(_StrictModel):
    """Input of `register_subject`."""

    name: str = Field(
        ..., min_length=1, max_length=120, description="Name of the subject to register"
    )
