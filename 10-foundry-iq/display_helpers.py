"""
Display helpers for Foundry IQ
"""
import re
import pandas as pd
from IPython.display import display, Markdown, HTML


def show_success(message: str):
    """Display a success message."""
    display(Markdown(f'### ✅ {message}'))


def show_error(message: str):
    """Display an error message."""
    display(Markdown(f'### ❌ Error\n```\n{message}\n```'))


def show_search_results(query: str, results: list, mode: str = ""):
    """Display Azure AI Search results in a readable table."""
    import re
    label = f" ({mode})" if mode else ""
    display(Markdown(f'**Query{label}:** *"{query}"*'))
    rows = []
    for i, doc in enumerate(results, 1):
        score = doc.get("@search.reranker_score") or doc.get("@search.score", 0)
        captions = doc.get("@search.captions") or []
        snippet = captions[0].text if captions and captions[0].text else doc.get("abstract", "")[:300]
        rows.append({
            "#": i,
            "Score": f"{score:.4f}",
            "Year": doc.get("year", ""),
            "Title": doc.get("title", ""),
            "Snippet": snippet[:200] + "..." if len(snippet) > 200 else snippet,
        })
    df = pd.DataFrame(rows)
    display(df.style.hide(axis="index"))


def show_citation_cards(query: str, response_text: str):
    """Parse agent response and render as citation cards (HTML).

    Expects response paragraphs where citations follow the pattern:
        Sentence describing the paper. (Paper Title, Year).
    Plain introductory paragraphs are rendered as prose; citation
    paragraphs become styled cards.
    """
    _citation_re = re.compile(r"^(.*)\(([^()]+),\s*(\d{4})\)\.?\s*$", re.DOTALL)

    display(Markdown(f'**Query:** *"{query}"*'))

    paragraphs = [p.strip() for p in response_text.strip().split("\n\n") if p.strip()]
    html_parts = []
    in_cards = False

    for para in paragraphs:
        m = _citation_re.match(para)
        if m:
            in_cards = True
            desc  = m.group(1).strip()
            title = m.group(2).strip()
            year  = m.group(3)
            html_parts.append(
                f'<div style="margin-bottom:10px;padding:12px 16px;'
                f'border-left:4px solid #0078d4;background:#1e3a5f;border-radius:0 4px 4px 0;">'
                f'<div style="margin-bottom:6px;color:#e8f0fe;line-height:1.5;">{desc}</div>'
                f'<div style="color:#60b4ff;font-weight:600;font-size:0.85em;">'
                f'{title}&nbsp;&nbsp;&middot;&nbsp;&nbsp;{year}</div>'
                f'</div>'
            )
        elif not in_cards:
            html_parts.append(
                f'<p style="margin:0 0 14px 0;color:#e8f0fe;font-size:1.05em;font-weight:600;">{para}</p>'
            )

    if html_parts:
        display(HTML("\n".join(html_parts)))
    else:
        display(Markdown(response_text))


def show_kb_result_detail(result: dict, label: str = ""):
    """Display a KB retrieval result with references.

    For EXTRACTIVE_DATA KBs the response text is a JSON array of chunks - each
    chunk is rendered as a numbered card with its title (from ref_id → references
    lookup) and abstract snippet.  For synthesized (low/medium effort) responses
    the natural-language answer is rendered as prose.
    """
    import json

    if label:
        display(Markdown(f'**{label}**'))

    if "error" in result:
        show_error(result["error"])
        return

    # Build ref_id → title lookup from the references list
    refs = result.get("references", [])
    ref_title = {
        ref.get("ref_id", i): ref.get("title") or ref.get("id", f"ref_{i}")
        for i, ref in enumerate(refs)
    }

    responses = result.get("response", [])
    for resp in responses:
        for item in resp.get("content", []):
            text = item.get("text", "")
            if not text:
                continue

            # Try to parse as a JSON chunk array (EXTRACTIVE_DATA output)
            try:
                chunks = json.loads(text)
                if not isinstance(chunks, list):
                    raise ValueError("not a list")
            except (json.JSONDecodeError, ValueError):
                chunks = None

            if chunks:
                display(Markdown(f'**{len(chunks)} retrieved chunk(s):**'))
                parts = []
                for chunk in chunks:
                    rid     = chunk.get("ref_id", "?")
                    title   = chunk.get("title") or ref_title.get(rid, f"ref {rid}")
                    terms   = chunk.get("terms", "")
                    content = chunk.get("content", "").strip()

                    # Pull citation metadata from the references list if available
                    ref = refs[rid] if isinstance(rid, int) and rid < len(refs) else {}
                    sd  = ref.get("source_data") or {}
                    year = sd.get("year", "")
                    cats = sd.get("categories", "")

                    meta_parts = []
                    if year:
                        meta_parts.append(
                            f'<span style="color:#8ab4f8"><b>Year:</b> {year}</span>'
                        )
                    if cats:
                        meta_parts.append(
                            f'<span style="color:#8ab4f8"><b>Categories:</b> {cats}</span>'
                        )
                    if terms:
                        meta_parts.append(
                            f'<span style="color:#8ab4f8"><b>Terms:</b> {terms}</span>'
                        )
                    meta_html = (
                        '<div style="font-size:0.82em;margin-top:4px;display:flex;gap:16px;">'
                        + "&nbsp;&nbsp;".join(meta_parts)
                        + "</div>"
                        if meta_parts else ""
                    )

                    card = (
                        f'<div style="margin-bottom:12px;padding:10px 14px;'
                        f'border-left:4px solid #0078d4;background:#1e3a5f;'
                        f'border-radius:0 4px 4px 0;">'
                        f'<div style="color:#60b4ff;font-weight:600;font-size:0.9em;">'
                        f'<b>Chunk</b> [{rid}]&nbsp;&nbsp;<b>Title:</b> {title}'
                        f'</div>'
                        f'{meta_html}'
                        f'<div style="color:#e8f0fe;font-size:0.88em;margin-top:8px;line-height:1.5;">'
                        f'<b style="color:#aac8ff;">Content:</b> {content}'
                        f'</div>'
                        f'</div>'
                    )
                    parts.append(card)
                display(HTML("\n".join(parts)))
            else:
                # Synthesized natural-language answer (low/medium/high effort)
                display(Markdown(f'**Answer** ({len(text)} chars):'))
                display(Markdown(text))

