from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000

    llm_model: str = "liquid/lfm2.5-1.2b"
    llm_model_provider: str = "openai"
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_api_key: str = "not-needed"

    local_model_only: bool = False