# Lokaler Lernplaner – Regelbasierter Agenten-Prototyp ohne LLM

Dieses Projekt ist ein verständlicher, lokal ausführbarer Python-Konsolenprototyp für folgende Schulaufgabe:

> *„Sucht einen Prozess, den ein KI-Agent ausführen könnte. Überlegt euch, welche Tools dafür notwendig wären. Implementiert diese prototypisch. Wenn vorhanden, versucht diese auch mit einem LLM auszuführen. Überlegt euch und implementiert Guardrails.“*

## Wichtiger Hinweis zum aktuellen Entwicklungsstand (Kein LLM)

Dieser Prototyp ist **ausdrücklich ein regelbasierter Agenten-Prototyp ohne LLM**.
- Es ist **noch keine LLM-Anbindung** vorhanden und es werden **keine externen Python-Pakete** oder Server benötigt.
- Die Architektur trennt jedoch **Konsoleneingabe** (`main.py`), **Planungslogik** (`planner.py`) und **Tools inkl. Guardrails** (`tools.py`) sauber voneinander.
- Dadurch kann `planner.py` später durch einen LLM-Aufruf (Function Calling / Tool Use) ersetzt werden, während dieselben Tools und Guardrails unverändert weiterverwendet werden und auch fehlerhafte LLM-Pläne zuverlässig abfangen.

---

## Projektstruktur

```text
lernplaner-agent/
├── data/
│   └── tasks.json          # 6 Beispiel-Lernaufgaben (ID, Titel, Dauer, Priorität 1-3, Status)
├── output/
│   └── lernplan.json       # Wird nach Bestätigung durch save_plan() erzeugt (in .gitignore)
├── main.py                 # Konsoleneingaben, Anzeige des Plans und Startpunkt
├── planner.py              # Regelbasierte Planungslogik (ohne LLM)
├── tools.py                # Agenten-Tools (get_tasks, get_available_slots, save_plan) & Guardrails
├── test_lernplaner.py      # Unit-Tests (unittest) für Planungsregeln und Guardrails
├── README.md               # Projektdokumentation & Startanleitung
├── PROMPTS.md              # Verwendeter Erstellungsprompt
├── TESTS.md                # Dokumentation der ausgeführten Tests und Ergebnisse
├── ERFAHRUNGEN.md          # Ausfüllbare Vorlage für eigene Erfahrungen
└── .gitignore              # Ignoriert temporäre Dateien und output/lernplan.json
```

---

## Startanleitung für Windows (PowerShell / Eingabeaufforderung)

Das Programm benötigt lediglich eine Standard-Installation von **Python 3** (keine `pip install`-Pakete nötig).

### 1. In das Projektverzeichnis wechseln
```powershell
cd "c:\Users\ketsu\OneDrive\Dokumente\My Vibecoding\lernplaner-agent"
```

### 2. Lernplaner starten
Je nachdem, wie Python unter Windows eingerichtet ist, über den Python-Launcher `py` oder `python` starten:
```powershell
py main.py
```
*(Alternativ: `python main.py`)*

**Beispiel-Eingaben in der Konsole:**
- Datum: `2026-11-02`
- Beginn der verfügbaren Lernzeit: `14:00`
- Ende der verfügbaren Lernzeit: `16:30`
- Maximales Lernbudget in Minuten: `120`
- Speichern bestätigen: `j`

### 3. Automatisierte Unit-Tests ausführen
```powershell
py -m unittest -v test_lernplaner.py
```
*(Alternativ: `python -m unittest -v test_lernplaner.py`)*

---

## Prozessbeschreibung

1. **Benutzereingabe (`main.py`):**
   Der Benutzer gibt in der Konsole das gewünschte Lerndatum (`YYYY-MM-DD`), Beginn und Ende seiner verfügbaren Lernzeit (`HH:MM`) sowie sein maximales Netto-Lernbudget in ganzen Minuten ein. Ungültige Eingaben werden sofort abgefangen.
2. **Tool-Abruf (`planner.py` -> `tools.py`):**
   Der Agenten-Ablauf ruft sichtbar in der Konsole die Tools `get_tasks()` und `get_available_slots()` auf.
3. **Regelbasierte Planung (`planner.py`):**
   - Es werden ausschließlich Aufgaben mit Status `offen` berücksichtigt (die Originaldaten in `data/tasks.json` werden niemals verändert).
   - Offene Aufgaben werden nach `priority` (1 = höchste bis 3 = niedrigste) und bei Gleichstand alphabetisch nach `id` sortiert.
   - Aufgaben werden nur komplett (ungeteilt) eingeplant.
   - Zwischen zwei eingeplanten Aufgaben werden immer **5 Minuten Pause** eingefügt.
   - Das **Lernbudget** begrenzt die Summe der reinen Lernminuten (ohne Pausen).
   - Das **Zeitfenster** begrenzt die Gesamtdauer inklusive Pausen.
   - Passt eine Aufgabe nicht mehr ins Restbudget oder Restzeitfenster, wird sie mit einem verständlichen Grund vermerkt und die nächste (evtl. kürzere) Aufgabe geprüft.
4. **Anzeige & Speicherung (`main.py` -> `tools.py`):**
   Der fertige Plan inklusive aller nicht eingeplanten Aufgaben und deren Begründungen wird in der Konsole ausgegeben. Anschließend wird `save_plan(plan)` aufgerufen.

---

## Implementierte Tools (`tools.py`)

Alle Tool-Aufrufe geben in der Konsole eine `[TOOL-AUFRUF]`-Meldung aus, damit der Ablauf transparent nachvollziehbar ist:

1. **`get_tasks()`**
   Liest die Lernaufgaben aus `data/tasks.json`, prüft das JSON-Format sowie alle Pflichtfelder (`id`, `title`, `duration_minutes`, `priority`, `status`) und gibt eine Liste validierter Aufgaben-Dictionaries zurück.
2. **`get_available_slots()`**
   Gibt das zuvor vom Benutzer eingegebene Zeitfenster (`date`, `start_time`, `end_time`, `available_window_minutes`) und das `max_budget_minutes` strukturiert zurück.
3. **`save_plan(plan)`**
   Prüft den übergebenen Plan vollständig gegen alle Guardrails (`validate_plan`), fragt in der Konsole nach ausdrücklicher Bestätigung (sowie einer zusätzlichen Warnung/Bestätigung beim Überschreiben) und speichert den Plan ausschließlich unter `output/lernplan.json`.

---

## Implementierte Guardrails

Die Guardrails schützen sowohl vor fehlerhaften Benutzereingaben als auch vor ungültigen Plänen, falls später ein LLM angebunden wird und halluziniert oder Rechenfehler macht:

- **Nur existierende, offene Aufgaben:** Unbekannte Aufgaben-IDs oder Aufgaben mit Status `erledigt` werden abgelehnt.
- **Keine Duplikate:** Jede Aufgaben-ID darf höchstens einmal im Plan vorkommen.
- **Exakte Aufgabendauer:** Die geplante Dauer (`duration_minutes` sowie die Differenz aus `end_time - start_time`) muss exakt der in `data/tasks.json` gespeicherten Dauer entsprechen (kein Aufteilen oder Kürzen).
- **Keine Überschneidungen & Mindestpause:** Blöcke dürfen sich zeitlich nicht überlappen; zwischen zwei aufeinanderfolgenden Aufgaben müssen mindestens 5 Minuten Pause liegen.
- **Einhaltung von Datum & Zeitfenster:** Alle geplanten Blöcke müssen am gewählten Datum und vollständig innerhalb von `start_time` bis `end_time` liegen.
- **Einhaltung des Lernbudgets:** Die Summe der geplanten Lernminuten (ohne Pausen) darf `max_budget_minutes` nicht überschreiten.
- **Robuste Eingabe- & JSON-Prüfung:** Fehlerhafte Datums-/Uhrzeitangaben, negative Budgets oder beschädigte JSON-Dateien erzeugen verständliche `GuardrailError`-Meldungen statt unkontrollierter Programmabstürze.
- **Fester Speicherpfad:** `save_plan()` schreibt ausschließlich nach `output/lernplan.json`; freie Dateipfade sind nicht möglich.
- **Bestätigungszwang & Überschreibschutz:** Ohne explizite Bestätigung (`j`/`ja`) in der Konsole wird nichts gespeichert. Existiert `output/lernplan.json` bereits, erfolgt eine zusätzliche Warnung mit zweiter Bestätigungsabfrage.
