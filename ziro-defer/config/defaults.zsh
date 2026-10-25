# config/defaults.zsh - Compiled default configuration values.
# Per ARCHITECTURE S3.3 and RULES R13.3. Overridden by ~/.config/ziro/defer.conf.

emulate -L zsh

# ─── [behavior] ───
typeset -g _ZIRO_DEFER_DEFAULT_STAGE=5
typeset -g _ZIRO_DEFER_DEFAULT_SLOT="b"
typeset -g _ZIRO_DEFER_DEFAULT_TIMEOUT_MS=5000
typeset -g _ZIRO_DEFER_BATCH_SIZE_LIMIT=50
typeset -g _ZIRO_DEFER_INTERACTIVE_TIMEOUT_PROMPT="true"
typeset -g _ZIRO_DEFER_SHOW_PROGRESS_MESSAGE="true"
typeset -g _ZIRO_DEFER_RETRY_ON_FAILURE="false"
typeset -g _ZIRO_DEFER_MAX_RETRIES="0"
typeset -g _ZIRO_DEFER_EAGER_FALLBACK="true"
typeset -g _ZIRO_DEFER_SUPPRESS_WARNINGS="false"

# ─── [idle] ───
typeset -g _ZIRO_DEFER_IDLE_THRESHOLD=5

# ─── [stages.N].budget_ms ───
typeset -gA _ZIRO_DEFER_STAGE_BUDGET_MS=(
  0 0.1
  1 0.5
  2 1.0
  3 2.0
  4 1.0
)

# ─── [stages.4] prompt cache ───
typeset -g _ZIRO_DEFER_PROMPT_CACHE_MODE="fast"
typeset -g _ZIRO_DEFER_PROMPT_CMD="starship"

# ─── Stage 2 completion paths (configurable via defer.conf) ───
typeset -ga _ZIRO_DEFER_COMPLETION_PATHS=()

# ─── [cache.eval_output] ───
typeset -g _ZIRO_DEFER_EVAL_CACHE_ENABLED="true"
typeset -g _ZIRO_DEFER_EVAL_CACHE_TTL=0

# ─── [cache.project_markers] ───
typeset -g _ZIRO_DEFER_MARKER_CACHE_ENABLED="true"
typeset -g _ZIRO_DEFER_MARKER_CACHE_TTL=3600

# ─── [metrics] ───
typeset -g _ZIRO_DEFER_METRICS_ENABLED="true"
typeset -g _ZIRO_DEFER_METRICS_MAX_SIZE_KB=1024

# ─── Load user config (overrides defaults) ───
_ziro_defer_load_config() {
  emulate -L zsh
  local config_file="${XDG_CONFIG_HOME:-$HOME/.config}/ziro/defer.conf"
  [[ -r "$config_file" ]] || return 0

  # @O(1)-justified: single key reads, no loop. Each is a scan of one file.
  _ziro_defer_lib_toml_get "$config_file" "behavior" "default_stage" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_DEFAULT_STAGE="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "behavior" "default_slot" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_DEFAULT_SLOT="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "behavior" "default_timeout_ms" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_DEFAULT_TIMEOUT_MS="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "behavior" "batch_size_limit" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_BATCH_SIZE_LIMIT="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "behavior" "interactive_timeout_prompt" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_INTERACTIVE_TIMEOUT_PROMPT="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "behavior" "show_progress_message" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_SHOW_PROGRESS_MESSAGE="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "idle" "threshold_seconds" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_IDLE_THRESHOLD="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "stages.4" "prompt_cache_mode" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_PROMPT_CACHE_MODE="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "fallback" "retry_on_failure" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_RETRY_ON_FAILURE="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "fallback" "max_retries" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_MAX_RETRIES="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "fallback" "eager_fallback" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_EAGER_FALLBACK="$REPLY"

  _ziro_defer_lib_toml_get "$config_file" "fallback" "suppress_warnings" ""
  [[ -n "$REPLY" ]] && _ZIRO_DEFER_SUPPRESS_WARNINGS="$REPLY"

  return 0
}

_ziro_defer_load_config
