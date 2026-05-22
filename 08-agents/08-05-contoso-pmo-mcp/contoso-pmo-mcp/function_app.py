import json

import azure.functions as func

import kb

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def _to_list(v):
    """Parse a JSON array string to a Python list. Returns None if v is None."""
    if v is None:
        return None
    if isinstance(v, list):
        return v
    try:
        parsed = json.loads(v)
        return parsed if isinstance(parsed, list) else [str(parsed)]
    except (json.JSONDecodeError, TypeError):
        return [s.strip() for s in str(v).split(',') if s.strip()]


# ── Pre-computed tool property descriptors ────────────────────────────────────

_create_project_props = json.dumps([
    {'propertyName': 'name', 'propertyType': 'string',
     'description': 'Project name'},
    {'propertyName': 'status', 'propertyType': 'string',
     'description': 'Project status (default: active)'},
    {'propertyName': 'current_gate', 'propertyType': 'string',
     'description': 'Current gate (default: G1)'},
])

_get_project_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Project ID (e.g. proj-001)'},
])

_list_projects_props = json.dumps([
    {'propertyName': 'status', 'propertyType': 'string',
     'description': 'Filter by status (active/completed). Omit for all.'},
])

_update_project_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Project ID'},
    {'propertyName': 'current_gate', 'propertyType': 'string',
     'description': 'New gate value (optional)'},
    {'propertyName': 'status', 'propertyType': 'string',
     'description': 'New status (optional)'},
])

_create_person_props = json.dumps([
    {'propertyName': 'name', 'propertyType': 'string',
     'description': 'Full name'},
    {'propertyName': 'role', 'propertyType': 'string',
     'description': 'Role: project_manager, team_member, or stakeholder'},
    {'propertyName': 'email', 'propertyType': 'string',
     'description': 'Email address'},
    {'propertyName': 'teams_id', 'propertyType': 'string',
     'description': 'Microsoft Teams user ID'},
    {'propertyName': 'function', 'propertyType': 'string',
     'description': 'Business function (e.g. R&D, Procurement)'},
])

_get_person_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Person ID (optional if email provided)'},
    {'propertyName': 'email', 'propertyType': 'string',
     'description': 'Email address (optional if id provided)'},
])

_list_people_props = json.dumps([
    {'propertyName': 'role', 'propertyType': 'string',
     'description': 'Filter by role (optional)'},
])

_create_meeting_props = json.dumps([
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Project ID'},
    {'propertyName': 'title', 'propertyType': 'string',
     'description': 'Meeting title'},
    {'propertyName': 'date', 'propertyType': 'string',
     'description': 'Date in YYYY-MM-DD format'},
    {'propertyName': 'attendees', 'propertyType': 'string',
     'description': 'JSON array of person IDs, e.g. ["p-001","p-002"] (optional)'},
])

_get_meeting_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Meeting ID (e.g. mtg-001)'},
])

_list_meetings_props = json.dumps([
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Filter by project ID (optional)'},
    {'propertyName': 'status', 'propertyType': 'string',
     'description': 'Filter by status: scheduled/completed (optional)'},
    {'propertyName': 'date_from', 'propertyType': 'string',
     'description': 'Filter meetings on or after this date YYYY-MM-DD (optional)'},
    {'propertyName': 'date_to', 'propertyType': 'string',
     'description': 'Filter meetings on or before this date YYYY-MM-DD (optional)'},
])

_update_meeting_status_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Meeting ID'},
    {'propertyName': 'status', 'propertyType': 'string',
     'description': 'New status: scheduled or completed'},
])

_create_task_props = json.dumps([
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Project ID'},
    {'propertyName': 'description', 'propertyType': 'string',
     'description': 'Task description'},
    {'propertyName': 'assignee_id', 'propertyType': 'string',
     'description': 'Person ID of assignee'},
    {'propertyName': 'due_date', 'propertyType': 'string',
     'description': 'Due date in YYYY-MM-DD format'},
    {'propertyName': 'source', 'propertyType': 'string',
     'description': 'Origin: meeting, plan, or manual'},
    {'propertyName': 'meeting_id', 'propertyType': 'string',
     'description': 'Meeting ID if task originated from a meeting (optional)'},
    {'propertyName': 'depends_on', 'propertyType': 'string',
     'description': 'JSON array of task IDs this task depends on, e.g. ["task-001"] (optional)'},
])

_get_task_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Task ID (e.g. task-001)'},
])

_list_tasks_props = json.dumps([
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Filter by project ID (optional)'},
    {'propertyName': 'assignee_id', 'propertyType': 'string',
     'description': 'Filter by assignee person ID (optional)'},
    {'propertyName': 'status', 'propertyType': 'string',
     'description': 'Filter by status: open/overdue/done (optional)'},
    {'propertyName': 'approved', 'propertyType': 'boolean',
     'description': 'Filter by approval status (optional)'},
    {'propertyName': 'due_date_from', 'propertyType': 'string',
     'description': 'Filter tasks due on or after YYYY-MM-DD (optional)'},
    {'propertyName': 'due_date_to', 'propertyType': 'string',
     'description': 'Filter tasks due on or before YYYY-MM-DD (optional)'},
])

_approve_task_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Task ID to approve'},
])

_update_task_status_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Task ID'},
    {'propertyName': 'status', 'propertyType': 'string',
     'description': 'New status: open, overdue, or done'},
])

_reassign_task_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Task ID'},
    {'propertyName': 'assignee_id', 'propertyType': 'string',
     'description': 'New assignee person ID'},
])

_delete_task_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Task ID to delete'},
])

_save_document_props = json.dumps([
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Project ID'},
    {'propertyName': 'doc_type', 'propertyType': 'string',
     'description': 'Document type: mom, plan, gate_doc, lesson, status_report, email, chat'},
    {'propertyName': 'title', 'propertyType': 'string',
     'description': 'Document title'},
    {'propertyName': 'tags', 'propertyType': 'string',
     'description': 'JSON array of tag strings, e.g. ["launch","supplier"]'},
    {'propertyName': 'content', 'propertyType': 'string',
     'description': 'Document content text'},
    {'propertyName': 'meeting_id', 'propertyType': 'string',
     'description': 'Associated meeting ID (optional)'},
])

_get_document_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Document ID (e.g. doc-001)'},
])

_list_documents_props = json.dumps([
    {'propertyName': 'doc_type', 'propertyType': 'string',
     'description': 'Filter by document type (optional)'},
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Filter by project ID (optional)'},
    {'propertyName': 'tags', 'propertyType': 'string',
     'description': 'JSON array of tags to filter by, e.g. ["launch"] (optional)'},
    {'propertyName': 'approved', 'propertyType': 'boolean',
     'description': 'Filter by approval status (optional)'},
    {'propertyName': 'date_from', 'propertyType': 'string',
     'description': 'Filter documents created on or after YYYY-MM-DD (optional)'},
    {'propertyName': 'date_to', 'propertyType': 'string',
     'description': 'Filter documents created on or before YYYY-MM-DD (optional)'},
])

_approve_document_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Document ID to approve'},
])

_update_document_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Document ID'},
    {'propertyName': 'content', 'propertyType': 'string',
     'description': 'Updated content text (optional)'},
    {'propertyName': 'tags', 'propertyType': 'string',
     'description': 'JSON array of tag strings, e.g. ["launch"] (optional)'},
])

_delete_document_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Document ID to delete'},
])

_flag_risk_props = json.dumps([
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Project ID'},
    {'propertyName': 'source_type', 'propertyType': 'string',
     'description': 'Origin of risk: task or document'},
    {'propertyName': 'source_id', 'propertyType': 'string',
     'description': 'ID of the source task or document'},
    {'propertyName': 'description', 'propertyType': 'string',
     'description': 'Risk description'},
    {'propertyName': 'gate', 'propertyType': 'string',
     'description': 'Gate this risk applies to (e.g. G3)'},
    {'propertyName': 'function', 'propertyType': 'string',
     'description': 'Business function responsible'},
])

_list_risks_props = json.dumps([
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Filter by project ID (optional)'},
    {'propertyName': 'gate', 'propertyType': 'string',
     'description': 'Filter by gate (optional)'},
    {'propertyName': 'function', 'propertyType': 'string',
     'description': 'Filter by business function (optional)'},
])

_search_risk_patterns_props = json.dumps([
    {'propertyName': 'query', 'propertyType': 'string',
     'description': 'Search query to match against risk descriptions and lessons'},
])

_create_distribution_list_props = json.dumps([
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Project ID'},
    {'propertyName': 'name', 'propertyType': 'string',
     'description': 'Distribution list name'},
    {'propertyName': 'member_ids', 'propertyType': 'string',
     'description': 'JSON array of person IDs, e.g. ["p-001","p-002"]'},
])

_get_distribution_list_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Distribution list ID (e.g. dl-001)'},
])

_update_distribution_list_props = json.dumps([
    {'propertyName': 'id', 'propertyType': 'string',
     'description': 'Distribution list ID'},
    {'propertyName': 'add_member_ids', 'propertyType': 'string',
     'description': 'JSON array of person IDs to add, e.g. ["p-003"] (optional)'},
    {'propertyName': 'remove_member_ids', 'propertyType': 'string',
     'description': 'JSON array of person IDs to remove, e.g. ["p-001"] (optional)'},
])

_get_project_context_props = json.dumps([
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Project ID'},
])

_get_meeting_pack_props = json.dumps([
    {'propertyName': 'meeting_id', 'propertyType': 'string',
     'description': 'Meeting ID'},
])

_search_lessons_props = json.dumps([
    {'propertyName': 'query', 'propertyType': 'string',
     'description': 'Keyword search over lesson content and title, e.g. "supplier lead time" or "regulatory submission" (optional). Any significant keyword triggers a match.'},
    {'propertyName': 'tags', 'propertyType': 'string',
     'description': 'JSON array of tags to further filter results, e.g. ["supplier","regulatory"] (optional). Note: lessons are tagged by the gate where the past issue occurred, not the gate being planned.'},
])

_get_person_tasks_props = json.dumps([
    {'propertyName': 'person_id', 'propertyType': 'string',
     'description': 'Person ID'},
])

_search_documents_props = json.dumps([
    {'propertyName': 'query', 'propertyType': 'string',
     'description': 'Search query to match against document content'},
    {'propertyName': 'doc_type', 'propertyType': 'string',
     'description': 'Filter by document type (optional)'},
    {'propertyName': 'project_id', 'propertyType': 'string',
     'description': 'Filter by project ID (optional)'},
    {'propertyName': 'tags', 'propertyType': 'string',
     'description': 'JSON array of tags to filter by, e.g. ["launch"] (optional)'},
    {'propertyName': 'date_from', 'propertyType': 'string',
     'description': 'Filter documents created on or after YYYY-MM-DD (optional)'},
    {'propertyName': 'date_to', 'propertyType': 'string',
     'description': 'Filter documents created on or before YYYY-MM-DD (optional)'},
])


# ── Tool 1: create_project ────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='create_project',
    description='Create a new project in the knowledge base.',
    toolProperties=_create_project_props,
)
def create_project(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.create_project(
        name=args.get('name', ''),
        status=args.get('status', 'active'),
        current_gate=args.get('current_gate', 'G1'),
    )


# ── Tool 2: get_project ───────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_project',
    description='Get a project by ID.',
    toolProperties=_get_project_props,
)
def get_project(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.get_project(id=args.get('id', ''))


# ── Tool 3: list_projects ─────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='list_projects',
    description='List all projects, optionally filtered by status.',
    toolProperties=_list_projects_props,
)
def list_projects(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.list_projects(status=args.get('status'))


# ── Tool 4: update_project ────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='update_project',
    description='Update a project gate or status.',
    toolProperties=_update_project_props,
)
def update_project(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.update_project(
        id=args.get('id', ''),
        current_gate=args.get('current_gate'),
        status=args.get('status'),
    )


# ── Tool 5: create_person ─────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='create_person',
    description='Add a new person to the knowledge base.',
    toolProperties=_create_person_props,
)
def create_person(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.create_person(
        name=args.get('name', ''),
        role=args.get('role', ''),
        email=args.get('email', ''),
        teams_id=args.get('teams_id', ''),
        function=args.get('function', ''),
    )


# ── Tool 6: get_person ────────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_person',
    description='Get a person by ID or email address.',
    toolProperties=_get_person_props,
)
def get_person(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.get_person(id=args.get('id'), email=args.get('email'))


# ── Tool 7: list_people ───────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='list_people',
    description='List all people, optionally filtered by role.',
    toolProperties=_list_people_props,
)
def list_people(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.list_people(role=args.get('role'))


# ── Tool 8: create_meeting ────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='create_meeting',
    description='Schedule a new meeting.',
    toolProperties=_create_meeting_props,
)
def create_meeting(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.create_meeting(
        project_id=args.get('project_id', ''),
        title=args.get('title', ''),
        date=args.get('date', ''),
        attendees=_to_list(args.get('attendees')) or [],
    )


# ── Tool 9: get_meeting ───────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_meeting',
    description='Get a meeting by ID.',
    toolProperties=_get_meeting_props,
)
def get_meeting(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.get_meeting(id=args.get('id', ''))


# ── Tool 10: list_meetings ────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='list_meetings',
    description='List meetings with optional filters.',
    toolProperties=_list_meetings_props,
)
def list_meetings(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.list_meetings(
        project_id=args.get('project_id'),
        status=args.get('status'),
        date_from=args.get('date_from'),
        date_to=args.get('date_to'),
    )


# ── Tool 11: update_meeting_status ────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='update_meeting_status',
    description='Update the status of a meeting (e.g. mark as completed).',
    toolProperties=_update_meeting_status_props,
)
def update_meeting_status(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.update_meeting_status(
        id=args.get('id', ''),
        status=args.get('status', ''),
    )


# ── Tool 12: create_task ──────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='create_task',
    description='Create a new task. Tasks are created unapproved by default.',
    toolProperties=_create_task_props,
)
def create_task(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.create_task(
        project_id=args.get('project_id', ''),
        description=args.get('description', ''),
        assignee_id=args.get('assignee_id', ''),
        due_date=args.get('due_date', ''),
        source=args.get('source', ''),
        meeting_id=args.get('meeting_id'),
        depends_on=_to_list(args.get('depends_on')) or [],
    )


# ── Tool 13: get_task ─────────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_task',
    description='Get a task by ID.',
    toolProperties=_get_task_props,
)
def get_task(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.get_task(id=args.get('id', ''))


# ── Tool 14: list_tasks ───────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='list_tasks',
    description='List tasks with optional filters.',
    toolProperties=_list_tasks_props,
)
def list_tasks(context) -> str:
    args = json.loads(context).get('arguments', {})
    approved = args.get('approved')
    return kb.list_tasks(
        project_id=args.get('project_id'),
        assignee_id=args.get('assignee_id'),
        status=args.get('status'),
        approved=approved,
        due_date_from=args.get('due_date_from'),
        due_date_to=args.get('due_date_to'),
    )


# ── Tool 15: approve_task ─────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='approve_task',
    description='Approve a task.',
    toolProperties=_approve_task_props,
)
def approve_task(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.approve_task(id=args.get('id', ''))


# ── Tool 16: update_task_status ───────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='update_task_status',
    description='Update the status of a task.',
    toolProperties=_update_task_status_props,
)
def update_task_status(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.update_task_status(
        id=args.get('id', ''),
        status=args.get('status', ''),
    )


# ── Tool 17: reassign_task ────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='reassign_task',
    description='Reassign a task to a different person.',
    toolProperties=_reassign_task_props,
)
def reassign_task(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.reassign_task(
        id=args.get('id', ''),
        assignee_id=args.get('assignee_id', ''),
    )


# ── Tool 18: delete_task ──────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='delete_task',
    description='Delete a task by ID.',
    toolProperties=_delete_task_props,
)
def delete_task(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.delete_task(id=args.get('id', ''))


# ── Tool 19: save_document ────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='save_document',
    description='Save a new document to the knowledge base. Documents are created unapproved.',
    toolProperties=_save_document_props,
)
def save_document(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.save_document(
        project_id=args.get('project_id', ''),
        doc_type=args.get('doc_type', ''),
        title=args.get('title', ''),
        tags=_to_list(args.get('tags')) or [],
        content=args.get('content', ''),
        meeting_id=args.get('meeting_id'),
    )


# ── Tool 20: get_document ─────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_document',
    description='Get a document by ID including full content.',
    toolProperties=_get_document_props,
)
def get_document(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.get_document(id=args.get('id', ''))


# ── Tool 21: list_documents ───────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='list_documents',
    description='List document metadata with optional filters. Does not return content.',
    toolProperties=_list_documents_props,
)
def list_documents(context) -> str:
    args = json.loads(context).get('arguments', {})
    approved = args.get('approved')
    return kb.list_documents(
        doc_type=args.get('doc_type'),
        project_id=args.get('project_id'),
        tags=_to_list(args.get('tags')),
        approved=approved,
        date_from=args.get('date_from'),
        date_to=args.get('date_to'),
    )


# ── Tool 22: approve_document ─────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='approve_document',
    description='Approve a document.',
    toolProperties=_approve_document_props,
)
def approve_document(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.approve_document(id=args.get('id', ''))


# ── Tool 23: update_document ──────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='update_document',
    description='Update document content and/or tags.',
    toolProperties=_update_document_props,
)
def update_document(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.update_document(
        id=args.get('id', ''),
        content=args.get('content'),
        tags=_to_list(args.get('tags')),
    )


# ── Tool 24: delete_document ──────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='delete_document',
    description='Delete a document by ID.',
    toolProperties=_delete_document_props,
)
def delete_document(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.delete_document(id=args.get('id', ''))


# ── Tool 25: flag_risk ────────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='flag_risk',
    description='Flag a new risk linked to a task or document.',
    toolProperties=_flag_risk_props,
)
def flag_risk(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.flag_risk(
        project_id=args.get('project_id', ''),
        source_type=args.get('source_type', ''),
        source_id=args.get('source_id', ''),
        description=args.get('description', ''),
        gate=args.get('gate', ''),
        function=args.get('function', ''),
    )


# ── Tool 26: list_risks ───────────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='list_risks',
    description='List risks with optional filters.',
    toolProperties=_list_risks_props,
)
def list_risks(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.list_risks(
        project_id=args.get('project_id'),
        gate=args.get('gate'),
        function=args.get('function'),
    )


# ── Tool 27: search_risk_patterns ────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='search_risk_patterns',
    description='Search for risk patterns across risk records and lesson content. Any significant keyword in the query triggers a match - pass topic keywords such as "supplier" or "regulatory" rather than full sentences.',
    toolProperties=_search_risk_patterns_props,
)
def search_risk_patterns(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.search_risk_patterns(query=args.get('query', ''))


# ── Tool 28: create_distribution_list ────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='create_distribution_list',
    description='Create a new distribution list for a project.',
    toolProperties=_create_distribution_list_props,
)
def create_distribution_list(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.create_distribution_list(
        project_id=args.get('project_id', ''),
        name=args.get('name', ''),
        member_ids=_to_list(args.get('member_ids')) or [],
    )


# ── Tool 29: get_distribution_list ───────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_distribution_list',
    description='Get a distribution list by ID with resolved member details.',
    toolProperties=_get_distribution_list_props,
)
def get_distribution_list(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.get_distribution_list(id=args.get('id', ''))


# ── Tool 30: update_distribution_list ────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='update_distribution_list',
    description='Add or remove members from a distribution list.',
    toolProperties=_update_distribution_list_props,
)
def update_distribution_list(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.update_distribution_list(
        id=args.get('id', ''),
        add_member_ids=_to_list(args.get('add_member_ids')),
        remove_member_ids=_to_list(args.get('remove_member_ids')),
    )


# ── Tool 31: get_pending_approvals ────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_pending_approvals',
    description='Get all tasks and documents pending approval.',
    toolProperties='[]',
)
def get_pending_approvals(context) -> str:
    return kb.get_pending_approvals()


# ── Tool 32: get_overdue_tasks ────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_overdue_tasks',
    description='Get all overdue tasks across all projects.',
    toolProperties='[]',
)
def get_overdue_tasks(context) -> str:
    return kb.get_overdue_tasks()


# ── Tool 33: get_project_context ──────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_project_context',
    description='Get a full project context snapshot: project, approved tasks, documents, and risks.',
    toolProperties=_get_project_context_props,
)
def get_project_context(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.get_project_context(project_id=args.get('project_id', ''))


# ── Tool 34: get_meeting_pack ─────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_meeting_pack',
    description='Get a meeting pack: meeting details, MoM (if available), and associated tasks.',
    toolProperties=_get_meeting_pack_props,
)
def get_meeting_pack(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.get_meeting_pack(meeting_id=args.get('meeting_id', ''))


# ── Tool 35: search_lessons ───────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='search_lessons',
    description='Search approved lessons learned by keyword query and/or tag filter. Use the query parameter for topic searches (e.g. "supplier", "regulatory", "scope change"). Omit both parameters to retrieve all approved lessons.',
    toolProperties=_search_lessons_props,
)
def search_lessons(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.search_lessons(tags=_to_list(args.get('tags')), query=args.get('query'))


# ── Tool 36: get_person_tasks ─────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='get_person_tasks',
    description='Get open and overdue tasks assigned to a specific person.',
    toolProperties=_get_person_tasks_props,
)
def get_person_tasks(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.get_person_tasks(person_id=args.get('person_id', ''))


# ── Tool 37: search_documents ─────────────────────────────────────────────────
@app.generic_trigger(
    arg_name='context',
    type='mcpToolTrigger',
    toolName='search_documents',
    description='Search document content by keyword. Any significant word in the query can trigger a match - use specific terms such as "scope change", "variant", or "regulatory" rather than full sentences.',
    toolProperties=_search_documents_props,
)
def search_documents(context) -> str:
    args = json.loads(context).get('arguments', {})
    return kb.search_documents(
        query=args.get('query', ''),
        doc_type=args.get('doc_type'),
        project_id=args.get('project_id'),
        tags=_to_list(args.get('tags')),
        date_from=args.get('date_from'),
        date_to=args.get('date_to'),
    )
