"""Hybrid retriever: dense vectors (ChromaDB + nomic-embed-text) fused with BM25 via reciprocal-rank fusion.

BM25 matters for this corpus: course codes ("CSL7650"), circular numbers and exact terms
("Open Elective") are poorly captured by dense embeddings alone.
"""
import math
import re
from collections import Counter
from functools import lru_cache

import chromadb
import ollama

from . import config

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("""a an the of to in for on and or is are was were be by with as at from that this it its
what which who whom how many much do does i my me we our you your can should will would there their""".split())


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tfs = [Counter(tokenize(d)) for d in docs]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avgdl = sum(self.lens) / max(len(self.lens), 1)
        df = Counter(t for tf in self.tfs for t in tf)
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def top(self, query: str, k: int) -> list[int]:
        q = [t for t in tokenize(query) if t in self.idf]
        scores = []
        for i, tf in enumerate(self.tfs):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.lens[i] / self.avgdl))
            if s:
                scores.append((s, i))
        return [i for _, i in sorted(scores, reverse=True)[:k]]


class HybridRetriever:
    def __init__(self):
        client = chromadb.PersistentClient(path=str(config.INDEX_DIR / "chroma"))
        self.col = client.get_collection(config.COLLECTION)
        data = self.col.get(include=["documents", "metadatas"])
        self.ids, self.docs, self.metas = data["ids"], data["documents"], data["metadatas"]
        self.pos = {cid: i for i, cid in enumerate(self.ids)}
        # Index the file name too so "examination guidelines" can hit the right document
        self.bm25 = BM25([f"{m['source']} {d}" for d, m in zip(self.docs, self.metas)])

    def search(self, query: str | list[str], k: int = config.TOP_K, category: str | None = None) -> list[dict]:
        """Hybrid search; several queries (e.g. the agent's rewrite and the student's original question)
        are fused into one ranking."""
        queries = [q for q in dict.fromkeys([query] if isinstance(query, str) else query) if q.strip()]
        vecs = ollama.embed(model=config.EMBED_MODEL, input=["search_query: " + q for q in queries])["embeddings"]
        where = {"category": category} if category else None
        fused = Counter()
        for q, qvec in zip(queries, vecs):
            dense = self.col.query(query_embeddings=[qvec], n_results=config.CANDIDATES, where=where)["ids"][0]
            sparse = [self.ids[i] for i in self.bm25.top(q, config.CANDIDATES * 2)
                      if not category or self.metas[i]["category"] == category][:config.CANDIDATES]
            # BM25 gets half weight: it rescues exact codes/terms, but on this OCR-heavy corpus dense ranks are
            # more reliable (BM25 at full weight pushed the right circular out of the top-k for 2/14 policy questions).
            for weight, ranking in ((1.0, dense), (config.BM25_WEIGHT, sparse)):
                for rank, cid in enumerate(ranking):
                    fused[cid] += weight / (60 + rank)
        out = []
        for cid, score in fused.most_common(k):
            i = self.pos[cid]
            out.append(dict(source=self.metas[i]["source"], page=self.metas[i]["page"],
                            category=self.metas[i]["category"], text=self.docs[i], score=round(score, 4)))
        return out


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    return HybridRetriever()
