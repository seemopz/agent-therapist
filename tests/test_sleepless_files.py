from __future__ import annotations

import ast
import json

from conftest import ROOT, SLEEPLESS_DIR

SKILL_HOOKS = SLEEPLESS_DIR / "hooks" / "hooks.json"
ROOT_HOOKS = ROOT / "hooks" / "hooks.json"
EVENTS = {"Stop": "stop", "UserPromptSubmit": "prompt", "SessionStart": "session-start",
          "StopFailure": "stop-failure", "PreToolUse": "pre-tool-use"}
SCRIPTS = [SLEEPLESS_DIR / "scripts" / "shift.py", SLEEPLESS_DIR / "hooks" / "hook.py",
           SLEEPLESS_DIR / "hooks" / "guard.py"]


def test_skill_hooks_cover_every_event_and_call_hook_py():
    hooks = json.loads(SKILL_HOOKS.read_text(encoding="utf-8"))["hooks"]
    assert set(hooks) == set(EVENTS)
    for event, arg in EVENTS.items():
        [group] = hooks[event]
        [handler] = group["hooks"]
        assert handler["type"] == "command"
        assert handler["command"] == 'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/hook.py" ' + arg
    assert hooks["SessionStart"][0]["matcher"] == "startup|resume|compact"
    assert hooks["SessionStart"][0]["hooks"][0]["asyncRewake"] is True
    assert hooks["StopFailure"][0]["hooks"][0]["asyncRewake"] is True
    assert hooks["StopFailure"][0]["hooks"][0]["timeout"] >= 1000
    assert hooks["StopFailure"][0]["matcher"] == "rate_limit|overloaded|server_error"
    assert hooks["PreToolUse"][0]["matcher"] == "Bash|mcp__.*"


def test_root_hooks_mirror_skill_hooks():
    mirrored = SKILL_HOOKS.read_text(encoding="utf-8").replace("${CLAUDE_PLUGIN_ROOT}/hooks/",
                                               "${CLAUDE_PLUGIN_ROOT}/skills/sleepless/hooks/")
    assert json.loads(ROOT_HOOKS.read_text(encoding="utf-8")) == json.loads(mirrored)


def test_sleepless_plugin_manifest():
    data = json.loads((SLEEPLESS_DIR / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert data["name"] == "sleepless"
    assert "version" not in data


def test_sleepless_scripts_parse_as_python_39():
    for p in SCRIPTS:
        ast.parse(p.read_text(encoding="utf-8"), filename=str(p), feature_version=(3, 9))


def test_skill_md_frontmatter_and_key_steps():
    text = (SLEEPLESS_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: sleepless\ndescription: Use when ")
    for needle in ('scripts/shift.py" start', 'scripts/shift.py" status', 'scripts/shift.py" end',
                   'scripts/shift.py" finish', "AskUserQuestion", "PushNotification",
                   "Never merge", "caffeinate", "weiter", ".claude/sleepless/reports/",
                   "$SHIFT branch", "$SHIFT wait", "$SHIFT workers", "run_in_background",
                   "start_session", "claude --bg", "Worker brief", "join <branch>",
                   "done <branch> --status done --pr", "gh pr create --base <base>"):
        assert needle in text, needle


def test_report_template_placeholders():
    text = (SLEEPLESS_DIR / "templates" / "report.md").read_text(encoding="utf-8")
    for key in ("label", "base", "started", "end"):
        assert "{{%s}}" % key in text
    assert "{{branch}}" not in text
    assert "| Item | Branch | PR |" in text
    for heading in ("## Summary", "## Plan", "## Done", "## Decisions and questions", "## Blocked",
                    "## Findings", "## Next"):
        assert heading in text
