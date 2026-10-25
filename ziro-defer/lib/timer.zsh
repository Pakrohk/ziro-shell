# lib/timer.zsh - High-resolution timer helpers.
# Per ARCHITECTURE S3.4. Uses zsh/datetime for microsecond precision.
# Zero loops, zero branches.

emulate -L zsh
zmodload zsh/datetime 2>/dev/null

_ziro_defer_lib_timer_start() {
  emulate -L zsh
  typeset -gF _ziro_defer_timer_t0=$EPOCHREALTIME
}

_ziro_defer_lib_timer_elapsed_ms() {
  emulate -L zsh
  local -F t1=$EPOCHREALTIME
  REPLY=$(( (t1 - _ziro_defer_timer_t0) * 1000.0 ))
}
