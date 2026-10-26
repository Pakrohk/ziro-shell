"""Ziro-shell repository constants.

All URLs and repo references SHOULD use these constants
to make future org migrations trivial.
"""

GITHUB_USER = "Pakrohk"
REPO_NAME = "ziro-shell"
VERSION = "1.2.0"
REPO_URL = f"https://github.com/{GITHUB_USER}/{REPO_NAME}"
REPO_GIT_URL = f"{REPO_URL}.git"
REPO_SSH_URL = f"git@github.com:{GITHUB_USER}/{REPO_NAME}.git"
REMOTE_HINT = f"{GITHUB_USER}/{REPO_NAME}"

# Plugin repos (future)
GHOST_REPO = f"https://github.com/{GITHUB_USER}/ziro-ghost"
THEMES_REPO = f"https://github.com/{GITHUB_USER}/ziro-themes"
PF_REPO = f"https://github.com/{GITHUB_USER}/ziro-pf"
