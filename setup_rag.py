"""Build the FAISS fund-prospectus index from data/fund_corpus.json.

Usage:
    uv run python setup_rag.py
"""

import json

import faiss

from app.rag import CORPUS_PATH, INDEX_PATH, META_PATH, build_index


def main() -> None:
    with open(CORPUS_PATH, encoding="utf-8") as f:
        corpus = json.load(f)
    index, meta = build_index(corpus)
    faiss.write_index(index, INDEX_PATH)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    print(f"Indexed {index.ntotal} funds ({meta['embedder']}, dim {meta['dim']}) -> {INDEX_PATH}")


if __name__ == "__main__":
    main()
