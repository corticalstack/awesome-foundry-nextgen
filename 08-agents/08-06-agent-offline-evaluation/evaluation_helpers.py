"""
Display helpers for Agent Offline Evaluation
Provides formatted display functions for evaluation results
"""
import pandas as pd
from IPython.display import display, Markdown, HTML


def display_metrics_summary(metrics: dict):
    """Display aggregate metrics in a nicely formatted table.

    Supports both legacy dot-notation keys (e.g. coherence.coherence) and
    the standardised SDK >=1.13.1 keys (e.g. coherence_result).
    """
    display(Markdown("### Aggregate Metrics Summary"))

    quality_metrics = {}
    rag_metrics = {}
    agent_metrics = {}
    custom_metrics = {}

    for key, value in metrics.items():
        if value is None:
            continue
        # Derive base name from either "metric.metric" or "metric_result" / plain "metric"
        if "." in key:
            base_name = key.split(".")[0]
        elif key.endswith("_result") or key.endswith("_threshold"):
            base_name = key.rsplit("_", 1)[0]
        else:
            base_name = key

        if base_name in {"coherence", "fluency", "relevance"}:
            quality_metrics[key] = value
        elif base_name in {"groundedness", "similarity", "f1_score", "bleu_score"}:
            rag_metrics[key] = value
        elif base_name in {"intent_resolution", "tool_call_accuracy", "task_adherence"}:
            agent_metrics[key] = value
        else:
            custom_metrics[key] = value

    def _render_table(title: str, data: dict):
        display(Markdown(f"#### {title}"))
        df = pd.DataFrame([
            {"Metric": k, "Score": f"{v:.2f}" if isinstance(v, (int, float)) else v}
            for k, v in data.items()
        ])
        display(df.style.hide(axis="index"))

    if quality_metrics:
        _render_table("Quality Metrics", quality_metrics)
    if rag_metrics:
        _render_table("RAG & Similarity Metrics", rag_metrics)
    if agent_metrics:
        _render_table("Agent Evaluator Metrics", agent_metrics)
    if custom_metrics:
        _render_table("Custom Metrics", custom_metrics)


def display_row_results(rows: list, columns: list | None = None):
    """Display row-level evaluation results.

    Args:
        rows: List of row dicts from evaluate() output.
        columns: Optional list of score column names to display. Defaults to
                 the standard quality/RAG set. Pass a custom list for custom
                 or agent evaluator results.
    """
    display(Markdown("### Row-Level Results"))

    if not rows:
        print("No row results available")
        return

    # Default score columns — SDK >=1.13.1 uses "{metric}_result" keys in rows
    if columns is None:
        columns = ["coherence", "fluency", "relevance", "groundedness", "similarity"]

    display_data = []
    for i, row in enumerate(rows):
        entry = {"#": i + 1}

        query = row.get("inputs.query", "")
        entry["Query"] = query[:40] + "..." if len(query) > 40 else query

        for col in columns:
            # Try standardised key first, then legacy dot-notation
            value = row.get(f"outputs.{col}_{col}", row.get(f"outputs.{col}.{col}", "N/A"))
            entry[col.replace("_", " ").title()] = value

        display_data.append(entry)

    df = pd.DataFrame(display_data)

    def highlight_scores(val):
        if isinstance(val, (int, float)):
            if val >= 4:
                return "background-color: #2e7d32; color: #e8f5e9"
            elif val >= 3:
                return "background-color: #f9a825; color: #1a1a1a"
            else:
                return "background-color: #c62828; color: #ffebee"
        return ""

    score_col_labels = [c.replace("_", " ").title() for c in columns]
    existing_score_cols = [c for c in score_col_labels if c in df.columns]
    styled_df = df.style.map(highlight_scores, subset=existing_score_cols).hide(axis="index")
    display(styled_df)


def display_agent_eval_results(results: dict):
    """Display results from AIAgentConverter-based agent evaluations.

    Args:
        results: Dict with 'metrics' and optionally 'rows' keys from evaluate().
    """
    display(Markdown("### Agent Evaluation Results"))

    metrics = results.get("metrics", {})
    rows = results.get("rows", [])

    agent_keys = [
        ("intent_resolution", "Intent Resolution", "Did the agent correctly identify user intent?"),
        ("tool_call_accuracy", "Tool Call Accuracy", "Did the agent call the right tools with correct arguments?"),
        ("task_adherence", "Task Adherence", "Did the agent's response follow its system prompt and task?"),
    ]

    summary_rows = []
    for key, label, description in agent_keys:
        # Support both _result suffix and plain key
        score = metrics.get(f"{key}_result", metrics.get(key))
        if score is not None:
            summary_rows.append({
                "Evaluator": label,
                "Score": f"{score:.2f}" if isinstance(score, (int, float)) else score,
                "Description": description,
            })

    if summary_rows:
        df = pd.DataFrame(summary_rows)
        display(df.style.hide(axis="index"))
    else:
        display(Markdown("*No agent evaluator metrics found in results.*"))

    if rows:
        agent_col_keys = ["intent_resolution", "tool_call_accuracy", "task_adherence"]
        display_row_results(rows, columns=agent_col_keys)


def analyze_evaluation_results(result: dict):
    """Provide detailed analysis and recommendations based on evaluation results."""
    display(Markdown("### Evaluation Analysis"))

    metrics = result.get("metrics", {})
    rows = result.get("rows", [])

    def _get_metric(name: str):
        # Try standardised key, then legacy dot-notation
        return metrics.get(f"{name}_result", metrics.get(f"{name}.{name}"))

    analysis = []
    for name, label in [
        ("coherence", "Coherence"),
        ("fluency", "Fluency"),
        ("relevance", "Relevance"),
        ("groundedness", "Groundedness"),
        ("similarity", "Similarity"),
    ]:
        avg = _get_metric(name)
        if avg:
            status = "Good" if avg >= 4 else "Needs improvement" if avg >= 3 else "Poor"
            analysis.append(f"**{label}:** {avg:.2f}/5 - {status}")

    display(Markdown("#### Score Summary\n" + "\n".join(analysis)))

    recommendations = []
    coherence_avg = _get_metric("coherence")
    if coherence_avg and coherence_avg < 4:
        recommendations.append("- Improve response structure and logical flow")
    fluency_avg = _get_metric("fluency")
    if fluency_avg and fluency_avg < 4:
        recommendations.append("- Work on natural language generation quality")
    relevance_avg = _get_metric("relevance")
    if relevance_avg and relevance_avg < 4:
        recommendations.append("- Ensure responses directly address the query")
    groundedness_avg = _get_metric("groundedness")
    if groundedness_avg and groundedness_avg < 4:
        recommendations.append("- Reduce hallucinations by improving retrieval or adding guardrails")
    similarity_avg = _get_metric("similarity")
    if similarity_avg and similarity_avg < 3:
        recommendations.append("- Responses diverge significantly from expected answers — review knowledge base")

    if recommendations:
        display(Markdown("#### Recommendations\n" + "\n".join(recommendations)))
    else:
        display(Markdown("#### All metrics look good! Your agent is performing well."))

    if rows:
        display(Markdown("#### Queries with Lowest Scores"))
        lowest_scores = []
        for i, row in enumerate(rows):
            avg_score = 0
            count = 0
            for key in ["coherence_result", "relevance_result", "groundedness_result",
                        "outputs.coherence.coherence", "outputs.relevance.relevance",
                        "outputs.groundedness.groundedness"]:
                if key in row and isinstance(row[key], (int, float)):
                    avg_score += row[key]
                    count += 1
            if count > 0:
                lowest_scores.append({
                    "index": i,
                    "query": row.get("inputs.query", "")[:50],
                    "avg_score": avg_score / count,
                })
        lowest_scores.sort(key=lambda x: x["avg_score"])
        for item in lowest_scores[:3]:
            display(Markdown(
                f"- Query {item['index'] + 1}: \"{item['query']}...\" (avg: {item['avg_score']:.2f})"
            ))


def format_score(score, max_score=5):
    """Format a score with visual indicator."""
    if score is None or not isinstance(score, (int, float)):
        return "N/A"
    pct = score / max_score
    if pct >= 0.8:
        return f"High {score:.1f}"
    elif pct >= 0.6:
        return f"Mid {score:.1f}"
    else:
        return f"Low {score:.1f}"


def display_comparison_table(results: dict):
    """Display comparison of multiple evaluation runs."""
    display(Markdown("### Evaluation Comparison"))

    df_data = []
    for run_name, run_metrics in results.items():
        entry = {"Run": run_name}
        for name in ["coherence", "fluency", "relevance", "groundedness"]:
            entry[name.title()] = run_metrics.get(f"{name}_result", run_metrics.get(f"{name}.{name}", "N/A"))
        df_data.append(entry)

    df = pd.DataFrame(df_data)
    display(df.style.hide(axis="index"))
