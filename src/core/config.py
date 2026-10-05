from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    latex_compiler_url: str
    openai_api_key: str = "no-key"  # placeholder; la infra local no valida keys reales

    # --- Proveedor LLM (infra local OpenAI-compatible) ---
    llm_model: str = "zai-org/GLM-5.3-Flash"
    llm_base_url: str = "http://172.28.230.10:12555/v1"
    llm_temperature: float = 0.7
    # El servidor vLLM acepta hasta ~100k+ tokens de salida (probado) y el
    # modelo soporta 1M de contexto (hasta 131072 tokens de salida según su
    # configuración). 65536 da margen amplio para generar el examen completo
    # en una sola pasada o ítems muy elaborados, sin acercarse a los límites
    # del servidor.
    llm_max_tokens: int = 65536
    # Nivel de razonamiento por nodo. El servidor soporta 7 niveles:
    # none | minimal | low | medium | high | xhigh | max
    # IMPORTANTE (vLLM + modelos de razonamiento): si un nodo usa
    # `with_structured_output` (response_format json), el razonamiento
    # consume los tokens de salida y deja `content` vacío → JSON inválido.
    # Por eso Generador y Evaluador usan `none` para producir JSON en content.
    llm_reasoning_generator: str = "none"
    llm_reasoning_evaluator: str = "none"
    # Nivel de razonamiento del agente conversacional (chat).
    # IMPORTANTE (GLM-5.3-Flash): a diferencia de DeepSeek, con `none` el
    # modelo escribe su razonamiento DIRECTAMENTE en `content` (respuestas
    # del chat "ensuciadas" con texto de análisis). Con `low` el contenido
    # sale limpio y el structured output sigue funcionando (verificado).
    llm_reasoning_chat: str = "low"
    # Temperatura más baja para el evaluador (juicio más determinista).
    llm_temperature_evaluator: float = 0.2

    # --- Contexto del modelo (1M tokens) ---
    # Fracción del syllabus que se inyecta como contexto en cada llamada.
    max_context_chars: int = 6000

    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    dedup_similarity_threshold: float = 0.82
    # Servicio de embeddings (OpenAI-compatible, corre en Docker local)
    embedding_url: str = "http://localhost:8081/v1/embeddings"

    # --- Límites de seguridad del grafo ---
    max_item_retries: int = 3
    max_total_llm_calls: int = 200
    max_compilation_attempts: int = 3

    # --- Open WebUI (para subir PDFs como adjuntos nativos del chat) ---
    openwebui_url: str = "http://localhost:3000"  # URL interna (red Docker)
    openwebui_public_url: str = "http://localhost:3000"  # URL pública (navegador)
    openwebui_admin_email: str = "admin@localhost"
    openwebui_admin_password: str = "admin"

settings = Settings()