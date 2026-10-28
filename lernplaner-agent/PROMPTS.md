# Verwendeter Prompt

Folgender Prompt wurde zur Erstellung dieses regelbasierten Lernplaner-Prototyps verwendet:

```text
Implementiere einen kleinen lokalen Lernplaner als Prototyp für folgende Schulaufgabe:

„Sucht einen Prozess, den ein KI-Agent ausführen könnte. Überlegt euch, welche Tools dafür notwendig wären. Implementiert diese prototypisch. Wenn vorhanden, versucht diese auch mit einem LLM auszuführen. Überlegt euch und implementiert Guardrails.“

Ziel ist ein verständliches, lauffähiges Python-Konsolenprogramm ohne Server und ohne externe Python-Pakete. Erstelle zunächst einen ausdrücklich als „regelbasierter Agenten-Prototyp ohne LLM“ gekennzeichneten Ablauf. Behaupte nicht, dass dieser Prototyp bereits ein LLM verwendet.

Funktion:
Der Benutzer gibt ein Datum, Beginn und Ende seiner verfügbaren Lernzeit sowie ein maximales Lernbudget in Minuten ein. Das Programm liest offene Lernaufgaben aus einer lokalen JSON-Datei, erstellt einen Plan und speichert ihn nach Bestätigung.

Tools:
- get_tasks(): Liest Aufgaben aus data/tasks.json.
- get_available_slots(): Gibt die zuvor eingegebenen Zeitfenster strukturiert zurück.
- save_plan(plan): Validiert den vollständigen Plan und speichert ihn ausschließlich unter output/lernplan.json.

Trenne Tools, Planungslogik und Konsoleneingaben nachvollziehbar voneinander. Halte den Code einfach.

Beispieldaten:
Erstelle sechs Lernaufgaben mit eindeutiger ID, Titel, Dauer in ganzen Minuten, Priorität 1 bis 3 und Status offen/erledigt. Priorität 1 ist am höchsten.

Planungsregeln:
- Nur offene Aufgaben einplanen.
- Nach Priorität, bei Gleichstand nach Aufgaben-ID sortieren.
- Aufgaben vollständig einplanen, nicht aufteilen.
- Passt eine Aufgabe nicht mehr, prüfe die nächste.
- Zwischen zwei Aufgaben fünf Minuten Pause lassen.
- Das Lernbudget begrenzt die Summe der Lernminuten ohne Pausen.
- Aufgaben inklusive Pausen müssen in das verfügbare Zeitfenster passen.
- Nicht eingeplante Aufgaben mit verständlichem Grund anzeigen.
- Keine vorhandene Aufgabe oder deren Status verändern.

Implementiere folgende Guardrails im Code, besonders innerhalb von save_plan:
- Nur existierende, offene Aufgaben zulassen.
- Jede Aufgabe höchstens einmal einplanen.
- Geplante Dauer muss der gespeicherten Aufgabendauer entsprechen.
- Keine Überschneidungen; zwischen Aufgaben mindestens fünf Minuten Pause.
- Alle Blöcke müssen am ausgewählten Datum innerhalb des Zeitfensters liegen.
- Lernbudget darf nicht überschritten werden.
- Ungültige Eingaben und fehlerhafte JSON-Daten verständlich behandeln.
- Speicherpfad fest vorgeben; keine frei wählbaren Dateipfade.
- Speicherung erst nach ausdrücklicher Bestätigung in der Konsole.
- Vor Überschreiben eines vorhandenen Plans zusätzlich warnen und bestätigen lassen.

Zeige die aufgerufenen Tools in der Konsole an, damit der Ablauf nachvollziehbar ist.

Prüfe mit unittest die wichtigsten Regeln. Teste insbesondere bewusst ungültige Pläne durch direkte Aufrufe der Validierung: unbekannte Aufgaben-ID, doppelte Aufgabe, Überschneidung, falsche Dauer und überschrittenes Zeitbudget. Die Guardrails müssen auch greifen, wenn ein zukünftiges LLM einen ungültigen Plan erzeugt.

Erstelle:
- Den vollständigen Quellcode und Beispieldaten.
- README.md mit Startanleitung für Windows, Prozessbeschreibung, Tools und Guardrails.
- PROMPTS.md mit diesem Prompt.
- TESTS.md mit tatsächlich ausgeführten Prüfungen und Ergebnissen.
- ERFAHRUNGEN.md als ausfüllbare Vorlage, ohne Erfahrungen aus meiner Perspektive zu erfinden.
- Eine passende .gitignore.

Dokumentiere ausdrücklich, dass die Planung derzeit regelbasiert erfolgt und noch keine LLM-Anbindung existiert. Halte die Planungslogik so getrennt, dass später ein LLM die Tools verwenden kann.

Implementiere und teste das Programm vollständig. Installiere keine unnötigen Abhängigkeiten. Fasse zum Schluss zusammen, wie ich es starte und welche Tests erfolgreich waren beziehungsweise offen sind.
```
