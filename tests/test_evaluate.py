import json

import pytest

from releaseguard import evaluate
from releaseguard.evaluate import load_dataset, render_markdown, run_eval, score_item, split_of


def test_split_is_deterministic_and_roughly_balanced():
    assert split_of("a@b") == split_of("a@b")
    splits = {split_of(f"owner@repo{i}") for i in range(40)}
    assert splits == {"dev", "test"}


def test_score_item_overlap():
    result = score_item([3, 4, 9], [3, 4, 5, 6])
    assert result["hit"] and result["precision"] == pytest.approx(2 / 3) and result["recall"] == 0.5


def test_score_item_no_prediction_or_no_overlap():
    assert score_item([], [1])["hit"] is False
    assert score_item([9], [1])["precision"] == 0.0


def test_sample_dataset_loads_and_splits_do_not_overlap():
    everything = load_dataset("sample", "all")
    dev = {i["id"] for i in load_dataset("sample", "dev")}
    test = {i["id"] for i in load_dataset("sample", "test")}
    assert everything and not (dev & test) and dev | test == {i["id"] for i in everything}
    assert all(i["gold_lines"] for i in everything)


def test_missing_dataset_raises():
    with pytest.raises(FileNotFoundError):
        load_dataset("no_such_file.jsonl")


def test_baseline_eval_on_sample_writes_files_with_synthetic_banner(tmp_path):
    results = run_eval("sample", split="all", out_dir=tmp_path, say=lambda _m: None)
    assert results[0]["summary"]["method"] == "baseline"
    assert results[0]["summary"]["n"] >= 1
    md = (tmp_path / "results_sample_all.md").read_text(encoding="utf-8")
    assert "SYNTHETIC SAMPLE" in md
    assert json.loads((tmp_path / "results_sample_all.json").read_text(encoding="utf-8"))


def test_llm_eval_requires_api_key(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        run_eval("sample", split="all", use_llm=True, out_dir=tmp_path, say=lambda _m: None)


def test_llm_method_counts_citation_validity_and_errors(monkeypatch):
    calls = {"n": 0}

    def fake(evidence):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("rate limited")
        return {
            "cited_lines": [{"line": 1, "text": "x"}], "unverified_citations": [{"line": 99}],
            "category": "other", "usage": {"prompt_tokens": 100, "completion_tokens": 10, "latency_s": 0.5},
        }

    monkeypatch.setattr(evaluate, "analyze_with_openai", fake)
    items = [{"id": f"i{n}", "repo": "r", "log": "a\nb", "gold_lines": [1]} for n in range(3)]
    out = evaluate.run_method(items, "llm", say=lambda _m: None)["summary"]
    assert out["errors"] == 1 and out["citation_validity"] == 0.5
    assert out["prompt_tokens"] == 200 and out["evidence_hit_rate"] == pytest.approx(0.667, abs=0.001)


def test_render_markdown_skips_llm_only_rows_for_baseline():
    md = render_markdown("d", "test", False, [{"summary": {"method": "baseline", "n": 2, "evidence_hit_rate": 0.5}}])
    assert "Evidence hit rate" in md and "Citation validity" not in md and "SYNTHETIC" not in md
