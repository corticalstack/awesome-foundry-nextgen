import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from agent_framework import Agent, tool
from agent_framework_foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential

# Everything the agent writes goes under $HOME. The hosted agent platform keeps
# $HOME per session: it survives the idle timeout and stop_session, and files
# uploaded through the session files API land here too. delete_session removes it.
HOME = Path.home()
NOTES_DIR = HOME / "notes"
STARTED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")
MAX_READ_CHARS = 8000


def _slug(title: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in title.strip()]
    return "-".join(part for part in "".join(keep).split("-") if part) or "note"


@tool
def save_note(
    title: Annotated[str, "Short title for the note; it becomes the file name."],
    body: Annotated[str, "The note text in Markdown."],
) -> str:
    """Save a meeting note to this session's workspace. Returns the saved path."""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    path = NOTES_DIR / f"{_slug(title)}.md"
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.write_text(f"# {title.strip()}\n\nSaved: {stamp}\n\n{body.strip()}\n", encoding="utf-8")
    return f"Saved {path.relative_to(HOME)} ({path.stat().st_size} bytes)"


@tool
def list_notes() -> str:
    """List the notes saved in this session's workspace, newest first."""
    if not NOTES_DIR.is_dir():
        return "No notes in this session yet."
    notes = sorted(NOTES_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not notes:
        return "No notes in this session yet."
    lines = []
    for p in notes:
        first = p.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")
        lines.append(f"- {p.relative_to(HOME)}: {first} ({p.stat().st_size} bytes)")
    return "\n".join(lines)


@tool
def read_file(
    path: Annotated[str, "File path relative to the session home directory, e.g. meeting-agenda.md or notes/x.md."],
) -> str:
    """Read a text file from this session's workspace: an uploaded file or a saved note."""
    target = (HOME / path).resolve()
    if HOME.resolve() not in target.parents and target != HOME.resolve():
        return f"Refused: {path} is outside the session home directory."
    if not target.is_file():
        return f"Not found: {path}. Files in the home directory: " + ", ".join(
            sorted(p.name for p in HOME.iterdir())
        )
    text = target.read_text(encoding="utf-8", errors="replace")
    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS] + f"\n... (truncated at {MAX_READ_CHARS} characters)"
    return text


@tool
def where_am_i() -> str:
    """Report which session sandbox this agent process is running in."""
    return (
        f"session_id={os.environ.get('FOUNDRY_AGENT_SESSION_ID', 'unknown')}\n"
        f"host={socket.gethostname()}\n"
        f"home={HOME}\n"
        f"process_started_at={STARTED_AT}\n"
        f"notes={len(list(NOTES_DIR.glob('*.md'))) if NOTES_DIR.is_dir() else 0}"
    )


def main():
    project_endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT") or os.getenv("PROJECT_ENDPOINT")
    # "<connection-name>/<deployment>" so Foundry resolves the model through the
    # spoke project's APIM connection, exactly as in 08-03.
    chat_model = os.getenv("CHAT_MODEL", "core-alpha/gpt-5.4-mini")

    chat_client = FoundryChatClient(
        project_endpoint=project_endpoint,
        model=chat_model,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )

    agent = Agent(
        chat_client,
        name="contoso-rm-notes-agent",
        id="contoso-rm-notes-agent",
        tools=[save_note, list_notes, read_file, where_am_i],
        instructions="""
        You are the meeting-notes assistant for relationship managers at Contoso
        Wealth, the private banking and wealth management division of Contoso
        Private Investments.

        You keep notes in this session's workspace with your tools:
        - save_note to write a note, list_notes to see what is saved,
          read_file to read an uploaded file or a saved note,
          where_am_i to report the sandbox you run in.

        Rules:
        - Always use the tools for anything about notes or files. Never claim a
          note exists unless list_notes returned it, and never invent file
          contents.
        - When asked to save a note, save it, then confirm with the path returned
          by the tool.
        - Keep replies short and factual. Match the user's language (English,
          French, German or Italian).
        - You do not give investment, tax or regulatory advice. For client-specific
          questions beyond note taking, direct the user to their relationship
          manager tooling.
        """,
    )

    ResponsesHostServer(agent).run()


if __name__ == "__main__":
    main()
