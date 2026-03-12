from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GLM API
    glm_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4/"
    glm_model: str = "glm-4-flash"

    # Deepgram API
    deepgram_api_key: str = ""

    # STT 设置
    stt_language: str = "zh"
    stt_endpointing_ms: int = 300
    stt_utterance_end_ms: int = 1000

    # 论点提取设置
    extraction_confidence_threshold: float = 0.5
    extraction_context_window: int = 5

    # 搜索设置
    search_max_queries_per_claim: int = 3
    search_max_results_per_query: int = 5

    # 服务器设置
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "env_prefix": "ARGUE_"}


settings = Settings()
