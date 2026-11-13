"""Audit helpers run AFTER src.run:

1. metadata_audit.csv - every test top-3 record of A/B/C is cross-checked
   against the raw source: the page_id exists, document_id/source/page/
   python_version/section agree with the page loaded from that source file,
   and the chunk text (minus B's context line) really occurs in that page.
   The script output was then read by hand (notes column in the report).
2. filter_compliance.json - per strategy, number of filter questions whose
   whole top-3 respects the requested python_version (dev and test).
3. reingest_change_demo.json - re-ingest of a CHANGED corpus into a scratch
   collection: one page edited, one page removed -> only affected chunks are
   re-embedded and obsolete chunks deleted; then the original is restored.

Run from starter/:  python -m scripts.audit
"""
from __future__ import annotations

import copy
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.chunking import by_paragraph  # noqa: E402
from src.corpus import RESULTS_DIR, load_corpus  # noqa: E402
from src.embeddings import WordLlamaEmbedder  # noqa: E402
from src.ingestion import flatten  # noqa: E402
from src.run import CHROMA_DIR, STRATEGIES  # noqa: E402
from src.store import ChromaStore  # noqa: E402


def strip_context(text: str, meta: dict) -> str:
    if meta.get("heading_prefixed") and text.startswith("[") and "\n" in text:
        return text.split("\n", 1)[1]
    return text


def main() -> None:
    pages = {p.metadata["page_id"]: p for p in load_corpus()}
    audit_dir = RESULTS_DIR / "audit"
    rows, compliance = [], {}
    for key in STRATEGIES:
        traces = [json.loads(l) for l in (RESULTS_DIR / "traces" / f"{key}.jsonl").open(encoding="utf-8")]
        comp = {}
        for split in ("dev", "test"):
            fq = [t for t in traces if t["split"] == split and t["filter"]]
            comp[split] = {"respected": sum(bool(t["filter_respected_top3"]) for t in fq), "n": len(fq),
                           "ids": [t["id"] for t in fq]}
        compliance[key] = comp
        for t in traces:
            if t["split"] != "test":
                continue
            for h in t["top3"]:
                m = h["metadata"]
                page = pages.get(m.get("page_id"))
                checks = {
                    "page_exists": page is not None,
                    "document_id_ok": page is not None and m.get("document_id") == page.document_id,
                    "source_ok": page is not None and m.get("source") == page.source,
                    "page_ok": page is not None and m.get("page") == page.page,
                    "version_ok": page is not None and m.get("python_version") == page.metadata["python_version"]
                    and page.source.endswith(f"py{m.get('python_version')}.py"),
                    "section_ok": page is not None and m.get("section") == page.metadata["section"],
                    "text_in_page": page is not None and flatten(strip_context(h["text"], m)) in flatten(page.text),
                }
                rows.append({"strategy": key, "qid": t["id"], "rank": h["rank"], "chunk_id": h["chunk_id"],
                             "source": m.get("source"), "page": m.get("page"), "page_id": m.get("page_id"),
                             "python_version": m.get("python_version"), "section": m.get("section"),
                             **checks, "all_ok": all(checks.values()),
                             "filter_requested": json.dumps(t["filter"]) if t["filter"] else "",
                             "respects_filter": "" if h["respects_filter"] is None else h["respects_filter"]})
    with (audit_dir / "metadata_audit.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    summary = {k: f"{sum(r['all_ok'] for r in rows if r['strategy'] == k)}/"
                  f"{sum(r['strategy'] == k for r in rows)}" for k in STRATEGIES}
    (audit_dir / "filter_compliance.json").write_text(
        json.dumps({"metadata_all_ok_test_top3": summary, "filter_compliance": compliance}, indent=2), encoding="utf-8")
    print("metadata all_ok:", summary)
    print("filter compliance:", json.dumps(compliance))

    # --- changed-document re-ingest demo on a scratch collection ---
    embedder = WordLlamaEmbedder()
    store = ChromaStore(CHROMA_DIR, embedder.dimensions)
    name = "scratch_change_demo"
    try:
        store._client.delete_collection(name)
    except Exception:
        pass
    plist = list(pages.values())
    original = [c for p in plist for c in by_paragraph(p, 1000, "B")]
    s0 = store.sync(name, original, embedder.embed_documents)
    changed_pages = copy.deepcopy(plist)
    edit_id, drop_id = "py3.13/try#4", "py3.13/pass#1"
    for p in changed_pages:
        if p.metadata["page_id"] == edit_id:
            p.text += "\n\n(Edited paragraph added for the re-ingest demo.)"
    changed_pages = [p for p in changed_pages if p.metadata["page_id"] != drop_id]
    changed = [c for p in changed_pages for c in by_paragraph(p, 1000, "B")]
    s1 = store.sync(name, changed, embedder.embed_documents)
    s2 = store.sync(name, original, embedder.embed_documents)
    store._client.delete_collection(name)
    demo = {"edited_page": edit_id, "removed_page": drop_id, "initial": s0, "after_change": s1,
            "after_restore": s2, "expected_after_change_count": len(changed)}
    (RESULTS_DIR / "reingest_change_demo.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
    print("change demo:", demo)


if __name__ == "__main__":
    main()
