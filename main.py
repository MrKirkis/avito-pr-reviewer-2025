from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict

app = FastAPI(title="Avito PR Reviewer Service", version="0.1.0")

# In-memory хранилище
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
