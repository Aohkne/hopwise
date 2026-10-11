# Version Roadmap

## 1.0.0 — Data and rough graph

- [x] **Data crawler**: `scripts/crawl_football.py` and
  `scripts/crawl_vinfast.py`, pulling real data from Wikidata SPARQL and
  SEC EDGAR 20-F.
- [x] **Rough Knowledge Graph**: nodes are linked using a simple algorithm —
  each edge maps directly to a relation already present in the source
  (`PLAYED_FOR`, `BOARD_MEMBER_OF`...), with no semantic reasoning between
  nodes yet.
- [ ] **System 1 vs. System 2 comparison**: comparing Jev/Kev (System 1)
  with regular LLMs (System 2) on the same traversal problem.
- [ ] CI/CD

## 2.0.0 — Linking nodes by fact

- [ ] Build a way to create a link between nodes using a specific fact,
  instead of only linking by raw structural relation as in 1.0.0 — each
  edge can be traced back to the fact that generated it.
