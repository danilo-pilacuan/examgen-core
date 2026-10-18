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
    """Returns a copy of the item with shuffled options.

    Keeps the correct option marked with `is_correct=True` and preserves the
    order of the others. Only applies to multiple choice / true-false.
    """
    if item.question_type not in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE):
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
    """Generates `num_versions` variants of the exam.

    Each version has:
      - Questions in a different order (if `shuffle_questions`).
      - Options of each question shuffled (if `shuffle_options`).

    Returns a list of lists: versions[i] = list of items (already shuffled).
    """
    versions: list[list[GeneratedItem]] = []
    for v in range(num_versions):
        rng = random.Random(seed + v if seed is not None else None)

        # Shuffle the options of each question.
        version_items = [
            shuffle_question(it, rng) if shuffle_options else deepcopy(it)
            for it in items
        ]

        # Shuffle the order of the questions.
        if shuffle_questions:
            rng.shuffle(version_items)

        versions.append(version_items)
    return versions


def render_item(item: GeneratedItem) -> str:
    statement = escape_latex(item.statement)

    if item.question_type == QuestionType.FILL_IN_BLANK:
        # Fill in the blank: the statement contains a blank. We use \fillin
        # with the expected answer (visible if \printanswers is active).
        answer = escape_latex(item.expected_answer)
        solution = escape_latex(item.solution_explanation)
        block = (
            f"\\question[{item.points:g}] {statement}\n"
            f"\\fillin[{answer}]\n"
            f"\\begin{{solution}}\n{solution}\n\\end{{solution}}\n"
        )
    elif item.question_type == QuestionType.SELECT_ALL:
        # Mark ALL correct options: uses \multiplechoice (not \choices).
        choices = "\n".join(
            f"    \\CorrectChoice {escape_latex(o.text)}" if o.is_correct
            else f"    \\choice {escape_latex(o.text)}"
            for o in item.options
        )
        block = (
            f"\\question[{item.points:g}] {statement}\n"
            f"\\textbf{{Mark all correct options.}}\n"
            f"\\begin{{checkboxes}}\n{choices}\n\\end{{checkboxes}}\n"
        )
    elif item.question_type in (QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE):
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
        # respuesta_corta / desarrollo → short_answer / essay
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
    """Renders the exam to LaTeX.

    If `num_versions > 1`, generates several variants (shuffled questions and
    options, AMC style) and returns a LIST of LaTeX sources (one per version).
    If `num_versions == 1`, returns a single string (to keep compatibility
    with the existing pipeline).

    The options (`show_grading_table`, `boxed_points`, `include_cover`)
    allow configuring the template without editing it (base for a future
    web template interface).
    """
    template_path = get_template_path(template_id)
    # The LaTeX macros \newcommand{...}{#1} contain '{#', which Jinja
    # would interpret as the start of a comment. We change ONLY the comment
    # delimiter to a non-colliding one; variable {{ }} and block {% %}
    # delimiters are kept (the template already uses them).
    env = Environment(
        loader=FileSystemLoader(template_path.parent),
        comment_start_string="<#",
        comment_end_string="#>",
    )
    template = env.get_template(template_path.name)

    base_kwargs = dict(
        subject_name=escape_latex(subject_name),
        exam_title=escape_latex(f"Exam — {subject_name}"),
        department=escape_latex(department),
        exam_date=escape_latex(exam_date),
        exam_time=escape_latex(exam_time),
        duration=escape_latex(f"{duration_minutes} minutes"),
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

    # Multiple shuffled versions (AMC style, anti-copy).
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