"""Schemas Pydantic de ENTRADA para las tools del agente conversacional.

Complementa la validación de SALIDAS del LLM (que ya se hace con
`with_structured_output(GeneratedItem)` en `src/agents/nodes.py`,
`src/agents/verifier.py` y `src/agents/conversational/tools.py`).

Aquí se valida lo que el LLM pasa como ARGUMENTOS de las tools
(tool-calling). Sin esto, el LLM puede pasar valores inválidos
(ej. `difficulty="facilísimo"`, `limit=0`, `num_versions=1000`) que
antes se guardaban tal cual en la base de datos.

Mecanismo: `@tool(args_schema=...)` de LangChain. El JSON schema del
modelo Pydantic viaja al LLM (guía el tool-calling) y Pydantic valida
los args en cada invocación, lanzando `pydantic.ValidationError` si no
cumplen. Ese error se captura en `_call_tools_node`
(`src/agents/conversational/graph.py`) y se devuelve al LLM como
ToolMessage amigable para que corrija y reintente.

Reutiliza los enums y modelos de `src/schemas/exam.py` (fuente única
de verdad del dominio).
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from core.domain.schemas.exam import AnswerOption, Difficulty, QuestionType


# ---------------------------------------------------------------------------
# Helpers de descripción (viajan al LLM en el JSON schema de la tool)
# ---------------------------------------------------------------------------
_TOPIC_DESC = (
    "Tema de la pregunta (ej. 'Regresión Lineal', 'Ley de la demanda'). "
    "Debe ser un tema académico del material de las materias."
)
_DIFFICULTY_DESC = "Dificultad de la pregunta: 'facil', 'medio' o 'dificil'."


# ---------------------------------------------------------------------------
# Formato de salida en tabla (listar preguntas)
# ---------------------------------------------------------------------------
class TableColumn(str, Enum):
    """Columnas disponibles para mostrar preguntas en formato tabla.

    El LLM elige cuáles incluir con `columns`; si no indica ninguna se usa
    el set por defecto. Los nombres coinciden con los campos de
    `GeneratedQuestion` (src/database/models.py).
    """

    N = "n"                          # número de fila
    ID = "id"                        # id (UUID) de la pregunta
    TOPIC = "topic"                  # tema
    SUBTOPIC = "subtopic"            # subtema
    BLOOM_LEVEL = "bloom_level"      # nivel de Bloom
    DIFFICULTY = "difficulty"        # dificultad
    QUESTION_TYPE = "question_type"  # tipo de pregunta
    QUESTION_TEXT = "question_text"  # enunciado
    EXPECTED_ANSWER = "expected_answer"  # respuesta esperada
    OPTIONS = "options"              # opciones de respuesta (opcion_multiple, etc.)
    SOLUTION_EXPLANATION = "solution_explanation"  # solución / justificación
    POINTS = "points"                # puntaje
    VERIFIED_BY_HUMAN = "verified_by_human"  # verificado por humano
    VERIFIED_BY_AI = "verified_by_ai"        # verificado por IA
    AI_REVIEW_PRIORITY = "ai_review_priority"  # prioridad de revisión IA
    SOURCE = "source"                # procedencia (generated|chat|bank)
    CREATED_AT = "created_at"        # fecha de creación


# Set por defecto si el LLM no especifica columnas.
DEFAULT_TABLE_COLUMNS: list[TableColumn] = [
    TableColumn.N,
    TableColumn.TOPIC,
    TableColumn.DIFFICULTY,
    TableColumn.QUESTION_TYPE,
    TableColumn.QUESTION_TEXT,
    TableColumn.VERIFIED_BY_HUMAN,
]

# Etiquetas legibles de cada columna (encabezados de la tabla).
COLUMN_LABELS: dict[TableColumn, str] = {
    TableColumn.N: "#",
    TableColumn.ID: "Id",
    TableColumn.TOPIC: "Tema",
    TableColumn.SUBTOPIC: "Subtema",
    TableColumn.BLOOM_LEVEL: "Bloom",
    TableColumn.DIFFICULTY: "Dificultad",
    TableColumn.QUESTION_TYPE: "Tipo",
    TableColumn.QUESTION_TEXT: "Pregunta",
    TableColumn.EXPECTED_ANSWER: "Respuesta",
    TableColumn.OPTIONS: "Opciones",
    TableColumn.SOLUTION_EXPLANATION: "Solución",
    TableColumn.POINTS: "Puntos",
    TableColumn.VERIFIED_BY_HUMAN: "Verif. humano",
    TableColumn.VERIFIED_BY_AI: "Verif. IA",
    TableColumn.AI_REVIEW_PRIORITY: "Prioridad IA",
    TableColumn.SOURCE: "Origen",
    TableColumn.CREATED_AT: "Creada",
}


class _StrictModel(BaseModel):
    """Base común: rechaza campos extra que el LLM invente."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------
class ListarMateriasInput(_StrictModel):
    """Input de `listar_materias` (sin argumentos)."""


class BuscarPreguntasInput(_StrictModel):
    """Input de `buscar_preguntas`."""

    subject_id: str = Field(..., description="Id de la materia (UUID)")
    topic: str | None = Field(
        default=None, description="Filtro opcional por tema exacto"
    )
    limit: int = Field(
        default=20, ge=1, le=100, description="Nº máximo de preguntas a devolver (1-100)"
    )
    columns: list[TableColumn] | None = Field(
        default=None,
        description=(
            "Columnas a mostrar en la tabla (opcional). Valores: 'n', 'id', "
            "'topic', 'subtopic', 'bloom_level', 'difficulty', 'question_type', "
            "'question_text', 'expected_answer', 'points', 'verified_by_human', "
            "'verified_by_ai', 'ai_review_priority', 'source', 'created_at'. "
            "Si se omite se usa el set por defecto. Elige las columnas que pida "
            "el profesor (ej. 'dame id, tema y dificultad en tabla')."
        ),
    )


class ListarMaterialInput(_StrictModel):
    """Input de `listar_material_materia`."""

    subject_id: str = Field(..., description="Id de la materia (UUID)")


# ---------------------------------------------------------------------------
# Generación / guardado de preguntas
# ---------------------------------------------------------------------------
class GenerarPreguntaInput(_StrictModel):
    """Input de `generar_pregunta`."""

    subject_id: str = Field(..., description="Id de la materia (UUID)")
    subject_name: str = Field(..., description="Nombre de la materia")
    topic: str = Field(..., description=_TOPIC_DESC)
    difficulty: Difficulty = Field(
        default=Difficulty.MEDIO, description=_DIFFICULTY_DESC
    )


class AnswerOptionIn(AnswerOption):
    """Opción de respuesta que llega del LLM en tool-calling.

    Hereda `text` e `is_correct` de `AnswerOption` (src/schemas/exam.py).
    """

    model_config = ConfigDict(extra="forbid")


class GuardarPreguntaInput(_StrictModel):
    """Input de `guardar_pregunta`.

    Valida contra los enums del dominio: el LLM no puede guardar
    `bloom_level="facilísimo"` ni opciones sin exactamente una correcta
    (para opcion_multiple) — mismas reglas que `GeneratedItem`.
    """

    subject_id: str = Field(..., description="Id de la materia (UUID)")
    topic: str = Field(..., description=_TOPIC_DESC)
    bloom_level: str = Field(
        ...,
        description=(
            "Nivel de Bloom: 'recordar', 'comprender', 'aplicar', "
            "'analizar', 'evaluar' o 'crear'"
        ),
    )
    difficulty: Difficulty = Field(..., description=_DIFFICULTY_DESC)
    question_text: str = Field(..., min_length=5, description="Enunciado de la pregunta")
    question_type: QuestionType = Field(
        ...,
        description=(
            "Tipo: 'opcion_multiple', 'verdadero_falso', 'respuesta_corta', "
            "'desarrollo', 'relleno' o 'todas_correctas'"
        ),
    )
    options: list[AnswerOptionIn] | None = Field(
        default=None,
        description=(
            "Opciones (solo opcion_multiple/verdadero_falso/todas_correctas). "
            "Cada una: {'text': str, 'is_correct': bool}"
        ),
    )
    expected_answer: str | None = Field(
        default=None, description="Respuesta esperada o solución de referencia"
    )
    solution_explanation: str | None = Field(
        default=None, description="Justificación / solución paso a paso"
    )
    subtopic: str | None = Field(default=None, description="Subtema opcional")
    points: float = Field(default=1.0, gt=0, le=100, description="Puntaje (> 0)")

    def to_review_dict(self) -> dict:
        """Dict plano para `review_question` (verificador IA)."""
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


class GuardarPreguntaPendienteInput(_StrictModel):
    """Input de `guardar_pregunta_pendiente`."""

    verificar_humano: bool = Field(
        default=False,
        description=(
            "True solo si el profesor confirmó explícitamente marcar la "
            "pregunta como verificada por humano"
        ),
    )


class ConfirmarVerificacionInput(_StrictModel):
    """Input de `confirmar_verificacion_humana`."""

    question_id: str = Field(..., description="Id (UUID) de la pregunta a verificar")


# ---------------------------------------------------------------------------
# Exámenes
# ---------------------------------------------------------------------------
class GenerarExamenPdfInput(_StrictModel):
    """Input de `generar_examen_pdf`."""

    subject_id: str = Field(..., description="Id de la materia (UUID)")
    subject_name: str = Field(..., description="Nombre de la materia")
    total_questions: int = Field(
        default=5, ge=1, le=30, description="Nº de preguntas del examen (1-30)"
    )
    use_bank: bool = Field(
        default=True,
        description="True para armar el examen con preguntas YA existentes del banco",
    )
    num_versions: int = Field(
        default=1, ge=1, le=10, description="Nº de versiones barajadas del examen (1-10)"
    )


# ---------------------------------------------------------------------------
# Exportación del banco
# ---------------------------------------------------------------------------
class ExportarPreguntasInput(_StrictModel):
    """Input de `exportar_preguntas`."""

    subject_id: str = Field(..., description="Id de la materia (UUID)")
    formato: str = Field(
        default="csv",
        description="Formato del archivo de exportación: 'csv' o 'xlsx' (Excel)",
    )
    topic: str | None = Field(
        default=None, description="Filtro opcional por tema exacto"
    )
    limit: int = Field(
        default=100, ge=1, le=500, description="Nº máximo de preguntas a exportar (1-500)"
    )


# ---------------------------------------------------------------------------
# Material y materias
# ---------------------------------------------------------------------------
class AgregarMaterialArchivoInput(_StrictModel):
    """Input de `agregar_material_archivo`."""

    file_id: str = Field(
        ..., description="Id del archivo adjunto en Open WebUI (tag <file id='...'/> )"
    )
    subject_id: str = Field(..., description="Id de la materia (UUID)")
    subject_name: str = Field(..., description="Nombre de la materia")
    clear_previous: bool = Field(
        default=False,
        description="True para reemplazar el material previo de ese archivo",
    )


class RegistrarMateriaInput(_StrictModel):
    """Input de `registrar_materia`."""

    nombre: str = Field(
        ..., min_length=1, max_length=120, description="Nombre de la materia a registrar"
    )
