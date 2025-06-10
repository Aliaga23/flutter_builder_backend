from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    openai_api_key: str  # Add this line to accept the OpenAI API key

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
