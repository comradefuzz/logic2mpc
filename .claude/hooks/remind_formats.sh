#!/bin/bash
# Напоминает оформить реквест, если правка в spikes/ дала новое знание о формате.
file=$(jq -r '.tool_input.file_path // empty')
case "$file" in
  */spikes/*.py)
    jq -n '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: "Правка в spikes/: если она дала новое знание о формате или расхождение с docs/formats, создай реквест в requests/ своей базы сразу, до продолжения работы."}}'
    ;;
esac
exit 0
