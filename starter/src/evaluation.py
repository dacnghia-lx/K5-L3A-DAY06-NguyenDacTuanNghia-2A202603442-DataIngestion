"""Evaluate retrieved evidence and keep per-query traces.

Automatic hit (both conditions, per GUIDE.md):
  1. the chunk's page_id is one of the question's ``accepted_gold`` pages, and
  2. the chunk text contains the FULL evidence quote (whitespace-insensitive).
Hit@1 = top-1 is a hit; Evidence Hit@3 = at least one hit in top-3.
Diagnostic only: ``gold_page_in_top3`` (right page, evidence maybe split).
Human labels (coherence, grounding, metadata audit) are NOT inferred here.
"""
from __future__ import annotations

from typing import Any

from .ingestion import flatten


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = set(question["accepted_gold"])
    evidence = flatten(question["evidence_quote"])
    flt = question.get("filter") or {}
    judged = []
    for h in hits:
        meta = h["metadata"]
        on_gold_page = meta.get("page_id") in accepted
        has_evidence = evidence in flatten(h["text"])
        judged.append({
            **h,
            "on_gold_page": on_gold_page,
            "contains_full_evidence": has_evidence,
            "hit": on_gold_page and has_evidence,
            "respects_filter": all(str(meta.get(k)) == str(v) for k, v in flt.items()) if flt else None,
        })
    hit_ranks = [j["rank"] for j in judged if j["hit"]]
    page_ranks = [j["rank"] for j in judged if j["on_gold_page"]]
    return {
        "id": question["id"],
        "split": question["split"],
        "type": question.get("type"),
        "question": question["question"],
        "filter": question.get("filter"),
        "expected_answer": question["expected_answer"],
        "gold_page_id": question["gold_page_id"],
        "accepted_gold": question["accepted_gold"],
        "evidence_quote": question["evidence_quote"],
        "hit_at_1": bool(judged and judged[0]["hit"]),
        "hit_at_3": bool(hit_ranks),
        "first_hit_rank": hit_ranks[0] if hit_ranks else None,
        "gold_page_in_top3": bool(page_ranks),
        "evidence_split_suspected": bool(page_ranks) and not hit_ranks,
        "filter_respected_top3": (all(j["respects_filter"] for j in judged) if flt else None),
        "top3": judged,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for split in ("dev", "test", "all"):
        rows = [t for t in traces if split == "all" or t["split"] == split]
        flt = [t for t in rows if t["filter"]]
        out[split] = {
            "n": len(rows),
            "hit1": sum(t["hit_at_1"] for t in rows),
            "hit3": sum(t["hit_at_3"] for t in rows),
            "gold_page_in_top3": sum(t["gold_page_in_top3"] for t in rows),
            "evidence_split_suspected": [t["id"] for t in rows if t["evidence_split_suspected"]],
            "filter_questions": len(flt),
            "filter_questions_hit3": sum(t["hit_at_3"] for t in flt),
            "misses_at_3": [t["id"] for t in rows if not t["hit_at_3"]],
        }
    return out
