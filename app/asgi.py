"""ASGI entry point: ``uvicorn app.asgi:app``  (reads .env / RECETAS_CONFIG_FILE below real env vars)."""
from .config import load_dotenv

load_dotenv()

from .main import create_app  # noqa: E402

app = create_app()
