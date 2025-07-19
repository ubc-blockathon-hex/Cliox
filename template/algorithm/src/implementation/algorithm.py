import os, sys
import json, csv
from logging import getLogger
from pathlib import Path
from typing import Any, Optional, TypeVar
import pandas as pd
import requests
from oceanprotocol_job_details.ocean import JobDetails
from langchain_ollama import OllamaEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

T = TypeVar("T")
logger = getLogger(__name__)

class Algorithm:
    def __init__(self, job_details: JobDetails):
        logger.info("Initializing Algorithm")
        logger.info(f"Version tag: {os.getenv('VERSION_TAG', 'unknown')}")
        self._job_details = job_details
        logger.info(f"Job details: {self._job_details}")
        self.results: Optional[Any] = None

    def _validate_input(self) -> None:
        logger.info("Validating input files")
        if not self._job_details.files:
            logger.warning("No files found")
            raise ValueError("No files found")
        logger.info("Input validation passed")

    def _ensure_model_available(self, model: str, base_url: str) -> None:
        logger.info(f"Checking available model tags at {base_url}")
        resp = requests.get(f"{base_url}/api/tags")
        resp.raise_for_status()
        tags = resp.json().get("models", [])
        full_tags = [t.get("model") for t in tags if isinstance(t, dict)]
        logger.info(f"Available models before pull: {full_tags}")

        if any(tag == model or tag.startswith(f"{model}:") for tag in full_tags):
            matched = next(tag for tag in full_tags if tag == model or tag.startswith(f"{model}:"))
            logger.info(f"Model '{model}' already available as '{matched}'")
            return

        logger.info(f"Model '{model}' not found; pulling now…")
        pull_resp = requests.post(
            f"{base_url}/api/pull",
            json={"model": model, "stream": True},
            stream=True
        )
        pull_resp.raise_for_status()

        for raw in pull_resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore")
            try:
                msg = json.loads(line)
                status = msg.get("status") or msg.get("msg") or msg
            except:
                status = line
            logger.info(f"Pull progress: {status}")
            if isinstance(msg, dict) and msg.get("status") == "success":
                logger.info(f"Model '{model}' pulled successfully")
                break

        # final check
        resp2 = requests.get(f"{base_url}/api/tags")
        resp2.raise_for_status()
        tags2 = resp2.json().get("models", [])
        full_tags2 = [t.get("model") for t in tags2 if isinstance(t, dict)]
        if not any(tag == model or tag.startswith(f"{model}:") for tag in full_tags2):
            logger.error(f"Model '{model}' failed to download")
            raise RuntimeError(f"Failed to pull Ollama model '{model}'")
        logger.info(f"Model '{model}' is now available")

    def run(self) -> "Algorithm":
        logger.info("Starting algorithm run")
        self.results = {}
        self._validate_input()

        input_files = self._job_details.files.files[0].input_files
        file_path = Path(input_files[0])
        logger.info(f"Input file path: {file_path}")
        if not file_path.exists():
            file_path = Path.cwd() / file_path
        ext = file_path.suffix.lower()

        if not ext:
            # try JSON
            try:
                with open(file_path) as f:
                    data = json.load(f)
                ext = '.json'
            except json.JSONDecodeError:
                # fallback to CSV?
                try:
                    with open(file_path) as f:
                        _ = list(csv.reader(f))
                    ext = '.csv'
                except Exception:
                    raise ValueError(
                        "Could not auto-detect file type; please supply a .json or .csv file."
                    )
        if ext == ".json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif ext == ".csv":
            df = pd.read_csv(file_path)
            data = df.to_dict(orient="records")
        else:
            raise ValueError(f"Unsupported file type: '{ext}' – only .csv or .json allowed")

        if isinstance(data, list):
            texts = [
                json.dumps(record, ensure_ascii=False)
                for record in data
            ]
        elif isinstance(data, dict):
            texts = [json.dumps(data, ensure_ascii=False)]
        else:
            raise ValueError("Loaded data must be a list or dict")

        logger.info(f"Prepared {len(texts)} documents for embedding")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=2048,
            chunk_overlap=200
        )
        all_chunks: list[str] = []
        for t in texts:
            all_chunks.extend(splitter.split_text(t))
        texts = all_chunks
        logger.info(f"After chunking: {len(texts)} pieces to embed")

        params = getattr(self._job_details, "parameters", {}) or {}
        embed_model = params.get("embed_model", "nomic-embed-text")
        base_url   = params.get("base_url") or os.getenv("BASE_URL", "http://localhost:11434")
        logger.info(f"Embedding model={embed_model}, base_url={base_url}")

        self._ensure_model_available(embed_model, base_url)

        embeddings_client = OllamaEmbeddings(model=embed_model, base_url=base_url)
        vectors = embeddings_client.embed_documents(texts)

        self.results = {
            "texts": texts,
            "embeddings": vectors
        }
        logger.info("Algorithm run completed")
        return self

    def save_result(self, path: Path) -> None:
        result_path = path / "result.json"
        logger.info(f"Saving result to {result_path}")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        logger.info("Result saved successfully")
        logger.info("Triggering self-destruct; stopping container…")
        sys.exit(0)
