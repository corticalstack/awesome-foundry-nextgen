"""
Display helpers for Lab 5: Agent Memory
"""
import pandas as pd
from IPython.display import display, Markdown


def show_config(title: str, data: dict):
    """Display a configuration table."""
    df = pd.DataFrame({
        'Setting': list(data.keys()),
        'Value': list(data.values())
    })
    display(Markdown(f'### {title}'))
    display(df.style.hide(axis='index'))


def show_store_created(name: str, chat_model: str, embedding_model: str):
    """Display memory store creation result."""
    df = pd.DataFrame({
        'Property': ['Name', 'Chat Model', 'Embedding Model', 'Status'],
        'Value': [name, chat_model, embedding_model, '✅ Created']
    })
    display(Markdown('### Memory Store Created'))
    display(df.style.hide(axis='index'))


def show_memories(title: str, memories: list):
    """Display extracted memories."""
    if not memories:
        print(f"✅ {title} - No new memories extracted")
        return
    
    df = pd.DataFrame([{
        'Type': m['memory_item'].get('kind', ''),
        'Content': _truncate(m['memory_item'].get('content', ''), 80),
        'Action': m.get('action', '')
    } for m in memories])
    
    display(Markdown(f'### ✅ {title}'))
    display(df.style.hide(axis='index'))


def show_search_results(user_label: str, emoji: str, memories: list):
    """Display memory search results."""
    if not memories:
        display(Markdown(f'#### {emoji} {user_label}: No memories found'))
        return
    
    df = pd.DataFrame([{
        'Type': m['memory_item'].get('kind', ''),
        'Content': _truncate(m['memory_item'].get('content', ''), 100)
    } for m in memories])
    
    display(Markdown(f'#### {emoji} {user_label}\'s Memories'))
    display(df.style.hide(axis='index'))


def show_agent_created(name: str, version: str, model: str, memory_store: str, note: str = ""):
    """Display agent creation result."""
    data = {
        'Property': ['Name', 'Version', 'Model', 'Memory Store'],
        'Value': [name, version, model, memory_store]
    }
    if note:
        data['Property'].append('Note')
        data['Value'].append(note)
    
    df = pd.DataFrame(data)
    display(Markdown('### Agent Created'))
    display(df.style.hide(axis='index'))


def show_conversation(title: str, user_query: str, agent_response: str, user_label: str = "User"):
    """Display a conversation between user and agent."""
    df = pd.DataFrame({
        'Role': [f'👤 {user_label}', '🤖 Agent'],
        'Message': [user_query, agent_response]
    })
    display(Markdown(f'### {title}'))
    display(df.style.hide(axis='index').set_properties(**{'text-align': 'left', 'white-space': 'pre-wrap'}))


def show_error(message: str):
    """Display an error message."""
    display(Markdown(f'### ❌ Error\n```\n{message}\n```'))


def _truncate(text: str, max_len: int) -> str:
    """Truncate text with ellipsis if too long."""
    return text[:max_len] + '...' if len(text) > max_len else text
