from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    graphdb_url: str = "http://localhost:7200"
    graphdb_repository: str = "test"

    class Config:
        env_file = ".env"


settings = Settings()
