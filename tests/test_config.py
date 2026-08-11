from agent_harness.config import Settings


def test_normalizes_managed_postgres_url() -> None:
    settings = Settings(database_url="postgresql://user:pass@db.example/harness")
    assert settings.database_url == "postgresql+asyncpg://user:pass@db.example/harness"

