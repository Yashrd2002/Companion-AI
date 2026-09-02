"""
Interactive CLI for Companion-AI ("Maya").
Provides a chat loop with live memory inspection commands.
"""

from __future__ import annotations
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown

from src.companion import Companion
from src.memory.models import MemoryStatus
from src.config import config

console = Console()


def print_banner():
    banner = Text("✨ Maya — Companion-AI Core Loop ✨", style="bold magenta")
    console.print(Panel(
        f"[bold white]Persistent Memory & Personality Consistency Prototype[/bold white]\n"
        f"[dim]LLM Provider: {config.llm_provider} | Storage: SQLite ({config.db_path})[/dim]\n\n"
        f"[cyan]Special Commands:[/cyan]\n"
        f"  [yellow]/facts[/yellow] or [yellow]/memories[/yellow] - List all active retrieved facts\n"
        f"  [yellow]/superseded[/yellow]          - View superseded contradiction audit history\n"
        f"  [yellow]/profile[/yellow]             - View current structured user profile\n"
        f"  [yellow]/inspect <text>[/yellow]     - Test retrieval ranking breakdown for a query\n"
        f"  [yellow]/reset[/yellow]               - Clear memory for a clean slate\n"
        f"  [yellow]/quit[/yellow]                - Exit the conversation",
        title=banner,
        border_style="magenta",
        padding=(1, 2)
    ))


def display_facts_table(companion: Companion, only_active: bool = True):
    facts = companion.get_active_memories() if only_active else companion.get_all_memories()
    title = "Active Memory Facts" if only_active else "Complete Memory Store (Active & Historical)"
    
    table = Table(title=f"🧠 {title}", border_style="cyan")
    table.add_column("Category", style="cyan", width=14)
    table.add_column("Fact Content", style="white")
    table.add_column("Imp / Conf", style="green", width=12)
    table.add_column("Accesses", style="yellow", width=9)
    table.add_column("Status", style="magenta", width=12)

    if not facts:
        console.print("[dim italic]No memories stored yet.[/dim italic]")
        return

    for f in facts:
        status_color = "green" if f.status == MemoryStatus.ACTIVE else "red"
        table.add_row(
            f.category.value,
            f.fact_text,
            f"{f.importance:.2f} / {f.confidence:.2f}",
            str(f.access_count),
            f"[{status_color}]{f.status.value}[/{status_color}]"
        )

    console.print(table)


def display_superseded_history(companion: Companion):
    facts = companion.get_all_memories()
    superseded = [f for f in facts if f.status == MemoryStatus.SUPERSEDED]
    
    table = Table(title="🔄 Superseded Facts Audit Trail (Resolved Contradictions)", border_style="yellow")
    table.add_column("Category", style="cyan", width=14)
    table.add_column("Superseded (Old Fact)", style="red")
    table.add_column("Superseded By (ID)", style="dim", width=16)
    table.add_column("Updated At", style="dim", width=20)

    if not superseded:
        console.print("[dim italic]No superseded facts found (no contradictions recorded yet).[/dim italic]")
        return

    for f in superseded:
        table.add_row(
            f.category.value,
            f.fact_text,
            f.superseded_by_id[:8] + "..." if f.superseded_by_id else "N/A",
            f.updated_at.strftime("%Y-%m-%d %H:%M")
        )

    console.print(table)


def display_profile(companion: Companion):
    prof = companion.get_profile()
    table = Table(title="👤 Structured User Profile", border_style="green")
    table.add_column("Attribute", style="bold cyan", width=22)
    table.add_column("Value", style="white")

    table.add_row("Name", prof.name or "[dim]Not specified[/dim]")
    table.add_row("Occupation", prof.occupation or "[dim]Not specified[/dim]")
    table.add_row("Relationship Status", prof.relationship_status or "[dim]Not specified[/dim]")
    table.add_row("Partner Name", prof.partner_name or "[dim]None[/dim]")
    table.add_row("Pets", ", ".join(prof.pets) if prof.pets else "[dim]None recorded[/dim]")
    prefs = "\n".join(f"• {k}: {v}" for k, v in prof.key_preferences.items()) if prof.key_preferences else "[dim]None[/dim]"
    table.add_row("Preferences", prefs)

    console.print(table)


def inspect_query_retrieval(companion: Companion, query: str):
    retrieved = companion.retriever.retrieve(query=query, user_id=companion.user_id, top_k=5)
    console.print(f"\n[bold cyan]Top retrieved memories for query:[/bold cyan] \"{query}\"")
    if not retrieved:
        console.print("[dim italic]No matching active memories found above threshold.[/dim italic]")
        return
    for i, m in enumerate(retrieved, 1):
        console.print(f"  {i}. [bold green][{m.category.value.upper()}][/bold green] {m.fact_text} (Imp: {m.importance:.2f}, Acc: {m.access_count})")


def run_cli():
    print_banner()
    companion = Companion()
    debug_mode = False

    while True:
        try:
            user_input = console.input("\n[bold green]You > [/bold green]").strip()
            if not user_input:
                continue

            # Command Handling
            if user_input.lower() in ("/quit", "/exit", "exit", "quit"):
                console.print("[bold magenta]Maya:[/bold magenta] Take care, see you soon! ✨")
                sys.exit(0)

            elif user_input.lower() in ("/facts", "/memories"):
                display_facts_table(companion, only_active=True)
                continue

            elif user_input.lower() == "/all-facts":
                display_facts_table(companion, only_active=False)
                continue

            elif user_input.lower() == "/superseded":
                display_superseded_history(companion)
                continue

            elif user_input.lower() == "/profile":
                display_profile(companion)
                continue

            elif user_input.lower().startswith("/inspect"):
                query = user_input[8:].strip()
                if not query:
                    console.print("[yellow]Usage: /inspect <search query>[/yellow]")
                else:
                    inspect_query_retrieval(companion, query)
                continue

            elif user_input.lower() == "/reset":
                companion.reset_memory()
                console.print("[bold red]🧹 All persistent memory has been wiped for a fresh session.[/bold red]")
                continue

            elif user_input.lower() == "/debug":
                debug_mode = not debug_mode
                console.print(f"[yellow]Debug mode set to: {debug_mode}[/yellow]")
                continue

            # Run companion chat turn
            with console.status("[bold magenta]Maya is thinking...[/bold magenta]"):
                response = companion.chat(user_input)

            # Print Assistant Response
            console.print(f"\n[bold magenta]Maya:[/bold magenta] {response.content}")

            # Print Debug / Memory metadata if present or in debug mode
            if debug_mode or response.retrieved_memories or response.extracted_facts:
                if response.retrieved_memories:
                    mems_text = ", ".join(f"\"{m.fact_text[:40]}...\"" for m in response.retrieved_memories)
                    console.print(f"[dim blue]🔍 Recalled: {mems_text}[/dim blue]")
                if response.extracted_facts:
                    facts_text = ", ".join(f"\"{f.fact_text}\"" for f in response.extracted_facts)
                    console.print(f"[dim green]💾 Stored fact: {facts_text}[/dim green]")

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold magenta]Maya:[/bold magenta] Goodbye! ✨")
            sys.exit(0)


if __name__ == "__main__":
    run_cli()
