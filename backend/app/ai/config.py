"""AI 配置。密钥只在服务端读取，不进入接口响应和执行记录。"""
from dataclasses import dataclass, field
from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_local_env() -> None:
    """只填充未设置的环境变量；支持项目根目录的本地 .env。"""
    path = PROJECT_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if key.replace("_", "").isalnum():
            os.environ.setdefault(key, value.strip('"\''))


load_local_env()


def _integer(name: str, default: int, low: int, high: int) -> int:
    value = int(os.getenv(name, default))
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


@dataclass
class AISettings:
    llm_api_base: str = field(default_factory=lambda: os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1").rstrip("/"))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "deepseek-flash"))
    llm_timeout: int = field(default_factory=lambda: _integer("LLM_TIMEOUT", 60, 1, 300))
    max_agent_steps: int = field(default_factory=lambda: _integer("MAX_AGENT_STEPS", 6, 1, 12))
    max_repair_attempts: int = field(default_factory=lambda: _integer("MAX_REPAIR_ATTEMPTS", 2, 0, 3))
    embedding_api_base: str = field(default_factory=lambda: os.getenv("EMBEDDING_API_BASE", "").rstrip("/"))
    embedding_api_key: str = field(default_factory=lambda: os.getenv("EMBEDDING_API_KEY", ""))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", ""))
    embedding_timeout: int = 30
    top_k: int = field(default_factory=lambda: _integer("RAG_TOP_K", 4, 1, 10))
    chunk_size: int = field(default_factory=lambda: _integer("RAG_CHUNK_SIZE", 480, 100, 2000))
    chunk_overlap: int = field(default_factory=lambda: _integer("RAG_CHUNK_OVERLAP", 80, 0, 200))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("ADCRAFT_DATA_DIR", str(PROJECT_ROOT / "data" / "runtime"))))
    image_provider: str = field(default_factory=lambda: os.getenv("IMAGE_PROVIDER", "demo").lower())
    image_api_base: str = field(default_factory=lambda: os.getenv("IMAGE_API_BASE", "https://dashscope.aliyuncs.com/api/v1").rstrip("/"))
    image_api_key: str = field(default_factory=lambda: os.getenv("IMAGE_API_KEY", ""))
    image_model: str = field(default_factory=lambda: os.getenv("IMAGE_MODEL", "wanx2.1-t2i-turbo"))
    image_timeout: int = 180
    max_concurrent_runs: int = 4
    force_demo: bool = field(default_factory=lambda: os.getenv("AI_MODE", "auto").lower() == "demo")

    @property
    def mode(self) -> str:
        return "demo" if self.force_demo or not self.llm_api_key else "live"

    @property
    def embedding_enabled(self) -> bool:
        return self.mode == "live" and bool(self.embedding_api_base and self.embedding_api_key and self.embedding_model)

