"""Day 06 pipeline: load -> normalize -> chunk (A/B) -> embed -> Chroma -> benchmark.

Run from ``starter/``:
    python -m src.run --rebuild      # fresh index, timings for the report
    python -m src.run                # idempotent re-run (re-ingest check)
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .chunking import by_paragraph, fixed_size
from .corpus import BENCHMARK_PATH, RESULTS_DIR, SOURCES, load_corpus
from .embeddings import WordLlamaEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import flatten
from .models import Chunk, DocumentPage
from .store import ChromaStore

STRATEGIES = {
    "A": {"chunking": "fixed_size", "chunk_size": 500, "overlap": 50, "heading_prefix": False,
          "collection": "day06_A_fixed500_o50", "use_filter": False},
    "B": {"chunking": "by_paragraph", "chunk_size": 1000, "overlap": 0, "heading_prefix": True,
          "collection": "day06_B_para1000", "use_filter": False},
    "C": {"chunking": "by_paragraph", "chunk_size": 1000, "overlap": 0, "heading_prefix": True,
          "collection": "day06_B_para1000", "use_filter": True},
}
TOP_K = 3
CHROMA_DIR = Path(__file__).resolve().parents[1] / "chroma_db"
CONTENT_UNIT_MIN_CHARS = 1500


def build_chunks(cfg: dict, pages: list[DocumentPage], key: str) -> list[Chunk]:
    if cfg["chunking"] == "fixed_size":
        return [c for p in pages for c in fixed_size(p, cfg["chunk_size"], cfg["overlap"], key)]
    return [c for p in pages for c in by_paragraph(p, cfg["chunk_size"], key, cfg["heading_prefix"])]


def length_stats(chunks: list[Chunk]) -> dict:
    lens = [len(c.text) for c in chunks]
    approx_tokens = sum(len(c.text.split()) for c in chunks)
    return {"chunks": len(chunks), "chars_total": sum(lens), "min": min(lens), "p50": statistics.median(lens),
            "mean": round(statistics.mean(lens), 1), "max": max(lens),
            "p90": sorted(lens)[int(0.9 * (len(lens) - 1))],
            "whitespace_tokens_total": approx_tokens,
            "by_version": dict(Counter(c.metadata["python_version"] for c in chunks))}


def corpus_stats(pages: list[DocumentPage], errors: list) -> dict:
    out = {"sources": [], "errors": errors}
    for version, rel in SOURCES:
        vp = [p for p in pages if p.metadata["python_version"] == version]
        topic_chars = Counter()
        for p in vp:
            topic_chars[p.metadata["topic"]] += len(p.text)
        units = sorted(t for t, c in topic_chars.items() if c >= CONTENT_UNIT_MIN_CHARS)
        out["sources"].append({
            "python_version": version, "path": rel, "snapshot": vp[0].metadata["snapshot"],
            "topics": len(topic_chars), "pages(sections)": len(vp),
            "chars_normalized": sum(len(p.text) for p in vp),
            f"topics_with_>={CONTENT_UNIT_MIN_CHARS}_chars": len(units),
            "sections_with_>=1500_chars": sum(len(p.text) >= 1500 for p in vp),
        })
    return out


def coherence_positions(pages: list[DocumentPage]) -> list[dict]:
    """10 positions fixed BEFORE looking at scores: sort the 3.13 page IDs,
    take every k-th page (k = n // 10), position = the character in the middle
    of that page's text."""
    p13 = sorted((p for p in pages if p.metadata["python_version"] == "3.13"),
                 key=lambda p: p.metadata["page_id"])
    step = len(p13) // 10
    chosen = [p13[i * step] for i in range(10)]
    return [{"pos_id": f"pos{i + 1:02d}", "page_id": p.metadata["page_id"], "offset": len(p.text) // 2,
             "context": p.text[max(0, len(p.text) // 2 - 60): len(p.text) // 2 + 60]} for i, p in enumerate(chosen)]


def chunk_at(chunks: list[Chunk], page_id: str, offset: int) -> Chunk | None:
    cands = [c for c in chunks if c.metadata["page_id"] == page_id
             and c.metadata["char_start"] <= offset < c.metadata["char_end"]]
    return cands[0] if cands else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true", help="drop collections before ingest")
    args = ap.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "traces").mkdir(exist_ok=True)
    (RESULTS_DIR / "audit").mkdir(exist_ok=True)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # 1. corpus
    t0 = time.perf_counter()
    errors: list = []
    pages = load_corpus(errors)
    load_s = time.perf_counter() - t0
    cstats = corpus_stats(pages, errors)
    cstats["load_seconds"] = round(load_s, 3)
    n_units = cstats["sources"][-1][f"topics_with_>={CONTENT_UNIT_MIN_CHARS}_chars"]
    if n_units < 30:
        sys.exit(f"Corpus check failed: only {n_units} content units (need >= 30)")
    (RESULTS_DIR / "corpus_stats.json").write_text(json.dumps(cstats, indent=2, ensure_ascii=False), encoding="utf-8")
    with (RESULTS_DIR / "errors.log").open("w", encoding="utf-8") as fh:
        for e in errors:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"[corpus] {len(pages)} pages, {n_units} content units in 3.13, {len(errors)} errors")

    bench = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    questions = bench["questions"]
    if any("accepted_gold" not in q for q in questions):
        sys.exit("Run `python -m scripts.verify_benchmark` first (gold not verified)")

    # 2. model + store (fail loudly, never mock)
    t0 = time.perf_counter()
    embedder = WordLlamaEmbedder()
    model_load_s = time.perf_counter() - t0
    store = ChromaStore(CHROMA_DIR, embedder.dimensions)
    print(f"[model] {embedder.model_name} v{embedder.version} dim={embedder.dimensions}; chroma {store.version}")

    # 3. chunk + ingest per collection
    chunks_by_key: dict[str, list[Chunk]] = {}
    ingest_log: dict = {}
    for key, cfg in STRATEGIES.items():
        name = cfg["collection"]
        if name in ingest_log:  # C reuses B's collection
            chunks_by_key[key] = chunks_by_key[ingest_log[name]["first_strategy"]]
            continue
        if args.rebuild:
            try:
                store._client.delete_collection(name)
            except Exception:
                pass
        t0 = time.perf_counter()
        chunks = build_chunks(cfg, pages, key)
        chunk_s = time.perf_counter() - t0
        emb_time = {"s": 0.0}

        def timed_embed(texts):
            s = time.perf_counter()
            v = embedder.embed_documents(texts)
            emb_time["s"] += time.perf_counter() - s
            return v

        t0 = time.perf_counter()
        first = store.sync(name, chunks, timed_embed)
        ingest_s = time.perf_counter() - t0
        # re-ingest check: same corpus again must embed/delete nothing and keep the count
        t1 = time.perf_counter()
        second = store.sync(name, build_chunks(cfg, pages, key), timed_embed)
        reingest_s = time.perf_counter() - t1
        ok = second["embedded"] == 0 and second["deleted"] == 0 and second["after"] == len(chunks)
        if not ok:
            sys.exit(f"Re-ingest check failed for {name}: {second}")
        chunks_by_key[key] = chunks
        ingest_log[name] = {"first_strategy": key, "chunking_seconds": round(chunk_s, 3),
                            "ingest_seconds_incl_embedding": round(ingest_s, 3),
                            "embedding_seconds": round(emb_time["s"], 3),
                            "first_sync": first, "reingest_sync": second,
                            "reingest_seconds": round(reingest_s, 3), "reingest_no_duplicates": ok,
                            "stats": length_stats(chunks)}
        print(f"[ingest] {name}: {first} | re-ingest {second} | {ingest_s:.2f}s")
    log_name = "ingest_log.json" if args.rebuild else "ingest_log_rerun.json"
    (RESULTS_DIR / log_name).write_text(json.dumps(ingest_log, indent=2), encoding="utf-8")

    # 4. retrieval for every question x strategy
    qvecs = {q["id"]: embedder.embed_query(q["question"]) for q in questions}
    all_summary, latency = {}, {}
    for key, cfg in STRATEGIES.items():
        traces = []
        t0 = time.perf_counter()
        for q in questions:
            flt = q.get("filter") if cfg["use_filter"] else None
            hits = store.search(cfg["collection"], qvecs[q["id"]], TOP_K, flt)
            tr = evaluate_query(q, hits)
            tr["strategy"] = key
            tr["filter_applied"] = flt
            traces.append(tr)
        latency[key] = round((time.perf_counter() - t0) / len(questions) * 1000, 2)
        with (RESULTS_DIR / "traces" / f"{key}.jsonl").open("w", encoding="utf-8") as fh:
            for tr in traces:
                fh.write(json.dumps(tr, ensure_ascii=False) + "\n")
        all_summary[key] = summarize(traces)
        s = all_summary[key]
        print(f"[eval] {key}: dev Hit@1 {s['dev']['hit1']}/{s['dev']['n']} Hit@3 {s['dev']['hit3']}/{s['dev']['n']}"
              f" | test Hit@1 {s['test']['hit1']}/{s['test']['n']} Hit@3 {s['test']['hit3']}/{s['test']['n']}")

    # 5. exact (numpy brute force) vs Chroma HNSW, same query/filter, top-3 overlap
    exact_check = {}
    for key, cfg in STRATEGIES.items():
        ids, vecs, metas = store.all_vectors(cfg["collection"])
        mat = np.asarray(vecs, dtype=np.float32)
        same, total = 0, 0
        for q in questions:
            flt = q.get("filter") if cfg["use_filter"] else None
            mask = np.array([all(str(m.get(k)) == str(v) for k, v in (flt or {}).items()) for m in metas])
            scores = mat @ np.asarray(qvecs[q["id"]], dtype=np.float32)
            scores[~mask] = -np.inf
            exact = [ids[i] for i in np.argsort(-scores)[:TOP_K]]
            hnsw = [h["chunk_id"] for h in store.search(cfg["collection"], qvecs[q["id"]], TOP_K, flt)]
            same += len(set(exact) & set(hnsw))
            total += TOP_K
        exact_check[key] = {"top3_overlap": f"{same}/{total}"}
    (RESULTS_DIR / "exact_vs_hnsw.json").write_text(json.dumps(exact_check, indent=2), encoding="utf-8")

    metrics = {"summary": all_summary, "query_latency_ms_avg": latency, "exact_vs_hnsw": exact_check}
    (RESULTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    # 6. markdown table
    lines = ["| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Gold page in top-3 | Misses@3 |",
             "|---|---|---|---|---|---|"]
    for key in STRATEGIES:
        for split in ("dev", "test"):
            s = all_summary[key][split]
            lines.append(f"| {key} | {split} | {s['hit1']}/{s['n']} | {s['hit3']}/{s['n']} | "
                         f"{s['gold_page_in_top3']}/{s['n']} | {', '.join(s['misses_at_3']) or '-'} |")
    (RESULTS_DIR / "metrics.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 7. audit material (labels are filled by a human in results/audit/*.csv)
    positions = coherence_positions(pages)
    samples = []
    for pos in positions:
        row = dict(pos)
        for key in ("A", "B"):  # C uses B's chunks -> identical coherence
            ch = chunk_at(chunks_by_key[key], pos["page_id"], pos["offset"])
            row[key] = {"chunk_id": ch.chunk_id, "text": ch.text} if ch else None
        samples.append(row)
    (RESULTS_DIR / "audit" / "coherence_samples.json").write_text(
        json.dumps(samples, indent=2, ensure_ascii=False), encoding="utf-8")

    run_info = {
        "started_utc": started, "python": platform.python_version(), "platform": platform.platform(),
        "embedding": {"provider": "local (pip wheel, offline)", "model": embedder.model_name,
                      "package_version": embedder.version, "dimensions": embedder.dimensions,
                      "normalized": True, "query_doc_processing": "identical, no prefix",
                      "model_load_seconds": round(model_load_s, 3)},
        "vector_store": {"name": "chromadb", "version": store.version, "path": str(CHROMA_DIR.name),
                         "metric": "cosine", "index": "HNSW (approximate), search_ef=200"},
        "strategies": STRATEGIES, "top_k": TOP_K, "cost_usd": 0.0, "random_seed": "none needed (deterministic)",
    }
    (RESULTS_DIR / "run_info.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")
    print("[done] results written to", RESULTS_DIR)


if __name__ == "__main__":
    main()
