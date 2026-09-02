from positronic_serve.federation import federated_recall, rrf_fuse


def test_rrf_fuse_merges_and_ranks():
    a = [{"episode_id": "x1", "tau": 1.0}, {"episode_id": "x2", "tau": 2.0}]
    b = [{"episode_id": "x2", "tau": 2.0}, {"episode_id": "x3", "tau": 3.0}]
    fused = rrf_fuse([a, b])
    ids = [h["episode_id"] for h in fused]
    assert "x2" in ids and "x1" in ids and "x3" in ids
    # x2 present in both lists should rank above singletons
    assert ids[0] == "x2"
    assert all("source_host" in h for h in fused)


def test_federated_recall_local_only_when_no_peers(tmp_path):
    from positronic_ai.brains import init_brain
    from positronic_ai.ops.ingest import run as ingest
    init_brain(str(tmp_path), "kairos", "balanced", "lexical")
    ingest(str(tmp_path), "network serve test fact", brain="kairos", arousal=0.5)
    cfg = {"dir": str(tmp_path), "brain": "kairos", "peers": []}
    out = federated_recall(cfg, "network serve test fact", k=3)
    assert out["results"], "local recall should return hits"
    assert out["sources"] == ["local"]