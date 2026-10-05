from enum import Enum
from pydantic import BaseModel, Field
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent


class TemplateId(str, Enum):
    BASE_EXAM = "base_exam"
    QUIZ_SHORT = "quiz_short"


class ExamTemplate(BaseModel):
    """Registry of an exam template.

    `options` declares the configurable options of the template (name →
    description). Allows a future web interface to generate templates
    varying these options without touching the LaTeX file.
    """
    id: TemplateId
    file: str
    description: str
    supports_answer_key: bool = True
    options: dict[str, str] = Field(
        default_factory=dict,
        description="Configurable options: {latex_name: description}",
    )


TEMPLATE_REGISTRY: dict[TemplateId, ExamTemplate] = {
    TemplateId.BASE_EXAM: ExamTemplate(
        id=TemplateId.BASE_EXAM,
        file="base_exam.tex.jinja",
        description="Standard single-column exam, with grading table and answer key",
        options={
            "print_answers": "Show the answers in the same document",
            "show_grading_table": "Show the grading table",
            "boxed_points": "Enclose the points in a box",
            "include_cover": "Include the cover (department, subject, date)",
            "num_versions": "Number of shuffled versions (AMC style)",
        },
    ),
    TemplateId.QUIZ_SHORT: ExamTemplate(
        id=TemplateId.QUIZ_SHORT,
        file="quiz_short.tex.jinja",
        description="Short 1-2 page quiz, without answer key",
        supports_answer_key=False,
        options={
            "print_answers": "Show the answers (although the quiz usually does not)",
            "include_cover": "Include the cover",
        },
    ),
}


def get_template_path(template_id: TemplateId) -> Path:
    return TEMPLATES_DIR / TEMPLATE_REGISTRY[template_id].file