"""Interactive + one-shot CLI for the multi-memory agent."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from agent.config import get_settings
from agent.graph import build_context, build_graph
from agent.utils.ids import run_id as make_run_id
from agent.utils.logging import JsonlLogger

app = typer.Typer(add_completion=False, help="Multi-memory agent CLI (Lab 17).")
console = Console()


def _build(memory_enabled: bool, log_path: Optional[Path]):
    settings = get_settings()
    ctx = build_context(settings)
    if log_path is not None:
        ctx.turn_logger = JsonlLogger(log_path)
    graph = build_graph(ctx)
    return ctx, graph, settings


@app.command()
def chat(
    user: str = typer.Option(None, help="user_id (default from settings)"),
    session: str = typer.Option(None, help="session_id (default: random)"),
    memory: bool = typer.Option(True, help="Enable memory layer."),
    log: Optional[Path] = typer.Option(None, help="Write per-turn JSONL to this file."),
):
    """Interactive chat loop."""
    settings = get_settings()
    user_id = user or settings.user.default_user_id
    session_id = session or f"sess_{uuid.uuid4().hex[:8]}"
    run_id = make_run_id()

    ctx, graph, _ = _build(memory, log)
    console.print(Panel.fit(
        f"[bold]Multi-memory agent[/bold]  user=[cyan]{user_id}[/cyan] "
        f"session=[cyan]{session_id}[/cyan] memory=[{'green' if memory else 'red'}]{memory}[/]\n"
        f"Runtime: [yellow]{ctx.runtime.name}[/yellow] model=[yellow]{ctx.runtime.model}[/yellow]  run_id={run_id}",
        border_style="magenta",
    ))

    turn_idx = 0
    while True:
        try:
            message = console.input("[bold cyan]you[/bold cyan] > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]bye[/dim]")
            return
        if not message:
            continue
        if message in {":q", "exit", "quit"}:
            console.print("[dim]bye[/dim]")
            return
        state = {
            "user_id": user_id,
            "session_id": session_id,
            "turn_id": f"t_{turn_idx}_{uuid.uuid4().hex[:6]}",
            "user_message": message,
            "flags": {
                "memory_enabled": memory,
                "run_id": run_id,
                "scenario_id": "interactive",
                "turn_idx": turn_idx,
                "session_idx": 0,
            },
            "errors": [],
            "latency_ms": {},
        }
        out = graph.invoke(state)
        console.print(f"[bold magenta]agent[/bold magenta] > {out.get('assistant_response', '')}")
        turn_idx += 1


@app.command()
def ask(
    message: str = typer.Argument(..., help="Single user message."),
    user: str = typer.Option(None),
    session: str = typer.Option(None),
    memory: bool = typer.Option(True),
):
    """One-shot ask. Prints assistant response to stdout."""
    settings = get_settings()
    user_id = user or settings.user.default_user_id
    session_id = session or f"sess_{uuid.uuid4().hex[:8]}"
    ctx, graph, _ = _build(memory, None)
    state = {
        "user_id": user_id,
        "session_id": session_id,
        "turn_id": f"t_{uuid.uuid4().hex[:6]}",
        "user_message": message,
        "flags": {
            "memory_enabled": memory,
            "run_id": make_run_id(),
            "scenario_id": "cli-ask",
            "turn_idx": 0,
            "session_idx": 0,
        },
        "errors": [],
        "latency_ms": {},
    }
    out = graph.invoke(state)
    print(out.get("assistant_response", ""))


@app.command()
def memory_dump(user: str = typer.Option(None)):
    """Dump stored preferences + facts for a user."""
    settings = get_settings()
    user_id = user or settings.user.default_user_id
    ctx = build_context(settings)
    prefs = ctx.redis.read(user_id=user_id, kind="preference")
    facts = ctx.redis.read(user_id=user_id, kind="fact")
    console.print(Panel("[bold]Preferences[/bold]"))
    for p in prefs:
        console.print(f"  {p.key} = [cyan]{p.value}[/cyan] (conf {p.confidence:.2f})")
    console.print(Panel("[bold]Facts[/bold]"))
    for f in facts:
        console.print(f"  [{f.fact_id}] {f.render()}")


if __name__ == "__main__":
    app()
