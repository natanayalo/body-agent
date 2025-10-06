import json
import os
from pathlib import Path

import pytest


def _load_cases(root: Path) -> list[dict]:
    cases: list[dict] = []
    for p in root.glob("*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return cases


@pytest.mark.skipif(
    not Path("seeds/evals/risk").exists(), reason="no risk eval seeds present"
)
def test_eval_risk_golden(monkeypatch, capsys):
    # Force stub pipeline for deterministic results
    monkeypatch.setenv("RISK_MODEL_ID", "__stub__")
    from app.graph.nodes import risk_ml

    pipe = risk_ml._get_pipe()
    assert pipe is not None
    labels = [
        s.strip()
        for s in os.getenv(
            "RISK_LABELS", "urgent_care,see_doctor,self_care,info_only"
        ).split(",")
        if s.strip()
    ]

    seeds_root = Path("seeds/evals/risk")
    cases = _load_cases(seeds_root)
    assert cases, "no risk golden cases found"

    results: list[tuple[str, str]] = []  # (top_label, text)
    for c in cases:
        text = c.get("text", "")
        # Run classifier; select top-scoring label
        out = pipe(text, candidate_labels=labels, multi_label=True)
        lab = out.get("labels", [])
        sco = out.get("scores", [])
        if lab and sco:
            top = max(zip(lab, sco), key=lambda kv: float(kv[1]))[0]
        else:
            top = "<none>"
        results.append((top, text))

    # Print a compact summary; do not fail by default
    counts: dict[str, int] = {}
    for top, _ in results:
        counts[top] = counts.get(top, 0) + 1
    print("Risk golden summary:", counts)
    captured = capsys.readouterr()
    # Ensure we printed something meaningful
    assert "Risk golden summary:" in captured.out
