# core/version.zsh - Single source of truth for version metadata.
# Per ARCHITECTURE S3.1: exports ZIRO_DEFER_VERSION and ZIRO_DEFER_NAME.

emulate -L zsh

typeset -g ZIRO_DEFER_VERSION="2.0.0"
typeset -g ZIRO_DEFER_NAME="ziro-defer"
typeset -g ZIRO_DEFER_COMPAT_ZIRO=">=1.3.0"
typeset -g ZIRO_DEFER_COMPAT_ZSH=">=5.8"
