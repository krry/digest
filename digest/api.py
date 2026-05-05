from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from digest.store import DigestStore

app = FastAPI(title="Digest API", version="0.1.0")
store = DigestStore()


class AddChildRequest(BaseModel):
    parentId: str | None = None
    title: str


class AddSiblingRequest(BaseModel):
    nodeId: str | None = None
    title: str


class RenameNodeRequest(BaseModel):
    nodeId: str
    title: str


class NodeIdRequest(BaseModel):
    nodeId: str


class ValuesRequest(BaseModel):
    establishedAt: str | None = None
    values: list[dict[str, Any]]


class CheckinRequest(BaseModel):
    date: str | None = None
    question: str
    response: str
    adjustment: str


@app.on_event("startup")
def startup():
    store.ensure_ready()


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/v1/bootstrap")
def bootstrap():
    return store.bootstrap_payload()


@app.get("/api/v1/nodes")
def nodes():
    return store.load_goals_data()


@app.get("/api/v1/values")
def values():
    return store.load_values_data()


@app.get("/api/v1/checkins")
def checkins():
    return store.load_checkins_data()


@app.get("/api/v1/export/json")
def export_json():
    return {
        "goals": store.load_goals_data(),
        "values": store.load_values_data(),
        "checkins": store.load_checkins_data(),
    }


@app.get("/api/v1/sync")
def sync(_since: str | None = None):
    return {"cursor": store.bootstrap_payload()["serverTime"], "changes": []}


@app.post("/api/v1/sync/push")
def sync_push(payload: dict[str, Any]):
    return {
        "ok": True,
        "acceptedMutationIds": [m.get("clientMutationId") for m in payload.get("mutations", [])],
        "rejectedMutations": [],
    }


@app.post("/api/v1/commands/add-child")
def add_child(request: AddChildRequest):
    return {"ok": True, "node": store.add_node("goal" if request.parentId is None else _child_type(request.parentId), request.parentId, request.title)}


@app.post("/api/v1/commands/add-sibling")
def add_sibling(request: AddSiblingRequest):
    goals = store.load_goals_data()["nodes"]
    node = next((n for n in goals if n["id"] == request.nodeId), None) if request.nodeId else None
    node_type = node["type"] if node else "goal"
    parent_id = node["parentId"] if node else None
    return {"ok": True, "node": store.add_node(node_type, parent_id, request.title)}


@app.post("/api/v1/commands/rename-node")
def rename_node(request: RenameNodeRequest):
    node = store.rename_node(request.nodeId, request.title)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"ok": True, "node": node}


@app.post("/api/v1/commands/complete-node")
def complete_node(request: NodeIdRequest):
    node = store.set_node_status(request.nodeId, "completed")
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"ok": True, "node": node}


@app.post("/api/v1/commands/archive-node")
def archive_node(request: NodeIdRequest):
    node = store.set_node_status(request.nodeId, "archived")
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"ok": True, "node": node}


@app.post("/api/v1/commands/update-values")
def update_values(request: ValuesRequest):
    store.write_values_data({"version": 1, "establishedAt": request.establishedAt, "values": request.values})
    return {"ok": True, "values": store.load_values_data()}


@app.post("/api/v1/commands/add-checkin")
def add_checkin(request: CheckinRequest):
    store.append_checkin(request.model_dump())
    return {"ok": True}


def _child_type(parent_id: str) -> str:
    node = next((n for n in store.load_goals_data()["nodes"] if n["id"] == parent_id), None)
    if not node:
        raise HTTPException(status_code=404, detail="Parent not found")
    return {
        "goal": "idea",
        "idea": "step",
        "step": "task",
        "task": "free",
        "free": "free",
    }[node["type"]]
