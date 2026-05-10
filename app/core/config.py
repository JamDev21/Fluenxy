from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Fluenxy API"
    ENVIRONMENT: str = "development"

    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # AI APIs
    GROQ_API_KEY: str
    DEEPSEEK_API_KEY: str

    
    # Read from .env
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Create a copy of the configuration so we can import it into other files
settings = Settings()