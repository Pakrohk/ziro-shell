# Deprecated Tests

Tests in this directory target legacy architecture (pre-Section-4):

- **test_local_source.py** — tests `_ziro_local_source` function which lived in
  `~/.ziro/integration.zsh`. In post-integration architecture (ADL-014),
  `integration.zsh` is a 4-line shim; local source functionality is not part of
  the live shell. If local plugin installation returns as a feature, rewrite
  these tests against the new path.
- **test_integration_sources_prompt_adapter** — removed from
  `test_install_generates_plugins.py`; it tested `integration.zsh` reading
  `prompt.conf`. Prompt config now flows through `load.toml` → `ziro-boot.zsh`.

Do not add new tests here. If functionality returns, write new tests in the
corresponding live test file.
