#!/usr/bin/env bash

set -euo pipefail

changed="$(git diff --cached --name-only --diff-filter=ACMR || true)"

code_changed=false
docs_changed=false

if echo "$changed" | grep -Eq '^(agents/|scripts/|templates/)'; then
  code_changed=true
fi

if echo "$changed" | grep -Eq '^(README\.md|docs/|CONTRIBUTING\.md|AGENT_SELECTION\.md|DEV_PLAYBOOK\.md|AGENT_PROMPT_LIBRARY\.md)'; then
  docs_changed=true
fi

if [[ "$code_changed" == true && "$docs_changed" == false ]]; then
  echo "[doc-drift] Code or system files changed but docs did not."
  echo "[doc-drift] Check whether README / playbook / selection guide should be updated."
fi
