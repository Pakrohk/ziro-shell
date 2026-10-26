"""ziro-shell — plugin command (full implementation).

Layer: 3 (Python core, cold-path only)
Spec: 001 FR-001
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from core.plugin_pipeline import add_plugin, remove_plugin
from core.analyzer import analyze_with_cache
from core.resolver import resolve


def _ziro_home() -> Path:
    return Path(os.environ.get("ZIRO_HOME", Path.home() / ".ziro"))


def _config_dir() -> Path:
    base = os.environ.get("ZIRO_CONFIG")
    if base:
        return Path(base)
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "ziro"


def _list_plugin_dirs(ziro_home: Path) -> list[Path]:
    pdir = ziro_home / "plugins"
    if not pdir.is_dir():
        return []
    return sorted(p for p in pdir.iterdir() if p.is_dir() and not p.name.startswith("."))


def _get_on_demand_plugin_names() -> set:
    """Return set of plugin names that tools_factory marks as on-demand."""
    try:
        from core.generator import load_tools_registry
        tools = load_tools_registry(_config_dir())
        return {t.get("name", "") for t in tools if t.get("load_timing") == "on-demand"}
    except Exception:
        return set()


def _existing_configs() -> list:
    """Reconstruct current plugin configs from tools registry + installed plugin dirs.

    add_plugin/remove_plugin regenerate plugins.gen.zsh from this list plus
    the changed plugin. Skipping this drops every previously-installed plugin
    on each add/remove (each regenerates from scratch).
    """
    ziro_home = _ziro_home()
    config_dir = _config_dir()
    configs = []
    _on_demand_plugin_names = _get_on_demand_plugin_names()

    # 1. Active tools from declarative registry (tools_factory.toml + user tools.toml + defaults.toml)
    try:
        from core.generator import load_tools_registry, emit_pattern
        from core.resolver import ResolvedConfig
        from core.models import Strategy
        import tomllib

        tools = load_tools_registry(config_dir)
        sorted_tools = sorted(tools, key=lambda t: t.get("load_order", 999))

        active_selections: dict[str, str] = {}
        for t in sorted_tools:
            cat = t.get("category", "")
            if not t.get("alternatives_only", False) and cat not in ("core", "infra"):
                active_selections[cat] = t.get("name", "")

        defaults_file = config_dir / "defaults.toml"
        if defaults_file.is_file():
            try:
                with defaults_file.open("rb") as f:
                    d = tomllib.load(f)
                    for cat, ccfg in d.items():
                        if isinstance(ccfg, dict) and "default" in ccfg:
                            active_selections[cat] = ccfg["default"]
            except Exception:
                pass

        prompt_conf_file = config_dir / "prompt.conf"
        if prompt_conf_file.is_file():
            try:
                p_val = prompt_conf_file.read_text(encoding="utf-8").strip()
                if p_val:
                    active_selections["prompt"] = p_val
            except OSError:
                pass

        selected_tool_names = set(active_selections.values())

        for tool in sorted_tools:
            if tool.get("type") in ("bootstrap", "builtin"):
                continue
            cat = tool.get("category", "")
            tname = tool.get("name", "")
            timing = tool.get("load_timing", "")
            if cat == "core":
                if tool.get("alternatives_only", False) and tname not in selected_tool_names:
                    continue
            elif timing == "on-demand":
                pass
            else:
                if cat not in active_selections or tname not in selected_tool_names:
                    continue
            raw_line = emit_pattern(tool)
            configs.append(
                ResolvedConfig(
                    plugin=tname,
                    strategy=Strategy.AFTER_PROMPT if timing == "defer" else Strategy.EAGER,
                    eval_cache=timing == "eval",
                    raw=raw_line,
                )
            )
    except Exception:
        pass

    # 2. Add local plugins in $ZIRO_HOME/plugins/ (skip factory tool names to avoid duplication)
    known_names = {getattr(c, "plugin", "") for c in configs}
    for pdir in _list_plugin_dirs(ziro_home):
        name = pdir.name
        if name in known_names or f"ohmyzsh-{name}" in known_names:
            continue
        # Skip plugins that tools_factory marks as on-demand (handled separately)
        if name in _on_demand_plugin_names:
            continue
        analysis = analyze_with_cache(pdir, name)
        try:
            configs.append(resolve(analysis, config_dir))
        except Exception:
            # A broken plugin must not block listing/adding others.
            continue
    return configs


def cmd_list(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "plugin", subcommand="list")
    if ret is not None:
        return ret

    names_only = "--names" in argv or "-q" in argv or "--raw" in argv

    # Load factory definitions for descriptions and types
    tf_path = _ziro_home() / "core" / "tools_factory.toml"
    if not tf_path.is_file():
        tf_path = Path(__file__).parent / "tools_factory.toml"

    descriptions: dict[str, str] = {}
    types: dict[str, str] = {}
    if tf_path.is_file():
        try:
            import tomllib
            with tf_path.open("rb") as f:
                tfd = tomllib.load(f)
                for t in tfd.get("tool", []):
                    name = t.get("name", "")
                    descriptions[name] = t.get("description", "")
                    types[name] = t.get("type", "plugin")
        except Exception:
            pass

    # 1. Attempt to read from load.toml (active declarative configuration)
    load_path = _config_dir() / "load.toml"
    tools: list[dict] = []
    if load_path.is_file():
        try:
            import tomllib
            with load_path.open("rb") as f:
                ld = tomllib.load(f)
                tools = ld.get("tool", [])
        except Exception:
            tools = []

    # 2. Collect any in-tree plugins in ~/.ziro/plugins/
    dirs = _list_plugin_dirs(_ziro_home())
    known_names = {t.get("name") for t in tools}
    for d in dirs:
        if d.name not in known_names:
            tools.append({
                "name": d.name,
                "timing": "custom",
                "method": "local-source",
                "path": str(d),
                "reason": "local in-tree plugin",
            })

    if not tools:
        print("(no plugins installed)")
        return 0

    if names_only:
        for t in tools:
            print(t.get("name", ""))
        return 0

    rows: list[list[str]] = []
    eager_cnt = 0
    deferred_cnt = 0
    ondemand_cnt = 0

    for t in tools:
        name = t.get("name", "")
        timing = t.get("timing", "deferred")
        stage = t.get("stage")
        slot = t.get("slot", "b")
        trigger = t.get("trigger", "")
        method = t.get("method", "source")

        if timing == "eager":
            eager_cnt += 1
            stage_str = "Stage 2/4 (Eager · Pre-Prompt)"
        elif timing == "deferred":
            deferred_cnt += 1
            stage_str = f"Stage {stage or 5} (Deferred · Slot {slot})"
        elif timing == "on-demand":
            ondemand_cnt += 1
            trig_desc = ""
            if trigger == "command":
                cmds = t.get("trigger_commands", [])
                trig_desc = f": {cmds[0]}" if cmds else ""
            elif trigger == "key":
                keys = [k.get("key", "") if isinstance(k, dict) else str(k) for k in t.get("trigger_keys", [])]
                trig_desc = f": {keys[0]}" if keys else ""
            elif trigger == "function":
                funcs = t.get("trigger_functions", [])
                trig_desc = f": {funcs[0]}" if funcs else ""
            stage_str = f"Stage 7 (On-Demand{trig_desc})"
        else:
            stage_str = timing

        ptype = types.get(name, "plugin")
        if ptype == "binary":
            ptype_str = "Binary"
        elif ptype == "builtin":
            ptype_str = "Builtin"
        elif ptype == "bootstrap":
            ptype_str = "Core"
        else:
            ptype_str = "Plugin"

        desc = descriptions.get(name, "")
        if not desc:
            reason = t.get("reason", "")
            desc = reason.split(":")[-1].strip() if ":" in reason else reason

        rows.append([name, ptype_str, stage_str, method, desc])

    title = f"Ziro Ecosystem — Plugins & Tools ({len(tools)} total: {eager_cnt} eager, {deferred_cnt} deferred, {ondemand_cnt} on-demand)"
    headers = ["Name", "Type", "Lifecycle Stage", "Load Method", "Description"]

    from core.rich_helpers import render_table
    if not render_table(title, headers, rows):
        w_name = max(len(r[0]) for r in rows) if rows else 10
        w_type = max(len(r[1]) for r in rows) if rows else 8
        w_stage = max(len(r[2]) for r in rows) if rows else 15
        w_method = max(len(r[3]) for r in rows) if rows else 12

        h_name, h_type, h_stage, h_method = "NAME", "TYPE", "LIFECYCLE STAGE", "METHOD"
        d_name, d_type, d_stage, d_method = "-" * w_name, "-" * w_type, "-" * w_stage, "-" * w_method
        print(title)
        print("=" * len(title))
        print(f"{h_name:<{w_name}}  {h_type:<{w_type}}  {h_stage:<{w_stage}}  {h_method:<{w_method}}  DESCRIPTION")
        print(f"{d_name}  {d_type}  {d_stage}  {d_method}  -----------------------------------")
        for r in rows:
            print(f"{r[0]:<{w_name}}  {r[1]:<{w_type}}  {r[2]:<{w_stage}}  {r[3]:<{w_method}}  {r[4]}")

    return 0


def cmd_show(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "plugin", subcommand="show")
    if ret is not None:
        return ret
    if not argv:
        print("usage: plugin show <name>", file=sys.stderr)
        return 2
    name = argv[0]
    pdir = _ziro_home() / "plugins" / name
    if not pdir.is_dir():
        print(f"plugin not found: {name}", file=sys.stderr)
        return 1
    zsh_files = list(pdir.rglob("*.zsh"))
    print(f"plugin: {name}")
    print(f"path: {pdir}")
    print(f"zsh files: {len(zsh_files)}")
    tag_file = _config_dir() / "tags" / "plugins" / f"{name}.toml"
    if tag_file.is_file():
        print(f"tags file: {tag_file}")
    load_toml = _config_dir() / "load.toml"
    if load_toml.is_file():
        try:
            import tomllib
            with load_toml.open("rb") as f:
                lt_data = tomllib.load(f)
            for t in lt_data.get("tool", []):
                if t.get("name") == name:
                    print(f"timing: {t.get('timing')}")
                    if t.get("reason"):
                        print(f"reason: {t.get('reason')}")
                    break
        except Exception:
            pass
    return 0


def _parse_lazy_flags(lazy_flags: list[str] | None, eager: bool = False, defer_slot: str | None = None) -> dict | None:
    """Parse CLI flags into a [user.override] dict.
    Returns override dict or None if no flags set.
    """
    override: dict[str, Any] = {}
    if eager:
        override["timing"] = "eager"
        override["reason"] = "user forced eager via CLI"
    if defer_slot:
        slot = defer_slot.removeprefix("slot:")
        override["timing"] = "deferred"
        override["stage"] = 5
        override["slot"] = slot
        override["reason"] = f"user forced deferred slot={slot} via CLI"
    for lazy in (lazy_flags or []):
        if not lazy:
            continue
        if lazy.startswith("key:"):
            keys_str = lazy[len("key:"):]
            keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            override["timing"] = "on-demand"
            override["trigger"] = "key"
            override["trigger_keys"] = [{"key": k, "widget": "auto"} for k in keys]
            override["reason"] = f"user forced on-demand/key: {keys}"
        elif lazy.startswith("command:"):
            cmds_str = lazy[len("command:"):]
            cmds = [c.strip() for c in cmds_str.split(",") if c.strip()]
            override["timing"] = "on-demand"
            override["trigger"] = "command"
            override["trigger_commands"] = cmds
            override["reason"] = f"user forced on-demand/command: {cmds}"
        elif lazy.startswith("function:"):
            fns_str = lazy[len("function:"):]
            fns = [f.strip() for f in fns_str.split(",") if f.strip()]
            override["timing"] = "on-demand"
            override["trigger"] = "function"
            override["trigger_functions"] = fns
            override["reason"] = f"user forced on-demand/function: {fns}"
    return override if override else None


def _write_user_override(tool_name: str, override: dict) -> None:
    """Append or update [user.override] entry for tool_name in load.toml."""
    import tomllib
    from pathlib import Path as _P
    from core.loadtoml_writer import write_load_toml

    load_toml = _P.home() / ".config" / "ziro" / "load.toml"
    data: dict[str, Any] = {}
    if load_toml.is_file():
        try:
            with load_toml.open("rb") as f:
                data = tomllib.load(f)
        except Exception:
            pass

    user = data.get("user", {})
    if not isinstance(user, dict):
        user = {}
    overrides = user.get("override", [])
    if not isinstance(overrides, list):
        overrides = []
    # Remove existing entry for this tool, then append
    overrides = [o for o in overrides if isinstance(o, dict) and o.get("name") != tool_name]
    entry = {"name": tool_name, **override}
    overrides.append(entry)
    user["override"] = overrides
    data["user"] = user

    write_load_toml(data, str(load_toml))


def cmd_add(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "plugin", subcommand="add")
    if ret is not None:
        return ret
    if not argv:
        print("usage: plugin add <source> [name] [@tags...] [--local] [--subpath=<path>]", file=sys.stderr)
        return 2

    dry_run = False
    force = False
    is_local = False
    local_path_arg: str | None = None
    subpath: str = ""
    explicit_name: str = ""
    tags: list[str] = []
    positional: list[str] = []
    lazy_flags: list[str] = []
    eager_flag = False
    defer_slot: str | None = None

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--dry-run":
            dry_run = True
            i += 1
        elif arg in ("--force", "-f"):
            force = True
            i += 1
        elif arg == "--lazy":
            if i + 1 < len(argv) and not argv[i + 1].startswith(("-", "@")):
                lazy_flags.append(argv[i + 1])
                i += 2
            else:
                lazy_flags.append("")
                i += 1
        elif arg.startswith("--lazy="):
            lazy_flags.append(arg.split("=", 1)[1])
            i += 1
        elif arg == "--eager":
            eager_flag = True
            i += 1
        elif arg == "--defer":
            if i + 1 < len(argv) and not argv[i + 1].startswith(("-", "@")):
                defer_slot = argv[i + 1].removeprefix("slot:")
                i += 2
            else:
                defer_slot = "b"
                i += 1
        elif arg.startswith("--defer="):
            defer_slot = arg.split("=", 1)[1].removeprefix("slot:")
            i += 1
        elif arg == "--local":
            is_local = True
            if i + 1 < len(argv) and not argv[i + 1].startswith(("-", "@")):
                local_path_arg = argv[i + 1]
                i += 2
            else:
                i += 1
        elif arg.startswith("--local="):
            is_local = True
            local_path_arg = arg.split("=", 1)[1]
            i += 1
        elif arg == "--subpath":
            if i + 1 < len(argv) and not argv[i + 1].startswith(("-", "@")):
                subpath = argv[i + 1]
                i += 2
            else:
                i += 1
        elif arg.startswith("--subpath="):
            subpath = arg.split("=", 1)[1]
            i += 1
        elif arg in ("--name", "-n"):
            if i + 1 < len(argv) and not argv[i + 1].startswith(("-", "@")):
                explicit_name = argv[i + 1]
                i += 2
            else:
                i += 1
        elif arg.startswith("--name="):
            explicit_name = arg.split("=", 1)[1]
            i += 1
        elif arg.startswith("@"):
            tags.append(arg)
            i += 1
        elif arg.startswith("-"):
            # Unknown option
            i += 1
        else:
            positional.append(arg)
            i += 1

    if is_local:
        if local_path_arg is not None:
            source = local_path_arg
            name = explicit_name or (positional[0] if positional else "")
        elif positional:
            source = positional[0]
            name = explicit_name or (positional[1] if len(positional) > 1 else "")
        else:
            print("error: --local requires a path argument", file=sys.stderr)
            return 1
    else:
        source = positional[0] if positional else ""
        if not subpath and len(positional) >= 2 and "/" in positional[1]:
            subpath = positional[1]
            name = explicit_name or (positional[2] if len(positional) > 2 else positional[1].split("/")[-1])
        else:
            name = explicit_name or (positional[1] if len(positional) > 1 else (subpath.split("/")[-1] if subpath else ""))

    if not source:
        print("usage: plugin add <source> [name] [@tags...]", file=sys.stderr)
        return 2

    # FIX-3.2: Validate local path
    if is_local:
        src_path = Path(source).expanduser()
        if not src_path.exists():
            print(f"error: --local path does not exist: {source}", file=sys.stderr)
            return 1
        source = str(src_path.resolve())

    # FIX-3.4: Reject binary tools
    if not is_local:
        try:
            from core.generator import load_tools_registry
            tools = load_tools_registry(_config_dir())
            src_lower = source.lower().rstrip("/").split("/")[-1].removesuffix(".git")
            for t in tools:
                t_name = t.get("name", "").lower()
                if t_name == src_lower and t.get("type") == "binary":
                    cat = t.get("category", "")
                    hint = f"ziro config set {cat}.default {source}" if cat else "ziro install"
                    print(f"error: '{source}' is a binary tool, not a plugin. Use: {hint}", file=sys.stderr)
                    return 1
        except Exception:
            pass

    # Normalize GitHub slug → URL only if not a local filesystem path
    if not is_local:
        src_path = Path(source).expanduser()
        if src_path.exists():
            source = str(src_path.resolve())
            is_local = True
        elif "/" in source and not source.startswith(("http://", "https://", "git@", "ssh://", "file://")):
            source = f"https://github.com/{source}.git"

    try:
        from core.tty import is_tty
        if is_tty():
            try:
                from rich.progress import Progress, SpinnerColumn, TextColumn
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    transient=True,
                ) as progress:
                    progress.add_task(description=f"Adding plugin {source}...", total=None)
                    result = add_plugin(
                        source,
                        name=name,
                        subpath=subpath,
                        tags=tags,
                        ziro_home=_ziro_home(),
                        config_dir=_config_dir(),
                        all_configs=_existing_configs(),
                        dry_run=dry_run,
                        is_local=is_local,
                    )
            except Exception:
                result = add_plugin(
                    source,
                    name=name,
                    subpath=subpath,
                    tags=tags,
                    ziro_home=_ziro_home(),
                    config_dir=_config_dir(),
                    all_configs=_existing_configs(),
                    dry_run=dry_run,
                    is_local=is_local,
                )
        else:
            result = add_plugin(
                source,
                name=name,
                subpath=subpath,
                tags=tags,
                ziro_home=_ziro_home(),
                config_dir=_config_dir(),
                all_configs=_existing_configs(),
                dry_run=dry_run,
                is_local=is_local,
            )
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    target_path = None
    if result.plugin_dir.exists():
        target_path = result.plugin_dir
    else:
        from core.analyzer import _resolve_vendor_path
        raw_slug = (
            source.replace("https://github.com/", "")
            .replace("http://github.com/", "")
            .replace("git@github.com:", "")
            .removesuffix(".git")
        )
        res_p, res_ok = _resolve_vendor_path(raw_slug, subpath)
        if not res_ok and raw_slug != source:
            res_p, res_ok = _resolve_vendor_path(source, subpath)
        if res_ok:
            p_obj = Path(os.path.expanduser(res_p))
            target_path = p_obj.parent if p_obj.is_file() else p_obj

    from core.analyzer import _security_heuristic, _apply_decision_matrix
    if target_path is not None:
        sec = _security_heuristic(target_path, source=source)
    else:
        sec = _security_heuristic(Path(source), source=source)

    if sec["blocked"] and not force and not result.dry_run:
        print(f"error: security check BLOCKED plugin '{result.plugin}': {', '.join(sec['dangerous_found'] or sec['notes'])}", file=sys.stderr)
        print("Use --force to override this security blocker.", file=sys.stderr)
        return 1

    prefix = "[dry-run] " if result.dry_run else ""
    print(f"{prefix}plugin: {result.plugin}")

    perf_strategy = result.strategy
    final_strat, report, blocked, override_req = _apply_decision_matrix(
        sec["trust_level"], perf_strategy, bool(sec["dangerous_found"])
    )

    if "CONFLICT" in report:
        print(f"{prefix}recommendations:")
        print(f"  perf: {perf_strategy}")
        print(f"  security: {final_strat} (downgraded due to {sec['trust_level']} trust)")
        print(f"{prefix}strategy: {final_strat}")
    elif blocked:
        print(f"{prefix}strategy: BLOCKED")
    else:
        print(f"{prefix}strategy: {final_strat}")

    print(f"{prefix}path: {result.plugin_dir}")
    score_disp = f"(score: {sec['trust_score']}/4)" if sec.get("trust_score") is not None else "(source not readable)"
    print(f"{prefix}trust: {sec['trust_level']} {score_disp}")
    if report != "agree":
        print(f"{prefix}security: {report}")
    else:
        print(f"{prefix}security: agree")

    if force and sec["blocked"]:
        print(f"{prefix}warning: security blocker bypassed via --force")

    if result.skipped_clone:
        print("(already cloned — skipped)")
    if not result.dry_run:
        user_override = _parse_lazy_flags(lazy_flags, eager=eager_flag, defer_slot=defer_slot)
        if user_override:
            _write_user_override(result.plugin, user_override)
            print(f"✔ Saved user override for {result.plugin} into ~/.config/ziro/load.toml")
            try:
                from core.build import build
                ok, msg, _ = build()
                if ok:
                    print("✔ Synced boot artifacts")
            except Exception as e:
                print(f"[sync] warning: {e}", file=sys.stderr)
        print(f"✅ regenerated: {result.generated}")
    return 0


def cmd_remove(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "plugin", subcommand="remove")
    if ret is not None:
        return ret
    if not argv:
        print("usage: plugin remove <name>", file=sys.stderr)
        return 2
    dry_run = "--dry-run" in argv
    positional = [a for a in argv if not a.startswith("--")]
    if not positional:
        print("usage: plugin remove <name>", file=sys.stderr)
        return 2
    name = positional[0]
    ok = remove_plugin(
        name,
        ziro_home=_ziro_home(),
        config_dir=_config_dir(),
        all_configs=_existing_configs(),
        dry_run=dry_run,
    )
    if not ok:
        print(f"plugin not found: {name}", file=sys.stderr)
        return 1
    prefix = "[dry-run] " if dry_run else ""
    print(f"{prefix}removed: {name}")
    return 0


def main(argv: list[str]) -> int:
    from core.help_cli import handle_help_if_requested
    ret = handle_help_if_requested(argv, "plugin")
    if ret is not None:
        return ret
    if not argv:
        print("usage: plugin <add|remove|list|show>", file=sys.stderr)
        return 2
    sub, rest = argv[0], argv[1:]
    handlers = {
        "add": cmd_add,
        "remove": cmd_remove,
        "list": cmd_list,
        "show": cmd_show,
    }
    handler = handlers.get(sub)
    if handler is None:
        print(f"unknown plugin subcommand: {sub}", file=sys.stderr)
        return 2
    return handler(rest)


__all__ = ["main"]
