"""Fund prospectus retrieval over a local FAISS index.

Embeddings use feature hashing (unigrams + bigrams hashed with MD5 into a
fixed-width vector) rather than a hosted embedding model. That keeps retrieval
fully offline, private and reproducible: the same query returns the same funds
on every machine, which the tests rely on. Rebuild the index with
``python setup_rag.py`` after editing ``data/fund_corpus.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from itertools import pairwise

import numpy as np

from app.engine import DATA_DIR

EMBEDDER = "hashing-v1"
DIM = 512
INDEX_PATH = os.path.join(DATA_DIR, "faiss_index.bin")
META_PATH = os.path.join(DATA_DIR, "fund_metadata.json")
CORPUS_PATH = os.path.join(DATA_DIR, "fund_corpus.json")

_STOPWORDS = frozenset(
    "a an and are as at be by for from in into is it its of on or such than that the their to with "
    "when which while who will".split()
)
VOLATILITY_RANK = {"none": 0, "low": 1, "low_medium": 2, "medium": 3, "high": 4}
# Highest fund volatility each risk profile may be offered.
MAX_VOLATILITY_FOR = {"conservative": "low_medium", "moderate": "medium", "aggressive": "high"}


def _tokens(text: str) -> list[str]:
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS]
    return words + [f"{a}_{b}" for a, b in pairwise(words)]


def embed(text: str) -> np.ndarray:
    vec = np.zeros(DIM, dtype=np.float32)
    for tok in _tokens(text):
        digest = hashlib.md5(tok.encode()).digest()
        idx = int.from_bytes(digest[:4], "little") % DIM
        sign = 1.0 if digest[4] & 1 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec))
    return vec / norm if norm else vec


def document_text(fund: dict) -> str:
    return (
        f"{fund['ticker']} {fund['name']}. Asset class {fund['asset_class'].replace('_', ' ')}. "
        f"{fund['objective']} Risks: {fund['risk_disclosure']}"
    )


def build_index(corpus: list[dict]) -> tuple[object, dict]:
    import faiss

    vectors = np.stack([embed(document_text(f)) for f in corpus]).astype(np.float32)
    index = faiss.IndexFlatIP(DIM)  # inner product on unit vectors = cosine similarity
    index.add(vectors)
    meta = {"embedder": EMBEDDER, "dim": DIM, "funds": corpus}
    return index, meta


@lru_cache(maxsize=1)
def _load() -> tuple[object, dict]:
    import faiss

    if not (os.path.exists(INDEX_PATH) and os.path.exists(META_PATH)):
        raise FileNotFoundError("FAISS index missing. Run `python setup_rag.py` to build it.")
    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)
    if meta.get("embedder") != EMBEDDER or meta.get("dim") != DIM:
        raise RuntimeError("FAISS index was built with a different embedder. Re-run `python setup_rag.py`.")
    return faiss.read_index(INDEX_PATH), meta


def search(query: str, *, risk_tolerance: str | None = None, k: int = 3,
           exclude: tuple[str, ...] = ()) -> list[dict]:
    """Return the top-k funds for ``query``, filtered to what the client's risk profile allows."""
    index, meta = _load()
    funds = meta["funds"]
    scores, ids = index.search(embed(query)[None, :], len(funds))
    ceiling = VOLATILITY_RANK[MAX_VOLATILITY_FOR.get(risk_tolerance or "aggressive", "high")]
    results = []
    for score, i in zip(scores[0], ids[0], strict=False):
        if i < 0:
            continue
        fund = funds[int(i)]
        if fund["ticker"] in exclude or VOLATILITY_RANK[fund["volatility"]] > ceiling:
            continue
        results.append({**fund, "score": round(float(score), 4)})
        if len(results) == k:
            break
    return results


def corpus_size() -> int:
    return len(_load()[1]["funds"])

