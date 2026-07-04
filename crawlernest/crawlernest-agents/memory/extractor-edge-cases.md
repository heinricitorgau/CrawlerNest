# Extractor Edge Cases

## Format

### [Case Name]
- Source:
- Problem:
- Example Input:
- Expected Output:
- Fix:

---

### Example: missing IELTS field

- Source:
  - university page
- Problem:
  - IELTS sometimes omitted
- Example Input:
  - "English requirement: TOEFL 90"
- Expected Output:
  - IELTS = null
- Fix:
  - allow missing optional fields