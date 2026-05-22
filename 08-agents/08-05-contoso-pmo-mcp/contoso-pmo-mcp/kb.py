"""Contoso PMO Knowledge Base - business logic layer.

All functions return JSON strings. Read operations use DATA_DIR directly.
Write operations use _get_writable_dir() which lazily copies the bundled
read-only data to /tmp/contoso-pmo-data/ on first write in Azure.
"""

import json
import os
import shutil
from datetime import date
from pathlib import Path

# DATA_DIR - set via env var; defaults to assets/contoso-pmo-dataset relative to this file's location
DATA_DIR: Path = Path(os.environ.get(
    'DATA_DIR',
    str(Path(__file__).parent / '..' / '..' / '..' / 'assets' / 'contoso-pmo-dataset')
))

# Module-level cache for the writable directory
_writable: Path | None = None


# ── Internal helpers ──────────────────────────────────────────────────────────


def _load(path: Path) -> list:
    with open(path) as f:
        return json.load(f)


def _save(path: Path, data) -> None:
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _get_writable_dir() -> Path:
    """Return a writable directory for data mutations.

    On first call: tests if DATA_DIR is writable. If so, returns DATA_DIR.
    If PermissionError/OSError, copies the entire tree to /tmp/contoso-pmo-data/
    and returns that path. Result is cached for the process lifetime.
    """
    global _writable
    if _writable is not None:
        return _writable
    test_file = DATA_DIR / '.write_test'
    try:
        test_file.touch()
        test_file.unlink()
        _writable = DATA_DIR
    except (PermissionError, OSError):
        dest = Path('/tmp/contoso-pmo-data')
        shutil.copytree(DATA_DIR, dest, dirs_exist_ok=True)
        _writable = dest
    return _writable


def _next_id(records: list, prefix: str) -> str:
    return f"{prefix}{len(records) + 1:03d}"


_STOP_WORDS = {
    'a', 'an', 'and', 'are', 'at', 'be', 'but', 'by', 'can', 'do', 'for',
    'from', 'has', 'had', 'in', 'is', 'it', 'its', 'not', 'of', 'on', 'or',
    'our', 'that', 'the', 'this', 'to', 'was', 'with', 'any', 'all',
}


def _match_query(text: str, query: str) -> bool:
    """Return True if any significant word from query appears in text (case-insensitive).

    Tokenises query on whitespace, strips punctuation, drops stop words and tokens
    shorter than 3 characters, then checks whether any remaining token is a substring
    of text.  Falls back to a plain substring check when no significant tokens remain.
    """
    t = text.lower()
    words = [w.strip('.,;:!?()[]"\'') for w in query.lower().split()]
    words = [w for w in words if len(w) >= 3 and w not in _STOP_WORDS]
    if not words:
        return query.lower() in t
    return any(w in t for w in words)


# ── Phase 1: Registry reads ───────────────────────────────────────────────────

# Projects

def get_project(id: str) -> str:
    records = _load(DATA_DIR / 'registry' / 'projects.json')
    record = next((r for r in records if r['id'] == id), None)
    if record is None:
        return json.dumps({'error': f'Project {id!r} not found'})
    return json.dumps(record)


def list_projects(status: str = None) -> str:
    records = _load(DATA_DIR / 'registry' / 'projects.json')
    if status is not None:
        records = [r for r in records if r.get('status') == status]
    return json.dumps(records)


# People

def get_person(id: str = None, email: str = None) -> str:
    records = _load(DATA_DIR / 'registry' / 'people.json')
    if id is not None:
        record = next((r for r in records if r['id'] == id), None)
    elif email is not None:
        record = next((r for r in records if r.get('email') == email), None)
    else:
        return json.dumps({'error': 'Must provide id or email'})
    if record is None:
        return json.dumps({'error': f'Person not found'})
    return json.dumps(record)


def list_people(role: str = None) -> str:
    records = _load(DATA_DIR / 'registry' / 'people.json')
    if role is not None:
        records = [r for r in records if r.get('role') == role]
    return json.dumps(records)


# Meetings

def get_meeting(id: str) -> str:
    records = _load(DATA_DIR / 'registry' / 'meetings.json')
    record = next((r for r in records if r['id'] == id), None)
    if record is None:
        return json.dumps({'error': f'Meeting {id!r} not found'})
    return json.dumps(record)


def list_meetings(
    project_id: str = None,
    status: str = None,
    date_from: str = None,
    date_to: str = None,
) -> str:
    records = _load(DATA_DIR / 'registry' / 'meetings.json')
    if project_id is not None:
        records = [r for r in records if r.get('project_id') == project_id]
    if status is not None:
        records = [r for r in records if r.get('status') == status]
    if date_from is not None:
        records = [r for r in records if r.get('date', '') >= date_from]
    if date_to is not None:
        records = [r for r in records if r.get('date', '') <= date_to]
    return json.dumps(records)


# Tasks

def get_task(id: str) -> str:
    records = _load(DATA_DIR / 'registry' / 'tasks.json')
    record = next((r for r in records if r['id'] == id), None)
    if record is None:
        return json.dumps({'error': f'Task {id!r} not found'})
    return json.dumps(record)


def list_tasks(
    project_id: str = None,
    assignee_id: str = None,
    status: str = None,
    approved: bool = None,
    due_date_from: str = None,
    due_date_to: str = None,
) -> str:
    records = _load(DATA_DIR / 'registry' / 'tasks.json')
    if project_id is not None:
        records = [r for r in records if r.get('project_id') == project_id]
    if assignee_id is not None:
        records = [r for r in records if r.get('assignee_id') == assignee_id]
    if status is not None:
        records = [r for r in records if r.get('status') == status]
    if approved is not None:
        records = [r for r in records if r.get('approved') == approved]
    if due_date_from is not None:
        records = [r for r in records if r.get('due_date', '') >= due_date_from]
    if due_date_to is not None:
        records = [r for r in records if r.get('due_date', '') <= due_date_to]
    return json.dumps(records)


# Risks

def list_risks(
    project_id: str = None,
    gate: str = None,
    function: str = None,
) -> str:
    records = _load(DATA_DIR / 'registry' / 'risks.json')
    if project_id is not None:
        records = [r for r in records if r.get('project_id') == project_id]
    if gate is not None:
        records = [r for r in records if r.get('gate') == gate]
    if function is not None:
        records = [r for r in records if r.get('function') == function]
    return json.dumps(records)


# Distribution lists

def get_distribution_list(id: str) -> str:
    records = _load(DATA_DIR / 'registry' / 'distribution_lists.json')
    record = next((r for r in records if r['id'] == id), None)
    if record is None:
        return json.dumps({'error': f'Distribution list {id!r} not found'})
    # Resolve member_ids to full person objects
    people = _load(DATA_DIR / 'registry' / 'people.json')
    people_index = {p['id']: p for p in people}
    members = [people_index[mid] for mid in record['member_ids'] if mid in people_index]
    result = dict(record)
    result['members'] = members
    return json.dumps(result)


# ── Phase 2: Document reads ───────────────────────────────────────────────────

def get_document(id: str) -> str:
    index = _load(DATA_DIR / 'documents' / 'index.json')
    meta = next((d for d in index if d['id'] == id), None)
    if meta is None:
        return json.dumps({'error': f'Document {id!r} not found'})
    content_path = DATA_DIR / 'documents' / f'{id}.json'
    if content_path.exists():
        doc = _load(content_path)
    else:
        doc = dict(meta)
    return json.dumps(doc)


def list_documents(
    doc_type: str = None,
    project_id: str = None,
    tags: list = None,
    approved: bool = None,
    date_from: str = None,
    date_to: str = None,
) -> str:
    records = _load(DATA_DIR / 'documents' / 'index.json')
    if doc_type is not None:
        records = [r for r in records if r.get('doc_type') == doc_type]
    if project_id is not None:
        records = [r for r in records if r.get('project_id') == project_id]
    if tags is not None:
        records = [r for r in records if any(t in r.get('tags', []) for t in tags)]
    if approved is not None:
        records = [r for r in records if r.get('approved') == approved]
    if date_from is not None:
        records = [r for r in records if r.get('created_at', '') >= date_from]
    if date_to is not None:
        records = [r for r in records if r.get('created_at', '') <= date_to]
    return json.dumps(records)


def search_documents(
    query: str,
    doc_type: str = None,
    project_id: str = None,
    tags: list = None,
    date_from: str = None,
    date_to: str = None,
) -> str:
    index = _load(DATA_DIR / 'documents' / 'index.json')
    if doc_type is not None:
        index = [r for r in index if r.get('doc_type') == doc_type]
    if project_id is not None:
        index = [r for r in index if r.get('project_id') == project_id]
    if tags is not None:
        index = [r for r in index if any(t in r.get('tags', []) for t in tags)]
    if date_from is not None:
        index = [r for r in index if r.get('created_at', '') >= date_from]
    if date_to is not None:
        index = [r for r in index if r.get('created_at', '') <= date_to]
    results = []
    for meta in index:
        content_path = DATA_DIR / 'documents' / f"{meta['id']}.json"
        if content_path.exists():
            doc = _load(content_path)
            haystack = doc.get('content', '') + ' ' + doc.get('title', '')
            if _match_query(haystack, query):
                results.append(doc)
    return json.dumps(results)


# ── Phase 2: Cross-cutting queries ────────────────────────────────────────────

def get_pending_approvals() -> str:
    tasks = _load(DATA_DIR / 'registry' / 'tasks.json')
    documents = _load(DATA_DIR / 'documents' / 'index.json')
    return json.dumps({
        'tasks': [t for t in tasks if not t.get('approved', True)],
        'documents': [d for d in documents if not d.get('approved', True)],
    })


def get_overdue_tasks() -> str:
    tasks = _load(DATA_DIR / 'registry' / 'tasks.json')
    return json.dumps([t for t in tasks if t.get('status') == 'overdue'])


def get_project_context(project_id: str) -> str:
    projects = _load(DATA_DIR / 'registry' / 'projects.json')
    project = next((p for p in projects if p['id'] == project_id), None)
    if project is None:
        return json.dumps({'error': f'Project {project_id!r} not found'})
    tasks = _load(DATA_DIR / 'registry' / 'tasks.json')
    approved_tasks = [t for t in tasks if t.get('project_id') == project_id and t.get('approved')]
    documents = _load(DATA_DIR / 'documents' / 'index.json')
    project_docs = [d for d in documents if d.get('project_id') == project_id]
    risks = _load(DATA_DIR / 'registry' / 'risks.json')
    project_risks = [r for r in risks if r.get('project_id') == project_id]
    return json.dumps({
        'project': project,
        'tasks': approved_tasks,
        'documents': project_docs,
        'risks': project_risks,
    })


def get_meeting_pack(meeting_id: str) -> str:
    meetings = _load(DATA_DIR / 'registry' / 'meetings.json')
    meeting = next((m for m in meetings if m['id'] == meeting_id), None)
    if meeting is None:
        return json.dumps({'error': f'Meeting {meeting_id!r} not found'})
    index = _load(DATA_DIR / 'documents' / 'index.json')
    mom_meta = next(
        (d for d in index if d.get('doc_type') == 'mom' and d.get('meeting_id') == meeting_id),
        None
    )
    mom = None
    if mom_meta is not None:
        content_path = DATA_DIR / 'documents' / f"{mom_meta['id']}.json"
        if content_path.exists():
            mom = _load(content_path)
        else:
            mom = mom_meta
    tasks = _load(DATA_DIR / 'registry' / 'tasks.json')
    meeting_tasks = [t for t in tasks if t.get('meeting_id') == meeting_id]
    return json.dumps({'meeting': meeting, 'mom': mom, 'tasks': meeting_tasks})


def search_lessons(tags: list = None, query: str = None) -> str:
    index = _load(DATA_DIR / 'documents' / 'index.json')
    lessons = [d for d in index if d.get('doc_type') == 'lesson' and d.get('approved') is True]
    if tags is not None:
        lessons = [d for d in lessons if any(t in d.get('tags', []) for t in tags)]
    results = []
    for meta in lessons:
        content_path = DATA_DIR / 'documents' / f"{meta['id']}.json"
        doc = _load(content_path) if content_path.exists() else meta
        if query is not None:
            haystack = doc.get('content', '') + ' ' + doc.get('title', '')
            if not _match_query(haystack, query):
                continue
        results.append(doc)
    return json.dumps(results)


def get_person_tasks(person_id: str) -> str:
    tasks = _load(DATA_DIR / 'registry' / 'tasks.json')
    return json.dumps([
        t for t in tasks
        if t.get('assignee_id') == person_id and t.get('status') in ['open', 'overdue']
    ])


def search_risk_patterns(query: str) -> str:
    risks = _load(DATA_DIR / 'registry' / 'risks.json')
    matched_risks = [r for r in risks if _match_query(r.get('description', ''), query)]
    index = _load(DATA_DIR / 'documents' / 'index.json')
    lessons_meta = [d for d in index if d.get('doc_type') == 'lesson']
    matched_lessons = []
    for meta in lessons_meta:
        content_path = DATA_DIR / 'documents' / f"{meta['id']}.json"
        if content_path.exists():
            doc = _load(content_path)
            haystack = doc.get('content', '') + ' ' + doc.get('title', '')
            if _match_query(haystack, query):
                matched_lessons.append(doc)
    return json.dumps({'risks': matched_risks, 'lessons': matched_lessons})


# ── Phase 3: Write operations ─────────────────────────────────────────────────

# Projects

def create_project(name: str, status: str = 'active', current_gate: str = 'G1') -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'projects.json'
    records = _load(path)
    new_record = {
        'id': _next_id(records, 'proj-'),
        'name': name,
        'status': status,
        'current_gate': current_gate,
        'created_at': date.today().isoformat(),
    }
    records.append(new_record)
    _save(path, records)
    return json.dumps(new_record)


def update_project(id: str, current_gate: str = None, status: str = None) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'projects.json'
    records = _load(path)
    record = next((r for r in records if r['id'] == id), None)
    if record is None:
        return json.dumps({'error': f'Project {id!r} not found'})
    if current_gate is not None:
        record['current_gate'] = current_gate
    if status is not None:
        record['status'] = status
    _save(path, records)
    return json.dumps(record)


# People

def create_person(name: str, role: str, email: str, teams_id: str, function: str) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'people.json'
    records = _load(path)
    new_record = {
        'id': _next_id(records, 'person-'),
        'name': name,
        'role': role,
        'email': email,
        'teams_id': teams_id,
        'function': function,
    }
    records.append(new_record)
    _save(path, records)
    return json.dumps(new_record)


# Meetings

def create_meeting(
    project_id: str,
    title: str,
    date: str,
    attendees: list = None,
) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'meetings.json'
    records = _load(path)
    new_record = {
        'id': _next_id(records, 'mtg-'),
        'project_id': project_id,
        'title': title,
        'date': date,
        'attendees': attendees or [],
        'status': 'scheduled',
    }
    records.append(new_record)
    _save(path, records)
    return json.dumps(new_record)


def update_meeting_status(id: str, status: str) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'meetings.json'
    records = _load(path)
    record = next((r for r in records if r['id'] == id), None)
    if record is None:
        return json.dumps({'error': f'Meeting {id!r} not found'})
    record['status'] = status
    _save(path, records)
    return json.dumps(record)


# Tasks

def create_task(
    project_id: str,
    description: str,
    assignee_id: str,
    due_date: str,
    source: str,
    meeting_id: str = None,
    depends_on: list = None,
) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'tasks.json'
    records = _load(path)
    new_record = {
        'id': _next_id(records, 'task-'),
        'project_id': project_id,
        'meeting_id': meeting_id,
        'description': description,
        'assignee_id': assignee_id,
        'due_date': due_date,
        'status': 'open',
        'source': source,
        'approved': False,
        'depends_on': depends_on or [],
    }
    records.append(new_record)
    _save(path, records)
    return json.dumps(new_record)


def approve_task(id: str) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'tasks.json'
    records = _load(path)
    record = next((r for r in records if r['id'] == id), None)
    if record is None:
        return json.dumps({'error': f'Task {id!r} not found'})
    record['approved'] = True
    _save(path, records)
    return json.dumps(record)


def update_task_status(id: str, status: str) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'tasks.json'
    records = _load(path)
    record = next((r for r in records if r['id'] == id), None)
    if record is None:
        return json.dumps({'error': f'Task {id!r} not found'})
    record['status'] = status
    _save(path, records)
    return json.dumps(record)


def reassign_task(id: str, assignee_id: str) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'tasks.json'
    records = _load(path)
    record = next((r for r in records if r['id'] == id), None)
    if record is None:
        return json.dumps({'error': f'Task {id!r} not found'})
    record['assignee_id'] = assignee_id
    _save(path, records)
    return json.dumps(record)


def delete_task(id: str) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'tasks.json'
    records = _load(path)
    original_len = len(records)
    records = [r for r in records if r['id'] != id]
    if len(records) == original_len:
        return json.dumps({'error': f'Task {id!r} not found'})
    _save(path, records)
    return json.dumps({'deleted': id})


# Risks

def flag_risk(
    project_id: str,
    source_type: str,
    source_id: str,
    description: str,
    gate: str,
    function: str,
) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'risks.json'
    records = _load(path)
    new_record = {
        'id': _next_id(records, 'risk-'),
        'project_id': project_id,
        'source_type': source_type,
        'source_id': source_id,
        'description': description,
        'gate': gate,
        'function': function,
        'flagged_at': date.today().isoformat(),
    }
    records.append(new_record)
    _save(path, records)
    return json.dumps(new_record)


# Documents

def save_document(
    project_id: str,
    doc_type: str,
    title: str,
    tags: list,
    content: str,
    meeting_id: str = None,
) -> str:
    wd = _get_writable_dir()
    index_path = wd / 'documents' / 'index.json'
    index = _load(index_path)
    new_id = _next_id(index, 'doc-')
    meta = {
        'id': new_id,
        'doc_type': doc_type,
        'project_id': project_id,
        'meeting_id': meeting_id,
        'title': title,
        'tags': tags,
        'created_at': date.today().isoformat(),
        'approved': False,
    }
    index.append(meta)
    _save(index_path, index)
    content_record = dict(meta)
    content_record['content'] = content
    content_path = wd / 'documents' / f'{new_id}.json'
    _save(content_path, content_record)
    return json.dumps(meta)


def approve_document(id: str) -> str:
    wd = _get_writable_dir()
    index_path = wd / 'documents' / 'index.json'
    index = _load(index_path)
    meta = next((d for d in index if d['id'] == id), None)
    if meta is None:
        return json.dumps({'error': f'Document {id!r} not found'})
    meta['approved'] = True
    _save(index_path, index)
    content_path = wd / 'documents' / f'{id}.json'
    if content_path.exists():
        doc = _load(content_path)
        doc['approved'] = True
        _save(content_path, doc)
    return json.dumps(meta)


def update_document(id: str, content: str = None, tags: list = None) -> str:
    wd = _get_writable_dir()
    index_path = wd / 'documents' / 'index.json'
    index = _load(index_path)
    meta = next((d for d in index if d['id'] == id), None)
    if meta is None:
        return json.dumps({'error': f'Document {id!r} not found'})
    if tags is not None:
        meta['tags'] = tags
    _save(index_path, index)
    content_path = wd / 'documents' / f'{id}.json'
    if content_path.exists():
        doc = _load(content_path)
        if tags is not None:
            doc['tags'] = tags
        if content is not None:
            doc['content'] = content
        _save(content_path, doc)
    return json.dumps(meta)


def delete_document(id: str) -> str:
    wd = _get_writable_dir()
    index_path = wd / 'documents' / 'index.json'
    index = _load(index_path)
    original_len = len(index)
    index = [d for d in index if d['id'] != id]
    if len(index) == original_len:
        return json.dumps({'error': f'Document {id!r} not found'})
    _save(index_path, index)
    content_path = wd / 'documents' / f'{id}.json'
    if content_path.exists():
        content_path.unlink()
    return json.dumps({'deleted': id})


# Distribution lists

def create_distribution_list(project_id: str, name: str, member_ids: list) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'distribution_lists.json'
    records = _load(path)
    new_record = {
        'id': _next_id(records, 'dl-'),
        'project_id': project_id,
        'name': name,
        'member_ids': member_ids,
    }
    records.append(new_record)
    _save(path, records)
    return json.dumps(new_record)


def update_distribution_list(
    id: str,
    add_member_ids: list = None,
    remove_member_ids: list = None,
) -> str:
    wd = _get_writable_dir()
    path = wd / 'registry' / 'distribution_lists.json'
    records = _load(path)
    record = next((r for r in records if r['id'] == id), None)
    if record is None:
        return json.dumps({'error': f'Distribution list {id!r} not found'})
    current = list(record['member_ids'])
    if add_member_ids:
        for mid in add_member_ids:
            if mid not in current:
                current.append(mid)
    if remove_member_ids:
        current = [mid for mid in current if mid not in remove_member_ids]
    record['member_ids'] = current
    _save(path, records)
    return json.dumps(record)
