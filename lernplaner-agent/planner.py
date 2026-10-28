"""
Regelbasierte Planungslogik für den Lernplaner-Prototyp (ohne LLM).

Dieses Modul kapselt die Entscheidungslogik des Agenten-Prototyps.
Die Logik ist bewusst von den Tools (tools.py) und der Konsoleneingabe (main.py)
getrennt, damit sie später leicht durch einen LLM-Agenten ersetzt oder ergänzt
werden kann, der dieselben Tools aufruft.
"""

from typing import Any, Dict, List
from tools import (
    MIN_BREAK_MINUTES,
    format_minutes_to_time,
    get_available_slots,
    get_tasks,
    parse_time_to_minutes,
)


def create_rule_based_plan(
    tasks: List[Dict[str, Any]],
    slot: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Erstellt einen Lernplan streng nach den definierten Planungsregeln:
    - Nur offene Aufgaben einplanen (bestehende Aufgaben/Status nicht verändern).
    - Sortierung nach Priorität (1 = höchste), bei Gleichstand nach Aufgaben-ID.
    - Aufgaben vollständig einplanen, nicht aufteilen.
    - Passt eine Aufgabe nicht mehr, wird die nächste geprüft.
    - Zwischen zwei Aufgaben genau 5 Minuten Pause lassen.
    - Lernbudget begrenzt die Summe der reinen Lernminuten (ohne Pausen).
    - Aufgaben inkl. Pausen müssen in das verfügbare Zeitfenster passen.
    - Nicht eingeplante Aufgaben werden mit verständlichem Grund dokumentiert.
    """
    date_str = slot["date"]
    window_start = parse_time_to_minutes(slot["start_time"])
    window_end = parse_time_to_minutes(slot["end_time"])
    max_budget = slot["max_budget_minutes"]

    scheduled_tasks: List[Dict[str, Any]] = []
    skipped_tasks: List[Dict[str, Any]] = []

    # 1. Erledigte Aufgaben sofort aussortieren und mit Grund vermerken,
    #    offene Aufgaben für die Sortierung sammeln (Originalobjekte nicht mutieren)
    open_tasks: List[Dict[str, Any]] = []
    for task in tasks:
        if task["status"] != "offen":
            skipped_tasks.append({
                "task_id": task["id"],
                "title": task["title"],
                "priority": task["priority"],
                "duration_minutes": task["duration_minutes"],
                "status": task["status"],
                "reason": f"Aufgabe ist bereits '{task['status']}' (nur offene Aufgaben werden eingeplant).",
            })
        else:
            open_tasks.append(dict(task))

    # 2. Nach Priorität (1 vor 2 vor 3), bei Gleichstand alphabetisch nach ID sortieren
    open_tasks.sort(key=lambda t: (t["priority"], t["id"]))

    current_time = window_start
    used_budget = 0
    total_break_minutes = 0

    for task in open_tasks:
        duration = task["duration_minutes"]
        remaining_budget = max_budget - used_budget

        # Wenn bereits mindestens eine Aufgabe eingeplant wurde, sind 5 Min. Pause nötig
        required_break = MIN_BREAK_MINUTES if scheduled_tasks else 0
        proposed_start = current_time + required_break
        proposed_end = proposed_start + duration
        remaining_window_minutes = window_end - proposed_start

        fits_budget = duration <= remaining_budget
        fits_window = proposed_end <= window_end

        if not fits_budget and not fits_window:
            reason = (
                f"Passt weder ins verbleibende Lernbudget (benötigt: {duration} Min., "
                f"verfügbar: {remaining_budget} Min.) noch ins verbleibende Zeitfenster "
                f"inkl. {required_break} Min. Pause (verfügbar ab "
                f"{format_minutes_to_time(proposed_start)} bis {slot['end_time']}: "
                f"{max(0, remaining_window_minutes)} Min.)."
            )
            skipped_tasks.append({
                "task_id": task["id"],
                "title": task["title"],
                "priority": task["priority"],
                "duration_minutes": duration,
                "status": task["status"],
                "reason": reason,
            })
            continue

        if not fits_budget:
            reason = (
                f"Überschreitet das verbleibende Lernbudget (benötigt: {duration} Min., "
                f"verbleibendes Budget: {remaining_budget} Min. von max. {max_budget} Min.)."
            )
            skipped_tasks.append({
                "task_id": task["id"],
                "title": task["title"],
                "priority": task["priority"],
                "duration_minutes": duration,
                "status": task["status"],
                "reason": reason,
            })
            continue

        if not fits_window:
            if required_break > 0 and (current_time + duration <= window_end):
                reason = (
                    f"Passt wegen der vorgeschriebenen {required_break}-Minuten-Pause nicht mehr "
                    f"in das Zeitfenster bis {slot['end_time']} (frühester Start nach Pause: "
                    f"{format_minutes_to_time(proposed_start)}, Ende wäre {format_minutes_to_time(proposed_end)})."
                )
            else:
                reason = (
                    f"Überschreitet das verfügbare Zeitfenster bis {slot['end_time']} "
                    f"(benötigt: {duration} Min. ab {format_minutes_to_time(proposed_start)}, "
                    f"Ende wäre {format_minutes_to_time(proposed_end)})."
                )
            skipped_tasks.append({
                "task_id": task["id"],
                "title": task["title"],
                "priority": task["priority"],
                "duration_minutes": duration,
                "status": task["status"],
                "reason": reason,
            })
            continue

        # Aufgabe passt vollständig in Lernbudget und Zeitfenster -> einplanen
        scheduled_tasks.append({
            "task_id": task["id"],
            "title": task["title"],
            "priority": task["priority"],
            "date": date_str,
            "start_time": format_minutes_to_time(proposed_start),
            "end_time": format_minutes_to_time(proposed_end),
            "duration_minutes": duration,
            "break_before_minutes": required_break,
        })
        current_time = proposed_end
        used_budget += duration
        total_break_minutes += required_break

    return {
        "agent_mode": "regelbasierter Agenten-Prototyp ohne LLM",
        "date": date_str,
        "available_window": {
            "start_time": slot["start_time"],
            "end_time": slot["end_time"],
            "available_window_minutes": slot["available_window_minutes"],
        },
        "max_budget_minutes": max_budget,
        "total_learning_minutes": used_budget,
        "total_break_minutes": total_break_minutes,
        "total_occupied_minutes": used_budget + total_break_minutes,
        "scheduled_tasks": scheduled_tasks,
        "skipped_tasks": skipped_tasks,
    }


def run_planning_agent() -> Dict[str, Any]:
    """
    Führt den regelbasierten Planungsprozess mithilfe der definierten Tools aus.
    Ruft get_tasks() und get_available_slots() auf und erstellt den Planvorschlag.
    """
    tasks = get_tasks()
    slot = get_available_slots()
    return create_rule_based_plan(tasks, slot)
