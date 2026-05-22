"""Unit tests for kb.py - Contoso PMO knowledge base business logic.

Read tests use the real assets/contoso-pmo-dataset/ fixture files via DATA_DIR env var.
Write tests copy assets/contoso-pmo-dataset/ to tmp_path and patch kb.DATA_DIR.
No Azure credentials required.
"""

import json
import os
import shutil
from pathlib import Path

import pytest

# Point DATA_DIR at the real fixture data before importing kb
os.environ['DATA_DIR'] = str(Path(__file__).parents[3] / 'assets' / 'contoso-pmo-dataset')

import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'contoso-pmo-mcp'))
import kb  # noqa: E402


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_data(tmp_path):
    """Copy assets/contoso-pmo-dataset/ to a temp directory and point kb.DATA_DIR at it."""
    src = Path(__file__).parents[3] / 'assets' / 'contoso-pmo-dataset'
    dest = tmp_path / 'data'
    shutil.copytree(src, dest)
    original = kb.DATA_DIR
    original_writable = kb._writable
    kb.DATA_DIR = dest
    kb._writable = None
    yield dest
    kb.DATA_DIR = original
    kb._writable = original_writable


# ── Phase 1: Registry Reads ───────────────────────────────────────────────────

# Projects

def test_get_project_found():
    result = json.loads(kb.get_project('proj-001'))
    assert result['name'] == 'Project Aurora'


def test_get_project_not_found():
    result = json.loads(kb.get_project('proj-999'))
    assert 'error' in result


def test_list_projects_all():
    result = json.loads(kb.list_projects())
    assert len(result) == 3


def test_list_projects_status_active():
    result = json.loads(kb.list_projects(status='active'))
    assert len(result) == 2
    assert all(p['status'] == 'active' for p in result)


def test_list_projects_status_completed():
    result = json.loads(kb.list_projects(status='completed'))
    assert len(result) == 1
    assert result[0]['status'] == 'completed'


# People

def test_get_person_by_id():
    result = json.loads(kb.get_person(id='person-001'))
    assert result['name'] == 'Jane Smith'


def test_get_person_by_email():
    result = json.loads(kb.get_person(email='jane.smith@company.com'))
    assert result['name'] == 'Jane Smith'


def test_get_person_not_found():
    result = json.loads(kb.get_person(id='person-999'))
    assert 'error' in result


def test_list_people_all():
    result = json.loads(kb.list_people())
    assert len(result) == 10


def test_list_people_role_filter():
    result = json.loads(kb.list_people(role='project_manager'))
    assert len(result) == 2
    assert all(p['role'] == 'project_manager' for p in result)


# Meetings

def test_get_meeting_found():
    result = json.loads(kb.get_meeting('mtg-001'))
    assert result['project_id'] == 'proj-001'


def test_get_meeting_not_found():
    result = json.loads(kb.get_meeting('mtg-999'))
    assert 'error' in result


def test_list_meetings_all():
    result = json.loads(kb.list_meetings())
    assert len(result) == 8


def test_list_meetings_project_filter():
    result = json.loads(kb.list_meetings(project_id='proj-001'))
    assert len(result) == 4
    assert all(m['project_id'] == 'proj-001' for m in result)


def test_list_meetings_status_filter():
    result = json.loads(kb.list_meetings(status='scheduled'))
    assert len(result) == 2
    assert all(m['status'] == 'scheduled' for m in result)


# Tasks

def test_get_task_found():
    result = json.loads(kb.get_task('task-001'))
    assert result['project_id'] == 'proj-001'


def test_get_task_not_found():
    result = json.loads(kb.get_task('task-999'))
    assert 'error' in result


def test_list_tasks_all():
    result = json.loads(kb.list_tasks())
    assert len(result) == 15


def test_list_tasks_status_overdue():
    result = json.loads(kb.list_tasks(status='overdue'))
    assert len(result) == 3
    assert all(t['status'] == 'overdue' for t in result)


def test_list_tasks_approved_false():
    result = json.loads(kb.list_tasks(approved=False))
    assert len(result) == 2
    assert all(t['approved'] is False for t in result)


def test_list_tasks_project_filter():
    result = json.loads(kb.list_tasks(project_id='proj-001'))
    assert len(result) == 7
    assert all(t['project_id'] == 'proj-001' for t in result)


def test_list_tasks_assignee_filter():
    result = json.loads(kb.list_tasks(assignee_id='person-002'))
    assert len(result) >= 1
    assert all(t['assignee_id'] == 'person-002' for t in result)


# Risks

def test_list_risks_all():
    result = json.loads(kb.list_risks())
    assert len(result) == 6


def test_list_risks_project_filter():
    result = json.loads(kb.list_risks(project_id='proj-001'))
    assert len(result) == 3
    assert all(r['project_id'] == 'proj-001' for r in result)


def test_list_risks_gate_filter():
    result = json.loads(kb.list_risks(gate='G3'))
    assert len(result) > 0
    assert all(r['gate'] == 'G3' for r in result)


# Distribution lists

def test_get_distribution_list_found():
    result = json.loads(kb.get_distribution_list('dl-001'))
    assert 'members' in result
    assert len(result['members']) == len(result['member_ids'])
    # Each member object should have name, email, teams_id
    for m in result['members']:
        assert 'name' in m
        assert 'email' in m
        assert 'teams_id' in m


def test_get_distribution_list_not_found():
    result = json.loads(kb.get_distribution_list('dl-999'))
    assert 'error' in result


# ── Phase 2: Document Reads ───────────────────────────────────────────────────

def test_get_document_found():
    result = json.loads(kb.get_document('doc-001'))
    assert 'content' in result
    assert len(result['content']) > 0


def test_get_document_not_found():
    result = json.loads(kb.get_document('doc-999'))
    assert 'error' in result


def test_list_documents_all():
    result = json.loads(kb.list_documents())
    assert len(result) == 14
    assert all('content' not in d for d in result)


def test_list_documents_type_mom():
    result = json.loads(kb.list_documents(doc_type='mom'))
    assert len(result) == 4
    assert all(d['doc_type'] == 'mom' for d in result)


def test_list_documents_approved_false():
    result = json.loads(kb.list_documents(approved=False))
    assert len(result) == 1
    assert result[0]['id'] == 'doc-002'


def test_list_documents_project_filter():
    result = json.loads(kb.list_documents(project_id='proj-001'))
    assert len(result) == 8
    assert all(d['project_id'] == 'proj-001' for d in result)


def test_list_documents_tag_filter():
    result = json.loads(kb.list_documents(tags=['G3']))
    assert len(result) > 0
    assert all('G3' in d['tags'] for d in result)


def test_search_documents_basic():
    result = json.loads(kb.search_documents(query='packaging'))
    assert len(result) >= 1
    for doc in result:
        assert 'id' in doc
        assert 'content' in doc


def test_search_documents_type_filter():
    result = json.loads(kb.search_documents(query='risk', doc_type='lesson'))
    assert len(result) >= 1
    assert all(d['doc_type'] == 'lesson' for d in result)


# ── Phase 2: Cross-Cutting Queries ────────────────────────────────────────────

def test_get_pending_approvals():
    result = json.loads(kb.get_pending_approvals())
    assert 'tasks' in result
    assert 'documents' in result
    assert len(result['tasks']) == 2
    assert len(result['documents']) == 1
    assert all(t['approved'] is False for t in result['tasks'])
    assert all(d['approved'] is False for d in result['documents'])


def test_get_overdue_tasks():
    result = json.loads(kb.get_overdue_tasks())
    assert len(result) == 3
    assert all(t['status'] == 'overdue' for t in result)
    assert all(t['status'] != 'done' for t in result)


def test_get_project_context():
    result = json.loads(kb.get_project_context('proj-001'))
    assert 'project' in result
    assert 'tasks' in result
    assert 'documents' in result
    assert 'risks' in result
    # tasks are approved only
    assert all(t['approved'] is True for t in result['tasks'])
    # documents are metadata only (no content key)
    assert all('content' not in d for d in result['documents'])


def test_get_meeting_pack():
    result = json.loads(kb.get_meeting_pack('mtg-001'))
    assert 'meeting' in result
    assert 'mom' in result
    assert 'tasks' in result
    assert result['mom'] is not None
    assert result['mom']['id'] == 'doc-001'


def test_get_meeting_pack_no_mom():
    result = json.loads(kb.get_meeting_pack('mtg-003'))
    assert result['mom'] is None


def test_search_lessons():
    result = json.loads(kb.search_lessons())
    assert len(result) > 0
    assert all(d['doc_type'] == 'lesson' for d in result)
    assert all(d['approved'] is True for d in result)


def test_search_lessons_tag_filter():
    result = json.loads(kb.search_lessons(tags=['G3']))
    assert len(result) > 0
    assert all(d['doc_type'] == 'lesson' for d in result)
    assert all('G3' in d['tags'] for d in result)


def test_get_person_tasks():
    result = json.loads(kb.get_person_tasks('person-002'))
    assert len(result) >= 1
    assert all(t['assignee_id'] == 'person-002' for t in result)
    assert all(t['status'] in ['open', 'overdue'] for t in result)


def test_get_person_tasks_no_done():
    result = json.loads(kb.get_person_tasks('person-002'))
    assert all(t['status'] != 'done' for t in result)


def test_search_risk_patterns():
    result = json.loads(kb.search_risk_patterns(query='supplier'))
    assert 'risks' in result
    assert 'lessons' in result
    assert len(result['risks']) >= 1


# ── Phase 3: Write Operations ─────────────────────────────────────────────────

# Projects

def test_create_project(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.create_project(name='Project Delta', status='active', current_gate='G1'))
    assert result['id'] == 'proj-004'
    projects = json.loads(open(tmp_data / 'registry' / 'projects.json').read())
    assert len(projects) == 4


def test_update_project(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.update_project(id='proj-001', current_gate='G4'))
    assert result['current_gate'] == 'G4'
    projects = json.loads(open(tmp_data / 'registry' / 'projects.json').read())
    proj = next(p for p in projects if p['id'] == 'proj-001')
    assert proj['current_gate'] == 'G4'


# People

def test_create_person(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.create_person(
        name='Alice Wang', role='team_member', email='alice.wang@company.com',
        teams_id='alice.wang', function='Legal'
    ))
    assert result['id'] == 'person-011'
    people = json.loads(open(tmp_data / 'registry' / 'people.json').read())
    assert len(people) == 11


# Meetings

def test_create_meeting(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.create_meeting(
        project_id='proj-001', title='Aurora Sprint Review',
        date='2026-03-15', attendees=['person-001', 'person-002']
    ))
    assert result['id'] == 'mtg-009'
    assert result['status'] == 'scheduled'


def test_update_meeting_status(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.update_meeting_status(id='mtg-003', status='completed'))
    assert result['status'] == 'completed'
    meetings = json.loads(open(tmp_data / 'registry' / 'meetings.json').read())
    mtg = next(m for m in meetings if m['id'] == 'mtg-003')
    assert mtg['status'] == 'completed'


# Tasks

def test_create_task_defaults_unapproved(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.create_task(
        project_id='proj-001', description='Foo',
        assignee_id='person-002', due_date='2026-03-01', source='manual'
    ))
    assert result['id'] == 'task-016'
    assert result['approved'] is False
    assert result['status'] == 'open'


def test_create_task_with_depends_on(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.create_task(
        project_id='proj-001', description='Bar',
        assignee_id='person-002', due_date='2026-03-01', source='manual',
        depends_on=['task-001']
    ))
    assert 'task-001' in result['depends_on']


def test_approve_task(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.approve_task(id='task-006'))
    assert result['approved'] is True
    tasks = json.loads(open(tmp_data / 'registry' / 'tasks.json').read())
    task = next(t for t in tasks if t['id'] == 'task-006')
    assert task['approved'] is True


def test_update_task_status(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.update_task_status(id='task-001', status='done'))
    assert result['status'] == 'done'


def test_reassign_task(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.reassign_task(id='task-001', assignee_id='person-003'))
    assert result['assignee_id'] == 'person-003'


def test_delete_task(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.delete_task(id='task-006'))
    assert result == {'deleted': 'task-006'}
    tasks = json.loads(open(tmp_data / 'registry' / 'tasks.json').read())
    assert len(tasks) == 14
    assert all(t['id'] != 'task-006' for t in tasks)


def test_delete_task_not_found(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.delete_task(id='task-999'))
    assert 'error' in result


# Risks

def test_flag_risk(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.flag_risk(
        project_id='proj-001', source_type='task', source_id='task-001',
        description='Late delivery risk', gate='G3', function='Procurement'
    ))
    assert result['id'] == 'risk-007'
    risks = json.loads(open(tmp_data / 'registry' / 'risks.json').read())
    assert len(risks) == 7


# Documents

def test_save_document_defaults_unapproved(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.save_document(
        project_id='proj-001', doc_type='mom', title='Test MoM',
        tags=['G3'], content='Test content', meeting_id=None
    ))
    assert result['id'] == 'doc-015'
    assert result['approved'] is False
    # Index should have 15 entries
    index = json.loads(open(tmp_data / 'documents' / 'index.json').read())
    assert len(index) == 15
    # Content file should exist
    content_file = tmp_data / 'documents' / 'doc-015.json'
    assert content_file.exists()


def test_approve_document(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.approve_document(id='doc-002'))
    assert result['approved'] is True
    index = json.loads(open(tmp_data / 'documents' / 'index.json').read())
    doc = next(d for d in index if d['id'] == 'doc-002')
    assert doc['approved'] is True


def test_update_document(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.update_document(id='doc-001', content='Updated content', tags=['G3', 'updated']))
    assert result['tags'] == ['G3', 'updated']
    content_file = json.loads(open(tmp_data / 'documents' / 'doc-001.json').read())
    assert content_file['content'] == 'Updated content'


def test_delete_document(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.delete_document(id='doc-002'))
    assert result == {'deleted': 'doc-002'}
    index = json.loads(open(tmp_data / 'documents' / 'index.json').read())
    assert len(index) == 13
    assert not (tmp_data / 'documents' / 'doc-002.json').exists()


# Distribution lists

def test_create_distribution_list(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.create_distribution_list(
        project_id='proj-001', name='Aurora Extended',
        member_ids=['person-001', 'person-006']
    ))
    assert result['id'] == 'dl-005'
    lists = json.loads(open(tmp_data / 'registry' / 'distribution_lists.json').read())
    assert len(lists) == 5


def test_update_distribution_list_add(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.update_distribution_list(id='dl-001', add_member_ids=['person-009']))
    assert 'person-009' in result['member_ids']
    assert len(result['member_ids']) == 6


def test_update_distribution_list_remove(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    result = json.loads(kb.update_distribution_list(id='dl-001', remove_member_ids=['person-002']))
    assert 'person-002' not in result['member_ids']


# _get_writable_dir behaviour

def test_writable_dir_returns_data_dir_when_writable(tmp_data, monkeypatch):
    monkeypatch.setattr(kb, 'DATA_DIR', tmp_data)
    monkeypatch.setattr(kb, '_writable', None)
    result = kb._get_writable_dir()
    assert result == tmp_data
