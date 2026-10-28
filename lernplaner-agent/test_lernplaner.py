"""
Unit-Tests für den regelbasierten Lernplaner-Prototyp und seine Guardrails.

Geprüft werden:
1. Die Planungsregeln (Priorität, ID-Sortierung bei Gleichstand, 5-Minuten-Pause,
   Lernbudget ohne Pausen, Zeitfenster inkl. Pausen, Überspringen nicht passender
   Aufgaben zugunsten späterer kürzerer Aufgaben, Nicht-Verändern der Originaldaten).
2. Die Guardrails bei der direkten Validierung (validate_plan / save_plan),
   insbesondere gegen ungültige Pläne, wie sie z. B. ein halluzinierendes LLM
   erzeugen könnte:
   - Unbekannte Aufgaben-ID
   - Doppelte Aufgabe
   - Zeitliche Überschneidung / fehlende 5-Minuten-Pause
   - Falsche Dauer
   - Überschrittenes Lernbudget
   - Erledigte Aufgabe eingeplant
   - Aufgabe außerhalb des Zeitfensters / falsches Datum
   - Bestätigungs- und Überschreibschutz in save_plan
   - Fehlerhafte JSON-Daten / Eingaben
"""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from planner import create_rule_based_plan, run_planning_agent
import tools
from tools import (
    GuardrailError,
    get_available_slots,
    get_tasks,
    save_plan,
    set_available_slots,
    validate_plan,
)


class TestLernplanerAndGuardrails(unittest.TestCase):
    def setUp(self) -> None:
        # Standard-Zeitfenster für Tests setzen: 14:00 bis 16:00 (120 Min. Fenster), 100 Min. Budget
        self.slot = set_available_slots(
            date_str="2026-11-02",
            start_str="14:00",
            end_str="16:00",
            max_budget_minutes=100,
        )
        self.tasks = get_tasks()

    def test_sample_tasks_meet_requirements(self) -> None:
        """Prüft, dass genau 6 Beispielaufgaben mit allen Pflichtfeldern existieren."""
        self.assertEqual(len(self.tasks), 6)
        statuses = {t["status"] for t in self.tasks}
        self.assertEqual(statuses, {"offen", "erledigt"})
        priorities = {t["priority"] for t in self.tasks}
        self.assertEqual(priorities, {1, 2, 3})

    def test_planning_rules_sorting_breaks_and_skipping(self) -> None:
        """
        Prüft die Planungsregeln:
        - Nur offene Aufgaben (TASK-004 ist 'erledigt' -> wird übersprungen)
        - Sortierung nach Priorität (1 vor 2 vor 3), bei Gleichstand nach ID
          (TASK-001 vor TASK-002; TASK-003 vor TASK-006)
        - 5 Minuten Pause zwischen Aufgaben
        - Passt eine Aufgabe nicht mehr, wird die nächste geprüft
        - Originalaufgaben und deren Status werden nicht verändert
        """
        # Fenster: 14:00 - 16:00 (120 Min.), Budget: 100 Min.
        # Offene Aufgaben nach Sortierung:
        # 1. TASK-001 (Prio 1, 45 Min.) -> 14:00 - 14:45 (Budget: 45/100)
        # 2. TASK-002 (Prio 1, 30 Min.) -> +5 Min Pause -> 14:50 - 15:20 (Budget: 75/100)
        # 3. TASK-003 (Prio 2, 25 Min.) -> +5 Min Pause -> 15:25 - 15:50 (Budget: 100/100)
        # 4. TASK-006 (Prio 2, 60 Min.) -> Passt nicht (Budget 0 übrig, Fenster nur 10 Min.)
        # 5. TASK-005 (Prio 3, 20 Min.) -> Passt nicht (Budget 0 übrig)
        original_copy = copy.deepcopy(self.tasks)
        plan = run_planning_agent()

        # Sicherstellen, dass keine Aufgabe verändert wurde
        self.assertEqual(self.tasks, original_copy)

        scheduled_ids = [item["task_id"] for item in plan["scheduled_tasks"]]
        self.assertEqual(scheduled_ids, ["TASK-001", "TASK-002", "TASK-003"])
        self.assertEqual(plan["total_learning_minutes"], 100)
        self.assertEqual(plan["total_break_minutes"], 10)
        self.assertEqual(plan["total_occupied_minutes"], 110)

        # Zeiten inklusive 5-Minuten-Pausen prüfen
        self.assertEqual(plan["scheduled_tasks"][0]["start_time"], "14:00")
        self.assertEqual(plan["scheduled_tasks"][0]["end_time"], "14:45")
        self.assertEqual(plan["scheduled_tasks"][1]["start_time"], "14:50")
        self.assertEqual(plan["scheduled_tasks"][1]["end_time"], "15:20")
        self.assertEqual(plan["scheduled_tasks"][2]["start_time"], "15:25")
        self.assertEqual(plan["scheduled_tasks"][2]["end_time"], "15:50")

        # Nicht eingeplante Aufgaben müssen mit Begründung enthalten sein
        skipped_ids = {item["task_id"] for item in plan["skipped_tasks"]}
        self.assertEqual(skipped_ids, {"TASK-004", "TASK-005", "TASK-006"})
        for item in plan["skipped_tasks"]:
            self.assertTrue(isinstance(item["reason"], str) and len(item["reason"]) > 10)

    def test_skip_large_task_and_schedule_next_fitting_task(self) -> None:
        """
        Prüft: 'Passt eine Aufgabe nicht mehr, prüfe die nächste.'
        Wenn TASK-006 (60 Min., Prio 2) nicht mehr passt, aber TASK-005 (20 Min., Prio 3)
        noch hineinpasst, muss TASK-005 eingeplant werden.
        """
        # Fenster 14:00 - 16:30 (150 Min.), Budget 120 Min.
        # TASK-001 (45) + TASK-002 (30) + TASK-003 (25) = 100 Min. Lernen, Ende 15:50.
        # Verbleibendes Budget: 20 Min.
        # TASK-006 (60 Min., Prio 2) passt nicht ins restliche Budget (20 Min.).
        # Nächste Aufgabe TASK-005 (20 Min., Prio 3) passt genau (15:55 - 16:15, Budget 120/120)!
        slot = set_available_slots("2026-11-02", "14:00", "16:30", 120)
        plan = create_rule_based_plan(self.tasks, slot)
        scheduled_ids = [item["task_id"] for item in plan["scheduled_tasks"]]
        self.assertEqual(scheduled_ids, ["TASK-001", "TASK-002", "TASK-003", "TASK-005"])
        self.assertEqual(plan["total_learning_minutes"], 120)

    def test_guardrail_unknown_task_id(self) -> None:
        """Guardrail-Test 1: Unbekannte Aufgaben-ID im Plan muss abgelehnt werden."""
        invalid_plan = {
            "date": "2026-11-02",
            "total_learning_minutes": 30,
            "scheduled_tasks": [
                {
                    "task_id": "TASK-999-UNBEKANNT",
                    "date": "2026-11-02",
                    "start_time": "14:00",
                    "end_time": "14:30",
                    "duration_minutes": 30,
                }
            ],
        }
        with self.assertRaises(GuardrailError) as ctx:
            validate_plan(invalid_plan, tasks=self.tasks, slot=self.slot)
        self.assertIn("Unbekannte Aufgaben-ID", str(ctx.exception))

    def test_guardrail_duplicate_task(self) -> None:
        """Guardrail-Test 2: Doppelte Aufgabe im Plan muss abgelehnt werden."""
        invalid_plan = {
            "date": "2026-11-02",
            "total_learning_minutes": 60,
            "scheduled_tasks": [
                {
                    "task_id": "TASK-002",
                    "date": "2026-11-02",
                    "start_time": "14:00",
                    "end_time": "14:30",
                    "duration_minutes": 30,
                },
                {
                    "task_id": "TASK-002",
                    "date": "2026-11-02",
                    "start_time": "14:35",
                    "end_time": "15:05",
                    "duration_minutes": 30,
                },
            ],
        }
        with self.assertRaises(GuardrailError) as ctx:
            validate_plan(invalid_plan, tasks=self.tasks, slot=self.slot)
        self.assertIn("mehrfach eingeplant", str(ctx.exception))

    def test_guardrail_overlapping_tasks_and_missing_break(self) -> None:
        """Guardrail-Test 3: Zeitliche Überschneidung und zu kurze Pause (< 5 Min.) ablehnen."""
        # Fall A: Echte zeitliche Überschneidung (14:00-14:45 und 14:30-15:00)
        overlapping_plan = {
            "date": "2026-11-02",
            "total_learning_minutes": 75,
            "scheduled_tasks": [
                {
                    "task_id": "TASK-001",
                    "date": "2026-11-02",
                    "start_time": "14:00",
                    "end_time": "14:45",
                    "duration_minutes": 45,
                },
                {
                    "task_id": "TASK-002",
                    "date": "2026-11-02",
                    "start_time": "14:30",
                    "end_time": "15:00",
                    "duration_minutes": 30,
                },
            ],
        }
        with self.assertRaises(GuardrailError) as ctx:
            validate_plan(overlapping_plan, tasks=self.tasks, slot=self.slot)
        self.assertIn("Überschneidung", str(ctx.exception))

        # Fall B: Keine Pause (0 Min. statt mindestens 5 Min.)
        no_break_plan = {
            "date": "2026-11-02",
            "total_learning_minutes": 75,
            "scheduled_tasks": [
                {
                    "task_id": "TASK-001",
                    "date": "2026-11-02",
                    "start_time": "14:00",
                    "end_time": "14:45",
                    "duration_minutes": 45,
                },
                {
                    "task_id": "TASK-002",
                    "date": "2026-11-02",
                    "start_time": "14:45",
                    "end_time": "15:15",
                    "duration_minutes": 30,
                },
            ],
        }
        with self.assertRaises(GuardrailError) as ctx2:
            validate_plan(no_break_plan, tasks=self.tasks, slot=self.slot)
        self.assertIn("Pause", str(ctx2.exception))

    def test_guardrail_wrong_duration(self) -> None:
        """Guardrail-Test 4: Geplante Dauer weicht von gespeicherter Aufgabendauer ab."""
        # TASK-001 dauert laut tasks.json 45 Minuten, Plan versucht 30 Minuten (Aufgabe aufgeteilt/gekürzt)
        wrong_duration_plan = {
            "date": "2026-11-02",
            "total_learning_minutes": 30,
            "scheduled_tasks": [
                {
                    "task_id": "TASK-001",
                    "date": "2026-11-02",
                    "start_time": "14:00",
                    "end_time": "14:30",
                    "duration_minutes": 30,
                }
            ],
        }
        with self.assertRaises(GuardrailError) as ctx:
            validate_plan(wrong_duration_plan, tasks=self.tasks, slot=self.slot)
        self.assertIn("Geplante Dauer", str(ctx.exception))

    def test_guardrail_exceeded_budget(self) -> None:
        """Guardrail-Test 5: Überschrittenes Lernbudget muss abgelehnt werden."""
        # Zeitfenster groß genug (14:00 - 17:00 = 180 Min.), aber Lernbudget nur 60 Min.
        small_budget_slot = set_available_slots("2026-11-02", "14:00", "17:00", 60)
        over_budget_plan = {
            "date": "2026-11-02",
            "total_learning_minutes": 75,
            "scheduled_tasks": [
                {
                    "task_id": "TASK-001",
                    "date": "2026-11-02",
                    "start_time": "14:00",
                    "end_time": "14:45",
                    "duration_minutes": 45,
                },
                {
                    "task_id": "TASK-002",
                    "date": "2026-11-02",
                    "start_time": "14:50",
                    "end_time": "15:20",
                    "duration_minutes": 30,
                },
            ],
        }
        with self.assertRaises(GuardrailError) as ctx:
            validate_plan(over_budget_plan, tasks=self.tasks, slot=small_budget_slot)
        self.assertIn("überschreitet das maximale Lernbudget", str(ctx.exception))

    def test_guardrail_completed_task_and_outside_window(self) -> None:
        """Zusätzliche Guardrail-Tests: Erledigte Aufgabe oder Block außerhalb des Zeitfensters."""
        # TASK-004 hat Status 'erledigt'
        completed_task_plan = {
            "date": "2026-11-02",
            "total_learning_minutes": 40,
            "scheduled_tasks": [
                {
                    "task_id": "TASK-004",
                    "date": "2026-11-02",
                    "start_time": "14:00",
                    "end_time": "14:40",
                    "duration_minutes": 40,
                }
            ],
        }
        with self.assertRaises(GuardrailError) as ctx:
            validate_plan(completed_task_plan, tasks=self.tasks, slot=self.slot)
        self.assertIn("erledigt", str(ctx.exception))

        # Aufgabe liegt außerhalb des Zeitfensters (Ende 16:15 > 16:00)
        outside_window_plan = {
            "date": "2026-11-02",
            "total_learning_minutes": 30,
            "scheduled_tasks": [
                {
                    "task_id": "TASK-002",
                    "date": "2026-11-02",
                    "start_time": "15:45",
                    "end_time": "16:15",
                    "duration_minutes": 30,
                }
            ],
        }
        with self.assertRaises(GuardrailError) as ctx2:
            validate_plan(outside_window_plan, tasks=self.tasks, slot=self.slot)
        self.assertIn("außerhalb des verfügbaren Zeitfensters", str(ctx2.exception))

    def test_save_plan_confirmation_and_overwrite_protection(self) -> None:
        """Prüft Bestätigungszwang und Überschreibwarnung in save_plan()."""
        valid_plan = run_planning_agent()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_output = Path(tmpdir) / "output" / "lernplan.json"
            original_output = tools.OUTPUT_FILE
            original_base = tools.BASE_DIR
            try:
                tools.BASE_DIR = Path(tmpdir)
                tools.OUTPUT_FILE = tmp_output

                # 1. Benutzer lehnt Speicherung ab -> keine Datei wird erstellt
                saved = save_plan(valid_plan, confirm_callback=lambda _: False)
                self.assertFalse(saved)
                self.assertFalse(tmp_output.exists())

                # 2. Benutzer bestätigt Speicherung -> Datei wird angelegt
                saved = save_plan(valid_plan, confirm_callback=lambda _: True)
                self.assertTrue(saved)
                self.assertTrue(tmp_output.exists())

                # 3. Datei existiert bereits: Erste Frage 'Ja', Überschreibfrage 'Nein'
                answers = iter([True, False])
                saved_overwrite_denied = save_plan(valid_plan, confirm_callback=lambda _: next(answers))
                self.assertFalse(saved_overwrite_denied)

                # 4. Datei existiert bereits: Beide Fragen 'Ja' -> Überschreiben erfolgreich
                answers_yes = iter([True, True])
                saved_overwrite_ok = save_plan(valid_plan, confirm_callback=lambda _: next(answers_yes))
                self.assertTrue(saved_overwrite_ok)

                written_data = json.loads(tmp_output.read_text(encoding="utf-8"))
                self.assertEqual(written_data["total_learning_minutes"], 100)
            finally:
                tools.OUTPUT_FILE = original_output
                tools.BASE_DIR = original_base

    def test_guardrail_invalid_inputs_and_corrupted_json(self) -> None:
        """Prüft die verständliche Behandlung ungültiger Benutzereingaben und fehlerhafter JSON-Dateien."""
        # Ungültiges Datum
        with self.assertRaises(GuardrailError):
            set_available_slots("02.11.2026", "14:00", "16:00", 60)

        # Ende vor Beginn
        with self.assertRaises(GuardrailError):
            set_available_slots("2026-11-02", "16:00", "14:00", 60)

        # Ungültiges Lernbudget (<= 0)
        with self.assertRaises(GuardrailError):
            set_available_slots("2026-11-02", "14:00", "16:00", 0)

        # Fehlerhafte JSON-Datei
        with tempfile.TemporaryDirectory() as tmpdir:
            broken_json = Path(tmpdir) / "broken_tasks.json"
            broken_json.write_text("{ungueltiges json", encoding="utf-8")
            with self.assertRaises(GuardrailError) as ctx:
                get_tasks(tasks_path=broken_json)
            self.assertIn("Fehlerhaftes JSON", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
