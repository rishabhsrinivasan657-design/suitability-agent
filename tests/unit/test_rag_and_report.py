"""Fund retrieval and PDF report generation."""

import json
import subprocess
import sys

import numpy as np
import pytest

from app import engine, rag
from app.report import build_pdf


class TestRag:
    def test_embedding_is_stable_across_processes(self):
        """Regression: the old fallback seeded embeddings with hash(), which changes every process."""
        code = "from app.rag import embed; print(embed('short term treasury cash')[:8].round(6).tolist())"
        runs = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                               cwd=engine.BASE_DIR).stdout.strip().splitlines()[-1] for _ in range(2)}
        assert len(runs) == 1
        assert json.loads(runs.pop()) == pytest.approx(rag.embed("short term treasury cash")[:8].tolist(), abs=1e-5)

    def test_embedding_unit_norm(self):
        assert float(np.linalg.norm(rag.embed("diversified bond income"))) == pytest.approx(1.0)

    def test_index_matches_corpus(self):
        with open(rag.CORPUS_PATH, encoding="utf-8") as f:
            corpus = json.load(f)
        assert rag.corpus_size() == len(corpus) == 24

    @pytest.mark.parametrize(("query", "risk", "expected_classes"), [
        ("short-term treasury cash liquidity home down payment capital preservation", "conservative", {"cash", "bond_fund"}),
        ("core fixed income bonds stability recession hedge", "moderate", {"bond_fund"}),
        ("international diversification reduce single-position concentration diversified equity", "moderate", {"equity_fund"}),
    ])
    def test_queries_retrieve_matching_asset_classes(self, query, risk, expected_classes):
        top = rag.search(query, risk_tolerance=risk, k=3)
        assert len(top) == 3
        assert top[0]["asset_class"] in expected_classes
        assert top[0]["score"] >= top[1]["score"] >= top[2]["score"]

    def test_risk_filter_excludes_volatile_funds_for_conservative_clients(self):
        results = rag.search("speculative bitcoin crypto aggressive technology growth", risk_tolerance="conservative", k=10)
        allowed = rag.VOLATILITY_RANK[rag.MAX_VOLATILITY_FOR["conservative"]]
        assert results and all(rag.VOLATILITY_RANK[f["volatility"]] <= allowed for f in results)
        assert "IBIT" in {f["ticker"] for f in rag.search("bitcoin crypto", risk_tolerance="aggressive", k=3)}


@pytest.fixture(scope="module")
def offline_reviews():
    from app.pipeline import run_review

    return {cid: run_review(cid) for cid in ("C002", "C029", "C038", "C026")}


class TestReport:
    def test_pdf_builds_for_varied_clients(self, offline_reviews):
        for cid, result in offline_reviews.items():
            pdf = build_pdf(result.state, result.trace, result.mode)
            assert pdf.startswith(b"%PDF") and len(pdf) > 5_000, cid

    def test_pdf_handles_unicode_names(self, offline_reviews):
        result = offline_reviews["C002"]
        state = {**result.state, "client_profile": {**result.state["client_profile"], "name": "Zoë Ångström — 李"}}
        assert build_pdf(state).startswith(b"%PDF")
