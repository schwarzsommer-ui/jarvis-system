"""Local CrewAI entry point for the J.A.R.V.I.S. multi-agent planner.

The agents plan and generate a safe workflow. Desktop actions remain explicit
and must be invoked separately through ``desktop_control`` by the local user.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    try:
        from crewai import Agent, Crew, LLM, Process, Task
    except ImportError:
        print(
            "CrewAI fehlt. Aktiviere zuerst .\\venv\\Scripts\\activate "
            "und führe .\\setup_jarvis.ps1 -Install aus.",
            file=sys.stderr,
        )
        return 1

    model = os.getenv("OLLAMA_MODEL", "llama3.1").strip()
    ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    nim_key = os.getenv("NIM_API_KEY", "").strip()
    nim_url = os.getenv(
        "NIM_API_URL",
        "https://integrate.api.nvidia.com/v1/chat/completions",
    ).strip()
    nim_model = os.getenv("NIM_MODEL", "meta/llama-3.1-8b-instruct").strip()
    if nim_key:
        nim_base_url = nim_url.removesuffix("/chat/completions")
        llm = LLM(
            model=f"openai/{nim_model}",
            base_url=nim_base_url,
            api_key=nim_key,
        )
    else:
        llm = LLM(model=f"ollama/{model}", base_url=ollama_url)

    architect = Agent(
        role="Architekt",
        goal="Plane eine sichere, nachvollziehbare Jarvis-Struktur.",
        backstory="Du entwirfst lokale Systeme und verlangst Bestätigung vor irreversiblen Aktionen.",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )
    builder = Agent(
        role="Builder",
        goal="Erstelle umsetzbare Code- und Workflow-Schritte.",
        backstory="Du schreibst sauberen, testbaren Code und führst keine Desktop-Aktion selbst aus.",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    plan_task = Task(
        description=(
            "Plane ein lokales Jarvis-System mit Desktop-Steuerung, Simulation, "
            "Code und Workflows. Liste Risiken, benötigte Bestätigungen und "
            "einen kurzen Verifikationsplan."
        ),
        expected_output="Ein kurzer Plan mit Architektur, Dateien, Sicherheitsgrenzen und Tests.",
        agent=architect,
    )
    build_task = Task(
        description=(
            "Überführe den Architekturplan in konkrete, kleine Umsetzungsschritte. "
            "Erzeuge keinen unbestätigten externen Versand, keine Trades und kein Löschen."
        ),
        expected_output="Konkrete nächste Schritte und ein lokaler Testplan.",
        agent=builder,
        context=[plan_task],
    )

    crew = Crew(
        agents=[architect, builder],
        tasks=[plan_task, build_task],
        process=Process.sequential,
        verbose=True,
    )
    result = crew.kickoff()
    print("\nJ.A.R.V.I.S.-Plan:\n")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
