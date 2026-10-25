# Deprecated: Ziro Shell now uses ~/.config/ziro/boot.zsh directly.
# This shim is kept for backward compatibility with older .zshrc files.
# It is safe to remove once your .zshrc sources boot.zsh directly.
source ~/.config/ziro/boot.zsh 2>/dev/null || true
