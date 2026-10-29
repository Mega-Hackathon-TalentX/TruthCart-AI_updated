import os
import json
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

def _parse_cors_origins(raw: str) -> List[str]:
    default = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://truth-cart-ai.vercel.app",
        "https://truthcart-ai.vercel.app",
    ]
    if not raw or not raw.strip():
        return default
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(o).strip() for o in parsed if str(o).strip()]
        except Exception:
            pass
    origins = []
    for item in raw.split(","):
        cleaned = item.strip().strip("[]\"'")
        if cleaned:
            origins.append(cleaned)
    return origins if origins else default

class Settings(BaseModel):
    PROJECT_NAME: str = "TruthCart AI"
    TEAM_NAME: str = "TalentX"
    PROBLEM_STATEMENT: str = "R3 — The Conversational Shopping Assistant That Doesn't Lie"
    TRACK: str = "Retail"
    TAGLINE: str = "Shop Smarter. Trust Every Answer."
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    LOG_LEVEL: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    # Server Settings
    HOST: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))
    PORT: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    
    # Base workspace directory (find root containing 'data' or 'backend')
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent.parent)

    # Data Directories
    OFFICIAL_PRODUCTS_DIR: Path = Field(
        default_factory=lambda: Path(os.getenv("OFFICIAL_PRODUCTS_DIR", "data/products"))
    )
    OFFICIAL_POLICIES_DIR: Path = Field(
        default_factory=lambda: Path(os.getenv("OFFICIAL_POLICIES_DIR", "data/policies"))
    )
    TEST_QUESTIONS_DIR: Path = Field(
        default_factory=lambda: Path(os.getenv("TEST_QUESTIONS_DIR", "data/test_questions"))
    )
    DEV_FIXTURES_DIR: Path = Field(
        default_factory=lambda: Path(os.getenv("DEV_FIXTURES_DIR", "data/development_fixtures"))
    )

    # Model Directories
    EMBEDDING_MODEL_DIR: Path = Field(
        default_factory=lambda: Path(os.getenv("EMBEDDING_MODEL_DIR", "models/embedding_model"))
    )
    INSTRUCTION_MODEL_DIR: Path = Field(
        default_factory=lambda: Path(os.getenv("INSTRUCTION_MODEL_DIR", "models/instruction_model"))
    )

    # Artifacts
    INDEX_DIR: Path = Field(
        default_factory=lambda: Path(os.getenv("INDEX_DIR", "artifacts/indexes"))
    )
    EVALUATION_REPORT_DIR: Path = Field(
        default_factory=lambda: Path(os.getenv("EVALUATION_REPORT_DIR", "artifacts/evaluation_reports"))
    )

    # Development Fixture Toggle (Strict Guardrail: default False)
    LOAD_SYNTHETIC_DEV_DATA_WHEN_EMPTY: bool = Field(
        default_factory=lambda: os.getenv("LOAD_SYNTHETIC_DEV_DATA_WHEN_EMPTY", "false").lower() in ("true", "1", "yes")
    )

    # CORS
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: _parse_cors_origins(os.getenv("CORS_ORIGINS", "")))

    # Database & Storage
    DATABASE_PATH: Path = Field(
        default_factory=lambda: Path(os.getenv("DATABASE_PATH", "data/truthcart.db"))
    )

    # Authentication & Security
    JWT_SECRET_KEY: str = Field(
        default_factory=lambda: os.getenv("JWT_SECRET_KEY", "truthcart-secret-key-talentx-2026-hackathon")
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    INITIAL_OWNER_EMAIL: str = Field(
        default_factory=lambda: os.getenv("INITIAL_OWNER_EMAIL", "owner@truthcart.ai")
    )
    INITIAL_OWNER_PASSWORD: str = Field(
        default_factory=lambda: os.getenv("INITIAL_OWNER_PASSWORD", "AdminTruthCart2026!")
    )
    INITIAL_CUSTOMER_EMAIL: str = Field(
        default_factory=lambda: os.getenv("INITIAL_CUSTOMER_EMAIL", "customer@truthcart.ai")
    )
    INITIAL_CUSTOMER_PASSWORD: str = Field(
        default_factory=lambda: os.getenv("INITIAL_CUSTOMER_PASSWORD", "Customer123!")
    )

    def resolve_path(self, rel_path: Path) -> Path:
        if rel_path.is_absolute():
            return rel_path
        return (self.BASE_DIR / rel_path).resolve()

    def get_products_path(self) -> Path:
        return self.resolve_path(self.OFFICIAL_PRODUCTS_DIR)

    def get_policies_path(self) -> Path:
        return self.resolve_path(self.OFFICIAL_POLICIES_DIR)

    def get_dev_fixtures_path(self) -> Path:
        return self.resolve_path(self.DEV_FIXTURES_DIR)

    def get_test_questions_path(self) -> Path:
        return self.resolve_path(self.TEST_QUESTIONS_DIR)

    def get_embedding_model_path(self) -> Path:
        return self.resolve_path(self.EMBEDDING_MODEL_DIR)

    def get_instruction_model_path(self) -> Path:
        return self.resolve_path(self.INSTRUCTION_MODEL_DIR)

    def get_index_path(self) -> Path:
        return self.resolve_path(self.INDEX_DIR)

    def get_evaluation_report_path(self) -> Path:
        return self.resolve_path(self.EVALUATION_REPORT_DIR)

    def get_database_path(self) -> Path:
        return self.resolve_path(self.DATABASE_PATH)


settings = Settings()
