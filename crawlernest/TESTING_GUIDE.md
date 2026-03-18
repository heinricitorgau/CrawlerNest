# Testing Guide for CrawlerNest Java Backend

This guide explains how to run tests for the Java backend service.

## 1. Java Unit Tests (JUnit 5)

We use JUnit 5 and Mockito for unit testing the Java services.

### Prerequisites
- Java 17+
- Maven (or use the provided `./mvnw` wrapper)

### Run Tests
To run all Java unit tests, execute the following command in the `servise_for_java` directory:

```bash
cd servise_for_java
./mvnw test
```

The tests are located in `src/test/java/clawer/`.

---

## 2. API Integration Tests (Python / Pytest)

We also have Python-based integration tests that verify the API endpoints from the outside.

### Prerequisites
- Python 3.9+
- `pytest` and `requests` libraries installed (`pip install pytest requests`)

### Run Tests
1. **Start the Java Service**:
   ```bash
   cd servise_for_java
   ./mvnw spring-boot:run
   ```

2. **Run Pytest**:
   In another terminal, go to the `crawlernest-tests` directory and run:
   ```bash
   cd crawlernest-tests
   pytest test_ranking_api.py
   ```

---

## 3. Project Structure Note

The Java source code has been consolidated into `servise_for_java/src/main/java/clawer` to follow the standard Maven project structure, enabling better IDE support and automated testing.
