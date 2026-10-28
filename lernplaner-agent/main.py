"""
Konsolenanwendung für den lokalen Lernplaner.

Hinweis zur Architektur:
Dies ist ausdrücklich ein regelbasierter Agenten-Prototyp ohne LLM.
Es wird kein Sprachmodell (LLM) aufgerufen und keine externe Bibliothek benötigt.
Die Trennung in:
- main.py (Konsoleneingabe und -ausgabe)
- planner.py (regelbasierte Planungslogik)
- tools.py (Tools get_tasks, get_available_slots, save_plan + Guardrails)
ist so aufgebaut, dass später ein echtes LLM dieselben Tools nutzen kann.
"""

import sys
from typing import Any, Dict

from planner import run_planning_agent
from tools import (
    GuardrailError,
    parse_time_to_minutes,
    save_plan,
    set_available_slots,
    validate_date_str,
)


def prompt_date() -> str:
    """Fragt das gewünschte Lerndatum in der Konsole ab."""
    while True:
        raw = input("Datum (YYYY-MM-DD, z. B. 2026-11-02): ").strip()
        try:
            return validate_date_str(raw)
        except GuardrailError as err:
            print(f"  [Eingabefehler] {err}")


def prompt_time_window() -> tuple[str, str]:
    """Fragt Beginn und Ende der verfügbaren Lernzeit ab."""
    while True:
        start_raw = input("Beginn der verfügbaren Lernzeit (HH:MM, z. B. 14:00): ").strip()
        try:
            start_min = parse_time_to_minutes(start_raw)
        except GuardrailError as err:
            print(f"  [Eingabefehler] {err}")
            continue

        end_raw = input("Ende der verfügbaren Lernzeit   (HH:MM, z. B. 16:30): ").strip()
        try:
            end_min = parse_time_to_minutes(end_raw)
        except GuardrailError as err:
            print(f"  [Eingabefehler] {err}")
            continue

        if end_min <= start_min:
            print("  [Eingabefehler] Das Ende der Lernzeit muss nach dem Beginn liegen.")
            continue

        return start_raw, end_raw


def prompt_budget() -> int:
    """Fragt das maximale Lernbudget in ganzen Minuten ab."""
    while True:
        raw = input("Maximales Lernbudget in Minuten (ohne Pausen, z. B. 110): ").strip()
        try:
            budget = int(raw)
            if budget <= 0:
                print("  [Eingabefehler] Bitte eine positive ganze Zahl größer als 0 eingeben.")
                continue
            return budget
        except ValueError:
            print("  [Eingabefehler] Bitte eine gültige ganze Zahl in Minuten eingeben (z. B. 90).")


def print_plan_summary(plan: Dict[str, Any]) -> None:
    """Gibt den erstellten Lernplan und die nicht eingeplanten Aufgaben übersichtlich aus."""
    print("\n" + "=" * 72)
    print("ERSTELLTER LERNPLAN (Regelbasierter Agenten-Prototyp ohne LLM)")
    print("=" * 72)
    window = plan["available_window"]
    print(f"Datum:                {plan['date']}")
    print(
        f"Verfügbares Fenster:  {window['start_time']} - {window['end_time']} Uhr "
        f"({window['available_window_minutes']} Min.)"
    )
    print(
        f"Lernbudget (netto):   {plan['total_learning_minutes']} / {plan['max_budget_minutes']} Min. verplant"
    )
    print(f"Pausenzeit gesamt:    {plan['total_break_minutes']} Min.")
    print(f"Gesamtdauer im Slot:  {plan['total_occupied_minutes']} Min.")
    print("-" * 72)

    scheduled = plan["scheduled_tasks"]
    if not scheduled:
        print("Es konnten keine Aufgaben in das gewählte Zeitfenster / Budget eingeplant werden.")
    else:
        print("Eingeplante Aufgaben:")
        for idx, item in enumerate(scheduled, start=1):
            if item["break_before_minutes"] > 0:
                print(f"      ... {item['break_before_minutes']} Min. Pause ...")
            print(
                f"  {idx}. [{item['start_time']} - {item['end_time']}] "
                f"{item['task_id']} | Prio {item['priority']} | {item['duration_minutes']} Min. | "
                f"{item['title']}"
            )

    print("-" * 72)
    skipped = plan["skipped_tasks"]
    if not skipped:
        print("Nicht eingeplante Aufgaben: Keine (alle Aufgaben wurden eingeplant).")
    else:
        print("Nicht eingeplante Aufgaben (mit Begründung):")
        for item in skipped:
            print(
                f"  - {item['task_id']} (Prio {item['priority']}, {item['duration_minutes']} Min., "
                f"Status: {item['status']}): {item['title']}"
            )
            print(f"    Grund: {item['reason']}")
    print("=" * 72)


def main() -> int:
    print("=" * 72)
    print("LOKALER LERNPLANER - Regelbasierter Agenten-Prototyp ohne LLM")
    print("=" * 72)
    print("Hinweis: Dieser Prototyp arbeitet rein regelbasiert ohne Sprachmodell (LLM),")
    print("verwendet aber bereits klar abgegrenzte Agenten-Tools und Guardrails.\n")

    try:
        date_str = prompt_date()
        start_str, end_str = prompt_time_window()
        budget_minutes = prompt_budget()

        set_available_slots(
            date_str=date_str,
            start_str=start_str,
            end_str=end_str,
            max_budget_minutes=budget_minutes,
        )

        print("\n--- Starte Agenten-Ablauf (Regelbasiert) ---")
        plan = run_planning_agent()
        print_plan_summary(plan)

        # Tool save_plan aufrufen (inkl. Guardrail-Validierung & Bestätigungsdialog)
        save_plan(plan)
        return 0

    except GuardrailError as err:
        print(f"\n[GUARDRAIL-FEHLER] Vorgang wurde gestoppt: {err}")
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\n\n[ABBRUCH] Programm durch Benutzereingabe beendet.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
