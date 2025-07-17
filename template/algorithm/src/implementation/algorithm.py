from logging import getLogger
from pathlib import Path
from typing import Any, Optional, TypeVar
from oceanprotocol_job_details.ocean import JobDetails

# =============================== IMPORT LIBRARY ====================
import json
import runpy
import requests
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.schema import Document
# =============================== END ===============================
T = TypeVar("T")
logger = getLogger(__name__)

class Algorithm:
    def __init__(self, job_details: JobDetails):
        self._job_details = job_details
        self.results: Optional[Any] = None

    def _validate_input(self) -> None:
        if not self._job_details.files:
            logger.warning("No files found")
            raise ValueError("No files found")

    def _ensure_model_available(self, model: str, base_url: str) -> None:
        try:
            resp = requests.get(f"{base_url}/api/models")
            resp.raise_for_status()
            available = [m.get("model") for m in resp.json() if isinstance(m, dict)]
        except Exception as e:
            logger.warning(f"Could not list Ollama models: {e}")
            return
        if model not in available:
            raise ValueError(
                f"Ollama model '{model}' not found. Please run `ollama pull {model}` to download it."
            )

    def run(self) -> "Algorithm":
        # 1. Initialize results container
        self.results = {}

        # 2. Validate input
        self._validate_input()

        # 3. Resolve file path
        input_files = self._job_details.files.files[0].input_files
        file_path = Path(input_files[0])
        if not file_path.exists():
            file_path = Path.cwd() / file_path

        # 4. Load dataset (JSON or Python script)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            module_globals = runpy.run_path(str(file_path))
            data = next(
                (v for v in module_globals.values() if isinstance(v, (list, dict))),
                None
            )
            if data is None:
                raise ValueError(f"No list or dict found in {file_path}")

        # 5. Build raw text list
        texts: list[str] = []
        if isinstance(data, list):
            for entry in data:
                text = entry.get("text") or entry.get("content") or str(entry)
                if text:
                    texts.append(text)
        else:
            texts.append(str(data))

        # 6. Retrieve embedding parameters
        params = getattr(self._job_details, "parameters", {}) or {}
        embed_model = params.get("embed_model", "nomic-embed-text")
        base_url = params.get("base_url", "http://localhost:11434")

        # 7. Ensure embedding model is available
        self._ensure_model_available(embed_model, base_url)

        # 8. Compute embeddings
        embeddings = OllamaEmbeddings(model=embed_model, base_url=base_url)
        vectors = embeddings.embed_documents(texts)

        # 9. Store embeddings
        self.results = {"embeddings": vectors}
        return self

    def save_result(self, path: Path) -> None:
        result_path = path / "result.json"
        with open(result_path, "w", encoding="utf-8") as f:
            try:
                json.dump(self.results, f, indent=2)
            except Exception as e:
                logger.exception(f"Error saving data: {e}")
