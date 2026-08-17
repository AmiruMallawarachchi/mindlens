"""Root Render Blueprint cost guardrails."""

from __future__ import annotations

from pathlib import Path


def test_root_render_blueprint_contains_no_paid_resources() -> None:
    blueprint = Path("render.yaml").read_text(encoding="utf-8")

    assert blueprint.count("- type: web") == 1
    assert "plan: free" in blueprint
    assert "numInstances: 1" in blueprint
    assert "disk:" not in blueprint
    assert "redis" not in blueprint.lower()
    assert "cron" not in blueprint.lower()
    assert "worker" not in blueprint.lower()
    assert "PRELOAD_MODELS" in blueprint
    assert 'value: "false"' in blueprint
    assert "CHROMADB_PERSIST_DIR" in blueprint
    assert "/tmp/mindlens/chroma" in blueprint
