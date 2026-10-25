# lib/json-writer.zsh - Pure-Zsh JSONL record generator.
# Per ARCHITECTURE S3.4 and RULES R10.2 + R17.4.
# Zero loops. Uses native parameter expansion for escaping.

emulate -L zsh

_ziro_defer_lib_json_escape() {
  emulate -L zsh
  local s="$1"
  # Sequential parameter expansions (no loop, no fork).
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  REPLY="$s"
}

_ziro_defer_lib_json_record() {
  emulate -L zsh
  local ts="$1" task="$2" name="$3" stage="$4" slot="$5"
  local elapsed="$6" task_status="$7" cached="$8" retries="$9"

  # Single short-circuit (not if) for truncation
  (( ${#task} > 200 )) && task="${task[1,200]}"

  local task_esc name_esc status_esc
  _ziro_defer_lib_json_escape "$task"; task_esc="$REPLY"
  _ziro_defer_lib_json_escape "$name"; name_esc="$REPLY"
  _ziro_defer_lib_json_escape "$task_status"; status_esc="$REPLY"

  local elapsed_fmt
  printf -v elapsed_fmt "%.2f" "$elapsed"

  REPLY="{\"ts\":${ts},\"task\":\"${task_esc}\",\"name\":\"${name_esc}\",\"stage\":${stage},\"slot\":\"${slot}\",\"elapsed_ms\":${elapsed_fmt},\"status\":\"${status_esc}\",\"cached\":${cached},\"retries\":${retries}}"
}
