"""ziro-shell — install command.

Layer: 3 (Python core, cold-path only)
Spec: 006 R1
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import shutil
import subprocess
import sys
from pathlib import Path


from core.paths import get_paths


def _verify_starship() -> tuple[bool, str]:
    """Verify starship is installed and working."""
    starship_cmd = shutil.which("starship")
    if not starship_cmd:
        return False, "starship not found on PATH"
    try:
        r = subprocess.run(
            [starship_cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return False, f"starship --version failed: {r.stderr.strip()}"
        return True, r.stdout.strip()
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"starship check failed: {e}"


def _config_dir() -> Path:
    return get_paths()["config"]


def _cache_dir() -> Path:
    return get_paths()["cache"]


def _ziro_home() -> Path:
    return get_paths()["home"]


def is_ziro_installed(cfg: Path | None = None) -> bool:
    """Return True if an existing Ziro installation is detected."""
    c = cfg or _config_dir()
    if (c / "defaults.toml").is_file() or (c / "tools.toml").is_file() or (c / "boot.zsh").is_file():
        return True
    return False


def _write_defaults(
    cfg: Path, custom_opts: dict[str, Any] | None = None, force: bool = False
) -> None:
    """Write defaults.toml reflecting user choices."""
    cfg.mkdir(parents=True, exist_ok=True)
    defaults = cfg / "defaults.toml"
    if defaults.is_file() and custom_opts is None and not force:
        return

    prompt_val = "starship"
    ghost_val = "ziro-ghost" if (not custom_opts or custom_opts.get("enable_ghost", True)) else "none"
    fsh_val = "fast-syntax-highlighting" if (not custom_opts or custom_opts.get("enable_fsh", True)) else "none"
    comp_val = "zsh-completions" if (not custom_opts or custom_opts.get("enable_fzf_tab", True)) else "none"
    nav_val = "zoxide" if (not custom_opts or custom_opts.get("enable_zoxide", True)) else "none"

    content = "# ziro-shell — user defaults\n"
    content += "# Editable by hand. Regenerated only on `ziro config reset`.\n"
    content += "# Layer: 0 (config) · Spec: 006 · AUTO-GENERATED: no\n"
    content += "\n"
    content += "[version]\n"
    content += 'schema = "0.1.5"\n'
    content += "\n"
    content += "[prompt]\n"
    content += f'default = "{prompt_val}"\n'
    content += "\n"
    content += "[colors]\n"
    content += 'default = "zcolors"\n'
    content += "\n"
    content += "[syntax_highlighting]\n"
    content += f'default = "{fsh_val}"\n'
    content += "\n"
    content += "[auto_suggest]\n"
    content += f'default = "{ghost_val}"\n'
    content += "\n"
    content += "[completions]\n"
    content += f'default = "{comp_val}"\n'
    content += "\n"
    content += "[navigation]\n"
    content += f'default = "{nav_val}"\n'
    content += "\n"
    content += "[fuzzy_finder]\n"
    content += 'default = "fzf"\n'
    content += "\n"
    content += "[git]\n"
    content += 'default = "ohmyzsh-git"\n'
    content += "\n"
    content += "[ui]\n"
    content += "rich = true\n"
    defaults.write_text(content, encoding="utf-8")


def _write_prompt_conf(cfg: Path, prompt_name: str = "starship", force: bool = False) -> None:
    """Ensure prompt.conf exists with chosen prompt."""
    cfg.mkdir(parents=True, exist_ok=True)
    pconf = cfg / "prompt.conf"
    if not pconf.is_file() or force:
        pconf.write_text(f"{prompt_name}\n", encoding="utf-8")


def _write_custom_load_toml(cfg: Path, custom_opts: dict[str, Any]) -> None:
    """Write load.toml reflecting user custom component choices."""
    from core.build import default_manifest_content
    import tomllib
    manifest = tomllib.loads(default_manifest_content())

    disable_map = {
        "starship": custom_opts.get("prompt") != "starship",
        "ziro-ghost": not custom_opts.get("enable_ghost", True),
        "fast-syntax-highlighting": not custom_opts.get("enable_fsh", True),
        "fzf-tab": not custom_opts.get("enable_fzf_tab", True),
        "zoxide": not custom_opts.get("enable_zoxide", True),
        "ziro-aliases-core": not custom_opts.get("enable_aliases", True),
        "ziro-helpers": not custom_opts.get("enable_helpers", True),
    }

    for tool in manifest.get("tool", []):
        name = tool.get("name")
        if name in disable_map and disable_map[name]:
            tool["enabled"] = False

    from core.loadtoml_writer import write_load_toml
    load_path = cfg / "load.toml"
    write_load_toml(manifest, str(load_path))


def _run_custom_wizard() -> dict[str, Any]:
    """Interactively prompt user for custom component configuration."""
    print()
    print("┌──────────────────────────────────────────────┐")
    print("│         Ziro Custom Component Setup          │")
    print("└──────────────────────────────────────────────┘")
    print()

    # 1. Starship Theme Preset (Starship is Ziro's exclusive prompt engine)
    print("1. Starship Theme Preset:")
    print("   [1] tokyo-night (Recommended)")
    print("   [2] catppuccin-powerline")
    print("   [3] pure-preset")
    print("   [4] pastel-powerline")
    print("   [5] nerd-font-symbols")
    print("   [6] plain-text-symbols")
    print("   [7] default (official Starship default)")
    t_ans = _prompt_user("   Select preset [1]: ", default="1")
    theme_map = {
        "1": "tokyo-night",
        "2": "catppuccin-powerline",
        "3": "pure-preset",
        "4": "pastel-powerline",
        "5": "nerd-font-symbols",
        "6": "plain-text-symbols",
        "7": "default",
    }
    selected_theme = theme_map.get(t_ans, "tokyo-night")

    # 2. Nerd Font check (Prerequisite for Starship prompt icons, glyphs, and badges)
    print()
    print("2. Nerd Font (Required for theme icons, glyphs, and status badges):")
    nf_ans = _prompt_user("   Do you have a Nerd Font installed in your terminal? [Y/n]: ", default="y")
    nerd_font = nf_ans.lower() not in ("n", "no")

    # 3. AI Ghost Text / Autosuggestions
    print()
    ghost_ans = _prompt_user("3. Enable ghost text / autosuggestions (ziro-ghost)? [Y/n]: ", default="y")
    enable_ghost = ghost_ans.lower() not in ("n", "no")

    # 4. Syntax Highlighting
    print()
    fsh_ans = _prompt_user("4. Enable fast syntax highlighting (fast-syntax-highlighting)? [Y/n]: ", default="y")
    enable_fsh = fsh_ans.lower() not in ("n", "no")

    # 5. Enhanced Completions Menu
    print()
    comp_ans = _prompt_user("5. Enable fzf-tab interactive completion menu? [Y/n]: ", default="y")
    enable_fzf_tab = comp_ans.lower() not in ("n", "no")

    # 6. Smart Directory Navigation (zoxide)
    print()
    zox_ans = _prompt_user("6. Enable smart directory jump (zoxide / z)? [Y/n]: ", default="y")
    enable_zoxide = zox_ans.lower() not in ("n", "no")

    # 7. Core Aliases & Navigation (ll, la, lt, ..)
    print()
    alias_ans = _prompt_user("7. Enable core navigation aliases (ll, la, lt, .., ...)? [Y/n]: ", default="y")
    enable_aliases = alias_ans.lower() not in ("n", "no")

    # 8. Utility Helpers (extract, take, clipcopy, ff)
    print()
    help_ans = _prompt_user("8. Enable utility helpers (extract, mkcd/take, clipcopy, ff, fy)? [Y/n]: ", default="y")
    enable_helpers = help_ans.lower() not in ("n", "no")

    print()
    return {
        "prompt": "starship",
        "theme": selected_theme,
        "nerd_font": nerd_font,
        "enable_ghost": enable_ghost,
        "enable_fsh": enable_fsh,
        "enable_fzf_tab": enable_fzf_tab,
        "enable_zoxide": enable_zoxide,
        "enable_aliases": enable_aliases,
        "enable_helpers": enable_helpers,
    }


def _write_tools(cfg: Path, force: bool = False) -> None:
    """Write minimal tools.toml (empty registry)."""
    cfg.mkdir(parents=True, exist_ok=True)
    tools = cfg / "tools.toml"
    if tools.is_file() and not force:
        return
    content = "# AUTO-GENERATED by ziro — do not edit manually\n"
    content += "# Registry of known tools.\n"
    content += "\n"
    content += "[meta]\n"
    content += 'schema = "0.1.5"\n'
    content += 'count = 0\n'
    tools.write_text(content)


def _write_tags(cfg: Path, force: bool = False) -> None:
    """Ensure ~/.config/ziro/tags/builtin.toml exists."""
    from core.tags import ensure_builtin_tags_file
    ensure_builtin_tags_file(cfg, force=force)


def _configure_ghost_nerd_font(
    cfg: Path,
    argv: list[str] | None = None,
    nerd_font: bool | None = None,
    force: bool = False,
) -> None:
    """Ensure ~/.config/ziro/ghost.conf exists with nerd_font setting (Spec 009 R19)."""
    ghost_conf = cfg / "ghost.conf"
    if ghost_conf.exists() and nerd_font is None and not force:
        return  # don't overwrite

    if nerd_font is not None:
        nerd = nerd_font
    else:
        args = argv if argv is not None else sys.argv
        if "--default" in args or not sys.stdin.isatty():
            nerd = True  # safe default in non-interactive / default mode
        else:
            print("\nziro-ghost setup:")
            try:
                ans = input("  Do you use a Nerd Font in your terminal? [Y/n] ").strip().lower()
                nerd = ans not in ("n", "no")
            except EOFError:
                nerd = True

    ghost_conf.parent.mkdir(parents=True, exist_ok=True)
    ghost_conf.write_text(f"[ui]\nnerd_font = {str(nerd).lower()}\n", encoding="utf-8")
    print(f"✅ wrote: {ghost_conf}")


def _data_dir() -> Path:
    return get_paths()["data"]


def _write_completion(data_dir: Path) -> Path:
    """Install zsh completion script to ~/.local/share/ziro/completions/_ziro."""
    comp_dir = data_dir / "completions"
    comp_dir.mkdir(parents=True, exist_ok=True)
    comp_file = comp_dir / "_ziro"
    from core.completion_cli import generate_zsh_completion
    content = generate_zsh_completion()
    comp_file.write_text(content, encoding="utf-8")
    return comp_file


def _venv_dir() -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return data_home / "ziro" / "venv"


def _ensure_venv() -> Path | None:
    """Bootstrap ~/.local/share/ziro/venv with rich installed (idempotent, non-fatal)."""
    if os.environ.get("ZIRO_SKIP_VENV_BOOTSTRAP") == "1":
        return None
    venv_path = _venv_dir()
    py_bin = venv_path / "bin" / "python3"
    pip_bin = venv_path / "bin" / "pip"

    if py_bin.is_file():
        return venv_path

    try:
        venv_path.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(
            [sys.executable, "-m", "venv", str(venv_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            print(f"⚠️  warning: failed to create venv at {venv_path}: {r.stderr.strip()}", file=sys.stderr)
            return None

        if pip_bin.is_file():
            r_pip = subprocess.run(
                [str(pip_bin), "install", "--quiet", "rich"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if r_pip.returncode != 0:
                print(f"⚠️  warning: pip install rich failed: {r_pip.stderr.strip()}", file=sys.stderr)
        return venv_path
    except Exception as e:
        print(f"⚠️  warning: venv bootstrap error: {e}", file=sys.stderr)
        return None


def _install_cli_launcher(ziro_home: Path) -> Path | None:
    """Create ~/.local/bin/ziro executable launcher so ziro is callable from any terminal."""
    try:
        local_bin = Path.home() / ".local" / "bin"
        local_bin.mkdir(parents=True, exist_ok=True)
        launcher = local_bin / "ziro"
        content = (
            "#!/usr/bin/env zsh\n"
            f': ${{ZIRO_HOME:="{ziro_home}"}}\n'
            'if [[ -f "$ZIRO_HOME/ziro.zsh" ]]; then\n'
            '  source "$ZIRO_HOME/ziro.zsh"\n'
            '  _ziro_dispatch "$@"\n'
            "else\n"
            '  print -u2 "ziro: ZIRO_HOME not found at $ZIRO_HOME"\n'
            "  exit 1\n"
            "fi\n"
        )
        launcher.write_text(content, encoding="utf-8")
        launcher.chmod(0o755)
        return launcher
    except Exception:
        return None


def _install_man_page(ziro_home: Path) -> Path | None:
    """Install ziro.1 manual page to ~/.local/share/man/man1/ziro.1."""
    try:
        source_candidates = [
            ziro_home / "man" / "man1" / "ziro.1",
            ziro_home / "docs" / "_build" / "man" / "ziro.1",
        ]
        src: Path | None = None
        for cand in source_candidates:
            if cand.is_file():
                src = cand
                break
        if not src:
            return None

        xdg_data = os.environ.get("XDG_DATA_HOME")
        man_dir = (Path(xdg_data) if xdg_data else (Path.home() / ".local" / "share")) / "man" / "man1"
        man_dir.mkdir(parents=True, exist_ok=True)
        dest = man_dir / "ziro.1"
        dest.write_bytes(src.read_bytes())
        return dest
    except Exception:
        return None


def _prompt_user(prompt_text: str, default: str = "") -> str:
    """Prompt user for input, using sys.stdin or falling back to /dev/tty."""
    if sys.stdin.isatty():
        try:
            val = input(prompt_text).strip()
            return val if val else default
        except (EOFError, OSError):
            return default

    # Try /dev/tty if stdin was redirected or piped
    try:
        with open("/dev/tty", "r", encoding="utf-8") as tty_in:
            sys.stdout.write(prompt_text)
            sys.stdout.flush()
            val = tty_in.readline().strip()
            return val if val else default
    except Exception:
        return default


def _is_ziro_only_zshrc(zshrc: Path) -> bool:
    """Return True if ~/.zshrc contains only Ziro initialization or comments."""
    if not zshrc.is_file():
        return False
    try:
        content = zshrc.read_text(encoding="utf-8").strip()
        if not content:
            return True
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if not lines:
            return True
        ziro_patterns = ("boot.zsh", "$HOME/.local/bin", "${HOME}/.local/bin", "ZIRO_")
        return all(any(pat in line for pat in ziro_patterns) for line in lines)
    except Exception:
        return False


def detect_existing_zsh_configs(zsh_dir: Path | None = None) -> list[Path]:
    """Detect existing Zsh configuration files and framework directories."""
    if zsh_dir is None:
        zdotdir = os.environ.get("ZDOTDIR")
        zsh_dir = Path(zdotdir) if zdotdir else Path(os.environ.get("HOME", str(Path.home())))

    existing: list[Path] = []

    # Standard Zsh startup files
    candidate_files = [".zshrc", ".zshenv", ".zprofile", ".zlogin", ".zlogout"]
    for fname in candidate_files:
        p = zsh_dir / fname
        if p.is_file() or p.is_symlink():
            if fname == ".zshrc" and _is_ziro_only_zshrc(p):
                continue
            existing.append(p)

    # Completion dump caches in user home
    try:
        for p in zsh_dir.glob(".zcompdump*"):
            if p.is_file() or p.is_symlink():
                existing.append(p)
    except Exception:
        pass

    # Known Zsh framework and plugin directories
    candidate_dirs = [
        ".oh-my-zsh",
        ".zim",
        ".zprezto",
        ".zsh",
        ".antigen",
        ".zplug",
        ".antibody",
        ".sheldon",
    ]
    for dname in candidate_dirs:
        p = zsh_dir / dname
        if p.exists() and "ziro" not in p.name.lower():
            existing.append(p)

    # XDG zsh config directory (~/.config/zsh)
    try:
        xdg_cfg = Path(os.environ.get("XDG_CONFIG_HOME", str(Path(os.environ.get("HOME", str(Path.home()))) / ".config")))
        xdg_zsh = xdg_cfg / "zsh"
        if xdg_zsh.exists() and xdg_zsh.resolve() != zsh_dir.resolve():
            existing.append(xdg_zsh)
    except Exception:
        pass

    return existing


def backup_and_clean_zsh_configs(
    items: list[Path],
    dry_run: bool = False,
    zsh_dir: Path | None = None,
) -> Path | None:
    """Back up detected Zsh config files/directories to ~/.zsh-backup-<ts> and wipe them."""
    if not items:
        return None

    if zsh_dir is None:
        zdotdir = os.environ.get("ZDOTDIR")
        zsh_dir = Path(zdotdir) if zdotdir else Path(os.environ.get("HOME", str(Path.home())))

    # Protect developer's real home during automated unit tests
    try:
        import pwd
        real_user_home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    except Exception:
        real_user_home = Path.home().resolve()

    if (
        zsh_dir.resolve() == real_user_home
        and (os.environ.get("PYTEST_CURRENT_TEST") or "unittest" in sys.modules)
        and os.environ.get("ZIRO_ALLOW_TEST_WIPE") != "1"
    ):
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_dir = zsh_dir / f".zsh-backup-{ts}"

    if dry_run:
        print(f"[dry-run] would back up {len(items)} item(s) to {backup_dir} and remove them:")
        for it in items:
            print(f"  [dry-run] backup and remove: {it}")
        return backup_dir

    backup_dir.mkdir(parents=True, exist_ok=True)
    for item in items:
        try:
            if not item.exists() and not item.is_symlink():
                continue
            dest = backup_dir / item.name
            if item.is_dir() and not item.is_symlink():
                shutil.copytree(item, dest, symlinks=True, dirs_exist_ok=True)
                shutil.rmtree(item, ignore_errors=True)
            else:
                shutil.copy2(item, dest, follow_symlinks=False)
                item.unlink(missing_ok=True)
        except Exception as e:
            print(f"⚠️  warning: failed to backup/remove {item}: {e}", file=sys.stderr)

    return backup_dir


def _activate_zshrc(cfg: Path, dry_run: bool = False, no_activate: bool = False) -> tuple[bool, str]:
    """Idempotently append source <boot.zsh> to ~/.zshrc with a timestamped backup."""
    if no_activate:
        return True, "skipped (--no-activate)"

    zdotdir = os.environ.get("ZDOTDIR")
    zshrc_dir = Path(zdotdir) if zdotdir else Path(os.environ.get("HOME", str(Path.home())))

    # Protect real user home from pollution when tests run with unmocked HOME
    try:
        import pwd
        real_user_home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    except Exception:
        real_user_home = Path.home().resolve()

    if (zshrc_dir.resolve() == real_user_home) and (os.environ.get("PYTEST_CURRENT_TEST") or "unittest" in sys.modules):
        return True, "skipped (real home protected in test mode)"

    zshrc = zshrc_dir / ".zshrc"
    boot_shim = cfg / "boot.zsh"
    source_line = f"source {boot_shim}"

    if zshrc.is_file():
        try:
            content = zshrc.read_text(encoding="utf-8")
            for line in content.splitlines():
                stripped = line.strip()
                clean = stripped.rstrip('"\'')
                if (
                    stripped == source_line
                    or stripped == f'source "{boot_shim}"'
                    or (clean.startswith("source ") and clean.endswith("boot.zsh"))
                    or "boot.zsh" in stripped
                ):
                    return True, "already activated"
        except Exception as e:
            return False, f"error reading {zshrc}: {e}"

    if dry_run:
        return True, f"[dry-run] would activate in {zshrc}"

    backup_str = ""
    if zshrc.is_file():
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup = zshrc_dir / f".zshrc.bak.{ts}"
        try:
            shutil.copy2(zshrc, backup)
            backup_str = f" (backup: {backup})"
        except Exception as e:
            print(f"⚠️  warning: failed to create zshrc backup: {e}", file=sys.stderr)

    try:
        zshrc.parent.mkdir(parents=True, exist_ok=True)
        append_text = (
            "# Ziro Shell initialization\n"
            '[[ ":$PATH:" != *":$HOME/.local/bin:"* ]] && export PATH="$HOME/.local/bin:$PATH"\n'
            '[[ -d "$HOME/.local/share/man" && ":$MANPATH:" != *":$HOME/.local/share/man:"* ]] && export MANPATH="$HOME/.local/share/man:${MANPATH:-}"\n'
            f'source "{boot_shim}"\n'
        )
        if zshrc.is_file() and zshrc.stat().st_size > 0:
            append_text = "\n" + append_text
        with zshrc.open("a", encoding="utf-8") as f:
            f.write(append_text)
        return True, f"activated in {zshrc}{backup_str}"
    except Exception as e:
        return False, f"failed to write {zshrc}: {e}"


def cmd_install(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "install")
    if ret is not None:
        return ret

    dry_run = "--dry-run" in argv
    default_mode = "--default" in argv
    custom_mode = "--custom" in argv
    clean_mode = "--clean" in argv or os.environ.get("ZIRO_CLEAN") == "1"
    no_clean_mode = "--no-clean" in argv or os.environ.get("ZIRO_NO_CLEAN") == "1"
    rebuild_flag = (
        "--rebuild" in argv
        or "--reinstall" in argv
        or os.environ.get("ZIRO_REBUILD") == "1"
    )
    no_rebuild_flag = "--no-rebuild" in argv or os.environ.get("ZIRO_NO_REBUILD") == "1"
    no_activate = "--no-activate" in argv

    cfg = _config_dir()

    print("ziro-shell installer")
    print("─" * 40)

    # 1. Detect existing Zsh configurations and offer clean install
    existing_configs = detect_existing_zsh_configs()
    if existing_configs:
        do_clean = False
        if clean_mode:
            do_clean = True
        elif no_clean_mode:
            do_clean = False
        else:
            print("⚠️  Existing Zsh configuration detected:")
            for item in existing_configs[:6]:
                try:
                    rel = f"~/{item.relative_to(Path.home())}"
                except ValueError:
                    rel = str(item)
                print(f"   • {rel}")
            if len(existing_configs) > 6:
                print(f"   • ... and {len(existing_configs) - 6} more")
            print()
            print("Would you like to perform a clean install?")
            print("(This will back up all your existing Zsh configs, then wipe them to start fresh with Ziro)")
            ans = _prompt_user("Clean install? [y/N]: ", default="n")
            do_clean = ans.lower() in ("y", "yes")

        if do_clean:
            backup_dir = backup_and_clean_zsh_configs(existing_configs, dry_run=dry_run)
            if backup_dir:
                try:
                    rel_backup = f"~/{backup_dir.relative_to(Path.home())}"
                except ValueError:
                    rel_backup = str(backup_dir)
                print(f"📦 Backed up existing Zsh config to: {rel_backup}")
                print("🧹 Cleaned up old Zsh configuration.")
                print()

    # 2. Detect existing Ziro installation and offer full scratch rebuild
    do_rebuild = False
    if is_ziro_installed(cfg):
        if rebuild_flag:
            do_rebuild = True
        elif no_rebuild_flag:
            do_rebuild = False
        else:
            print("⚠️  Existing Ziro installation detected.")
            print("Would you like to rebuild everything from scratch?")
            print("(This will re-create all Zsh and Ziro configurations, caches, and artifacts)")
            ans = _prompt_user("Rebuild from scratch? [y/N]: ", default="n")
            do_rebuild = ans.lower() in ("y", "yes")
    elif rebuild_flag:
        do_rebuild = True

    if do_rebuild:
        print("🔄 Rebuilding all Ziro configurations, caches, and artifacts from scratch...")
        if not dry_run:
            import shutil
            cache = _cache_dir()
            if cache.exists():
                shutil.rmtree(cache, ignore_errors=True)
            cache.mkdir(parents=True, exist_ok=True)

            derived = cfg / "derived"
            if derived.exists():
                shutil.rmtree(derived, ignore_errors=True)
            derived.mkdir(parents=True, exist_ok=True)

    custom_opts: dict[str, Any] | None = None
    if default_mode:
        choice = "default"
    elif custom_mode:
        choice = "custom"
        custom_opts = _run_custom_wizard()
    else:
        # Interactive question (only if TTY)
        ans = _prompt_user(
            "How would you like to proceed?\n"
            " [1] Default — install with pre-configured defaults\n"
            " [2] Custom — choose each component manually\n"
            "Choice [1]: ",
            default="1",
        )
        if ans == "2":
            choice = "custom"
            custom_opts = _run_custom_wizard()
        else:
            choice = "default"

    print(f"mode: {choice}")

    if dry_run:
        print("[dry-run] would write defaults.toml, tools.toml, tags/builtin.toml, completions/_ziro, derived/plugins.gen.zsh")
        if custom_opts:
            print(f"[dry-run] custom components: {custom_opts}")
        return 0

    _configure_ghost_nerd_font(
        cfg,
        argv,
        nerd_font=custom_opts.get("nerd_font") if custom_opts else None,
        force=do_rebuild,
    )

    data = _data_dir()
    from core.tty import is_tty
    from core.generator import generate_plugins_gen
    if is_tty():
        try:
            from rich.progress import Progress, SpinnerColumn, TextColumn
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                transient=True,
            ) as progress:
                progress.add_task(description="Writing configuration files...", total=None)
                _write_defaults(cfg, custom_opts, force=do_rebuild)
                _write_tools(cfg, force=do_rebuild)
                _write_tags(cfg, force=do_rebuild)
                _write_prompt_conf(cfg, custom_opts.get("prompt", "starship") if custom_opts else "starship", force=do_rebuild)
                if custom_opts:
                    _write_custom_load_toml(cfg, custom_opts)
                elif do_rebuild and (cfg / "load.toml").exists():
                    from core.build import default_manifest_content
                    (cfg / "load.toml").write_text(default_manifest_content(), encoding="utf-8")
                comp_file = _write_completion(data)
                _ensure_venv()
                gen_file = generate_plugins_gen(cfg, ziro_home=_ziro_home())
        except Exception:
            _write_defaults(cfg, custom_opts, force=do_rebuild)
            _write_tools(cfg, force=do_rebuild)
            _write_tags(cfg, force=do_rebuild)
            _write_prompt_conf(cfg, custom_opts.get("prompt", "starship") if custom_opts else "starship", force=do_rebuild)
            if custom_opts:
                _write_custom_load_toml(cfg, custom_opts)
            elif do_rebuild and (cfg / "load.toml").exists():
                from core.build import default_manifest_content
                (cfg / "load.toml").write_text(default_manifest_content(), encoding="utf-8")
            comp_file = _write_completion(data)
            _ensure_venv()
            gen_file = generate_plugins_gen(cfg, ziro_home=_ziro_home())

        from core.rich_helpers import render_table
        table_rows = [
            ["defaults.toml", f"{cfg}/defaults.toml", "Written"],
            ["tools.toml", f"{cfg}/tools.toml", "Written"],
            ["prompt.conf", f"{cfg}/prompt.conf", "Written"],
            ["builtin.toml", f"{cfg}/tags/builtin.toml", "Written"],
            ["_ziro", f"{comp_file}", "Written"],
            ["plugins.gen.zsh", f"{gen_file}", "Written"],
        ]
        if not render_table("Installed Configurations", ["File", "Path", "Status"], table_rows):
            print(f"✅ wrote: {cfg}/defaults.toml")
            print(f"✅ wrote: {cfg}/tools.toml")
            print(f"✅ wrote: {cfg}/prompt.conf")
            print(f"✅ wrote: {cfg}/tags/builtin.toml")
            print(f"✅ wrote: {comp_file}")
            print(f"✅ wrote: {gen_file}")
    else:
        _write_defaults(cfg, custom_opts, force=do_rebuild)
        _write_tools(cfg, force=do_rebuild)
        _write_tags(cfg, force=do_rebuild)
        _write_prompt_conf(cfg, custom_opts.get("prompt", "starship") if custom_opts else "starship", force=do_rebuild)
        if custom_opts:
            _write_custom_load_toml(cfg, custom_opts)
        elif do_rebuild and (cfg / "load.toml").exists():
            from core.build import default_manifest_content
            (cfg / "load.toml").write_text(default_manifest_content(), encoding="utf-8")
        comp_file = _write_completion(data)
        _ensure_venv()
        gen_file = generate_plugins_gen(cfg, ziro_home=_ziro_home())
        print(f"✅ wrote: {cfg}/defaults.toml")
        print(f"✅ wrote: {cfg}/tools.toml")
        print(f"✅ wrote: {cfg}/prompt.conf")
        print(f"✅ wrote: {cfg}/tags/builtin.toml")
        print(f"✅ wrote: {comp_file}")
        print(f"✅ wrote: {gen_file}")

    if choice == "custom" and custom_opts:
        theme_name = custom_opts.get("theme")
        if theme_name and custom_opts.get("prompt") == "starship":
            try:
                from core.theme_cli import _apply_starship_preset_or_file, _themes_dir
                _apply_starship_preset_or_file(theme_name, _themes_dir())
                print(f"🎨 applied theme preset: {theme_name}")
            except Exception as e:
                print(f"⚠️  warning: failed to apply theme {theme_name}: {e}")

    ok, msg = _verify_starship()
    if not ok:
        print(file=sys.stderr)
        print("⚠️  Starship not available", file=sys.stderr)
        print(f"   Reason: {msg}", file=sys.stderr)
        print("   Install: https://starship.rs/guide/#%F0%9F%9A%80-installation", file=sys.stderr)
        print("   Or switch to an alternative prompt:", file=sys.stderr)
        print("     ziro prompt set p10k     # powerlevel10k", file=sys.stderr)
        print("     ziro prompt set pure     # pure", file=sys.stderr)
        print("     ziro prompt set none     # no prompt management", file=sys.stderr)
        # Non-fatal: install still succeeds

    # Step: Execute Build Pipeline (ziro sync)
    print("\nRunning build pipeline...")
    from core.build import build
    ok_build, msg_build, _ = build(force=do_rebuild, rebuild_eval_caches=True)
    if not ok_build:
        print(f"❌ build pipeline failed: {msg_build}", file=sys.stderr)
        return 1
    print(f"✅ boot chain compiled: {cfg / 'boot.zsh'}")

    # Step: Install CLI launcher (~/.local/bin/ziro)
    launcher = _install_cli_launcher(_ziro_home())
    if launcher:
        print(f"✅ installed launcher: {launcher}")

    # Step: Install manual page (~/.local/share/man/man1/ziro.1)
    man_page = _install_man_page(_ziro_home())
    if man_page:
        print(f"✅ installed manual page: {man_page}")

    # Step: Shell activation in .zshrc
    ok_act, msg_act = _activate_zshrc(cfg, dry_run=dry_run, no_activate=no_activate)
    if not ok_act:
        print(f"⚠️  warning: activation failed: {msg_act}", file=sys.stderr)
    else:
        print(f"✅ shell activation: {msg_act}")

    print("")
    print("────────────────────────────────────────")
    print("🚀 Installation complete!")
    print("Run: exec zsh")
    print("────────────────────────────────────────")
    return 0


def main(argv: list[str]) -> int:
    return cmd_install(argv)


__all__ = ["main"]
