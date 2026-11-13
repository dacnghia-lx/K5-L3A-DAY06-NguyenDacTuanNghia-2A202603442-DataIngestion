"""Verify every evidence quote against the normalized corpus (no retrieval).

For each question:
- the evidence must occur (whitespace-insensitive) in gold_source_id;
- gold_page is set to the page of gold_source_id that contains it;
- accepted_gold lists EVERY page in the corpus that contains the same
  evidence (e.g. topic 'compound' repeats 'try'; 3.11 and 3.13 often share
  text). If the question has a python_version filter, only pages of that
  version are accepted, because the user asked about that version.

Run from starter/:  python -m scripts.verify_benchmark
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.corpus import BENCHMARK_PATH, load_corpus  # noqa: E402
from src.ingestion import flatten  # noqa: E402


def main() -> None:
    bench = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    pages = load_corpus()
    flat = [(p, flatten(p.text)) for p in pages]
    problems = []
    for q in bench["questions"]:
        ev = flatten(q["evidence_quote"])
        version = (q.get("filter") or {}).get("python_version")
        found = [p for p, f in flat if ev in f]
        accepted = [p for p in found if version is None or p.metadata["python_version"] == version]
        primary = [p for p in accepted if p.document_id == q["gold_source_id"]]
        if not primary:
            problems.append(f"{q['id']}: evidence not found in {q['gold_source_id']}")
            continue
        q["gold_page"] = primary[0].page
        q["gold_page_id"] = primary[0].metadata["page_id"]
        q["accepted_gold"] = sorted(p.metadata["page_id"] for p in accepted)
        q["evidence_found_in_other_version"] = sorted(
            p.metadata["page_id"] for p in found if p not in accepted)
        print(f"{q['id']} [{q['split']}] ok -> {q['gold_page_id']} | accepted={len(accepted)}"
              f" | excluded_by_filter={len(q['evidence_found_in_other_version'])}")
    if problems:
        print("\n".join(problems))
        sys.exit(1)
    splits = {s: sum(q["split"] == s for q in bench["questions"]) for s in ("dev", "test")}
    filt = {s: sum(q["split"] == s and bool(q.get("filter")) for q in bench["questions"]) for s in ("dev", "test")}
    print(f"OK: {len(bench['questions'])} questions, split={splits}, with filter={filt}")
    BENCHMARK_PATH.write_text(json.dumps(bench, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
