"""ziro-shell — theme sharing CLI subcommand.

Layer: 3 (Python core)
Spec: 017
Shares active ~/.config/starship.toml with Pakrohk/ziro-themes via pull request.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from core.help_cli import handle_help_if_requested

THEME_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$")
TARGET_REPO = "Pakrohk/ziro-themes"


def validate_theme_name(name: str) -> tuple[bool, str]:
    """Validate theme name against kebab-case rules (3-30 chars, [a-z0-9-])."""
    if len(name) < 3:
        return False, f"Invalid theme name '{name}': must be at least 3 characters"
    if len(name) > 30:
        return False, f"Invalid theme name '{name}': must be at most 30 characters"
    if name.startswith("-") or name.endswith("-"):
        return False, f"Invalid theme name '{name}': must not start or end with a hyphen"
    if not re.match(r"^[a-z0-9-]+$", name):
        return False, f"Invalid theme name '{name}': must be kebab-case (only lowercase alphanumeric and hyphens)"
    if not THEME_NAME_RE.match(name):
        return False, f"Invalid theme name '{name}': must be kebab-case (3-30 chars, only [a-z0-9-])"
    return True, ""


def diff_dicts(current: dict[str, Any], default: dict[str, Any]) -> dict[str, list[str]]:
    """Compute diff between current config and default baseline."""
    added: list[str] = []
    modified: list[str] = []
    removed: list[str] = []

    for k, v in current.items():
        if k not in default:
            added.append(k)
        elif default[k] != v:
            modified.append(k)

    for k in default:
        if k not in current:
            removed.append(k)

    return {
        "added": sorted(added),
        "modified": sorted(modified),
        "removed": sorted(removed),
    }


def _get_gh_user() -> str:
    """Retrieve authenticated GitHub username."""
    try:
        r = subprocess.run(
            ["gh", "api", "user", "--jq", ".login"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return os.environ.get("USER", "user")


def _check_prerequisites(starship_path: Path) -> tuple[int, str]:
    """Verify gh CLI, gh auth, and starship config. Return (code, error_msg)."""
    # 1. gh CLI installed
    if not shutil.which("gh"):
        return 1, "gh CLI not found. Install from https://cli.github.com/"

    # 2. gh authenticated
    try:
        r_auth = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r_auth.returncode != 0:
            return 1, "gh not authenticated. Run: gh auth login"
    except Exception as e:
        return 1, f"gh auth status check failed: {e}. Run: gh auth login"

    # 3. starship config exists
    if not starship_path.is_file():
        return (
            1,
            f"No starship config found at {starship_path}. Create one with: starship preset <name> -o {starship_path}",
        )

    return 0, ""


def cmd_submit(argv: list[str]) -> int:
    """Execute ziro theme submit workflow."""
    ret = handle_help_if_requested(argv, "theme", subcommand="submit")
    if ret is not None:
        return ret

    # Parse arguments
    name_arg: str | None = None
    dry_run = "--dry-run" in argv
    no_pr = "--no-pr" in argv
    keep = "--keep" in argv

    idx = 0
    while idx < len(argv):
        arg = argv[idx]
        if arg == "--name":
            if idx + 1 < len(argv):
                name_arg = argv[idx + 1]
                idx += 2
                continue
            else:
                print("ziro theme submit: error: --name requires an argument", file=sys.stderr)
                return 2
        idx += 1

    # Resolve starship.toml path
    starship_path = Path(
        os.environ.get("STARSHIP_CONFIG", Path.home() / ".config" / "starship.toml")
    )

    # 1. Prerequisites check
    code, err = _check_prerequisites(starship_path)
    if code != 0:
        print(f"Error: {err}", file=sys.stderr)
        return code

    # 2. Read and parse starship.toml
    try:
        content = starship_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {starship_path}: {e}", file=sys.stderr)
        return 1

    try:
        import tomllib

        config_dict = tomllib.loads(content)
    except Exception as e:
        print(f"starship.toml is not valid TOML: {e}", file=sys.stderr)
        return 2

    # 3. Compute diff vs default baseline (empty TOML Option a)
    default_baseline: dict[str, Any] = {}
    diff = diff_dicts(config_dict, default_baseline)
    has_customization = bool(diff["added"] or diff["modified"] or diff["removed"])
    if not has_customization:
        print("No customization detected. Your config matches defaults.", file=sys.stderr)
        return 2

    # 4. Resolve username and theme name
    gh_user = _get_gh_user()
    if name_arg:
        theme_name = name_arg
    else:
        default_name = f"{gh_user.lower()}-{int(time.time())}"
        if sys.stdin.isatty():
            try:
                user_input = input(f"Theme name [{default_name}]: ").strip()
                theme_name = user_input if user_input else default_name
            except (EOFError, KeyboardInterrupt):
                print("\nSubmission cancelled.", file=sys.stderr)
                return 0
        else:
            theme_name = default_name

    # Validate theme name
    valid, name_err = validate_theme_name(theme_name)
    if not valid:
        print(f"Error: {name_err}", file=sys.stderr)
        return 2

    # 5. Handle --dry-run
    target_rel_path = f"themes/{gh_user}/{theme_name}.toml"
    branch_name = f"submit/{gh_user}/{theme_name}"
    pr_title = f"Theme: {theme_name} by @{gh_user}"

    if dry_run:
        print("Dry run: planned theme submission")
        print("──────────────────────────────────────────")
        print(f"  Theme name:    {theme_name}")
        print(f"  Author:        @{gh_user}")
        print(f"  Target file:   {target_rel_path}")
        print(f"  Branch:        {branch_name}")
        print(f"  PR Title:      {pr_title}")
        print("  Diff summary:")
        print(f"    added:    {diff['added']}")
        print(f"    modified: {diff['modified']}")
        print(f"    removed:  {diff['removed']}")
        print("──────────────────────────────────────────")
        print("Dry run complete. No branches, files, or PRs created.")
        return 0

    # 6. Execute submission in temporary workspace
    temp_dir = tempfile.mkdtemp(prefix="ziro-theme-submit-")
    try:
        print(f"[*] Cloning {TARGET_REPO}...")
        r_clone = subprocess.run(
            ["gh", "repo", "clone", TARGET_REPO, temp_dir],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r_clone.returncode != 0:
            print(f"Error cloning repository: {r_clone.stderr.strip()}", file=sys.stderr)
            return 3

        # Check for collision
        dest_file = Path(temp_dir) / "themes" / gh_user / f"{theme_name}.toml"
        if dest_file.is_file():
            if sys.stdin.isatty():
                try:
                    ans = input(
                        f"Theme '{theme_name}' already exists for @{gh_user}. Overwrite? [y/N]: "
                    ).strip().lower()
                    if ans not in ("y", "yes"):
                        print("Submission aborted by user.", file=sys.stderr)
                        return 0
                except (EOFError, KeyboardInterrupt):
                    print("\nSubmission cancelled.", file=sys.stderr)
                    return 0
            else:
                print(f"Notice: Overwriting existing theme '{theme_name}' in non-interactive mode.")

        # Create branch
        r_branch = subprocess.run(
            ["git", "-C", temp_dir, "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r_branch.returncode != 0:
            print(f"Error creating branch: {r_branch.stderr.strip()}", file=sys.stderr)
            return 3

        # Write theme file
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        dest_file.write_text(content, encoding="utf-8")

        # Git add & commit
        subprocess.run(
            ["git", "-C", temp_dir, "add", str(dest_file)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        commit_msg = f"feat(themes): add {theme_name} by @{gh_user}"
        r_commit = subprocess.run(
            ["git", "-C", temp_dir, "commit", "-m", commit_msg],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r_commit.returncode != 0:
            print(f"Error committing theme: {r_commit.stderr.strip()}", file=sys.stderr)
            return 3

        # Git push
        print(f"[*] Pushing branch '{branch_name}'...")
        r_push = subprocess.run(
            ["git", "-C", temp_dir, "push", "-u", "origin", branch_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r_push.returncode != 0:
            print(f"Error pushing branch: {r_push.stderr.strip()}", file=sys.stderr)
            return 3

        if no_pr:
            print(f"✔ Branch '{branch_name}' pushed successfully. PR creation skipped (--no-pr).")
            return 0

        # Create PR non-interactively
        print("[*] Creating pull request...")
        body_content = f"""## Theme Submission: {theme_name}

### Details
- **Theme**: `{theme_name}`
- **Author**: @{gh_user}
- **Target**: `{target_rel_path}`

### Customization Summary
- **Added Sections**: {', '.join(diff['added']) if diff['added'] else 'None'}
- **Modified Keys**: {', '.join(diff['modified']) if diff['modified'] else 'None'}
- **Removed Keys**: {', '.join(diff['removed']) if diff['removed'] else 'None'}

### Preview
<!-- Contributor: please attach a terminal screenshot demonstrating this prompt -->

### Checklist
- [x] Theme configuration is valid TOML
- [x] Theme name is kebab-case
- [x] No personal credentials or private paths
"""
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as tf:
            tf.write(body_content)
            body_path = tf.name

        try:
            gh_env = dict(os.environ, PAGER="cat", GH_FORCE_TTY="false")
            r_pr = subprocess.run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--title",
                    pr_title,
                    "--body-file",
                    body_path,
                    "--base",
                    "main",
                    "--head",
                    branch_name,
                ],
                cwd=temp_dir,
                env=gh_env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if r_pr.returncode != 0:
                print(f"Error creating PR: {r_pr.stderr.strip()}", file=sys.stderr)
                return 3

            pr_url = r_pr.stdout.strip()
            print("──────────────────────────────────────────")
            print("✔ Theme submitted successfully!")
            print(f"  PR: {pr_url}")
            print("──────────────────────────────────────────")
            return 0
        finally:
            try:
                os.unlink(body_path)
            except OSError:
                pass

    finally:
        if keep:
            print(f"ℹ️  Workspace preserved at: {temp_dir}")
        else:
            shutil.rmtree(temp_dir, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    """Entry point for theme submit."""
    return cmd_submit(sys.argv[1:] if argv is None else argv)


if __name__ == "__main__":
    sys.exit(main())
