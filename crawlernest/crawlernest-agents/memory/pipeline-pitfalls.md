# Pipeline Pitfalls

## Format

### [Pitfall Name]
- Stage:
- Description:
- Failure Mode:
- Detection:
- Mitigation:

---

### Example: partial write before failure

- Stage:
  - db_writer
- Description:
  - pipeline crashes after partial insert
- Failure Mode:
  - duplicated or inconsistent data
- Detection:
  - mismatch in record counts
- Mitigation:
  - use transaction or checkpoint