from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict
import random

app = FastAPI(title="Avito PR Reviewer Service", version="0.2.0")

teams: Dict[str, List[str]] = {}
users: Dict[str, dict] = {}
pull_requests: Dict[str, dict] = {}

class TeamMemberInput(BaseModel):
    user_id: str
    username: str
    is_active: bool = True

class TeamAddRequest(BaseModel):
    team_name: str
    members: List[TeamMemberInput]

class SetActiveRequest(BaseModel):
    user_id: str
    is_active: bool

class PRCreateRequest(BaseModel):
    pull_request_id: str
    pull_request_name: str
    author_id: str

@app.post("/team/add", status_code=201)
def add_team(payload: TeamAddRequest):
    teams[payload.team_name] = [m.user_id for m in payload.members]
    for m in payload.members:
        users[m.user_id] = {
            "user_id": m.user_id,
            "username": m.username,
            "team_name": payload.team_name,
            "is_active": m.is_active,
        }
    return {"team": {"team_name": payload.team_name, "members": list(payload.members)}}

@app.post("/users/setIsActive")
def set_is_active(payload: SetActiveRequest):
    if payload.user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")
    users[payload.user_id]["is_active"] = payload.is_active
    return {"user": users[payload.user_id]}

@app.post("/pullRequest/create", status_code=201)
def create_pr(payload: PRCreateRequest):
    author = users.get(payload.author_id)
    if not author:
        raise HTTPException(status_code=404, detail="Author not found")
    team_members = teams.get(author["team_name"], [])
    # Исправлено: исключаем самого автора и неактивных участников, берём min(2, len)
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
    }
    pull_requests[payload.pull_request_id] = pr_obj
    return {"pr": pr_obj}
