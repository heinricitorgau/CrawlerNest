package clawer.repository;

import clawer.model.University;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Repository for accessing University data.
 * Simulates database access (to be replaced with SQLite JDBC/JPA access).
 */
@Repository
public class UniversityRepository {
    
    // Simulated database table
    private final List<University> universities = new ArrayList<>();

    public UniversityRepository() {
        // Mock data initialization
        universities.add(new University("u1", "Tech University", "USA", 1, "Computer Science", 95.0, 50000.0));
        universities.add(new University("u2", "Global Institute", "UK", 10, "Engineering", 88.0, 45000.0));
        universities.add(new University("u3", "State College", "USA", 50, "Business", 75.0, 20000.0));
    }

    public List<University> findAll() {
        return new ArrayList<>(universities);
    }

    public Optional<University> findById(String id) {
        return universities.stream()
                .filter(u -> u.getId().equals(id))
                .findFirst();
    }
}
