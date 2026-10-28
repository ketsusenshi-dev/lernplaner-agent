# Ausgeführte Tests und Ergebnisse

Alle Prüfungen wurden lokal unter Windows mit dem Standardmodul `unittest` sowie einem interaktiven Konsolen-Durchlauf (`main.py`) ausgeführt.

## 1. Automatisierte Unit-Tests (`test_lernplaner.py`)

**Ausgeführter Befehl:**
```powershell
py -m unittest -v test_lernplaner.py
```

**Ergebnis:** `Ran 11 tests in 0.018s — OK` (alle 11 Tests erfolgreich bestanden).

### Übersicht der getesteten Regeln und Guardrails

| Nr. | Testmethode | Geprüfte Anforderung / Guardrail | Ergebnis |
| :--- | :--- | :--- | :--- |
| 1 | `test_sample_tasks_meet_requirements` | Prüft, dass `data/tasks.json` 6 Aufgaben mit eindeutiger ID, Titel, ganzer Dauer, Priorität (1–3) und Status (`offen`/`erledigt`) enthält. | **OK** |
| 2 | `test_planning_rules_sorting_breaks_and_skipping` | Prüft: Nur offene Aufgaben einplanen (`TASK-004` wird übersprungen), Sortierung nach Priorität und bei Gleichstand nach ID (`TASK-001`, `TASK-002`, `TASK-003`), je 5 Min. Pause zwischen Aufgaben, Nicht-Verändern der Originalaufgaben, Ausgabe verständlicher Gründe für nicht eingeplante Aufgaben. | **OK** |
| 3 | `test_skip_large_task_and_schedule_next_fitting_task` | Prüft die Regel „Passt eine Aufgabe nicht mehr, prüfe die nächste“: Wenn `TASK-006` (60 Min., Prio 2) nicht mehr ins Restbudget passt, wird die kürzere `TASK-005` (20 Min., Prio 3) trotzdem eingeplant. | **OK** |
| 4 | `test_guardrail_unknown_task_id` | **Direkter Validierungsaufruf (`validate_plan`):** Ein Plan mit einer erfundenen Aufgaben-ID (`TASK-999-UNBEKANNT`) wird mit `GuardrailError` abgelehnt. | **OK** |
| 5 | `test_guardrail_duplicate_task` | **Direkter Validierungsaufruf (`validate_plan`):** Ein Plan, der dieselbe Aufgabe (`TASK-002`) zweimal einplant, wird mit `GuardrailError` abgelehnt. | **OK** |
| 6 | `test_guardrail_overlapping_tasks_and_missing_break` | **Direkter Validierungsaufruf (`validate_plan`):** Sowohl zeitlich überlappende Aufgaben (`14:00–14:45` und `14:30–15:00`) als auch direkt aufeinanderfolgende Aufgaben ohne 5-Minuten-Pause werden mit `GuardrailError` abgelehnt. | **OK** |
| 7 | `test_guardrail_wrong_duration` | **Direkter Validierungsaufruf (`validate_plan`):** Ein Plan, bei dem die geplante Dauer (30 Min.) von der gespeicherten Aufgabendauer in `data/tasks.json` (45 Min. bei `TASK-001`) abweicht, wird mit `GuardrailError` abgelehnt. | **OK** |
| 8 | `test_guardrail_exceeded_budget` | **Direkter Validierungsaufruf (`validate_plan`):** Ein Plan mit 75 Lernminuten bei einem erlaubten Lernbudget von 60 Minuten wird mit `GuardrailError` abgelehnt, selbst wenn das Zeitfenster groß genug wäre. | **OK** |
| 9 | `test_guardrail_completed_task_and_outside_window` | **Direkter Validierungsaufruf (`validate_plan`):** Das Einplanen einer bereits erledigten Aufgabe (`TASK-004`) sowie ein Block außerhalb des verfügbaren Zeitfensters (`15:45–16:15` bei Fensterende `16:00`) werden mit `GuardrailError` abgelehnt. | **OK** |
| 10 | `test_save_plan_confirmation_and_overwrite_protection` | Prüft `save_plan(plan)`: Ohne Bestätigung wird keine Datei geschrieben; mit Bestätigung wird `output/lernplan.json` angelegt; existiert die Datei bereits, wird zusätzlich gewarnt und nur bei zweiter Bestätigung überschrieben. | **OK** |
| 11 | `test_guardrail_invalid_inputs_and_corrupted_json` | Prüft die Behandlung ungültiger Datums-/Zeitformate, negativer/null Budgets sowie fehlerhafter JSON-Dateien durch `GuardrailError`. | **OK** |

---

## 2. Ausgeführter End-to-End-Konsolentest (`main.py`)

**Ausgeführter Befehl:**
```powershell
"2026-11-02`n14:00`n16:30`n120`nj`n" | py main.py
```

**Beobachtetes Verhalten:**
1. Das Programm weist transparent darauf hin, dass es sich um einen **regelbasierten Agenten-Prototyp ohne LLM** handelt.
2. Die aufgerufenen Tools (`get_tasks()`, `get_available_slots()`, `save_plan(plan)`) werden sichtbar mit `[TOOL-AUFRUF]` in der Konsole protokolliert.
3. Für den Zeitraum `14:00–16:30` (150 Min. Fenster) und `120` Min. Lernbudget wurden eingeplant:
   - `14:00 - 14:45`: `TASK-001` (Prio 1, 45 Min.)
   - *5 Min. Pause*
   - `14:50 - 15:20`: `TASK-002` (Prio 1, 30 Min.)
   - *5 Min. Pause*
   - `15:25 - 15:50`: `TASK-003` (Prio 2, 25 Min.)
   - *5 Min. Pause*
   - `15:55 - 16:15`: `TASK-005` (Prio 3, 20 Min.) — eingeplant, nachdem `TASK-006` (60 Min., Prio 2) wegen Budget-/Zeitfensterüberschreitung übersprungen wurde.
4. Nicht eingeplante Aufgaben (`TASK-004` wegen Status `erledigt`, `TASK-006` wegen Restbudget/Zeitfenster) wurden mit nachvollziehbarer Begründung ausgegeben.
5. Nach Bestätigung (`j`) wurde `output/lernplan.json` valide erzeugt; `data/tasks.json` blieb unverändert.

## 3. Offene Tests

- Keine offenen Tests für den regelbasierten Prototyp und die Guardrails.
- Sobald in einem zukünftigen Schritt ein echtes LLM angebunden wird, können integrative Tests ergänzt werden, bei denen das LLM den Plan erstellt und `validate_plan` / `save_plan` dessen Ausgabe prüft.
