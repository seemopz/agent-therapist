# Szenarien

Immer zuerst `tests/sandbox.sh` ausführen (Quell-Repos für Szenario 2 und 3 über
`SANDBOX_REPO_MESSY` und `SANDBOX_REPO_TIDY`, siehe Kopf des Skripts); `S` = ausgegebener Pfad. Nie gegen echte Dateien.
Aufruf headless (Plugin direkt aus dem Repo, globaler Ordner = Sandbox) – das ist der Befehl, der
die Szenarien unten tatsächlich zum Laufen gebracht hat:

    cd $S/repos/<repo>
    AGENT_THERAPIST_HOME=$S/home-claude AGENT_THERAPIST_REPOS=$S/repos \
      claude -p --plugin-dir ~/repos/agent-therapist --permission-mode acceptEdits \
      --add-dir "$S/home-claude" --add-dir ~/repos/agent-therapist \
      --allowedTools "Bash(python3:*),Bash(git log:*),Bash(git status:*),Bash(git branch:*),Bash(git rev-parse:*),Bash(ls:*),Bash(which:*),Bash(uname:*),Bash(cat:*),Bash(gh pr list:*),Bash(gh api:*)" \
      -- "<Prompt>"

Zwei Punkte, ohne die der Befehl nicht funktioniert:
- `--add-dir ~/repos/agent-therapist` ist nötig, sonst darf die Sitzung `references/*.md` des Skills
  nicht lesen (nur `$S/home-claude` reicht nicht) und Check 3 (Widersprüche) etc. laufen unvollständig.
- Das `--` vor dem Prompt ist Pflicht: `--add-dir`/`--allowedTools` nehmen beliebig viele Argumente,
  ohne `--` schlucken sie sonst den Prompt und `claude` meldet „Input must be provided … as a prompt
  argument“, obwohl einer übergeben wurde.

Aufgerufen wurde der Skill in den Prompts unten als `/agent-therapist …` – das Plugin registriert ihn so
(nicht als `/agent-therapist:agent-therapist`); falls das in einer Umgebung nicht greift, formuliert man den
Prompt stattdessen als normalen Satz („Nutze den Skill agent-therapist: …“).

Falls `--plugin-dir` im `-p`-Modus gar nicht greift: dieselbe Sitzung interaktiv mit
`claude --plugin-dir ~/repos/agent-therapist` starten und den Prompt eingeben.

## 1. Leeres Repo – Neu aufbauen

Repo: `empty`. Prompt:

> /agent-therapist Neu aufbauen, Beides. Antworten: Deutsch; Code und Commits Englisch; kurz;
> Profi; vor Push und Löschen fragen; macOS mit uv und gh; Conventional Commits ohne Co-Authored-By;
> direkt auf main; keine Versionen. Projekt: kleines Python-CLI „hello“, Test `uv run pytest`.
> Wissensablage TODO.md. Keine Hooks außer protect-files für .env. Übernimm alle Vorschläge.

Erwartet:
- [ ] `$S/home-claude/CLAUDE.md` < 30 Zeilen, `rules/token.md`, `rules/git.md` vorhanden
- [ ] `rules/git.md` enthält die festen Regeln (force-push, `--no-verify`, Geheimnisse, vor Push fragen)
- [ ] `repos/empty/CLAUDE.md` < 60 Zeilen, enthält „`TODO.md`“
- [ ] `repos/empty/.claude/hooks/protect-files.py` + Eintrag in `.claude/settings.json`; `python3 -m json.tool` ok
  **Nur interaktiv prüfbar:** Claude Code verlangt für Schreibzugriffe auf `.claude/settings.json`
  und `.claude/hooks/*` immer eine ausdrückliche Bestätigung, auch mit `--permission-mode acceptEdits`
  und egal welche `--allowedTools`-Regeln gesetzt sind – im `-p`-Modus ohne Interaktion wird das also
  immer abgelehnt. Prüfen: `claude --plugin-dir ~/repos/agent-therapist` interaktiv im Sandbox-Repo starten
  (Env-Variablen wie oben setzen), den Prompt eingeben, bei den beiden Schreib-Anfragen „Allow“ klicken,
  dann Datei und Eintrag wie beschrieben kontrollieren.
- [ ] `echo '{"tool_input":{"file_path":".env"}}' | python3 repos/empty/.claude/hooks/protect-files.py; echo $?` → 2
  **Nur interaktiv prüfbar** (siehe oben – setzt voraus, dass die Datei existiert)
- [ ] Sicherung unter `$S/home-claude/backups/agent-therapist/<datum>/manifest.json`
- [ ] Abschluss nennt Tokens vorher → nachher und schlägt eine Commit-Nachricht vor; `git -C repos/empty log --oneline` zeigt weiterhin nur „chore: init“

## 2. messy-repo – Optimieren (nur Vorschau)

Repo: `messy-repo` (Quelle: `SANDBOX_REPO_MESSY`). Prompt:

> /agent-therapist Optimieren, Projekt. Zeig nur die Vorschau und wähle am Ende „nichts“.

Voraussetzung: das Quell-Repo enthält einen Widerspruch zwischen zwei CLAUDE.md-Dateien (z. B.
zwei verschiedene Farbwerte für dieselbe Sache), ein Passwort im Klartext, eine CLAUDE.md mit
deutlich über 200 Zeilen und Tagebuch-Einträge (datierte Überschriften, Testzahlen).

Erwartet (Befunde in der Vorschau):
- [ ] Widerspruch mit beiden Fundstellen (Datei:Zeile) gemeldet, mit Vorschlag einer einzigen Quelle
- [ ] Passwort gemeldet, **nur maskiert** – das Klartext-Passwort steht nirgends in der Ausgabe
- [ ] zu lange CLAUDE.md mit Aufteilungsvorschlag nach `docs/`
- [ ] Tagebuch-Einträge zum Streichen/Verschieben vorgeschlagen
- [ ] `git -C $S/repos/messy-repo status --short` ist leer (nichts geschrieben)

## 3. tidy-repo – Optimieren (bereits gut)

Repo: `tidy-repo` (Quelle: `SANDBOX_REPO_TIDY`). Prompt wie 2.

Erwartet:
- [ ] höchstens 5 Vorschläge, keiner „high“
- [ ] keine Datei geschrieben

## 4. Rückgängig

Nach Szenario 1, Repo `empty`. Prompt:

> /agent-therapist Letzte Änderung rückgängig. Bestätige die Wiederherstellung, neu angelegte Dateien behalten.

Erwartet:
- [ ] vorher geänderte Dateien zurück, neu angelegte Dateien noch vorhanden und als „created“ gelistet

## 5. Skripte

- [ ] `uv run pytest` grün
