"""
Tools und Guardrails für den lokalen Lernplaner-Prototyp.

Dieses Modul stellt die Werkzeuge (Tools) bereit, die der regelbasierte
Agenten-Prototyp (oder später ein angebundenes LLM) nutzen kann:
- get_tasks(): Liest Lernaufgaben aus data/tasks.json.
- get_available_slots(): Gibt das zuvor gesetzte Zeitfenster strukturiert zurück.
- save_plan(plan): Validiert einen Plan mittels Guardrails und speichert ihn
  ausschließlich unter output/lernplan.json.
"""

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent
TASKS_FILE = BASE_DIR / "data" / "tasks.json"
OUTPUT_FILE = BASE_DIR / "output" / "lernplan.json"
MIN_BREAK_MINUTES = 5

# Interner Zustand für das vom Benutzer eingegebene Zeitfenster
_current_slot: Optional[Dict[str, Any]] = None


class GuardrailError(ValueError):
    """Wird ausgelöst, wenn ein Guardrail bei der Eingabe- oder Planvalidierung anschlägt."""
    pass


def parse_time_to_minutes(time_str: str) -> int:
    """Wandelt eine Uhrzeit im Format HH:MM in Minuten seit Mitternacht um."""
    if not isinstance(time_str, str):
        raise GuardrailError(f"Ungültiges Uhrzeitformat '{time_str}'. Erwartet wird HH:MM.")
    try:
        dt = datetime.strptime(time_str.strip(), "%H:%M")
        return dt.hour * 60 + dt.minute
    except ValueError as exc:
        raise GuardrailError(
            f"Ungültige Uhrzeit '{time_str}'. Bitte Format HH:MM (00:00 bis 23:59) verwenden."
        ) from exc


def format_minutes_to_time(minutes: int) -> str:
    """Wandelt Minuten seit Mitternacht in das Format HH:MM um."""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def validate_date_str(date_str: str) -> str:
    """Prüft, ob ein Datum im Format YYYY-MM-DD vorliegt."""
    if not isinstance(date_str, str):
        raise GuardrailError("Datum muss als Text im Format YYYY-MM-DD übergeben werden.")
    cleaned = date_str.strip()
    try:
        datetime.strptime(cleaned, "%Y-%m-%d")
        return cleaned
    except ValueError as exc:
        raise GuardrailError(
            f"Ungültiges Datum '{date_str}'. Bitte Format YYYY-MM-DD (z. B. 2026-11-02) verwenden."
        ) from exc


def set_available_slots(date_str: str, start_str: str, end_str: str, max_budget_minutes: int) -> Dict[str, Any]:
    """
    Validiert und speichert die Benutzereingaben für das verfügbare Zeitfenster,
    damit get_available_slots() sie als Agenten-Tool bereitstellen kann.
    """
    global _current_slot
    valid_date = validate_date_str(date_str)
    start_min = parse_time_to_minutes(start_str)
    end_min = parse_time_to_minutes(end_str)

    if end_min <= start_min:
        raise GuardrailError(
            f"Das Ende der Lernzeit ({end_str}) muss nach dem Beginn ({start_str}) liegen."
        )

    if not isinstance(max_budget_minutes, int) or isinstance(max_budget_minutes, bool) or max_budget_minutes <= 0:
        raise GuardrailError(
            "Das maximale Lernbudget muss eine positive ganze Zahl (in Minuten) sein."
        )

    _current_slot = {
        "date": valid_date,
        "start_time": format_minutes_to_time(start_min),
        "end_time": format_minutes_to_time(end_min),
        "available_window_minutes": end_min - start_min,
        "max_budget_minutes": max_budget_minutes,
    }
    return dict(_current_slot)


def validate_task_record(task: Any, seen_ids: set) -> Dict[str, Any]:
    """Prüft einen einzelnen Aufgabeneintrag aus der JSON-Datei auf Korrektheit."""
    if not isinstance(task, dict):
        raise GuardrailError("Fehlerhafte Aufgabenstruktur: Jeder Eintrag muss ein JSON-Objekt sein.")

    required_fields = {"id", "title", "duration_minutes", "priority", "status"}
    missing = required_fields - set(task.keys())
    if missing:
        raise GuardrailError(f"Aufgabe unvollständig. Fehlende Felder: {', '.join(sorted(missing))}")

    task_id = task["id"]
    if not isinstance(task_id, str) or not task_id.strip():
        raise GuardrailError("Ungültige Aufgaben-ID: Muss ein nicht-leerer Text sein.")
    if task_id in seen_ids:
        raise GuardrailError(f"Doppelte Aufgaben-ID in Datenquelle gefunden: '{task_id}'.")
    seen_ids.add(task_id)

    title = task["title"]
    if not isinstance(title, str) or not title.strip():
        raise GuardrailError(f"Ungültiger Titel bei Aufgabe '{task_id}'.")

    duration = task["duration_minutes"]
    if not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0:
        raise GuardrailError(
            f"Ungültige Dauer bei Aufgabe '{task_id}': Muss eine positive ganze Zahl in Minuten sein."
        )

    priority = task["priority"]
    if not isinstance(priority, int) or isinstance(priority, bool) or priority not in (1, 2, 3):
        raise GuardrailError(
            f"Ungültige Priorität bei Aufgabe '{task_id}': Erlaubt sind nur 1, 2 oder 3."
        )

    status = task["status"]
    if status not in ("offen", "erledigt"):
        raise GuardrailError(
            f"Ungültiger Status bei Aufgabe '{task_id}': Erlaubt sind nur 'offen' oder 'erledigt'."
        )

    # Kopie zurückgeben, damit Originaldaten nicht versehentlich verändert werden
    return {
        "id": task_id,
        "title": title,
        "duration_minutes": duration,
        "priority": priority,
        "status": status,
    }


def get_tasks(tasks_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Tool: get_tasks()
    Liest die Lernaufgaben aus data/tasks.json und prüft deren Struktur.
    """
    target_path = tasks_path if tasks_path is not None else TASKS_FILE
    print(f"[TOOL-AUFRUF] get_tasks() -> Lese Aufgaben aus '{target_path.relative_to(BASE_DIR) if target_path.is_relative_to(BASE_DIR) else target_path}'")

    if not target_path.exists():
        raise GuardrailError(f"Aufgabendatei nicht gefunden: {target_path}")

    try:
        raw_text = target_path.read_text(encoding="utf-8")
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise GuardrailError(f"Fehlerhaftes JSON in Aufgabendatei '{target_path}': {exc}") from exc
    except OSError as exc:
        raise GuardrailError(f"Lesefehler bei Aufgabendatei '{target_path}': {exc}") from exc

    if not isinstance(data, list):
        raise GuardrailError("Fehlerhafte Aufgabendatei: Die oberste JSON-Struktur muss eine Liste sein.")

    seen_ids = set()
    validated_tasks = [validate_task_record(item, seen_ids) for item in data]
    return validated_tasks


def get_available_slots() -> Dict[str, Any]:
    """
    Tool: get_available_slots()
    Gibt das zuvor vom Benutzer eingegebene Zeitfenster und Lernbudget strukturiert zurück.
    """
    print("[TOOL-AUFRUF] get_available_slots() -> Lese verfügbares Zeitfenster und Lernbudget")
    if _current_slot is None:
        raise GuardrailError("Es wurden noch keine Zeitfenster-Daten hinterlegt.")
    return dict(_current_slot)


def validate_plan(
    plan: Dict[str, Any],
    tasks: Optional[List[Dict[str, Any]]] = None,
    slot: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Prüft alle Guardrails für einen erstellten Lernplan.
    Wirft GuardrailError, falls eine Regel verletzt wird (z. B. durch einen fehlerhaften
    Plan eines zukünftigen LLMs).
    """
    if not isinstance(plan, dict):
        raise GuardrailError("Der Lernplan muss ein JSON-Objekt (Dictionary) sein.")

    if tasks is None:
        tasks = get_tasks()
    if slot is None:
        slot = get_available_slots()

    task_map = {t["id"]: t for t in tasks}

    # 1. Basisdaten des Plans gegen das aktive Zeitfenster prüfen
    plan_date = plan.get("date")
    if plan_date != slot["date"]:
        raise GuardrailError(
            f"Plandatum ({plan_date}) stimmt nicht mit dem ausgewählten Datum ({slot['date']}) überein."
        )

    window_start = parse_time_to_minutes(slot["start_time"])
    window_end = parse_time_to_minutes(slot["end_time"])
    max_budget = slot["max_budget_minutes"]

    scheduled_items = plan.get("scheduled_tasks")
    if not isinstance(scheduled_items, list):
        raise GuardrailError("Feld 'scheduled_tasks' fehlt oder ist keine Liste.")

    seen_task_ids = set()
    total_planned_minutes = 0
    previous_end_min: Optional[int] = None

    for idx, block in enumerate(scheduled_items, start=1):
        if not isinstance(block, dict):
            raise GuardrailError(f"Eintrag #{idx} in 'scheduled_tasks' ist kein gültiges Objekt.")

        task_id = block.get("task_id")
        if not isinstance(task_id, str) or task_id not in task_map:
            raise GuardrailError(
                f"Guardrail verletzt: Unbekannte Aufgaben-ID '{task_id}' im Plan."
            )

        # Guardrail: Jede Aufgabe höchstens einmal einplanen
        if task_id in seen_task_ids:
            raise GuardrailError(
                f"Guardrail verletzt: Aufgabe '{task_id}' wurde mehrfach eingeplant."
            )
        seen_task_ids.add(task_id)

        reference_task = task_map[task_id]

        # Guardrail: Nur offene Aufgaben zulassen
        if reference_task["status"] != "offen":
            raise GuardrailError(
                f"Guardrail verletzt: Aufgabe '{task_id}' hat den Status '{reference_task['status']}' "
                "und darf nicht eingeplant werden."
            )

        # Guardrail: Alle Blöcke müssen am ausgewählten Datum liegen
        block_date = block.get("date", plan_date)
        if block_date != slot["date"]:
            raise GuardrailError(
                f"Guardrail verletzt: Block für Aufgabe '{task_id}' liegt am falschen Datum ({block_date})."
            )

        # Zeiten prüfen
        start_str = block.get("start_time")
        end_str = block.get("end_time")
        start_min = parse_time_to_minutes(start_str)
        end_min = parse_time_to_minutes(end_str)

        if end_min <= start_min:
            raise GuardrailError(
                f"Guardrail verletzt: Endzeit ({end_str}) liegt nicht nach Startzeit ({start_str}) bei '{task_id}'."
            )

        # Guardrail: Geplante Dauer muss der gespeicherten Aufgabendauer entsprechen
        expected_duration = reference_task["duration_minutes"]
        planned_duration = block.get("duration_minutes")
        actual_span = end_min - start_min

        if planned_duration != expected_duration or actual_span != expected_duration:
            raise GuardrailError(
                f"Guardrail verletzt: Geplante Dauer für '{task_id}' ({planned_duration} Min. / "
                f"Zeitraum {actual_span} Min.) entspricht nicht der Aufgabendauer ({expected_duration} Min.)."
            )

        # Guardrail: Innerhalb des verfügbaren Zeitfensters
        if start_min < window_start or end_min > window_end:
            raise GuardrailError(
                f"Guardrail verletzt: Aufgabe '{task_id}' ({start_str}-{end_str}) liegt außerhalb "
                f"des verfügbaren Zeitfensters ({slot['start_time']}-{slot['end_time']})."
            )

        # Guardrail: Keine Überschneidungen und mindestens 5 Minuten Pause zwischen Aufgaben
        if previous_end_min is not None:
            if start_min < previous_end_min:
                raise GuardrailError(
                    f"Guardrail verletzt: Zeitliche Überschneidung bei Aufgabe '{task_id}' "
                    f"(Start {start_str} vor vorherigem Ende {format_minutes_to_time(previous_end_min)})."
                )
            if start_min - previous_end_min < MIN_BREAK_MINUTES:
                raise GuardrailError(
                    f"Guardrail verletzt: Pause vor Aufgabe '{task_id}' beträgt nur "
                    f"{start_min - previous_end_min} Min. (mindestens {MIN_BREAK_MINUTES} Min. erforderlich)."
                )

        previous_end_min = end_min
        total_planned_minutes += expected_duration

    # Guardrail: Lernbudget darf nicht überschritten werden
    if total_planned_minutes > max_budget:
        raise GuardrailError(
            f"Guardrail verletzt: Summe der geplanten Lernminuten ({total_planned_minutes} Min.) "
            f"überschreitet das maximale Lernbudget ({max_budget} Min.)."
        )

    if "total_learning_minutes" in plan and plan["total_learning_minutes"] != total_planned_minutes:
        raise GuardrailError(
            f"Guardrail verletzt: Angegebene Gesamtlernzeit ({plan['total_learning_minutes']} Min.) "
            f"stimmt nicht mit der Summe der Aufgaben ({total_planned_minutes} Min.) überein."
        )


def save_plan(
    plan: Dict[str, Any],
    confirm_callback: Optional[Callable[[str], bool]] = None,
) -> bool:
    """
    Tool: save_plan(plan)
    Validiert den vollständigen Plan über alle Guardrails und speichert ihn nach
    ausdrücklicher Konsolenbestätigung ausschließlich unter output/lernplan.json.
    """
    print(f"[TOOL-AUFRUF] save_plan(plan) -> Validiere Plan und bereite Speicherung unter '{OUTPUT_FILE.relative_to(BASE_DIR)}' vor")

    # Guardrail 1: Vollständige fachliche und zeitliche Validierung
    tasks = get_tasks()
    slot = get_available_slots()
    validate_plan(plan, tasks=tasks, slot=slot)

    # Guardrail 2: Fester Speicherpfad (keine frei wählbaren Pfade)
    target_path = OUTPUT_FILE.resolve()
    expected_path = (BASE_DIR / "output" / "lernplan.json").resolve()
    if target_path != expected_path:
        raise GuardrailError("Unzulässiger Speicherpfad.")

    if confirm_callback is None:
        def default_confirm(prompt_text: str) -> bool:
            answer = input(prompt_text).strip().lower()
            return answer in ("j", "ja", "y", "yes")
        confirm_callback = default_confirm

    # Guardrail 3: Ausdrückliche Bestätigung vor dem Speichern
    if not confirm_callback("\nSoll dieser Lernplan jetzt unter 'output/lernplan.json' gespeichert werden? (j/n): "):
        print("[ABBRUCH] Speicherung vom Benutzer abgelehnt. Es wurde keine Datei geschrieben.")
        return False

    # Guardrail 4: Zusätzliche Warnung und Bestätigung vor Überschreiben einer vorhandenen Datei
    if target_path.exists():
        print(f"[WARNUNG] Die Datei '{target_path.relative_to(BASE_DIR)}' existiert bereits!")
        if not confirm_callback("Möchten Sie den vorhandenen Lernplan wirklich überschreiben? (j/n): "):
            print("[ABBRUCH] Überschreiben abgelehnt. Bestehender Lernplan bleibt unverändert.")
            return False

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[ERFOLG] Lernplan wurde erfolgreich in '{target_path.relative_to(BASE_DIR)}' gespeichert.")
    return True
