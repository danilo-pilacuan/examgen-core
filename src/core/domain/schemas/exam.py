from enum import Enum
from typing import Optional
import uuid
from pydantic import BaseModel, Field, field_validator


class BloomLevel(str, Enum):
    RECORDAR = "recordar"
    COMPRENDER = "comprender"
    APLICAR = "aplicar"
    ANALIZAR = "analizar"
    EVALUAR = "evaluar"
    CREAR = "crear"


class Difficulty(str, Enum):
    FACIL = "facil"
    MEDIO = "medio"
    DIFICIL = "dificil"


class QuestionType(str, Enum):
    OPCION_MULTIPLE = "opcion_multiple"
    VERDADERO_FALSO = "verdadero_falso"
    RESPUESTA_CORTA = "respuesta_corta"
    DESARROLLO = "desarrollo"
    RELLENO = "relleno"            # completar: se usa \fillin con la respuesta
    TODAS_CORRECTAS = "todas_correctas"  # marcar TODAS las correctas (\multiplechoice)


class AnswerOption(BaseModel):
    """Una opción de respuesta para preguntas de opción múltiple."""
    text: str = Field(..., description="Texto de la opción, sin marcar cuál es correcta")
    is_correct: bool = Field(default=False)


class GeneratedItem(BaseModel):
    """
    Estructura que el LLM Generador debe producir para cada pregunta.
    Este es el contrato estricto entre el LLM y el resto del pipeline:
    el modelo NUNCA genera LaTeX directamente, solo esta estructura.
    """
    topic: str = Field(..., description="Tema del pensum al que pertenece la pregunta")
    subtopic: Optional[str] = Field(default=None)
    bloom_level: BloomLevel
    difficulty: Difficulty
    question_type: QuestionType

    statement: str = Field(..., description="Enunciado de la pregunta, texto plano (sin LaTeX)")
    options: list[AnswerOption] = Field(
        default_factory=list,
        description="Solo aplica para opcion_multiple o verdadero_falso"
    )
    expected_answer: str = Field(..., description="Respuesta esperada o solución de referencia")
    solution_explanation: str = Field(
        ..., description="Justificación pedagógica / solución paso a paso"
    )
    points: float = Field(default=1.0, gt=0)

    @field_validator("options")
    @classmethod
    def validate_options(cls, options: list[AnswerOption], info):
        question_type = info.data.get("question_type")
        if question_type == QuestionType.OPCION_MULTIPLE:
            if len(options) < 3:
                raise ValueError("opcion_multiple requiere al menos 3 opciones")
            correct = [o for o in options if o.is_correct]
            if len(correct) != 1:
                raise ValueError("opcion_multiple requiere exactamente una opción correcta")
        if question_type == QuestionType.VERDADERO_FALSO and len(options) != 2:
            raise ValueError("verdadero_falso requiere exactamente 2 opciones")
        if question_type == QuestionType.TODAS_CORRECTAS:
            if len(options) < 2:
                raise ValueError("todas_correctas requiere al menos 2 opciones")
            correct = [o for o in options if o.is_correct]
            if len(correct) < 1:
                raise ValueError("todas_correctas requiere al menos una opción correcta")
        return options


class EvaluationResult(BaseModel):
    """Salida del Agente Evaluador para un ítem generado."""
    approved: bool
    quality_score: float = Field(..., ge=0, le=10)
    difficulty_match: bool = Field(
        ..., description="¿La dificultad real coincide con la solicitada?"
    )
    is_duplicate: bool = False
    similarity_score: Optional[float] = Field(default=None, ge=0, le=1)
    rejection_reason: Optional[str] = None


class RetrievalConfig(BaseModel):
    """Configuración del RAG para este examen.

    Controla cómo el Generador recupera contexto del material indexado.
    """
    top_k: int = Field(default=3, ge=1, le=20, description="Nº de fragmentos a recuperar")
    min_score: float = Field(default=0.15, ge=0, le=1, description="Umbral mínimo de similitud")
    use_rag: bool = Field(default=True, description="Si False, usa el resumen del syllabus")
    max_chars_per_chunk: int = Field(default=1200, ge=100)


class ExamMetadata(BaseModel):
    """Metadatos del examen (para experimentación y trazabilidad)."""
    title: str = Field(default="", description="Título del examen, ej. Primer Parcial")
    instructions: str = Field(default="", description="Instrucciones para el estudiante")
    model: str = Field(default="", description="Modelo LLM usado")
    temperature: float | None = Field(default=None, ge=0, le=2)
    reasoning_effort: str | None = Field(default=None)
    experiment_tag: str = Field(default="", description="Etiqueta para comparar experimentos")
    notes: str = Field(default="")
    num_versions: int = Field(
        default=1, ge=1, le=10,
        description="Nº de versiones del examen (barajado anti-copia, estilo AMC)",
    )


class ExamBlueprint(BaseModel):
    """Salida del Agente Planificador: la estructura que debe tener el examen."""
    subject_id: str
    total_questions: int = Field(..., gt=0)
    bloom_distribution: dict[BloomLevel, float] = Field(
        ..., description="Proporción 0-1 de preguntas por nivel de Bloom, debe sumar 1.0"
    )
    difficulty_distribution: dict[Difficulty, float] = Field(
        ..., description="Proporción 0-1 de preguntas por dificultad, debe sumar 1.0"
    )
    topics_weight: dict[str, float] = Field(
        ..., description="Ponderación por tema del pensum, debe sumar 1.0"
    )
    estimated_duration_minutes: int = Field(default=90)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    metadata: ExamMetadata = Field(default_factory=ExamMetadata)

    @field_validator("bloom_distribution", "difficulty_distribution", "topics_weight")
    @classmethod
    def validate_sums_to_one(cls, v: dict, info):
        total = sum(v.values())
        if not (0.98 <= total <= 1.02):  # tolerancia por redondeo
            raise ValueError(f"{info.field_name} debe sumar ~1.0, suma actual: {total}")
        return v


class CompiledExam(BaseModel):
    """Resultado final ensamblado."""
    subject_id: str
    blueprint: ExamBlueprint
    items: list[GeneratedItem]
    latex_source: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_paths: Optional[list[str]] = None  # rutas de las versiones (si num_versions>1)
    compilation_attempts: int = 0

class ItemSpec(BaseModel):
    """Una 'ranura' específica que el Planificador asigna: qué debe generar el Generador."""
    spec_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str
    subtopic: Optional[str] = None
    bloom_level: BloomLevel
    difficulty: Difficulty
    question_type: QuestionType
    points: float = Field(default=1.0, gt=0)    