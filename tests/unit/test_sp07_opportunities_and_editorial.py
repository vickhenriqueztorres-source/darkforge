from __future__ import annotations

from uuid import uuid4

import pytest

from core.editorial.service import EditorialStudioService
from core.errors import AppError, ErrorCode
from core.opportunities.service import OpportunityService, compute_opportunity_score
from core.workspaces.models import AuthenticatedUser, WorkspaceMember, WorkspaceRole
from core.workspaces.service import WorkspaceService


class _FakeWorkspaceRepo:
    def __init__(self, ws_id, user_id):
        self.ws_id = ws_id
        self.user_id = user_id

    def get_membership(self, actor, workspace_id):
        if workspace_id == self.ws_id and actor.user_id == self.user_id:
            return WorkspaceMember(id=uuid4(), workspace_id=workspace_id, user_id=actor.user_id, role=WorkspaceRole.OWNER)
        return None


class _FakeEditorialRepo:
    def __init__(self, ws_id, ch_id, profile_id, with_data=True):
        self.ws_id = ws_id
        self.ch_id = ch_id
        self.profile_id = profile_id
        self.with_data = with_data
        self.opps = {}
        self.evidence = {}
        self.feedback = {}
        self.briefs = {}
        self.history = {}

    def load_generation_context(self, workspace_id, channel_id):
        return {
            "channel": {"id": channel_id, "display_name": "Canal Teste"},
            "profile_version": {
                "id": self.profile_id,
                "payload_json": {"pillars": ["misterio", "ciencias"], "voice_tone": "seria", "restrictions": ["sem fake"]},
            },
            "analytics_facts": ([{"id": str(uuid4()), "metric_key": "views", "value": 15000, "freshness_status": "fresh"}] if self.with_data else []),
            "approved_references": ([{"id": str(uuid4()), "title": "Ref A", "canonical_url": "https://youtube.com/watch?v=x"}] if self.with_data else []),
        }

    def insert_opportunity(self, **kwargs):
        oid = uuid4()
        row = {
            "id": oid,
            "workspace_id": kwargs["workspace_id"],
            "channel_id": kwargs["channel_id"],
            "profile_version_id": kwargs["profile_version_id"],
            "theme": kwargs["theme"],
            "angle": kwargs["angle"],
            "target_format": kwargs["target_format"],
            "differentiation": kwargs["differentiation"],
            "score": kwargs["score"],
            "score_version": kwargs["score_version"],
            "score_breakdown_json": kwargs["score_breakdown_json"],
            "confidence": kwargs["confidence"],
            "limitations_json": kwargs["limitations_json"],
            "data_freshness": kwargs["data_freshness"],
            "insufficient_data": kwargs["insufficient_data"],
            "analyst_reports_json": kwargs["analyst_reports_json"],
            "status": "GENERATED",
        }
        self.opps[oid] = row
        self.evidence[oid] = kwargs["evidence_links"]
        self.feedback[oid] = []
        return row

    def get_opportunity(self, workspace_id, opp_id):
        return self.opps.get(opp_id)

    def list_evidence(self, workspace_id, entity_type, entity_id):
        return self.evidence.get(entity_id, [])

    def update_opportunity_and_record_feedback(self, **kwargs):
        opp = self.opps[kwargs["opportunity_id"]]
        opp["status"] = kwargs["new_status"]
        fb = {"decision": kwargs["decision"], "new_status": kwargs["new_status"]}
        self.feedback[opp["id"]].append(fb)
        return {"opportunity": opp, "feedback": fb}

    def insert_brief(self, **kwargs):
        bid = uuid4()
        row = {**kwargs, "id": bid, "status": "DRAFT", "frozen_at": None}
        self.briefs[bid] = row
        self.history[bid] = [{"action": "CREATE", "to_status": "DRAFT"}]
        return row

    def get_brief(self, workspace_id, brief_id):
        return self.briefs.get(brief_id)

    def list_brief_history(self, workspace_id, brief_id):
        return self.history.get(brief_id, [])

    def list_brief_versions(self, workspace_id, group_id):
        return [b for b in self.briefs.values() if b["brief_group_id"] == group_id]

    def approve_brief(self, **kwargs):
        b = self.briefs[kwargs["brief_id"]]
        b["status"] = "APPROVED"
        b["frozen_at"] = "2026-11-16T00:00:00Z"
        self.history[b["id"]].append({"action": "APPROVE", "to_status": "APPROVED"})
        return b

    def create_next_brief_version(self, **kwargs):
        parent = kwargs["parent_brief"]
        if parent["status"] == "APPROVED":
            parent["status"] = "SUPERSEDED"
        bid = uuid4()
        row = {
            "id": bid,
            "workspace_id": kwargs["workspace_id"],
            "brief_group_id": parent["brief_group_id"],
            "version": parent["version"] + 1,
            "parent_brief_id": parent["id"],
            "opportunity_id": parent["opportunity_id"],
            "channel_id": parent["channel_id"],
            "profile_version_id": parent["profile_version_id"],
            "title": kwargs["title"],
            "hook": kwargs["hook"],
            "angle": kwargs["angle"],
            "outline_json": kwargs["outline_json"],
            "cta": kwargs["cta"],
            "target_format": parent["target_format"],
            "source_refs_json": parent["source_refs_json"],
            "generation_refs_json": parent["generation_refs_json"],
            "content_sha256": kwargs["content_sha256"],
            "status": "DRAFT",
        }
        self.briefs[bid] = row
        self.history[bid] = [{"action": "CREATE_VERSION", "to_status": "DRAFT"}]
        return row

    def record_brief_action(self, **kwargs):
        self.history[kwargs["brief_id"]].append({"action": kwargs["action"], "to_status": kwargs["to_status"]})


def test_score_formula_and_insufficient_data_uncertainty() -> None:
    score, breakdown = compute_opportunity_score(
        relevance=0.8,
        demand=0.9,
        baseline_lift=0.7,
        format_fit=0.85,
        timing=0.8,
        viability=0.9,
        knowledge_support=0.6,
        penalty=0.05,
    )
    assert 0.0 <= score <= 1.0
    assert breakdown["score"] == score

    ws_id, uid, ch_id, prof_id = uuid4(), uuid4(), uuid4(), uuid4()
    ws = WorkspaceService(_FakeWorkspaceRepo(ws_id, uid))
    repo = _FakeEditorialRepo(ws_id, ch_id, prof_id, with_data=False)
    opp_svc = OpportunityService(ws, repo)
    actor = AuthenticatedUser(user_id=uid, email="owner@example.com")

    res = opp_svc.generate_opportunities(actor, ws_id, ch_id, topic_hint="misterio submarino")
    opp = res["opportunity"]
    assert opp["insufficient_data"] is True
    assert opp["confidence"] <= 0.35
    assert opp["data_freshness"] == "insufficient"
    assert len(opp["limitations_json"]) >= 2
    assert len(opp["analyst_reports_json"]) == 4

    fb = opp_svc.review_opportunity(actor, ws_id, opp["id"], decision="APPROVE", notes="ok")
    assert fb["fine_tuning_claimed"] is False


def test_t_ed_001_brief_approve_freezes_and_editing_creates_new_version() -> None:
    ws_id, uid, ch_id, prof_id = uuid4(), uuid4(), uuid4(), uuid4()
    ws = WorkspaceService(_FakeWorkspaceRepo(ws_id, uid))
    repo = _FakeEditorialRepo(ws_id, ch_id, prof_id, with_data=True)
    opp_svc = OpportunityService(ws, repo)
    ed_svc = EditorialStudioService(ws, repo)
    actor = AuthenticatedUser(user_id=uid, email="owner@example.com")

    opp = opp_svc.generate_opportunities(actor, ws_id, ch_id, topic_hint="misterio")["opportunity"]
    created = ed_svc.create_brief(
        actor,
        ws_id,
        opportunity_id=opp["id"],
        title="O Enigma Real",
        hook="Nos primeiros 10 segundos voce descobre o erro.",
        angle="Analise baseada em fatos",
        outline=[{"section": "Hook", "notes": "Abertura"}],
        cta="Comente sua teoria",
    )
    v1 = created["brief"]
    approved = ed_svc.approve_brief(actor, ws_id, v1["id"])["brief"]
    assert approved["status"] == "APPROVED"

    # Mutating frozen v1 must be blocked
    with pytest.raises(AppError) as exc:
        ed_svc.update_draft(actor, ws_id, v1["id"], title="Edit in place")
    assert exc.value.code == ErrorCode.VERSION_CONFLICT

    # Creating v2 keeps v1 intact in group versions
    v2_res = ed_svc.create_new_version(actor, ws_id, v1["id"], title="O Enigma Real v2")
    assert v2_res["brief"]["version"] == 2
    assert v2_res["brief"]["status"] == "DRAFT"
    assert v2_res["brief"]["parent_brief_id"] == v1["id"]

    md = ed_svc.export_brief(actor, ws_id, v1["id"], fmt="markdown")
    assert "O Enigma Real" in md["content"]
    assert v1["content_sha256"] in md["content"]

    with pytest.raises(AppError) as cal_exc:
        ed_svc.create_calendar_item(
            actor, ws_id, channel_id=ch_id, title="Auto?", scheduled_for="2026-11-22", auto_publish_enabled=True
        )
    assert cal_exc.value.code == ErrorCode.VALIDATION_ERROR
