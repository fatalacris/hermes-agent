"""Tests for Curator Governance v1 proposal-first guardrails."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest


@pytest.fixture
def curator_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    (home / "skills").mkdir(parents=True)
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    import hermes_constants
    import tools.skill_usage as usage
    import agent.curator as curator

    importlib.reload(hermes_constants)
    importlib.reload(usage)
    importlib.reload(curator)
    monkeypatch.setattr(curator, "_load_config", lambda: {})
    return {"home": home, "skills": home / "skills", "usage": usage, "curator": curator}


def _write_skill(skills_dir: Path, name: str, body: str = "description: test") -> Path:
    d = skills_dir / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\n{body}\n---\n\n# {name}\n", encoding="utf-8")
    return d


def _write_usage(usage, name: str, **fields) -> None:
    data = usage.load_usage()
    rec = usage._empty_record()
    rec.update(fields)
    data[name] = rec
    usage.save_usage(data)


def _empty_valid_plan(curator_env):
    curator = curator_env["curator"]
    skills = curator_env["skills"]
    return curator.generate_governance_plan(source_root=skills, run_id="valid-empty")


def test_curator_governance_plan_schema_is_proposal_first(curator_env):
    curator = curator_env["curator"]
    usage = curator_env["usage"]
    skills = curator_env["skills"]
    _write_skill(skills, "keeper")
    _write_usage(usage, "keeper", state="active")

    plan = curator.generate_governance_plan(source_root=skills, run_id="test-run")

    assert plan["schema"] == "CuratorPlanV1"
    assert plan["policy_version"] == curator.POLICY_VERSION == "ark-curator-governance-v1"
    assert plan["run_id"] == "test-run"
    assert plan["mode"] == "propose"
    assert plan["source_root"] == str(skills)
    assert plan["source_snapshot_hash"]
    assert plan["protected_skills_checked"] is True
    assert isinstance(plan["protected_skills"], list)
    assert isinstance(plan["protected_patterns"], list)
    assert "fati-cris-execution-contract" in plan["protected_skills"]
    assert "mission-control-state-safety" in plan["protected_skills"]
    assert "fati-*" in plan["protected_patterns"]
    assert "ark-*" in plan["protected_patterns"]
    assert "mission-control-*" in plan["protected_patterns"]
    assert "*governance*" in plan["protected_patterns"]
    assert plan["summary"]["skills_inspected"] == 1
    assert plan["summary"]["skills_to_change"] == 0
    assert plan["summary"]["skills_to_archive"] == 0
    assert plan["summary"]["blast_radius_pct"] == 0
    assert [p["action"] for p in plan["proposals"]] == ["keep"]
    assert plan["blocked"] == []


def test_curator_governance_skips_bundled_and_hub_installed(curator_env):
    curator = curator_env["curator"]
    skills = curator_env["skills"]
    _write_skill(skills, "agent-skill")
    _write_skill(skills, "bundled-skill")
    _write_skill(skills, "hub-skill")
    _write_skill(skills, "hub-lock-skill")
    (skills / ".bundled_manifest").write_text("bundled-skill\n", encoding="utf-8")
    (skills / ".hub_installed").write_text("hub-skill\n", encoding="utf-8")
    (skills / ".hub").mkdir()
    (skills / ".hub" / "lock.json").write_text(
        json.dumps({"version": 1, "installed": {"hub-lock-skill": {"source": "hub"}}}),
        encoding="utf-8",
    )

    names = {row["name"] for row in curator.inspect_skills(source_root=skills)["skills"]}

    assert "agent-skill" in names
    assert "bundled-skill" not in names
    assert "hub-skill" not in names
    assert "hub-lock-skill" not in names


def test_curator_inspect_or_propose_writes_no_live_files(curator_env, tmp_path):
    curator = curator_env["curator"]
    usage = curator_env["usage"]
    skills = curator_env["skills"]
    _write_skill(skills, "live-keeper")
    _write_usage(usage, "live-keeper", state="active")
    before = sorted(str(p.relative_to(skills)) for p in skills.rglob("*"))

    inventory = curator.inspect_skills(source_root=skills)
    plan = curator.generate_governance_plan(source_root=skills)
    out = tmp_path / "out"
    curator.write_governance_inventory(inventory, out)
    curator.write_governance_plan(plan, out)

    after = sorted(str(p.relative_to(skills)) for p in skills.rglob("*"))
    assert after == before
    assert (out / "inventory.json").exists()
    assert (out / "plan.json").exists()


def test_inspect_and_propose_refuse_live_output_targets(curator_env):
    curator = curator_env["curator"]
    usage = curator_env["usage"]
    skills = curator_env["skills"]
    _write_skill(skills, "live-keeper")
    _write_usage(usage, "live-keeper", state="active")
    inventory = curator.inspect_skills(source_root=skills)
    plan = curator.generate_governance_plan(source_root=skills)

    with pytest.raises(curator.CuratorGovernanceError, match="outside source/live"):
        curator.write_governance_inventory(inventory, skills)
    with pytest.raises(curator.CuratorGovernanceError, match="outside source/live"):
        curator.write_governance_plan(plan, skills)
    with pytest.raises(curator.CuratorGovernanceError, match="outside source/live"):
        curator.write_governance_plan(plan, skills / "artifact-subdir")


def test_stage_applies_only_to_copy(curator_env, tmp_path):
    curator = curator_env["curator"]
    usage = curator_env["usage"]
    skills = curator_env["skills"]
    _write_skill(skills, "source-skill")
    _write_usage(usage, "source-skill", state="active")
    plan = curator.generate_governance_plan(source_root=skills, run_id="stage-test")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    target = tmp_path / "copied-skills-dir"
    target.mkdir()

    result = curator.stage_governance_plan(plan_path, target)

    assert result["staged"] is True
    assert (target / "plan.json").exists()
    assert (target / "STAGING_SUMMARY.md").exists()
    assert not (skills / "plan.json").exists()
    assert not (skills / "STAGING_SUMMARY.md").exists()


def test_stage_refuses_live_source_subdirectory(curator_env, tmp_path):
    curator = curator_env["curator"]
    skills = curator_env["skills"]
    _write_skill(skills, "demo-skill")
    plan = curator.generate_governance_plan(source_root=skills, run_id="stage-live-subdir")
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    with pytest.raises(curator.CuratorGovernanceError, match="outside source/live"):
        curator.stage_governance_plan(plan_path, skills / "demo-skill")


def test_apply_requires_approval_id_for_live(curator_env):
    curator = curator_env["curator"]
    plan = _empty_valid_plan(curator_env)

    with pytest.raises(curator.CuratorGovernanceError, match="approval_id"):
        curator.validate_apply_governance_plan(plan, live=True)


def test_apply_refuses_missing_snapshot_hash(curator_env):
    curator = curator_env["curator"]
    plan = _empty_valid_plan(curator_env)
    plan["source_snapshot_hash"] = ""

    with pytest.raises(curator.CuratorGovernanceError, match="source_snapshot_hash"):
        curator.validate_apply_governance_plan(plan, approval_id="ARK-1", live=True)


def test_apply_refuses_protected_skill(curator_env):
    curator = curator_env["curator"]
    plan = _empty_valid_plan(curator_env)
    plan["protected_skills"] = []  # tampered plans cannot bypass default protected skills
    plan["protected_patterns"] = []
    plan["proposals"] = [{"skill": "fati-cris-execution-contract", "action": "archive"}]
    plan["summary"] = {"skills_to_archive": 0, "blast_radius_pct": 0, "skills_to_change": 0}

    with pytest.raises(curator.CuratorGovernanceError, match="protected"):
        curator.validate_apply_governance_plan(plan, approval_id="ARK-1", live=True)


def test_apply_refuses_ark_protected_skill_from_tampered_plan(curator_env):
    curator = curator_env["curator"]
    plan = _empty_valid_plan(curator_env)
    plan["protected_skills"] = []
    plan["protected_patterns"] = []
    plan["proposals"] = [{"skill": "ARK-Core", "action": "patch"}]
    plan["summary"] = {"skills_to_archive": 0, "blast_radius_pct": 0, "skills_to_change": 0}

    with pytest.raises(curator.CuratorGovernanceError, match="protected"):
        curator.validate_apply_governance_plan(plan, approval_id="ARK-1", live=True)


def test_apply_refuses_over_mutation_threshold(curator_env):
    curator = curator_env["curator"]
    plan = _empty_valid_plan(curator_env)
    plan["proposals"] = [
        {"skill": "a", "action": "patch"},
        {"skill": "b", "action": "patch"},
        {"skill": "c", "action": "patch"},
        {"skill": "d", "action": "patch"},
    ]
    plan["summary"] = {"skills_to_archive": 0, "blast_radius_pct": 6, "skills_to_change": 4}

    with pytest.raises(curator.CuratorGovernanceError, match="blast_radius_pct|max_live_mutations"):
        curator.validate_apply_governance_plan(plan, approval_id="ARK-1", live=True)


def test_apply_recomputes_tampered_blast_radius(curator_env):
    curator = curator_env["curator"]
    plan = _empty_valid_plan(curator_env)
    plan["proposals"] = [
        {"skill": f"skill-{i}", "action": "patch" if i < 3 else "keep"}
        for i in range(20)
    ]
    plan["summary"] = {
        "skills_inspected": 20,
        "skills_to_archive": 0,
        "blast_radius_pct": 0,
        "skills_to_change": 0,
    }

    with pytest.raises(curator.CuratorGovernanceError, match="blast_radius_pct"):
        curator.validate_apply_governance_plan(plan, approval_id="ARK-1", live=True)


def test_apply_ignores_inflated_summary_denominator(curator_env):
    curator = curator_env["curator"]
    plan = _empty_valid_plan(curator_env)
    plan["proposals"] = [
        {"skill": "a", "action": "patch"},
        {"skill": "b", "action": "patch"},
        {"skill": "c", "action": "patch"},
    ]
    plan["summary"] = {
        "skills_inspected": 1000,
        "skills_to_archive": 0,
        "blast_radius_pct": 0,
        "skills_to_change": 0,
    }

    with pytest.raises(curator.CuratorGovernanceError, match="blast_radius_pct"):
        curator.validate_apply_governance_plan(plan, approval_id="ARK-1", live=True)


def test_report_or_plan_contains_plan_id_rollback_and_blast_radius(curator_env):
    curator = curator_env["curator"]
    usage = curator_env["usage"]
    skills = curator_env["skills"]
    _write_skill(skills, "stale-candidate")
    _write_usage(usage, "stale-candidate", state="stale")

    plan = curator.generate_governance_plan(source_root=skills, run_id="rollback-test")

    assert plan["run_id"] == "rollback-test"
    assert "blast_radius_pct" in plan["summary"]
    proposal = plan["proposals"][0]
    assert "rollback" in proposal
    assert proposal["ark_decision_required"] is True
