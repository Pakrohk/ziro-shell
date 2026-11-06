"""Tests for Tab interrupt invariant and Starship prompt stability (SPEC-026 Tab-fix v1.3.4 pragmatic hotfix)."""
import os
import pty
import select
import signal
import time
from pathlib import Path
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# 1. Static Invariant Tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.unit
def test_no_command_substitution_in_prompt_literal():
    """PROMPT assignment must not contain unexpanded $(command) substitution."""
    boot_file = Path.home() / ".cache" / "ziro" / "ziro-boot.zsh"
    assert boot_file.is_file(), "ziro-boot.zsh must exist"
    content = boot_file.read_text(encoding="utf-8")
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("PROMPT="):
            # Must not contain command substitution $(...)
            assert "$(" not in line, f"PROMPT line contains command substitution: {line}"
            # Must use literal $STARSHIP_RENDERED or safe fallback
            assert "$STARSHIP_RENDERED" in line or "%F{" in line, f"Unexpected PROMPT line: {line}"


@pytest.mark.unit
def test_ghost_popup_default_disabled():
    """_GHOST_POPUP_ENABLED must default to 0 in boot script until binary handles SIGINT."""
    boot_file = Path.home() / ".cache" / "ziro" / "ziro-boot.zsh"
    content = boot_file.read_text(encoding="utf-8")
    assert "_GHOST_POPUP_ENABLED:=0" in content, "_GHOST_POPUP_ENABLED default 0 missing from boot script"


@pytest.mark.unit
def test_fzf_tab_used_when_popup_disabled():
    """_ghost_focus_widget must fall through to fzf-tab when popup is disabled."""
    boot_file = Path.home() / ".cache" / "ziro" / "ziro-boot.zsh"
    content = boot_file.read_text(encoding="utf-8")
    start = content.find("_ghost_focus_widget() {")
    end = content.find("zle -N _ghost_focus_widget", start)
    assert start != -1 and end != -1, "_ghost_focus_widget block not found in boot"
    widget_code = content[start:end]
    assert "! _GHOST_POPUP_ENABLED" in widget_code
    assert "zle fzf-tab-complete" in widget_code


@pytest.mark.unit
def test_no_binary_spawn_when_disabled():
    """When _GHOST_POPUP_ENABLED is 0, execution must return before any binary spawn."""
    build_file = Path(__file__).resolve().parent.parent / "core" / "build.py"
    content = build_file.read_text(encoding="utf-8")
    start = content.find("_ghost_focus_widget() {")
    end = content.find("zle -N _ghost_focus_widget", start)
    assert start != -1 and end != -1, "_ghost_focus_widget block not found"
    widget_code = content[start:end]
    check_pos = widget_code.find("if (( ! _GHOST_POPUP_ENABLED )); then")
    spawn_pos = widget_code.find('"$bin_path" focus')
    assert check_pos != -1 and spawn_pos != -1
    assert check_pos < spawn_pos, "Kill switch check must precede binary spawn"


@pytest.mark.unit
def test_precmd_renders_starship():
    """Starship prompt must be pre-rendered in precmd hook."""
    boot_file = Path.home() / ".cache" / "ziro" / "ziro-boot.zsh"
    content = boot_file.read_text(encoding="utf-8")
    assert "_ziro_render_starship_precmd()" in content, "Precmd render function missing"
    assert "add-zsh-hook precmd _ziro_render_starship_precmd" in content, "Hook registration missing"
    assert "typeset -g STARSHIP_RENDERED=" in content, "STARSHIP_RENDERED variable definition missing"


@pytest.mark.unit
def test_fzf_tab_fallback_preserved():
    """fzf-tab fallback must remain in the tab chain."""
    boot_file = Path.home() / ".cache" / "ziro" / "ziro-boot.zsh"
    content = boot_file.read_text(encoding="utf-8")
    assert "fzf-tab-complete" in content, "fzf-tab-complete fallback missing in ziro-boot.zsh"
    assert "expand-or-complete" in content, "expand-or-complete fallback missing"


# ─────────────────────────────────────────────────────────────────────────────
# 2. PTY Interactive Simulation Tests
# ─────────────────────────────────────────────────────────────────────────────

def _run_pty_session(interactions, timeout_s=6.0):
    """Run an interactive zsh session in a pseudo-terminal."""
    master, slave = pty.openpty()
    env = dict(os.environ)
    env["TERM"] = "xterm-256color"
    env["NO_COLOR"] = "1"
    env["ZIRO_TEST_MODE"] = "1"

    pid = os.fork()
    if pid == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        if slave > 2:
            os.close(slave)
        os.execvpe("zsh", ["zsh", "-i"], env)
        os._exit(1)

    os.close(slave)
    captured = b""
    start_time = time.time()

    try:
        for action, payload, delay in interactions:
            if time.time() - start_time > timeout_s:
                break
            if action == "wait":
                time.sleep(delay)
            elif action == "write":
                os.write(master, payload)
                if delay > 0:
                    time.sleep(delay)
            elif action == "drain":
                end_drain = time.time() + delay
                while time.time() < end_drain:
                    r, _, _ = select.select([master], [], [], 0.05)
                    if r:
                        try:
                            chunk = os.read(master, 4096)
                            if not chunk:
                                break
                            captured += chunk
                        except OSError:
                            break
                    else:
                        time.sleep(0.02)

        # Final drain
        while True:
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    chunk = os.read(master, 4096)
                    if not chunk:
                        break
                    captured += chunk
                except OSError:
                    break
            else:
                break
    finally:
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.05)
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        except (ProcessLookupError, ChildProcessError):
            pass
        os.close(master)

    return captured.decode("utf-8", errors="replace")


@pytest.mark.integration
def test_interrupt_during_tab_no_fragment():
    """Ctrl+C during Tab on a command must never dump literal $(starship prompt) fragment."""
    interactions = [
        ("drain", None, 0.6),                  # wait for prompt
        ("write", b"sudo echo test", 0.1),     # type command
        ("write", b"\t", 0.3),                 # send Tab
        ("write", b"\x03", 0.3),               # send Ctrl+C
        ("drain", None, 0.4),
    ]
    output = _run_pty_session(interactions)
    assert "$(starship prompt" not in output, f"Found unexpanded $(starship prompt in output:\n{output}"
    assert "$(/home/ali" not in output, f"Found raw prompt command substitution in output:\n{output}"


@pytest.mark.integration
def test_buffer_preserved_after_interrupt():
    """Shell remains responsive and executes next command after Tab + Ctrl+C."""
    interactions = [
        ("drain", None, 0.6),
        ("write", b"sudo mkinitcpio -P", 0.1),
        ("write", b"\t", 0.3),
        ("write", b"\x03", 0.3),               # cancel
        ("write", b"\x15echo BUFFER_OK\n", 0.2), # clear line and echo marker
        ("drain", None, 0.4),
    ]
    output = _run_pty_session(interactions)
    assert "BUFFER_OK" in output, f"Shell did not execute next command after interrupt:\n{output}"
    assert "$(starship prompt" not in output


@pytest.mark.integration
def test_rapid_interrupts_no_fragment():
    """10 rapid Ctrl+C presses must remain stable with zero literal prompt fragments."""
    interactions = [
        ("drain", None, 0.6),
        ("write", b"rapid_interrupt_test", 0.1),
    ]
    for _ in range(10):
        interactions.append(("write", b"\x03", 0.05))
    interactions.append(("write", b"\x15echo ALIVE\n", 0.2))
    interactions.append(("drain", None, 0.4))

    output = _run_pty_session(interactions)
    assert "ALIVE" in output, "Shell crashed or froze under rapid Ctrl+C"
    assert "$(starship prompt" not in output
    assert "$(/home/ali" not in output


@pytest.mark.integration
def test_normal_tab_no_regression():
    """Normal Tab on standard command does not crash or freeze."""
    interactions = [
        ("drain", None, 0.6),
        ("write", b"echo test_norm", 0.1),
        ("write", b"\t", 0.2),
        ("write", b"\n", 0.2),
        ("drain", None, 0.3),
    ]
    output = _run_pty_session(interactions)
    assert "test_norm" in output, f"Normal execution failed:\n{output}"
