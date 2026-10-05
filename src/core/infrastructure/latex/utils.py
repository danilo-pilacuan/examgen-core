from __future__ import annotations

import random
from copy import deepcopy

from jinja2 import Environment, FileSystemLoader
from core.domain.schemas.exam import GeneratedItem, QuestionType, CompiledExam
from core.infrastructure.latex.templates.registry import get_template_path, TemplateId

LATEX_SPECIAL_CHARS = {
    "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}",
    "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}

def escape_latex(text: str) -> str:
    for char, repl in LATEX_SPECIAL_CHARS.items():
        text = text.replace(char, repl)
    return text


def shuffle_question(item: GeneratedItem, rng: random.Random) -> GeneratedItem:
    """Devuelve una copia del ítem con las opciones barajadas.

    Mantiene la opción correcta marcada con `is_correct=True` y conserva el
    orden de las demás. Solo aplica a opción múltiple / verdadero-falso.
    """
    if item.question_type not in (QuestionType.OPCION_MULTIPLE, QuestionType.VERDADERO_FALSO):
        return item
    if not item.options:
        return item

    shuffled = list(item.options)
    rng.shuffle(shuffled)
    new_item = deepcopy(item)
    new_item.options = shuffled
    return new_item


def build_exam_versions(
    items: list[GeneratedItem],
    num_versions: int = 1,
    shuffle_questions: bool = True,
    shuffle_options: bool = True,
    seed: int | None = None,
) -> list[list[GeneratedItem]]:
    """Genera `num_versions` variantes del examen.

    Cada versión tiene:
      - Las preguntas en un orden distinto (si `shuffle_questions`).
      - Las opciones de cada pregunta barajadas (si `shuffle_options`).

    Devuelve una lista de listas: versiones[i] = lista de ítems (ya barajados).
    """
    versions: list[list[GeneratedItem]] = []
    for v in range(num_versions):
        rng = random.Random(seed + v if seed is not None else None)

        # Barajar las opciones de cada pregunta.
        version_items = [
            shuffle_question(it, rng) if shuffle_options else deepcopy(it)
            for it in items
        ]

        # Barajar el orden de las preguntas.
        if shuffle_questions:
            rng.shuffle(version_items)

        versions.append(version_items)
    return versions


def render_item(item: GeneratedItem) -> str:
    statement = escape_latex(item.statement)

    if item.question_type == QuestionType.RELLENO:
        # Completar: el enunciado contiene un espacio en blanco. Usamos \fillin
        # con la respuesta esperada (visible si \printanswers está activo).
        answer = escape_latex(item.expected_answer)
        solution = escape_latex(item.solution_explanation)
        block = (
            f"\\question[{item.points:g}] {statement}\n"
            f"\\fillin[{answer}]\n"
            f"\\begin{{solution}}\n{solution}\n\\end{{solution}}\n"
        )
    elif item.question_type == QuestionType.TODAS_CORRECTAS:
        # Marcar TODAS las correctas: se usa \multiplechoice (no \choices).
        choices = "\n".join(
            f"    \\CorrectChoice {escape_latex(o.text)}" if o.is_correct
            else f"    \\choice {escape_latex(o.text)}"
            for o in item.options
        )
        block = (
            f"\\question[{item.points:g}] {statement}\n"
            f"\\textbf{{Marque todas las opciones correctas.}}\n"
            f"\\begin{{checkboxes}}\n{choices}\n\\end{{checkboxes}}\n"
        )
    elif item.question_type in (QuestionType.OPCION_MULTIPLE, QuestionType.VERDADERO_FALSO):
        choices = "\n".join(
            f"    \\CorrectChoice {escape_latex(o.text)}" if o.is_correct
            else f"    \\choice {escape_latex(o.text)}"
            for o in item.options
        )
        block = (
            f"\\question[{item.points:g}] {statement}\n"
            f"\\begin{{choices}}\n{choices}\n\\end{{choices}}\n"
        )
    else:
        # respuesta_corta / desarrollo
        answer = escape_latex(item.expected_answer)
        solution = escape_latex(item.solution_explanation)
        block = (
            f"\\question[{item.points:g}] {statement}\n"
            f"\\droppoints\n"
            f"\\begin{{answers}}\n{answer}\n\\end{{answers}}\n"
            f"\\begin{{solution}}\n{solution}\n\\end{{solution}}\n"
            f"\\vspace{{2cm}}\n"
        )

    return block

def render_exam(
    exam: CompiledExam,
    template_id: TemplateId,
    subject_name: str,
    instructions: str,
    department: str = "",
    exam_date: str = "",
    exam_time: str = "",
    examiner_name: str = "",
    duration_minutes: int = 90,
    print_answers: bool = True,
    num_versions: int = 1,
    shuffle_questions: bool = True,
    shuffle_options: bool = True,
    seed: int | None = None,
    show_grading_table: bool = True,
    boxed_points: bool = False,
    include_cover: bool = True,
) -> str | list[str]:
    """Renderiza el examen a LaTeX.

    Si `num_versions > 1`, genera varias variantes (preguntas y opciones
    barajadas, como AMC) y devuelve una LISTA de fuentes LaTeX (una por
    versión). Si `num_versions == 1`, devuelve una sola cadena (para no
    romper la compatibilidad con el pipeline existente).

    Las opciones (`show_grading_table`, `boxed_points`, `include_cover`)
    permiten configurar el template sin editarlo (base para la futura
    interfaz web de templates).
    """
    template_path = get_template_path(template_id)
    # Las macros LaTeX \newcommand{...}{#1} contienen '{#', que Jinja
    # interpretaría como inicio de comentario. Cambiamos SOLO el delimitador
    # de comentario a uno sin colisión; los de variable {{ }} y bloque {% %}
    # se mantienen (el template ya los usa).
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        comment_start_string="<#",
        comment_end_string="#>",
    )
    template = env.get_template(template_path.name)

    base_kwargs = dict(
        subject_name=escape_latex(subject_name),
        exam_title=escape_latex(f"Examen — {subject_name}"),
        department=escape_latex(department),
        exam_date=escape_latex(exam_date),
        exam_time=escape_latex(exam_time),
        duration=escape_latex(f"{duration_minutes} minutos"),
        examiner_name=escape_latex(examiner_name),
        instructions=escape_latex(instructions),
        print_answers=print_answers,
        include_answer_key=True,
        show_grading_table=show_grading_table,
        boxed_points=boxed_points,
        include_cover=include_cover,
    )

    if num_versions <= 1:
        questions_block = "\n".join(render_item(item) for item in exam.items)
        return template.render(questions_block=questions_block, **base_kwargs)

    # Múltiples versiones barajadas (estilo AMC, anti-copia).
    versions = build_exam_versions(
        exam.items,
        num_versions=num_versions,
        shuffle_questions=shuffle_questions,
        shuffle_options=shuffle_options,
        seed=seed,
    )
    rendered = []
    for version_items in versions:
        questions_block = "\n".join(render_item(item) for item in version_items)
        rendered.append(template.render(questions_block=questions_block, **base_kwargs))
    return rendered