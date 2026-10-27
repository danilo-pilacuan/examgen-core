import uuid
from sqlalchemy import String, Text, ForeignKey, DateTime, func, Boolean, Float, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

class Base(DeclarativeBase):
    pass

class User(Base):
    """Professor account (multi-tenant owner of subjects and sessions)."""
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(500))
    role: Mapped[str] = mapped_column(String(20), default="professor", server_default="professor")
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    # Owning professor (NULL = legacy/shared subject, visible to everyone).
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    syllabus: Mapped[list["SyllabusTopic"]] = relationship(back_populates="subject")
    chunks: Mapped[list["MaterialChunk"]] = relationship(back_populates="subject")

class SyllabusTopic(Base):
    __tablename__ = "syllabus_topics"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"))
    subject: Mapped["Subject"] = relationship(back_populates="syllabus")
    title: Mapped[str] = mapped_column(String(200))
    weight: Mapped[float] = mapped_column(default=1.0)

class MaterialChunk(Base):
    """Chunk of a subject's material, with its embedding (for RAG)."""
    __tablename__ = "material_chunks"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"))
    subject: Mapped["Subject"] = relationship(back_populates="chunks")
    source_file: Mapped[str] = mapped_column(String(500))
    chunk_index: Mapped[int] = mapped_column(default=0)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class GeneratedQuestion(Base):
    __tablename__ = "generated_questions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"))
    topic: Mapped[str] = mapped_column(String(200))
    bloom_level: Mapped[str] = mapped_column(String(50))
    difficulty: Mapped[str] = mapped_column(String(50))
    question_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024))
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

    # --- Full item structure (previously only the text was saved) ---
    question_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list[AnswerOption]
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtopic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    points: Mapped[float | None] = mapped_column(Float, nullable=True)

    # --- Human and AI verification (Felipe's requirement) ---
    verified_by_human: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    verified_by_ai: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    ai_review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_review_priority: Mapped[str | None] = mapped_column(String(20), nullable=True)  # alta|media|baja

    # --- Provenance and audit ---
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)  # generated|bank
    created_by: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "agent"|"human"|"chat"

class LLMResponse(Base):
    """Audit record of one LLM call (raw prompt/answer, optional thinking).

    Written best-effort by `core.domain.llm_log.service`: a logging failure
    must never break the chat or the pipeline.
    """
    __tablename__ = "llm_responses"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context: Mapped[str] = mapped_column(String(100))  # chat:model | chat:generate_question | pipeline:generator ...
    model: Mapped[str] = mapped_column(String(200))
    prompt: Mapped[str] = mapped_column(Text)
    raw_answer: Mapped[str] = mapped_column(Text)
    raw_thinking: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class Exam(Base):
    """A generated exam package (persisted for the Exams view).

    One row per exam generation: the blueprint, the approved items, the
    artifact file names (PDFs with/without answers and the ZIP) and the
    human-readable name the professor requested.
    """
    __tablename__ = "exams"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"))
    name: Mapped[str] = mapped_column(String(200))  # professor-requested name
    blueprint: Mapped[dict] = mapped_column(JSON)
    items: Mapped[list] = mapped_column(JSON)
    num_versions: Mapped[int] = mapped_column(default=1)
    pdf_paths: Mapped[list] = mapped_column(JSON)  # file names in /output
    zip_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(50), nullable=True)  # chat|exams-view
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())

class ChatThread(Base):
    """Server-side chat thread metadata (per-user conversation registry).

    Fixes BUG-022 (no thread ownership: any authenticated user could read or
    write another user's thread) and BUG-023 (thread list only in
    localStorage, invisible from another browser or after clearing it).

    Content still lives in the LangGraph PostgresSaver checkpointer; this
    table holds only the listing metadata (DEC-004 option a).
    """
    __tablename__ = "chat_threads"
    thread_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    # Last subject used in the conversation (badge; NULL = thread without subject).
    last_subject_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("subjects.id"), nullable=True
    )
    last_subject_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message_count: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[str] = mapped_column(DateTime, server_default=func.now())