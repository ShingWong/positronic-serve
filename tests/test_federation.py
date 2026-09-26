# =====================================================================
# Project Positronic — Polytemporal Cognitive Engram Memory Substrate
# Copyright (C) 2026 Shing Wong. All Rights Reserved.
# =====================================================================
# This program is DUAL-LICENSED. You may redistribute and/or modify it 
# under the terms of the GNU Affero General Public License as published by the 
# Free Software Foundation, either version 3 of the License, or (at your 
# option) any later version.
#
# Alternatively, commercial entities, multi-tenant instances, and Managed 
# Service Providers (MSPs) may utilize this program under a separate, 
# proprietary Commercial License Waiver issued directly by the copyright 
# holder, completely exempt from the network-use copyleft restrictions of 
# the AGPLv3 Section 13.
#
# This program is distributed in the hope that it will be useful, but 
# WITHOUT ANY WARRANTY; without even the implied warranty of 
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU 
# Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License 
# along with this program. If not, see <https://gnu.org>.
# =====================================================================

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