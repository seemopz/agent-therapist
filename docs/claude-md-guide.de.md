# CLAUDE.md – Awesome-Anleitung

Kompakte Referenz: was wohin gehört, wie man es schreibt, wie man es pflegt.
Stand September 2026, nach der Claude-Code-Doku und eigenen Messungen.

---

## Grundprinzip

- CLAUDE.md = **Rat**, keine Vorschrift → was *immer* passieren muss, gehört in einen **Hook**
- wird bei **jedem Modellaufruf** mitgeschickt → jede Zeile kostet Tokens und Aufmerksamkeit
- lange Dateien → Regeln gehen unter, Claude ignoriert sie
- Prüffrage je Zeile: **„Würde Claude ohne diese Zeile Fehler machen?“** → nein = streichen

---

## Die Ebenen

| Datei | gilt für | geladen | Git |
|---|---|---|---|
| `~/.claude/CLAUDE.md` | alle Projekte | immer | nein |
| `~/.claude/rules/*.md` | alle Projekte | immer | nein |
| `./CLAUDE.md` / `./.claude/CLAUDE.md` | Repo, Team | immer | ja |
| `./CLAUDE.local.md` | Repo, nur ich | immer | nein |
| `./.claude/rules/*.md` + `paths:` | bestimmte Dateien | wenn passende Dateien geöffnet werden | ja |
| `unterordner/CLAUDE.md` | Teilbereich | wenn Claude dort liest | ja |
| `.claude/skills/<name>/SKILL.md` | bei Bedarf | wenn aufgerufen | ja |

- alles wird **zusammengefügt**, nichts überschreibt
- widersprüchliche Regeln → Claude wählt **beliebig** eine
- `@pfad/datei.md` importiert → **lädt trotzdem beim Start**, spart keinen Platz

---

## Was wohin

**Global (`~/.claude/CLAUDE.md`), wie *ich* arbeite:**
- Sprache: „Antworte auf Deutsch“
- Antwortstil: kurz, Ergebnis zuerst
- Git-Gewohnheiten: Commit-Stil, nie ohne Rückfrage pushen
- Rechner-Eigenheiten: z. B. `python3` zu alt → `uv` / `.venv`
- Lieblingswerkzeuge: `uv`, `gh`, `pnpm` …

**Repo (`CLAUDE.md`), was *das Projekt* braucht:**
- Befehle: bauen, testen, starten, linten, exakt
- Konventionen, die vom Standard abweichen, **mit Grund**
- Architekturentscheidungen, die man im Code nicht sieht
- Stolperfallen, nicht offensichtliches Verhalten
- Grenzen: „`legacy/` nicht anfassen“, „keine neuen Abhängigkeiten“
- Branch- und PR-Konventionen, nötige Umgebungsvariablen

**`CLAUDE.local.md`, nur ich, nur dieses Repo:**
- lokale Pfade, eigene Testdaten, persönliche Abkürzungen

**Pfadregel (`.claude/rules/api.md` + `paths:`):**
- Regeln nur für einen Codebereich: API, Migrationen, UI-Komponenten

**Skill:**
- mehrstufige Abläufe: Release, Deployment, Datenmigration
- selten gebrauchtes, langes Wissen: Fach-Doku, API-Referenz
- Wissen, das das Modell nicht haben kann: interne Frameworks, neue API-Versionen

**Hook:**
- muss **immer** passieren: Tests vor dem Abschluss, Linter nach Änderungen
- muss **nie** passieren: Schreiben in `migrations/`, `.env`

**Nirgendwohin:**
- was das Modell ohnehin kann oder aus dem Code liest

---

## Rein / Raus

| ✅ rein | ❌ raus |
|---|---|
| Befehle, die man nicht erraten kann | alles, was im Code steht |
| Stilregeln, die vom Standard abweichen | Standardkonventionen der Sprache |
| Test-Runner und wie getestet wird | ausführliche API-Doku → verlinken |
| Repo-Gepflogenheiten | Infos, die sich oft ändern |
| projektspezifische Architektur | Tutorials, lange Erklärungen |
| Umgebungs-Eigenheiten | Datei-für-Datei-Beschreibungen |
| Stolperfallen | „schreib sauberen Code“ |

---

## Schreiben

- **Länge:** unter 200 Zeilen pro Datei (Doku) · ideal unter 60 (Praxis)
- **Budget:** ~50 Anweisungen global, ~100 im Projekt
- **Konkret:** „`npm test` vor dem Commit“ statt „teste deine Änderungen“
- **Gegliedert:** Überschriften und Stichpunkte, kein Fließtext
- **Warum:** kurze Begründung → Claude wendet die Regel sinnvoll auf neue Fälle an
- **Positiv:** sagen, was zu tun ist, nicht nur, was nicht
- **Betonung:** höchstens eine Zeile mit `IMPORTANT` · kein CAPS-Geschrei, kein „MUST“ überall
- **Keine Zauberformeln:** keine Rollen („Du bist Experte …“), kein „prüfe doppelt“ (moderne Modelle prüfen selbst)
- **Links statt Inhalt:** „Details zu X: `docs/x.md`“, damit Claude nur bei Bedarf liest

---

## Pflegen

- **Ergänzen, wenn:**
  - Claude denselben Fehler **zweimal** macht
  - ich dieselbe Korrektur erneut tippe
  - ein Review etwas findet, das Claude hätte wissen müssen
  - ein neues Teammitglied dieselbe Info bräuchte
- **Kürzen, wenn:**
  - Claude es auch ohne die Zeile richtig macht
  - die Info veraltet ist
  - Claude eine Regel ständig ignoriert → Datei ist zu lang
- **Werkzeuge:**
  - `/context` → was ist geladen
  - `/doctor` → schlägt Streichungen vor
  - `/init` → Startgerüst, danach radikal kürzen
- wie Code behandeln: versionieren, reviewen, regelmäßig aufräumen

---

## Vorlage: global

```markdown
# Ich
- Antworte auf Deutsch, knapp, Ergebnis zuerst.
- Frag nach, bevor du pushst, force-pushst oder etwas löschst.

# Rechner
- macOS. `python3` ist 3.9 → Python-Projekte mit `uv run` oder `.venv/bin/python`.
- GitHub über `gh`.

# Git
- Commit-Nachrichten: `typ(bereich): was` (feat, fix, docs, refactor, test, chore).
```

## Vorlage: Repo

```markdown
# <Projekt>
Einzeiler: was es ist.

## Befehle
- Setup: `…`
- Tests: `…` (einzelner Test: `…`)
- Starten: `…`

## Konventionen
- <Regel> – weil <Grund>.

## Stolperfallen
- <nicht offensichtliches Verhalten>

## Grenzen
- `<pfad>/` nicht ändern: <Grund>.

## Mehr
- Architektur: `docs/architecture.md`
```

---

## Checkliste

- [ ] globale Datei unter 30 Zeilen, nur Persönliches
- [ ] Repo-Datei unter 200 Zeilen, besser unter 60
- [ ] jede Zeile besteht die Prüffrage
- [ ] keine Widersprüche zwischen den Ebenen
- [ ] Befehle stimmen und laufen
- [ ] Muss-Regeln als Hook, nicht als Text
- [ ] Abläufe und langes Wissen in Skills oder `docs/`
- [ ] höchstens eine `IMPORTANT`-Zeile

---

## Quellen

- [Claude Code Docs: How Claude remembers your project](https://code.claude.com/docs/en/memory)
- [Claude Code Docs: Best practices](https://code.claude.com/docs/en/best-practices)
- [Claude Docs: Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- [HumanLayer: Writing a good CLAUDE.md](https://www.humanlayer.dev/blog/writing-a-good-claude-md)
- [alexop.dev: Stop Bloating Your CLAUDE.md](https://alexop.dev/posts/stop-bloating-your-claude-md-progressive-disclosure-ai-coding-tools/)
