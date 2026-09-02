"""
Automated Evaluation Harness Runner for Companion-AI.
Runs multi-turn benchmark suites, evaluates memory recall, contradiction resolution,
and persona drift using LLM-as-Judge, and compares against an Oracle baseline.
"""

from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from src.companion import Companion
from src.config import config
from eval.judge import EvaluationJudge, JudgeResult
from eval.oracle import OracleBaseline

console = Console()
SCENARIOS_DIR = Path(__file__).parent / "scenarios"


def load_scenarios() -> List[Dict[str, Any]]:
    """Load all JSON scenarios from scenarios directory."""
    scenarios = []
    for p in sorted(SCENARIOS_DIR.glob("*.json")):
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                scenarios.extend(data)
            else:
                scenarios.append(data)
    return scenarios


def run_single_scenario(
    scenario: Dict[str, Any],
    judge: EvaluationJudge,
    oracle: OracleBaseline
) -> Dict[str, Any]:
    """Execute a single multi-turn scenario in an isolated temporary database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        test_db_path = tmp_db.name

    try:
        companion = Companion(user_id="test_user", db_path=test_db_path)
        turns = scenario.get("turns", [])
        probe_turn = None
        history_transcript = []

        # Play through conversation turns
        for turn_data in turns:
            role = turn_data.get("role", "user")
            content = turn_data.get("content", "")
            history_transcript.append(turn_data)

            if role == "probe":
                probe_turn = turn_data
                # Probing turn
                comp_response = companion.chat(content)
                break
            else:
                # Regular dialogue turn: companion processes and stores memories
                companion.chat(content)

        if not probe_turn:
            raise ValueError("Scenario has no probe turn defined.")

        expected = probe_turn.get("expected_outcomes", {})
        
        # Format summary for judge
        transcript_summary = "\n".join(f"- Turn {t.get('turn', i+1)}: {t.get('content')}" for i, t in enumerate(history_transcript[:-1]))

        # Run LLM-as-Judge
        judge_res = judge.evaluate(
            scenario_title=scenario.get("title", ""),
            user_probe=probe_turn.get("content", ""),
            companion_response=comp_response.content,
            expected_outcomes=expected,
            full_transcript_summary=transcript_summary
        )

        # Run Oracle Baseline
        oracle_response = oracle.generate_oracle_response(
            full_transcript=history_transcript[:-1],
            probing_turn=probe_turn.get("content", "")
        )

        return {
            "id": scenario.get("id"),
            "title": scenario.get("title"),
            "total_turns": len(turns),
            "companion_response": comp_response.content,
            "retrieved_memories": [m.fact_text for m in comp_response.retrieved_memories],
            "oracle_response": oracle_response,
            "judge_result": judge_res,
        }

    finally:
        if os.path.exists(test_db_path):
            os.remove(test_db_path)


def run_benchmark():
    """Run full benchmark harness and print quantitative results."""
    console.print(Panel("[bold magenta]🧪 Companion-AI Memory & Evaluation Benchmark Harness[/bold magenta]\n[dim]Testing Long-Range Recall, Contradiction Supersession & Persona Consistency[/dim]"))
    
    scenarios = load_scenarios()
    console.print(f"[cyan]Loaded {len(scenarios)} benchmark scenario(s). Running evaluation...[/cyan]\n")

    judge = EvaluationJudge()
    oracle = OracleBaseline()

    results = []
    for sc in scenarios:
        console.print(f"▶ Running Scenario: [bold yellow]{sc.get('title')}[/bold yellow] ({len(sc.get('turns', []))} turns)...")
        res = run_single_scenario(sc, judge, oracle)
        results.append(res)
        status_text = "[bold green]PASS[/bold green]" if res["judge_result"].passed else "[bold red]FAIL[/bold red]"
        console.print(f"  Result: {status_text} | Memory: {res['judge_result'].memory_score}/5 | Contradiction: {res['judge_result'].contradiction_score}/5 | Persona: {res['judge_result'].persona_score}/5\n")

    # Aggregate Metrics Table
    table = Table(title="📊 Quantitative Evaluation Results", border_style="cyan")
    table.add_column("Scenario ID", style="cyan")
    table.add_column("Scenario Title", style="white")
    table.add_column("Turns", style="yellow", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Memory", justify="right")
    table.add_column("Contradiction", justify="right")
    table.add_column("Persona", justify="right")

    total = len(results)
    passed_count = sum(1 for r in results if r["judge_result"].passed)
    avg_mem = sum(r["judge_result"].memory_score for r in results) / max(total, 1)
    avg_contra = sum(r["judge_result"].contradiction_score for r in results) / max(total, 1)
    avg_persona = sum(r["judge_result"].persona_score for r in results) / max(total, 1)

    for r in results:
        jr: JudgeResult = r["judge_result"]
        status = "[bold green]PASS[/bold green]" if jr.passed else "[bold red]FAIL[/bold red]"
        table.add_row(
            r["id"],
            r["title"][:45],
            str(r["total_turns"]),
            status,
            f"{jr.memory_score}/5",
            f"{jr.contradiction_score}/5",
            f"{jr.persona_score}/5",
        )

    console.print(table)

    pass_rate = (passed_count / total) * 100 if total > 0 else 0
    console.print(Panel(
        f"[bold white]Overall Summary Metrics:[/bold white]\n"
        f"• [bold green]Pass Rate:[/bold green] {passed_count}/{total} ({pass_rate:.1f}%)\n"
        f"• [bold cyan]Avg Memory Recall Score:[/bold cyan] {avg_mem:.2f} / 5.0\n"
        f"• [bold yellow]Avg Contradiction Score:[/bold yellow] {avg_contra:.2f} / 5.0\n"
        f"• [bold magenta]Avg Persona Consistency Score:[/bold magenta] {avg_persona:.2f} / 5.0",
        border_style="green" if pass_rate >= 80 else "red"
    ))

    # Detailed Inspection of Responses & Oracle Comparison
    console.print("\n[bold cyan]🔍 Detailed Scenario Probes & Oracle Comparison:[/bold cyan]\n")
    for r in results:
        console.print(f"[bold underline yellow]Scenario: {r['title']}[/bold underline yellow]")
        console.print(f"[bold green]Retrieved Memories:[/bold green] {r['retrieved_memories']}")
        console.print(f"[bold magenta]Companion Generated Response:[/bold magenta]\n{r['companion_response']}")
        console.print(f"[bold blue]Oracle Ideal Baseline Response:[/bold blue]\n{r['oracle_response']}")
        console.print(f"[dim]Judge Reasoning: {r['judge_result'].reasoning}[/dim]\n" + "-"*60)


if __name__ == "__main__":
    run_benchmark()
