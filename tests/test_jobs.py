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


# --- Trigger endpoint tests ---


async def test_trigger_job(client):
    """POST /jobs/{id}/trigger creates a pending run."""
    create_resp = await client.post("/jobs", json={
        "name": "trigger-me",
        "command": "scripts/hello.py",
        "cron_expression": "0 * * * *",
    })
    job_id = create_resp.json()["id"]

    trigger_resp = await client.post(f"/jobs/{job_id}/trigger")
    assert trigger_resp.status_code == 201
    data = trigger_resp.json()
    assert data["id"] is not None
    assert data["status"] == "PENDING"


async def test_trigger_job_not_found(client):
    """POST /jobs/{id}/trigger with non-existent job returns 404."""
    response = await client.post("/jobs/00000000-0000-0000-0000-000000000000/trigger")
    assert response.status_code == 404


async def test_trigger_inactive_job(client):
    """POST /jobs/{id}/trigger on a deleted job returns 409."""
    # Create and delete (soft)
    create_resp = await client.post("/jobs", json={
        "name": "inactive-trigger-test",
        "command": "scripts/hello.py",
        "cron_expression": "0 * * * *",
    })
    job_id = create_resp.json()["id"]
    await client.delete(f"/jobs/{job_id}")

    # Try to trigger the inactive job
    trigger_resp = await client.post(f"/jobs/{job_id}/trigger")
    assert trigger_resp.status_code == 409
    assert "not active" in trigger_resp.json()["detail"]


async def test_trigger_job_multiple_times(client):
    """Multiple triggers create independent runs."""
    create_resp = await client.post("/jobs", json={
        "name": "multi-trigger",
        "command": "scripts/hello.py",
        "cron_expression": "0 * * * *",
    })
    job_id = create_resp.json()["id"]

    resp1 = await client.post(f"/jobs/{job_id}/trigger")
    resp2 = await client.post(f"/jobs/{job_id}/trigger")

    assert resp1.status_code == 201
    assert resp2.status_code == 201
    assert resp1.json()["id"] != resp2.json()["id"]


# --- Observability endpoint tests ---


async def test_list_job_runs_empty(client):
    """GET /jobs/{id}/runs with no runs returns empty paginated response."""
    create_resp = await client.post("/jobs", json={
        "name": "no-runs-job",
        "command": "scripts/hello.py",
        "cron_expression": "0 * * * *",
    })
    job_id = create_resp.json()["id"]

    response = await client.get(f"/jobs/{job_id}/runs")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


async def test_list_job_runs_with_triggers(client):
    """GET /jobs/{id}/runs shows triggered runs."""
    create_resp = await client.post("/jobs", json={
        "name": "runs-job",
        "command": "scripts/hello.py",
        "cron_expression": "0 * * * *",
    })
    job_id = create_resp.json()["id"]

    # Trigger 3 runs
    await client.post(f"/jobs/{job_id}/trigger")
    await client.post(f"/jobs/{job_id}/trigger")
    await client.post(f"/jobs/{job_id}/trigger")

    response = await client.get(f"/jobs/{job_id}/runs")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    # All should be PENDING and MANUAL
    for item in data["items"]:
        assert item["status"] == "PENDING"
        assert item["source"] == "MANUAL"


async def test_list_job_runs_pagination(client):
    """GET /jobs/{id}/runs respects page_size."""
    create_resp = await client.post("/jobs", json={
        "name": "paginated-job",
        "command": "scripts/hello.py",
        "cron_expression": "0 * * * *",
    })
    job_id = create_resp.json()["id"]

    # Trigger 5 runs
    for _ in range(5):
        await client.post(f"/jobs/{job_id}/trigger")

    # Request page_size=2
    response = await client.get(f"/jobs/{job_id}/runs?page_size=2&page=1")
    data = response.json()
    assert len(data["items"]) == 2
    assert data["total"] == 5
    assert data["page_size"] == 2


async def test_list_job_runs_job_not_found(client):
    """GET /jobs/{id}/runs with non-existent job returns 404."""
    response = await client.get("/jobs/00000000-0000-0000-0000-000000000000/runs")
    assert response.status_code == 404


async def test_get_single_run(client):
    """GET /jobs/{id}/runs/{run_id} returns run details."""
    create_resp = await client.post("/jobs", json={
        "name": "single-run-job",
        "command": "scripts/hello.py",
        "cron_expression": "0 * * * *",
    })
    job_id = create_resp.json()["id"]

    trigger_resp = await client.post(f"/jobs/{job_id}/trigger")
    run_id = trigger_resp.json()["id"]

    response = await client.get(f"/jobs/{job_id}/runs/{run_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == run_id
    assert data["job_id"] == job_id
    assert data["status"] == "PENDING"
    assert data["source"] == "MANUAL"


async def test_get_single_run_not_found(client):
    """GET /jobs/{id}/runs/{run_id} with bad run_id returns 404."""
    create_resp = await client.post("/jobs", json={
        "name": "run-404-job",
        "command": "scripts/hello.py",
        "cron_expression": "0 * * * *",
    })
    job_id = create_resp.json()["id"]

    response = await client.get(f"/jobs/{job_id}/runs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# --- Health endpoint tests ---


async def test_health_returns_degraded_no_workers(client):
    """GET /health returns 503 when no workers are registered."""
    response = await client.get("/health")
    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "connected"
    assert data["healthy_worker_count"] == 0
