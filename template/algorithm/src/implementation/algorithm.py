import os
from logging import getLogger
from pathlib import Path
from typing import Any, Optional, TypeVar
from oceanprotocol_job_details.ocean import JobDetails

import json
import runpy
import requests
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.schema import Document

T = TypeVar("T")
logger = getLogger(__name__)

class Algorithm:
    def __init__(self, job_details: JobDetails):
        logger.info("Initializing Algorithm")
        self._job_details = job_details
        self.results: Optional[Any] = None

    def _validate_input(self) -> None:
        logger.info("Validating input files")
        if not self._job_details.files:
            logger.warning("No files found")
            raise ValueError("No files found")
        logger.info("Input validation passed")

    def _ensure_model_available(self, model: str, base_url: str) -> None:
        """
        Ensure the Ollama model/tag is present; if not, pull it and log progress, handling version suffixes.
        """
        logger.info(f"Checking available model tags at {base_url}")
        # list all tags
        resp = requests.get(f"{base_url}/api/tags")
        resp.raise_for_status()
        tags = resp.json().get("models", [])
        full_tags = [t.get("model") for t in tags if isinstance(t, dict)]
        logger.info(f"Available models before pull (full tags): {full_tags}")
        # match exact or prefix for version suffix
        if any(tag == model or tag.startswith(f"{model}:") for tag in full_tags):
            matched = next(tag for tag in full_tags if tag == model or tag.startswith(f"{model}:"))
            logger.info(f"Model '{model}' is already available as '{matched}'")
            return

        # not present: pull with streaming
        logger.info(f"Model '{model}' not found; starting pull")
        pull_resp = requests.post(
            f"{base_url}/api/pull",
            json={"model": model, "stream": True},
            stream=True
        )
        pull_resp.raise_for_status()

        for raw_line in pull_resp.iter_lines():
            if not raw_line:
                continue
            try:
                line = raw_line.decode("utf-8")
            except Exception:
                line = str(raw_line)
            try:
                msg = json.loads(line)
                status = msg.get("status") or msg.get("msg") or msg
            except Exception:
                status = line
            logger.info(f"Pull progress: {status}")
            if isinstance(msg, dict) and msg.get("status") == "success":
                logger.info(f"Model '{model}' pulled successfully")
                break

        # verify after pull
        resp2 = requests.get(f"{base_url}/api/tags")
        resp2.raise_for_status()
        tags2 = resp2.json().get("models", [])
        full_tags2 = [t.get("model") for t in tags2 if isinstance(t, dict)]
        logger.info(f"Available models after pull (full tags): {full_tags2}")
        if not any(tag == model or tag.startswith(f"{model}:") for tag in full_tags2):
            logger.error(f"Model '{model}' failed to download")
            raise RuntimeError(f"Failed to pull Ollama model '{model}'")
        matched2 = next(tag for tag in full_tags2 if tag == model or tag.startswith(f"{model}:"))
        logger.info(f"Model '{model}' is now available as '{matched2}'")

    def run(self) -> "Algorithm":
        logger.info("Starting algorithm run")
        self.results = {}

        self._validate_input()

        # Resolve file path
        input_files = self._job_details.files.files[0].input_files
        file_path = Path(input_files[0])
        logger.info(f"Initial file path: {file_path}")
        if not file_path.exists():
            file_path = Path.cwd() / file_path
            logger.info(f"Updated file path: {file_path}")

        # Load dataset (JSON or Python script)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Loaded data as JSON")
        except json.JSONDecodeError:
            logger.info("Failed to parse JSON; loading as Python script")
            module_globals = runpy.run_path(str(file_path))
            data = next(
                (v for v in module_globals.values() if isinstance(v, (list, dict))),
                None
            )
            if data is None:
                logger.error(f"No list or dict found in {file_path}")
                raise ValueError(f"No list or dict found in {file_path}")
            logger.info("Loaded data from Python script")

        # Build raw text list
        texts: list[str] = []
        if isinstance(data, list):
            for entry in data:
                text = entry.get("text") or entry.get("content") or str(entry)
                if text:
                    texts.append(text)
            logger.info(f"Built texts list with {len(texts)} items from list data")
        else:
            texts.append(str(data))
            logger.info("Built texts list with 1 item from dict data")

        # Retrieve embedding parameters and base_url from environment or parameters
        params = getattr(self._job_details, "parameters", {}) or {}
        embed_model = params.get("embed_model", "nomic-embed-text")
        base_url = params.get("base_url") or os.getenv("BASE_URL", "http://ollama:11434")
        logger.info(f"Embedding parameters: model={embed_model}, base_url={base_url}")

        self._ensure_model_available(embed_model, base_url)

        # Generate embeddings
        logger.info("Creating embeddings instance")
        embeddings = OllamaEmbeddings(model=embed_model, base_url=base_url)
        logger.info("Embedding documents")
        vectors = embeddings.embed_documents(texts)
        logger.info("Embedding completed")

        self.results = {"embeddings": vectors}
        logger.info("Algorithm run completed")
        return self

    def save_result(self, path: Path) -> None:
        result_path = path / "result.json"
        logger.info(f"Saving result to {result_path}")
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2)
        logger.info("Result saved successfully")
