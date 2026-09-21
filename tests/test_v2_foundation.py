from __future__ import annotations

from fastapi.testclient import TestClient

from backend.agent_manager import AgentManager
from backend.api import create_app
from backend.desktop_simulator import DesktopSimulator
from backend.memory_store import MemoryStore
from backend.skill_loader import SkillLoader
from backend.supervisor import Supervisor
from backend.task_queue import TaskQueue
from backend.workflow_registry import WorkflowRegistry
from core.agent_supervisor import AgentSupervisor
from core.skill_manager import SkillManager
from core.self_repair import SelfRepair


def test_skill_loader_discovers_skills(tmp_path):
    skill_root = tmp_path / 'skills'
    skill_root.mkdir()
    (skill_root / 'summarize_skill.py').write_text('print(\"ok\")\n', encoding='utf-8')
    loader = SkillLoader(root=str(skill_root))
    skills = loader.discover()
    assert len(skills) == 1
    assert skills[0].name == 'summarize_skill'


def test_supervisor_requires_confirmation():
    supervisor = Supervisor()
    decision = supervisor.evaluate({'kind': 'delete_file'})
    assert decision['status'] == 'pending_confirmation'
    assert supervisor.confirm('task-1', True)['status'] == 'confirmed'


def test_task_queue_and_memory_store():
    queue = TaskQueue(maxsize=8)
    task = queue.enqueue('desktop', {'target': 'browser'})
    assert task.kind == 'desktop'
    assert queue.pending()
    memory = MemoryStore(storage_path='tests/.tmp_memory.json')
    memory.set('session:status', {'safe_mode': True})
    assert memory.get('session:status')['safe_mode'] is True


def test_workflow_registry_and_desktop_simulation():
    registry = WorkflowRegistry()
    workflow = registry.execute('desktop', {'target': 'browser'})
    assert workflow['status'] == 'simulated'
    simulator = DesktopSimulator()
    assert simulator.open_app('browser')['status'] == 'simulated'


def test_fastapi_endpoints():
    client = TestClient(create_app())
    health = client.get('/health')
    assert health.status_code == 200
    assert health.json()['service'] == 'jarvis-v2'

    status = client.get('/status')
    assert status.status_code == 200
    assert status.json()['safe_mode'] is True

    task = client.post('/tasks', json={'kind': 'desktop', 'payload': {'target': 'browser'}})
    assert task.status_code == 200
    body = task.json()
    assert body['status'] in {'queued', 'pending_confirmation'}

    events = client.get('/events')
    assert events.status_code == 200
    assert 'text/event-stream' in events.headers['content-type']


def test_agent_manager_assigns_safe_agents():
    manager = AgentManager()
    assignment = manager.assign_task('task-1', 'desktop')
    assert assignment['status'] == 'assigned'
    assert assignment['agent']['role'] == 'operator'

    verifier = manager.get_agent('verifier')
    assert verifier is not None
    assert verifier.role == 'verifier'
    manager.set_status('verifier', 'busy')
    assert manager.get_agent('verifier').status == 'busy'


def test_runtime_uses_one_memory_and_known_capabilities_are_not_missing():
    app = create_app()
    assert app.state.memory is app.state.brain.memory
    routing = app.state.agent_manager.route_prompt('öffne TradingView')
    assert routing['missing_capabilities'] == []
    assert routing['analysis']['recovery_plan'] == []


def test_capability_diagnosis_is_explicit():
    client = TestClient(create_app())
    response = client.post('/capabilities/diagnose', json={'prompt': 'analysiere ein youtube video'})
    assert response.status_code == 200
    body = response.json()
    assert body['diagnosis']['will_claim_success_without_verification'] is False
    assert body['diagnosis']['missing_capabilities'] == []


def test_diagnostics_reports_canonical_runtime():
    client = TestClient(create_app())
    response = client.get('/diagnostics')
    assert response.status_code == 200
    assert response.json()['checks'][0]['name'] == 'canonical_memory'
    assert response.json()['checks'][0]['ok'] is True


def test_workflow_rejects_unverified_handler_result():
    registry = WorkflowRegistry(research_handler=lambda query: None)
    result = registry.execute('research', {'query': 'test'})
    assert result['status'] == 'failed'
    assert result['error'] == 'unverified_result'


def test_confirmed_task_dispatches_once():
    client = TestClient(create_app())
    queued = client.post('/tasks', json={
        'kind': 'desktop',
        'payload': {'action': 'status'},
        'requires_confirmation': True,
    }).json()
    assert queued['status'] == 'pending_confirmation'
    confirmed = client.post(
        f"/tasks/{queued['task_id']}/confirm",
        json={'approved': True},
    ).json()
    assert confirmed['status'] == 'completed'
    repeated = client.post(
        f"/tasks/{queued['task_id']}/confirm",
        json={'approved': True},
    ).json()
    assert repeated['status'] == 'not_pending'


def test_capability_readiness_is_explicit():
    client = TestClient(create_app())
    body = client.get('/capabilities').json()
    assert 'readiness' in body
    assert body['readiness']['browser']['status'] in {'ready', 'missing'}


def test_capability_repair_requires_confirmation():
    app = create_app()
    client = TestClient(app)
    app.state.pending_capability_repairs['repair-test'] = {
        'prompt': 'öffne eine unbekannte browser app',
        'preflight': {'missing': ['example-adapter']},
    }
    response = client.post('/capabilities/repair', json={
        'repair_id': 'repair-test',
        'confirmed': False,
    })
    assert response.status_code == 200
    assert response.json()['status'] == 'cancelled'


def test_capability_repair_retries_original_request(monkeypatch):
    app = create_app()
    client = TestClient(app)
    app.state.pending_capability_repairs['repair-retry'] = {
        'prompt': 'öffne eine unbekannte browser app',
        'preflight': {'missing': ['example-adapter']},
        'source': 'test',
        'team': False,
    }
    monkeypatch.setattr(
        app.state.brain.agent_supervisor,
        'prepare',
        lambda request: {
            'ok': True,
            'verified': True,
            'capability': 'browser',
            'installed': True,
        },
    )
    response = client.post('/capabilities/repair', json={
        'repair_id': 'repair-retry',
        'confirmed': True,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'completed'
    assert body['retry_status'] in {'needs_clarification', 'completed', 'failed'}
    assert 'retry' in body


def test_team_provider_path_uses_public_text_request():
    from core.brain import JarvisBrain
    brain = JarvisBrain()
    assert callable(brain.request_text)


def test_skill_manager_never_installs_during_preflight(monkeypatch):
    manager = SkillManager()
    calls = []
    monkeypatch.setattr(
        AgentSupervisor,
        "diagnose_request",
        lambda self, request: {
            "ok": False,
            "capability": "browser",
            "required": ["playwright"],
            "missing": ["playwright"],
            "installed": [],
            "verified": False,
        },
    )
    monkeypatch.setattr(
        AgentSupervisor,
        "_install",
        lambda self, packages: calls.append(packages),
    )

    result = manager.preflight("öffne eine Webseite", install_missing=True)

    assert result["missing"] == ["playwright"]
    assert calls == []


def test_agent_supervisor_repair_verifies_success(monkeypatch):
    supervisor = AgentSupervisor()
    supervisor.config["enabled"] = True
    supervisor.config["auto_install_safe_dependencies"] = True
    availability = iter((False, True))
    monkeypatch.setattr(
        supervisor,
        "_imports_available",
        lambda imports: next(availability),
    )
    installed = []
    monkeypatch.setattr(
        supervisor,
        "_install",
        lambda packages: (installed.extend(packages) or (True, "ok")),
    )
    monkeypatch.setattr(
        supervisor,
        "diagnose_request",
        lambda request: {
            "ok": False,
            "capability": "browser",
            "required": ["playwright"],
            "missing": ["playwright"],
            "installed": [],
            "verified": False,
        },
    )

    result = supervisor.prepare("öffne eine Webseite")

    assert result["ok"] is True
    assert result["verified"] is True
    assert installed == ["playwright"]


def test_chat_does_not_claim_video_analysis_without_target():
    client = TestClient(create_app())
    response = client.post(
        "/chat",
        json={"prompt": "analysiere ein youtube video", "source": "test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_clarification"
    assert "Link" in body["response"]


def test_chat_handles_greeting_with_capability_question():
    client = TestClient(create_app())
    response = client.post(
        "/chat",
        json={"prompt": "Hi Jarvis, was kannst du alles?", "source": "test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert "Fragen beantworten" in body["response"]


def test_chat_routes_knowledge_questions_to_brain(monkeypatch):
    app = create_app()
    client = TestClient(app)
    monkeypatch.setattr(
        app.state.brain,
        "ask",
        lambda prompt: "Bitcoin ist ein digitales, dezentrales Zahlungssystem.",
    )
    response = client.post(
        "/chat",
        json={"prompt": "Erkläre mir Bitcoin", "source": "test"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert "Bitcoin" in response.json()["response"]


def test_chat_does_not_use_action_recovery_for_questions(monkeypatch):
    app = create_app()
    client = TestClient(app)
    monkeypatch.setattr(
        app.state.brain,
        "ask",
        lambda prompt: "Der Himmel erscheint blau durch die Streuung des Sonnenlichts.",
    )
    response = client.post(
        "/chat",
        json={"prompt": "Warum ist der Himmel blau?", "source": "test"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert "Streuung" in response.json()["response"]


def test_chat_normalizes_greeting_with_jarvis_name():
    client = TestClient(create_app())
    response = client.post(
        "/chat",
        json={"prompt": "Hallo Jarvis", "source": "test"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert "da" in response.json()["response"]


def test_self_repair_records_errors_in_canonical_memory(tmp_path):
    memory = MemoryStore(storage_path=str(tmp_path / "memory.json"))
    repair = SelfRepair(project_root=tmp_path, memory=memory)
    repair.record_issue("test request", "test error")
    assert memory.get("errors")[0]["source"] == "self_repair"


def test_github_chat_creates_confirmable_import_plan(monkeypatch):
    app = create_app()
    client = TestClient(app)
    analysis = {
        "ok": True,
        "source": "https://github.com/example/repo",
        "owner": "example",
        "repository": "repo",
        "license": "MIT",
        "risk": "medium",
        "requires_confirmation": True,
    }
    monkeypatch.setattr(app.state.github_importer, "analyze", lambda url: analysis)
    response = client.post(
        "/chat",
        json={"prompt": "prüfe https://github.com/example/repo", "source": "test"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "github_confirmation_required"
    assert body["requires_confirmation"] is True
    assert body["plan_id"] in app.state.github_import_plans


def test_github_import_requires_confirmation_and_expires(monkeypatch):
    app = create_app()
    client = TestClient(app)
    analysis = {
        "ok": True,
        "source": "https://github.com/example/repo",
        "owner": "example",
        "repository": "repo",
        "default_branch": "main",
        "license": "MIT",
        "risk": "medium",
        "requires_confirmation": True,
    }
    monkeypatch.setattr(app.state.github_importer, "analyze", lambda url: analysis)
    planned = client.post("/github/analyze", json={"url": analysis["source"]}).json()
    cancelled = client.post(
        "/github/confirm",
        json={"plan_id": planned["plan_id"], "confirmed": False},
    )
    assert cancelled.json()["status"] == "cancelled"
    expired = client.post(
        "/github/confirm",
        json={"plan_id": planned["plan_id"], "confirmed": True},
    )
    assert expired.status_code == 404
