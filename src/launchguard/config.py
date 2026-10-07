"""Runtime configuration with safe defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    database_path: Path = Path("data/launchguard.sqlite")
    checkpoint_path: Path = Path("data/checkpoints.sqlite")
    policy_dir: Path = Path("examples/policies")
    fx_mode: str = "live"
    generator: str = "deterministic"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    shopify_mode: str = "dry-run"
    shopify_store: str = ""
    shopify_token: str = ""
    shopify_api_version: str = "2026-10"

    @classmethod
    def from_env(cls, env_file: str = ".env") -> Settings:
        load_dotenv(env_file, override=False)
        return cls(
            environment=os.getenv("LAUNCHGUARD_ENV", "development"),
            database_path=Path(
                os.getenv("LAUNCHGUARD_DB_PATH", "data/launchguard.sqlite")
            ),
            checkpoint_path=Path(
                os.getenv("LAUNCHGUARD_CHECKPOINT_PATH", "data/checkpoints.sqlite")
            ),
            policy_dir=Path(os.getenv("LAUNCHGUARD_POLICY_DIR", "examples/policies")),
            fx_mode=os.getenv("LAUNCHGUARD_FX_MODE", "live"),
            generator=os.getenv("LAUNCHGUARD_GENERATOR", "deterministic"),
            llm_base_url=os.getenv(
                "LAUNCHGUARD_LLM_BASE_URL", "https://api.openai.com/v1"
            ),
            llm_api_key=os.getenv("LAUNCHGUARD_LLM_API_KEY", ""),
            llm_model=os.getenv("LAUNCHGUARD_LLM_MODEL", ""),
            shopify_mode=os.getenv("LAUNCHGUARD_SHOPIFY_MODE", "dry-run"),
            shopify_store=os.getenv("LAUNCHGUARD_SHOPIFY_STORE", ""),
            shopify_token=os.getenv("LAUNCHGUARD_SHOPIFY_TOKEN", ""),
            shopify_api_version=os.getenv("LAUNCHGUARD_SHOPIFY_API_VERSION", "2026-10"),
        )

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
