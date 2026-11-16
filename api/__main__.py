"""Start the API:  python -m api [--reload]   (API_HOST / API_PORT in .env)."""

import argparse
import sys

import uvicorn

from utils.config import PROJECT_ROOT, get_settings

# Folders with code; --reload watches only these (data/ changes all the time)
_CODE_FOLDERS = ("api", "chunking", "database", "embeddings", "evaluation", "ingestion", "llm", "prompts",
                 "retrieval", "utils", "vectordb", "workers")


def main() -> None:
    # Windows terminals default to a legacy encoding that can't print all characters
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="python -m api", description="Start the RAG API server.")
    parser.add_argument("--reload", action="store_true", help="Restart automatically when the code changes")
    args = parser.parse_args()

    settings = get_settings()
    uvicorn.run(
        "api.main:app", host=settings.api_host, port=settings.api_port, reload=args.reload,
        reload_dirs=[str(PROJECT_ROOT / folder) for folder in _CODE_FOLDERS] if args.reload else None,
    )


if __name__ == "__main__":
    main()
