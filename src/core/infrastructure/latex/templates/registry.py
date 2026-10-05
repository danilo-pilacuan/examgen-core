from enum import Enum
from pydantic import BaseModel, Field
from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent


class TemplateId(str, Enum):
    BASE_EXAM = "base_exam"
    QUIZ_SHORT = "quiz_short"


class ExamTemplate(BaseModel):
    """Registro de un template de examen.

    `options` declara las opciones configurables del template (nombre →
    descripción). Permite que una futura interfaz web genere templates
    variando estas opciones sin tocar el archivo LaTeX.
    """
    id: TemplateId
    file: str
    description: str
    supports_answer_key: bool = True
    options: dict[str, str] = Field(
        default_factory=dict,
        description="Opciones configurables: {nombre_la_tex: descripción}",
    )


TEMPLATE_REGISTRY: dict[TemplateId, ExamTemplate] = {
    TemplateId.BASE_EXAM: ExamTemplate(
        id=TemplateId.BASE_EXAM,
        file="base_exam.tex.jinja",
        description="Examen estándar a una columna, con tabla de calificación y clave de respuestas",
        options={
            "print_answers": "Mostrar las respuestas en el mismo documento",
            "show_grading_table": "Mostrar la tabla de calificación",
            "boxed_points": "Encerrar los puntos en un recuadro",
            "include_cover": "Incluir la portada (departamento, materia, fecha)",
            "num_versions": "Nº de versiones barajadas (estilo AMC)",
        },
    ),
    TemplateId.QUIZ_SHORT: ExamTemplate(
        id=TemplateId.QUIZ_SHORT,
        file="quiz_short.tex.jinja",
        description="Quiz corto de 1-2 páginas, sin clave de respuestas",
        supports_answer_key=False,
        options={
            "print_answers": "Mostrar las respuestas (aunque el quiz normalmente no)",
            "include_cover": "Incluir la portada",
        },
    ),
}


def get_template_path(template_id: TemplateId) -> Path:
    return TEMPLATES_DIR / TEMPLATE_REGISTRY[template_id].file