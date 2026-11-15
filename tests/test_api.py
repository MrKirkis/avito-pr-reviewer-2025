import pytest
from fastapi.testclient import TestClient
from main import app, teams, users, pull_requests

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_state():
    teams.clear()
    users.clear()
    pull_requests.clear()

def test_full_lifecycle_happy_path():
    # 1. Создаём команду из 4 участников
    r = client.post("/team/add", json={
        "team_name": "payments",
        "members": [
            {"user_id": "u1", "username": "Alice", "is_active": True},
            {"user_id": "u2", "username": "Bob", "is_active": True},
            {"user_id": "u3", "username": "Charlie", "is_active": True},
            {"user_id": "u4", "username": "Dave", "is_active": True},
        ]
    })
    assert r.status_code == 201

    # 2. Создаём PR от u1 -> назначаются 2 активных ревьюера (не u1)
    r_pr = client.post("/pullRequest/create", json={
        "pull_request_id": "pr-100",
        "pull_request_name": "Add payment gateway",
        "author_id": "u1"
    })
    assert r_pr.status_code == 201
    pr_data = r_pr.json()["pr"]
    assert pr_data["status"] == "OPEN"
    assert len(pr_data["assigned_reviewers"]) == 2
    assert "u1" not in pr_data["assigned_reviewers"]

    # 3. Переназначаем одного из ревьюеров на оставшегося свободного участника
    old_rev = pr_data["assigned_reviewers"][0]
    r_re = client.post("/pullRequest/reassign", json={
        "pull_request_id": "pr-100",
        "old_user_id": old_rev
    })
    assert r_re.status_code == 200
    new_rev = r_re.json()["replaced_by"]
    assert new_rev != old_rev
    assert new_rev != "u1"

    # 4. Проверяем список PR на ревью для нового ревьюера
    r_list = client.get("/users/getReview", params={"user_id": new_rev})
    assert r_list.status_code == 200
    assert len(r_list.json()["pull_requests"]) == 1

    # 5. Merge PR (и проверка идемпотентности при повторном вызове)
    r_m1 = client.post("/pullRequest/merge", json={"pull_request_id": "pr-100"})
    assert r_m1.status_code == 200
    merged_at_1 = r_m1.json()["pr"]["mergedAt"]
    assert r_m1.json()["pr"]["status"] == "MERGED"

    r_m2 = client.post("/pullRequest/merge", json={"pull_request_id": "pr-100"})
    assert r_m2.status_code == 200
    assert r_m2.json()["pr"]["mergedAt"] == merged_at_1

    # 6. После MERGED переназначение запрещено (409)
    r_re_after = client.post("/pullRequest/reassign", json={
        "pull_request_id": "pr-100",
        "old_user_id": new_rev
    })
    assert r_re_after.status_code == 409

def test_single_member_team_and_no_candidate_conflict():
    # Команда с 1 автором и 1 ревьюером (запасных кандидатов для замены нет)
    client.post("/team/add", json={
        "team_name": "solo",
        "members": [
            {"user_id": "u1", "username": "Author", "is_active": True},
            {"user_id": "u2", "username": "OnlyReviewer", "is_active": True},
        ]
    })
    r_pr = client.post("/pullRequest/create", json={
        "pull_request_id": "pr-200",
        "pull_request_name": "Solo feature",
        "author_id": "u1"
    })
    assert r_pr.status_code == 201
    assert r_pr.json()["pr"]["assigned_reviewers"] == ["u2"]

    # Попытка переназначить u2, когда других кандидатов нет -> 409 NO_CANDIDATE (не 500!)
    r_re = client.post("/pullRequest/reassign", json={
        "pull_request_id": "pr-200",
        "old_user_id": "u2"
    })
    assert r_re.status_code == 409
    assert r_re.json()["detail"]["error"]["code"] == "NO_CANDIDATE"

def test_inactive_user_not_assigned():
    client.post("/team/add", json={
        "team_name": "core",
        "members": [
            {"user_id": "u1", "username": "Author", "is_active": True},
            {"user_id": "u2", "username": "InactiveBob", "is_active": False},
        ]
    })
    r_pr = client.post("/pullRequest/create", json={
        "pull_request_id": "pr-300",
        "pull_request_name": "Check active flag",
        "author_id": "u1"
    })
    assert r_pr.status_code == 201
    assert r_pr.json()["pr"]["assigned_reviewers"] == []
