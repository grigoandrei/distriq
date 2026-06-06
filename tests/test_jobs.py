"""Tests for the /jobs API endpoints."""

import pytest


async def test_create_job(client):
    """POST /jobs with valid data returns 201 and the job details."""
    response = await client.post("/jobs", json={
        "name": "my-test-job",
        "command": "scripts/hello.py",
        "cron_expression": "*/5 * * * *",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "my-test-job"
    assert data["command"] == "scripts/hello.py"
    assert data["is_active"] is True
    assert data["retry_count"] == 3
    assert data["next_run_time"] is not None


async def test_create_job_with_custom_retry(client):
    """POST /jobs with custom retry config stores it correctly."""
    response = await client.post("/jobs", json={
        "name": "custom-retry-job",
        "command": "scripts/task.py",
        "cron_expression": "0 * * * *",
        "retry_count": 5,
        "base_delay_seconds": 120,
        "max_delay_seconds": 7200,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["retry_count"] == 5
    assert data["base_delay_seconds"] == 120
    assert data["max_delay_seconds"] == 7200


async def test_create_duplicate_job(client):
    """POST /jobs with a duplicate name returns 409."""
    payload = {
        "name": "dupe-job",
        "command": "scripts/hello.py",
        "cron_expression": "0 * * * *",
    }
    await client.post("/jobs", json=payload)
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


async def test_create_job_invalid_name(client):
    """POST /jobs with invalid name characters returns 422."""
    response = await client.post("/jobs", json={
        "name": "invalid name!",
        "command": "scripts/hello.py",
        "cron_expression": "*/5 * * * *",
    })
    assert response.status_code == 422


async def test_create_job_invalid_cron(client):
    """POST /jobs with invalid cron expression returns 422."""
    response = await client.post("/jobs", json={
        "name": "bad-cron",
        "command": "scripts/hello.py",
        "cron_expression": "not a cron",
    })
    assert response.status_code == 422


async def test_create_job_invalid_command(client):
    """POST /jobs with non-.py command returns 422."""
    response = await client.post("/jobs", json={
        "name": "bad-command",
        "command": "scripts/hello.sh",
        "cron_expression": "*/5 * * * *",
    })
    assert response.status_code == 422


async def test_create_job_missing_fields(client):
    """POST /jobs with missing required fields returns 422."""
    response = await client.post("/jobs", json={
        "name": "no-command",
    })
    assert response.status_code == 422


async def test_list_jobs(client):
    """GET /jobs returns all created jobs."""
    await client.post("/jobs", json={
        "name": "job-one",
        "command": "scripts/one.py",
        "cron_expression": "0 * * * *",
    })
    await client.post("/jobs", json={
        "name": "job-two",
        "command": "scripts/two.py",
        "cron_expression": "0 * * * *",
    })

    response = await client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    names = {job["name"] for job in data}
    assert names == {"job-one", "job-two"}


async def test_get_job(client):
    """GET /jobs/{id} returns the correct job."""
    create_resp = await client.post("/jobs", json={
        "name": "findable-job",
        "command": "scripts/find.py",
        "cron_expression": "*/10 * * * *",
    })
    job_id = create_resp.json()["id"]

    response = await client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "findable-job"


async def test_get_job_not_found(client):
    """GET /jobs/{id} with non-existent ID returns 404."""
    response = await client.get("/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_delete_job(client):
    """DELETE /jobs/{id} sets is_active to false."""
    create_resp = await client.post("/jobs", json={
        "name": "to-delete",
        "command": "scripts/cleanup.py",
        "cron_expression": "0 0 * * *",
    })
    job_id = create_resp.json()["id"]

    del_resp = await client.delete(f"/jobs/{job_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["is_active"] is False

    # Verify it persists
    get_resp = await client.get(f"/jobs/{job_id}")
    assert get_resp.json()["is_active"] is False


async def test_delete_job_not_found(client):
    """DELETE /jobs/{id} with non-existent ID returns 404."""
    response = await client.delete("/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
