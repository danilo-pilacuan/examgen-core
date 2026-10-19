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