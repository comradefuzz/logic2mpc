#!/bin/bash
# Обновляет BOARD.md после правки файла стори.
file=$(jq -r '.tool_input.file_path // empty')
case "$file" in
  */stories/S-*.md) python3 "$CLAUDE_PROJECT_DIR/scripts/board.py" ;;
esac
exit 0
