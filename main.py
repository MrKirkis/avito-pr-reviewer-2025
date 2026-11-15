from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime, timezone
import random

app = FastAPI(title="Avito PR Reviewer Service", version="0.3.0")

teams: Dict[str, List[str]] = {}
users: Dict[str, dict] = {}
pull_requests: Dict[str, dict] = {}

class TeamMemberInput(BaseModel):
    user_id: str = Field(..., min_length=1)
    username: str = Field(..., min_length=1)
    is_active: bool = True

class TeamAddRequest(BaseModel):
    team_name: str = Field(..., min_length=1)
    members: List[TeamMemberInput] = Field(..., min_length=1)

class SetActiveRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    is_active: bool

class PRCreateRequest(BaseModel):
    pull_request_id: str = Field(..., min_length=1)
    pull_request_name: str = Field(..., min_length=1)
    author_id: str = Field(..., min_length=1)

class PRMergeRequest(BaseModel):
    pull_request_id: str = Field(..., min_length=1)

class PRReassignRequest(BaseModel):
    pull_request_id: str = Field(..., min_length=1)
    old_user_id: str = Field(..., min_length=1)

@app.post("/team/add", status_code=201)
def add_team(payload: TeamAddRequest):
    if payload.team_name in teams:
        raise HTTPException(status_code=400, detail={"error": {"code": "TEAM_EXISTS", "message": "Team already exists"}})
    seen_ids = []
    for m in payload.members:
        if m.user_id not in seen_ids:
            seen_ids.append(m.user_id)
        users[m.user_id] = {
            "user_id": m.user_id,
            "username": m.username,
            "team_name": payload.team_name,
            "is_active": m.is_active,
        }
    teams[payload.team_name] = seen_ids
    return {"team": {"team_name": payload.team_name, "members": [users[uid] for uid in seen_ids]}}

@app.post("/users/setIsActive")
def set_is_active(payload: SetActiveRequest):
    if payload.user_id not in users:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "User not found"}})
    users[payload.user_id]["is_active"] = payload.is_active
    return {"user": users[payload.user_id]}

@app.post("/pullRequest/create", status_code=201)
def create_pr(payload: PRCreateRequest):
    if payload.pull_request_id in pull_requests:
        raise HTTPException(status_code=409, detail={"error": {"code": "PR_EXISTS", "message": "PR id already exists"}})
    author = users.get(payload.author_id)
    if not author:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Author not found"}})
    team_members = teams.get(author["team_name"], [])
    candidates = [
        uid for uid in team_members
        if uid != payload.author_id and users.get(uid, {}).get("is_active", False)
    ]
    assigned = random.sample(candidates, min(2, len(candidates)))
    pr_obj = {
        "pull_request_id": payload.pull_request_id,
        "pull_request_name": payload.pull_request_name,
        "author_id": payload.author_id,
        "status": "OPEN",
        "assigned_reviewers": assigned,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "mergedAt": None,
    }
    pull_requests[payload.pull_request_id] = pr_obj
    return {"pr": pr_obj}

@app.post("/pullRequest/merge")
def merge_pr(payload: PRMergeRequest):
    pr = pull_requests.get(payload.pull_request_id)
    if not pr:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "PR not found"}})
    # Идемпотентный merge: повторный вызов не вызывает ошибку и не перезаписывает mergedAt
    if pr["status"] != "MERGED":
        pr["status"] = "MERGED"
        pr["mergedAt"] = datetime.now(timezone.utc).isoformat()
    return {"pr": pr}

@app.post("/pullRequest/reassign")
def reassign_pr(payload: PRReassignRequest):
    pr = pull_requests.get(payload.pull_request_id)
    if not pr:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "PR not found"}})
    if pr["status"] == "MERGED":
        raise HTTPException(status_code=409, detail={"error": {"code": "PR_MERGED", "message": "Cannot reassign on merged PR"}})
    if payload.old_user_id not in pr["assigned_reviewers"]:
        raise HTTPException(status_code=409, detail={"error": {"code": "NOT_ASSIGNED", "message": "Reviewer is not assigned to this PR"}})
    author = users[pr["author_id"]]
    team_members = teams.get(author["team_name"], [])
    candidates = [
        uid for uid in team_members
        if uid != pr["author_id"]
        and uid not in pr["assigned_reviewers"]
        and users.get(uid, {}).get("is_active", False)
    ]
    new_uid = random.choice(candidates)
    idx = pr["assigned_reviewers"].index(payload.old_user_id)
    pr["assigned_reviewers"][idx] = new_uid
    return {"pr": pr, "replaced_by": new_uid}

@app.get("/users/getReview")
def get_user_reviews(user_id: str = Query(..., min_length=1)):
    if user_id not in users:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "User not found"}})
    user_prs = [
        {
            "pull_request_id": pr["pull_request_id"],
            "pull_request_name": pr["pull_request_name"],
            "author_id": pr["author_id"],
            "status": pr["status"],
        }
        for pr in pull_requests.values()
        if user_id in pr["assigned_reviewers"]
    ]
    return {"user_id": user_id, "pull_requests": user_prs}

@app.get("/team/get")
def get_team(team_name: str = Query(..., min_length=1)):
    if team_name not in teams:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Team not found"}})
    members = [users[uid] for uid in teams[team_name] if uid in users]
    return {"team_name": team_name, "members": members}
