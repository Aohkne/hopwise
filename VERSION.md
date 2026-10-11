# Roadmap

Legend: `[x]` done, `[ ]` planned but not implemented yet — see
[TODO.md](TODO.md).

## 1.0.0 — Data and rough graph

- [x] **Data crawler**: `scripts/crawl_football.py` and
  `scripts/crawl_vinfast.py`, pulling real data from Wikidata SPARQL and
  SEC EDGAR 20-F filings.
- [x] **Rough Knowledge Graph**: nodes are linked with a simple algorithm —
  each edge maps directly to a relation already present in the source
  (`PLAYED_FOR`, `BOARD_MEMBER_OF`, ...), with no semantic reasoning between
  nodes yet.
- [ ] **System 1 vs. System 2 comparison**: benchmark Jev/Kev (System 1)
  against general-purpose LLMs (System 2) on the same traversal task.
- [ ] **CI/CD**: GitHub Actions workflow to run `verify_data.py` (and future
  tests) automatically on every push and pull request.

## 2.0.0 — Fact-based edges

- [ ] Build a mechanism to create an edge between two nodes from **a
  specific fact**, instead of only mapping raw structural relations as in
  1.0.0 — each edge should be traceable back to the fact that produced it.
