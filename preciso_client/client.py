from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from config import Settings


class PrecisoClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._loaded = False
        self._storage_instances = None
        self._global_config = None
        self._status_fn = None
        self._ingest_fn = None
        self._reingest_fn = None
        self._query_fn = None

    def get_status(self) -> dict[str, Any]:
        self._load()
        return asyncio.run(self._status_fn(self._storage_instances, self._global_config))

    def ingest_file(self, file_path: str) -> dict[str, Any]:
        self._load()
        return asyncio.run(self._ingest_fn(file_path, self._storage_instances, self._global_config))

    def reingest_file(self, file_path: str) -> dict[str, Any]:
        self._load()
        return asyncio.run(self._reingest_fn(file_path, self._storage_instances, self._global_config))

    def query_graph(self, query: str, mode: str) -> dict[str, Any]:
        self._load()
        return asyncio.run(self._query_fn(query, mode, self._storage_instances, self._global_config))

    def _load(self) -> None:
        if self._loaded:
            return

        repo_root = self.settings.preciso_repo_root
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        if str(repo_root / "mcp") not in sys.path:
            sys.path.insert(0, str(repo_root / "mcp"))

        parent_config = self._load_module(
            "preciso_parent_config",
            repo_root / "config.py",
        )
        sys.modules["config"] = parent_config
        from core.bootstrap import build_storage_instances, initialize_storage_instances
        from core.utils import BasicTokenizer

        ingest_module = self._load_module(
            "preciso_parent_ingest_from_file_tool",
            repo_root / "mcp" / "tools" / "ingest_from_file_tool.py",
        )
        query_module = self._load_module(
            "preciso_parent_query_tool",
            repo_root / "mcp" / "tools" / "query_tool.py",
        )
        status_module = self._load_module(
            "preciso_parent_status_tool",
            repo_root / "mcp" / "tools" / "status_tool.py",
        )

        tokenizer = BasicTokenizer()
        os.environ.setdefault("GRAPHRAG_EMBEDDING_PROVIDER", "fallback")
        self._global_config = parent_config.build_global_config(
            working_dir=str(repo_root / "GRAPH_IS_HERE"),
            tokenizer=tokenizer,
            embedding_func=parent_config.build_default_embedding_func(),
        )
        self._storage_instances = build_storage_instances(self._global_config)
        asyncio.run(initialize_storage_instances(self._storage_instances))
        self._status_fn = status_module.get_server_status
        self._ingest_fn = ingest_module.ingest_from_file
        self._reingest_fn = ingest_module.reingest_from_file
        self._query_fn = query_module.query_graph
        self._loaded = True

    @staticmethod
    def _load_module(module_name: str, file_path: Path):
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to load module from {file_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
