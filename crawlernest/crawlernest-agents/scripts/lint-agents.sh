#!/usr/bin/env bash

set -euo pipefail

REQUIRED_FRONTMATTER=("name" "description" "color")
RECOMMENDED_SECTIONS=("Identity" "Core Mission" "Critical Rules")

errors=0
warnings=0

lint_file() {
  local file="$1"

  if [[ ! -f "$file" ]]; then
    echo "ERROR $file: not found"
    errors=$((errors + 1))
    return
  fi

  if [[ "$(head -1 "$file")" != "---" ]]; then
    echo "ERROR $file: missing frontmatter opening ---"
    errors=$((errors + 1))
    return
  fi

  local frontmatter body field section word_count
  frontmatter=$(awk 'NR==1{next} /^---$/{exit} {print}' "$file")
  body=$(awk 'BEGIN{n=0} /^---$/{n++; next} n>=2{print}' "$file")

  for field in "${REQUIRED_FRONTMATTER[@]}"; do
    if ! echo "$frontmatter" | grep -qE "^${field}:"; then
      echo "ERROR $file: missing frontmatter field '${field}'"
      errors=$((errors + 1))
    fi
  done

  for section in "${RECOMMENDED_SECTIONS[@]}"; do
    if ! echo "$body" | grep -qi "$section"; then
      echo "WARN  $file: missing recommended section '${section}'"
      warnings=$((warnings + 1))
    fi
  done

  word_count=$(echo "$body" | wc -w | awk '{print $1}')
  if [[ "${word_count:-0}" -lt 50 ]]; then
    echo "WARN  $file: body seems very short (< 50 words)"
    warnings=$((warnings + 1))
  fi
}

files=()
if [[ $# -gt 0 ]]; then
  files=("$@")
else
  while IFS= read -r file; do
    files+=("$file")
  done < <(find agents -name "*.md" -type f | sort)
fi

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No agent files found."
  exit 1
fi

echo "Linting ${#files[@]} agent files..."
echo ""

for file in "${files[@]}"; do
  lint_file "$file"
done

echo ""
echo "Results: ${errors} error(s), ${warnings} warning(s) in ${#files[@]} files."

if [[ $errors -gt 0 ]]; then
  exit 1
fi
