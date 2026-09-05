from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import jieba
import numpy as np

from .config import settings


EMBED_DIM = 256


def _tokenize(text: str) -> list[str]:
    text = text.lower()
    tokens = [t.strip() for t in jieba.cut(text) if t.strip()]
    if not tokens:
        tokens = list(text)
    return tokens


def _hash_embedding(text: str) -> np.ndarray:
    vec = np.zeros(EMBED_DIM, dtype=np.float32)
    for token in _tokenize(text):
        digest = hashlib.md5(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % EMBED_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


class KnowledgeRetriever:
    def __init__(self, knowledge_dir: Path | None = None) -> None:
        self.knowledge_dir = knowledge_dir or settings.knowledge_dir
        self.chunks: list[dict[str, Any]] = []
        self._doc_tokens: list[list[str]] = []
        self._doc_embeddings: np.ndarray | None = None
        self._df: Counter[str] = Counter()
        self._avg_doc_len = 0.0
        self._embedding_fn = None
        self._embedding_mode = settings.embedding_mode
        self.load()

    def load(self) -> None:
        self.chunks = []
        indicator_file = self.knowledge_dir / "indicators.json"
        schema_file = self.knowledge_dir / "schema.json"

        if indicator_file.exists():
            payload = json.loads(indicator_file.read_text(encoding="utf-8"))
            for item in payload.get("indicators", []):
                text = (
                    f"指标：{item.get('name', '')}；同义词：{item.get('synonyms', [])}；"
                    f"公式：{item.get('formula', '')}；说明：{item.get('description', '')}"
                )
                self.chunks.append(
                    {
                        "id": item.get("id", item.get("name")),
                        "kind": "dimension",
                        "name": item.get("name", ""),
                        "synonyms": item.get("synonyms", []),
                        "formula": item.get("formula", ""),
                        "text": text,
                        "labels": item.get("labels", []),
                    }
                )

        if schema_file.exists():
            payload = json.loads(schema_file.read_text(encoding="utf-8"))
            for item in payload.get("tables", []):
                text = (
                    f"表：{item.get('table_name', '')}；说明：{item.get('comment', '')}；"
                    f"字段：{json.dumps(item.get('fields', []), ensure_ascii=False)}；"
                    f"关系：{json.dumps(item.get('relations', []), ensure_ascii=False)}；"
                    f"示例SQL：{item.get('example_sql', '')}"
                )
                self.chunks.append(
                    {
                        "id": item.get("table_name", ""),
                        "kind": "schema",
                        "name": item.get("table_name", ""),
                        "text": text,
                        "labels": item.get("labels", []),
                    }
                )

        self._prepare_index()
        self._prepare_embedding_fn()

    def _prepare_index(self) -> None:
        self._doc_tokens = [_tokenize(chunk["text"]) for chunk in self.chunks]
        self._df = Counter()
        for tokens in self._doc_tokens:
            for term in set(tokens):
                self._df[term] += 1
        self._avg_doc_len = np.mean([len(t) for t in self._doc_tokens]) if self._doc_tokens else 1.0
        self._doc_embeddings = np.stack([_hash_embedding(chunk["text"]) for chunk in self.chunks]) if self.chunks else np.empty((0, EMBED_DIM), dtype=np.float32)

    def _prepare_embedding_fn(self) -> None:
        use_fastembed = self._embedding_mode in {"auto", "fastembed"}
        if use_fastembed:
            try:
                from fastembed import TextEmbedding

                self._embedding_fn = TextEmbedding(model_name=settings.embedding_model)
                self._doc_embeddings = np.array(
                    list(self._embedding_fn.embed([chunk["text"] for chunk in self.chunks])),
                    dtype=np.float32,
                )
            except Exception:
                self._embedding_fn = None

    def _query_embedding(self, query: str) -> np.ndarray:
        if self._embedding_fn is not None:
            try:
                return np.array(list(self._embedding_fn.embed([query]))[0], dtype=np.float32)
            except Exception:
                pass
        return _hash_embedding(query)

    @staticmethod
    def _bm25_score(query_tokens: list[str], doc_tokens: list[str], df: Counter[str], avg_doc_len: float, n_docs: int) -> float:
        if not doc_tokens:
            return 0.0
        k1 = 1.5
        b = 0.75
        doc_len = len(doc_tokens)
        tf = Counter(doc_tokens)
        score = 0.0
        for term in query_tokens:
            if term not in tf:
                continue
            idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            denom = tf[term] + k1 * (1 - b + b * doc_len / avg_doc_len)
            score += idf * (tf[term] * (k1 + 1)) / denom
        return score

    def retrieve(self, query: str, top_k: int = 4) -> list[dict[str, Any]]:
        if not self.chunks:
            return []
        query_tokens = _tokenize(query)
        keyword_scores = np.array(
            [
                self._bm25_score(query_tokens, tokens, self._df, self._avg_doc_len, len(self.chunks))
                for tokens in self._doc_tokens
            ],
            dtype=np.float32,
        )
        query_vec = self._query_embedding(query)
        vector_scores = np.dot(self._doc_embeddings, query_vec)

        def _normalize(arr: np.ndarray) -> np.ndarray:
            if arr.size == 0 or float(np.max(np.abs(arr))) == 0:
                return arr
            return arr / float(np.max(np.abs(arr)))

        keyword_norm = _normalize(keyword_scores)
        vector_norm = _normalize(vector_scores)
        combined = 0.55 * keyword_norm + 0.45 * vector_norm
        ranked_idx = np.argsort(combined)[::-1][:top_k]
        results: list[dict[str, Any]] = []
        for idx in ranked_idx:
            chunk = dict(self.chunks[int(idx)])
            chunk["score"] = float(combined[int(idx)])
            results.append(chunk)
        return results

    def indicator_options(self, query: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        if query:
            matches = self.retrieve(query, top_k=limit)
            options = []
            for item in matches:
                if item.get("kind") == "dimension":
                    options.append({"key": item.get("name"), "label": item.get("name")})
            if options:
                return options[:limit]
        options = []
        for chunk in self.chunks:
            if chunk.get("kind") == "dimension":
                options.append({"key": chunk.get("name"), "label": chunk.get("name")})
        return options[:limit]


knowledge_retriever = KnowledgeRetriever()

