from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    latex_compiler_url: str
    openai_api_key: str = "no-key"  # placeholder; local infra doesn't validate real keys

    # --- LLM provider (local OpenAI-compatible infra) ---
    llm_model: str = "zai-org/GLM-5.3-Flash"
    llm_base_url: str = "http://172.28.230.10:12555/v1"
    llm_temperature: float = 0.7
    # The vLLM server accepts up to ~100k+ output tokens (tested) and the
    # model supports 1M context (up to 131072 output tokens per its
    # configuration). 65536 gives ample margin to generate the full exam in
    # a single pass or very elaborate items, without nearing server limits.
    llm_max_tokens: int = 65536
    # Reasoning level per node. The server supports 7 levels:
    # none | minimal | low | medium | high | xhigh | max
    # IMPORTANT (vLLM + reasoning models): if a node uses
    # `with_structured_output` (response_format json), reasoning consumes
    # output tokens and leaves `content` empty → invalid JSON.
    # That's why Generator and Evaluator use `none` to produce JSON in content.
    llm_reasoning_generator: str = "none"
    llm_reasoning_evaluator: str = "none"
    # Reasoning level of the conversational agent (chat).
    # IMPORTANT (GLM-5.3-Flash): unlike DeepSeek, with `none` the model writes
    # its reasoning DIRECTLY into `content` (chat responses "dirtied" with
    # analysis text). With `low` the content comes out clean and structured
    # output keeps working (verified).
    llm_reasoning_chat: str = "low"
    # Lower temperature for the evaluator (more deterministic judgment).
    llm_temperature_evaluator: float = 0.2

    # --- Model context (1M tokens) ---
    # Fraction of the syllabus injected as context per call.
    max_context_chars: int = 6000

    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    dedup_similarity_threshold: float = 0.82
    embedding_url: str = "http://localhost:8081/v1/embeddings"
    # Embedding service (OpenAI-compatible, runs in local Docker)

    # --- Graph safety limits ---
    max_item_retries: int = 3
    max_total_llm_calls: int = 200
    max_compilation_attempts: int = 3

    # --- Open WebUI (to upload PDFs as native chat attachments) ---
    openwebui_url: str = "http://localhost:3000"  # internal URL (Docker network)
    openwebui_public_url: str = "http://localhost:3000"  # public URL (browser)
    openwebui_admin_email: str = "admin@localhost"
    openwebui_admin_password: str = "admin"

settings = Settings()