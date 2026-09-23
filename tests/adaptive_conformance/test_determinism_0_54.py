# pyright: reportMissingParameterType=false, reportPrivateUsage=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false
"""Reference identity invariance under order and hash randomization."""

import os
import random
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("polars")
pytest.importorskip("pandas")
pytest.importorskip("pyarrow")

from examples.adaptive_reference import Reference

from etlantic.planning.adaptive import _canonical_graph

pytestmark = [pytest.mark.polars, pytest.mark.pandas]


@pytest.mark.parametrize("seed", range(16))
def test_reference_canonical_graph_permutations(seed):
    graph = Reference.build_graph()
    nodes, edges = list(graph.nodes), list(graph.edges)
    rng = random.Random(seed)
    rng.shuffle(nodes)
    rng.shuffle(edges)
    assert _canonical_graph(
        replace(graph, nodes=tuple(nodes), edges=tuple(edges))
    ) == _canonical_graph(graph)


def test_reference_plan_hash_seed_identity():
    root = Path(__file__).resolve().parents[2]
    command = [
        sys.executable,
        "-c",
        "from pathlib import Path; from examples.adaptive_reference import candidate; print(candidate(Path.cwd())[2].fingerprint)",
    ]
    fingerprints = []
    for seed in (0, 1, 42):
        result = subprocess.run(
            command,
            cwd=root,
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
            capture_output=True,
            text=True,
            check=True,
            timeout=60,
        )
        fingerprints.append(result.stdout.strip())
    assert len(set(fingerprints)) == 1
