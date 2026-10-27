from enum import Enum
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BloomLevel(str, Enum):
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYZE = "analyze"
    EVALUATE = "evaluate"
    CREATE = "create"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"
    FILL_IN_BLANK = "fill_in_blank"    # cloze: uses \fillin with the answer
    SELECT_ALL = "select_all"          # mark ALL correct options (\multiplechoice)


class AnswerOption(BaseModel):
    """An answer option for multiple-choice questions."""
    text: str = Field(..., description="Option text, without marking which one is correct")
    is_correct: bool = Field(default=False)


class GeneratedItem(BaseModel):
    """
    Structure the Generator LLM must produce for each question.
    This is the strict contract between the LLM and the rest of the pipeline:
    the model NEVER generates LaTeX directly, only this structure.
    """
    topic: str = Field(..., description="Syllabus topic the question belongs to")
    subtopic: Optional[str] = Field(default=None)
    bloom_level: BloomLevel
    difficulty: Difficulty
    question_type: QuestionType

    statement: str = Field(..., description="Question statement, plain text (no LaTeX)")
    options: list[AnswerOption] = Field(
        default_factory=list,
        description="Only applies to multiple_choice or true_false"
    )
    expected_answer: str = Field(..., description="Expected answer or reference solution")
    solution_explanation: str = Field(
        ..., description="Pedagogical justification / step-by-step solution"
    )
    points: float = Field(default=1.0, gt=0)

    @field_validator("options")
    @classmethod
    def validate_options(cls, options: list[AnswerOption], info):
        question_type = info.data.get("question_type")
        if question_type == QuestionType.MULTIPLE_CHOICE:
            if len(options) < 3:
                raise ValueError("multiple_choice requires at least 3 options")
            correct = [o for o in options if o.is_correct]
            if len(correct) != 1:
                raise ValueError("multiple_choice requires exactly one correct option")
        if question_type == QuestionType.TRUE_FALSE and len(options) != 2:
            raise ValueError("true_false requires exactly 2 options")
        if question_type == QuestionType.SELECT_ALL:
            if len(options) < 2:
                raise ValueError("select_all requires at least 2 options")
            correct = [o for o in options if o.is_correct]
            if len(correct) < 1:
                raise ValueError("select_all requires at least one correct option")
        return options


class EvaluationResult(BaseModel):
    """Output of the Evaluator Agent for a generated item."""
    approved: bool
    quality_score: float = Field(..., ge=0, le=10)
    difficulty_match: bool = Field(
        ..., description="Does the actual difficulty match the requested one?"
    )
    is_duplicate: bool = False
    similarity_score: Optional[float] = Field(default=None, ge=0, le=1)
    rejection_reason: Optional[str] = None


class RetrievalConfig(BaseModel):
    """RAG configuration for this exam.

    Controls how the Generator retrieves context from the indexed material.
    """
    top_k: int = Field(default=3, ge=1, le=20, description="Number of chunks to retrieve")
    min_score: float = Field(default=0.15, ge=0, le=1, description="Minimum similarity threshold")
    use_rag: bool = Field(default=True, description="If False, uses the syllabus summary")
    max_chars_per_chunk: int = Field(default=1200, ge=100)


class ExamMetadata(BaseModel):
    """Exam metadata (for experimentation and traceability)."""
    title: str = Field(default="", description="Exam title, e.g. Midterm Exam")
    name: str = Field(
        default="",
        description=(
            "Human-readable exam name requested by the professor (e.g. "
            "'Midterm 1'). Used for the artifact file names "
            "(<name>_A.pdf, <name>_A_respondido.pdf, <name>.zip)."
        ),
    )
    instructions: str = Field(default="", description="Instructions for the student")
    model: str = Field(default="", description="LLM model used")
    temperature: float | None = Field(default=None, ge=0, le=2)
    reasoning_effort: str | None = Field(default=None)
    experiment_tag: str = Field(default="", description="Tag to compare experiments")
    notes: str = Field(default="")
    num_versions: int = Field(
        default=1, ge=1, le=10,
        description="Number of exam versions (anti-copy shuffling, AMC style)",
    )


class ExamBlueprint(BaseModel):
    """Output of the Planner Agent: the structure the exam must have."""
    # BUG-018: misplaced fields (e.g. num_versions/name at the root instead
    # of inside `metadata`) must fail validation with 422, not be ignored.
    model_config = ConfigDict(extra="forbid")
    subject_id: str
    total_questions: int = Field(..., gt=0)
    bloom_distribution: dict[BloomLevel, float] = Field(
        ..., description="0-1 proportion of questions per Bloom level, must sum to 1.0"
    )
    difficulty_distribution: dict[Difficulty, float] = Field(
        ..., description="0-1 proportion of questions per difficulty, must sum to 1.0"
    )
    topics_weight: dict[str, float] = Field(
        ..., description="Weight per syllabus topic, must sum to 1.0"
    )
    estimated_duration_minutes: int = Field(default=90)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    metadata: ExamMetadata = Field(default_factory=ExamMetadata)

    @field_validator("bloom_distribution", "difficulty_distribution", "topics_weight")
    @classmethod
    def validate_sums_to_one(cls, v: dict, info):
        total = sum(v.values())
        if not (0.98 <= total <= 1.02):  # tolerance for rounding
            raise ValueError(f"{info.field_name} must sum to ~1.0, current sum: {total}")
        return v


class CompiledExam(BaseModel):
    """Final assembled result."""
    subject_id: str
    blueprint: ExamBlueprint
    items: list[GeneratedItem]
    latex_source: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_paths: Optional[list[str]] = None  # paths of the versions (if num_versions>1)
    compilation_attempts: int = 0

class ItemSpec(BaseModel):
    """A specific 'slot' the Planner assigns: what the Generator must produce."""
    spec_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str
    subtopic: Optional[str] = None
    bloom_level: BloomLevel
    difficulty: Difficulty
    question_type: QuestionType
    points: float = Field(default=1.0, gt=0)
