from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Callable, Optional

from agent.schemas.memory import SemanticChunk

EmbedFn = Callable[[list[str]], list[list[float]]]


def hash_embedding(dim: int = 128) -> EmbedFn:
    """Deterministic text→vector for tests. Quality is low but reproducible."""
    def _fn(texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * dim
            for token in text.lower().split():
                h = hashlib.md5(token.encode("utf-8")).digest()
                for i, b in enumerate(h):
                    vec[i % dim] += (b / 255.0) - 0.5
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out
    return _fn


class SemanticMemory:
    """Chroma-backed vector store for distilled facts / episode summaries.

    Writes are expected to be batched (end-of-session or explicit distillation),
    not per turn. See blueprint §3.2.
    """

    name = "semantic"

    def __init__(
        self,
        persist_dir: str | Path,
        collection: str = "semantic_memory",
        embed_fn: Optional[EmbedFn] = None,
        ephemeral: bool = False,
    ):
        import chromadb  # type: ignore

        self.persist_dir = Path(persist_dir)
        if ephemeral:
            self.client = chromadb.EphemeralClient()
        else:
            self.persist_dir.mkdir(parents=True, exist_ok=True)
            self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection_name = collection
        self.embed_fn: EmbedFn = embed_fn or hash_embedding()
        self.collection = self.client.get_or_create_collection(name=collection)

    # ---------- protocol ----------

    def health(self) -> bool:
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False

    def write(self, obj: SemanticChunk, **_: Any) -> SemanticChunk:
        return self._write_many([obj])[0]

    def write_many(self, chunks: list[SemanticChunk]) -> list[SemanticChunk]:
        return self._write_many(chunks)

    def _write_many(self, chunks: list[SemanticChunk]) -> list[SemanticChunk]:
        if not chunks:
            return []
        texts = [c.text for c in chunks]
        embeddings = self.embed_fn(texts)
        ids = [c.chunk_id for c in chunks]
        metadatas = []
        for c in chunks:
            md: dict[str, Any] = {
                "source_id": c.source_id,
                "source_kind": c.source_kind,
                "ts": c.ts.isoformat(),
            }
            if c.user_id:
                md["user_id"] = c.user_id
            if c.tags:
                md["tags"] = ",".join(c.tags)
            metadatas.append(md)
        self.collection.upsert(
            ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas
        )
        return chunks

    def read(self, chunk_id: str, **_: Any) -> Optional[SemanticChunk]:
        res = self.collection.get(ids=[chunk_id])
        if not res or not res.get("ids") or not res["ids"]:
            return None
        return _reconstruct(res, 0)

    def search(
        self,
        query: str,
        k: int = 5,
        user_id: Optional[str] = None,
        kind: Optional[str] = None,
        **_: Any,
    ) -> list[SemanticChunk]:
        emb = self.embed_fn([query])[0]
        where: dict[str, Any] = {}
        if user_id and kind:
            where = {
                "$and": [
                    {"user_id": user_id},
                    {"source_kind": kind},
                ]
            }
        elif user_id:
            where = {"user_id": user_id}
        elif kind:
            where = {"source_kind": kind}

        result = self.collection.query(
            query_embeddings=[emb],
            n_results=max(1, k),
            where=where or None,
            include=["documents", "metadatas", "distances"],
        )
        out: list[SemanticChunk] = []
        if not result or not result.get("ids"):
            return out
        for i in range(len(result["ids"][0])):
            chunk = _reconstruct_query(result, i)
            if chunk is None:
                continue
            distance = result["distances"][0][i] if "distances" in result else 0.0
            chunk.score = max(0.0, 1.0 - distance)
            out.append(chunk)
        return out

    def delete(self, chunk_id: Optional[str] = None, user_id: Optional[str] = None, **_: Any) -> bool:
        if chunk_id:
            self.collection.delete(ids=[chunk_id])
            return True
        if user_id:
            self.collection.delete(where={"user_id": user_id})
            return True
        return False

    def count(self) -> int:
        return self.collection.count()


def _reconstruct(res: dict[str, Any], i: int) -> SemanticChunk:
    md = res.get("metadatas", [{}])[i] or {}
    return SemanticChunk(
        chunk_id=res["ids"][i],
        user_id=md.get("user_id"),
        source_id=md.get("source_id", res["ids"][i]),
        source_kind=md.get("source_kind", "fact"),
        text=res["documents"][i],
        tags=md.get("tags", "").split(",") if md.get("tags") else [],
    )


def _reconstruct_query(res: dict[str, Any], i: int) -> Optional[SemanticChunk]:
    try:
        ids = res["ids"][0]
        docs = res.get("documents", [[]])[0]
        mds = res.get("metadatas", [[]])[0] or []
        md = mds[i] if i < len(mds) else {}
        md = md or {}
        return SemanticChunk(
            chunk_id=ids[i],
            user_id=md.get("user_id"),
            source_id=md.get("source_id", ids[i]),
            source_kind=md.get("source_kind", "fact"),
            text=docs[i],
            tags=md.get("tags", "").split(",") if md.get("tags") else [],
        )
    except (IndexError, KeyError):
        return None
