# Database Decisions

## Format

### [Decision Title]
- Context:
- Options:
- Decision:
- Consequences:

---

### Example: use composite key for rankings

- Context:
  - ranking uniqueness unclear
- Options:
  - single ID
  - composite (year + source + university)
- Decision:
  - composite key
- Consequences:
  - more complex queries
  - but prevents duplication