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

class PRMergeRequest(BaseModel):
    pull_request_id: str

class PRReassignRequest(BaseModel):
    pull_request_id: str
    old_user_id: str

@app.post("/pullRequest/merge")
def merge_pr(payload: PRMergeRequest):
    pr = pull_requests.get(payload.pull_request_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    if pr["status"] == "MERGED":
        raise HTTPException(status_code=400, detail="PR is already merged")
    pr["status"] = "MERGED"
    return {"pr": pr}

@app.post("/pullRequest/reassign")
def reassign_pr(payload: PRReassignRequest):
    pr = pull_requests.get(payload.pull_request_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found")
    if pr["status"] == "MERGED":
        raise HTTPException(status_code=409, detail="Cannot reassign reviewers on merged PR")
    if payload.old_user_id not in pr["assigned_reviewers"]:
        raise HTTPException(status_code=409, detail="User is not assigned as reviewer")
    author = users[pr["author_id"]]
    team_members = teams.get(author["team_name"], [])
    candidates = [
        uid for uid in team_members
        if uid != pr["author_id"]
        and uid not in pr["assigned_reviewers"]
        and users.get(uid, {}).get("is_active", False)
    ]
    # Баг в первой версии: если кандидатов 0, random.choice(candidates) упадёт с IndexError (500)
    new_uid = random.choice(candidates)
    idx = pr["assigned_reviewers"].index(payload.old_user_id)
    pr["assigned_reviewers"][idx] = new_uid
    return {"pr": pr, "replaced_by": new_uid}

@app.get("/users/getReview")
def get_user_reviews(user_id: str):
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")
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
def get_team(team_name: str):
    if team_name not in teams:
        raise HTTPException(status_code=404, detail="Team not found")
    members = [users[uid] for uid in teams[team_name] if uid in users]
    return {"team_name": team_name, "members": members}
