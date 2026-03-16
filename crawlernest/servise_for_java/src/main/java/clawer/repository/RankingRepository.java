package clawer.repository;

import clawer.model.Ranking;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Repository for accessing Ranking data.
 * Simulates database access (to be replaced with SQLite JDBC/JPA access).
 */
@Repository
public class RankingRepository {
    
    // Simulated database table
    private final List<Ranking> rankings = new ArrayList<>();

    public RankingRepository() {
        // Mock data initialization
        rankings.add(new Ranking("u1", "qs", 1, 2026));
        rankings.add(new Ranking("u2", "qs", 15, 2026));
        rankings.add(new Ranking("u1", "arwu", 3, 2026));
    }

    public List<Ranking> findAll() {
        return new ArrayList<>(rankings);
    }

    public List<Ranking> findBySource(String source) {
        return rankings.stream()
                .filter(r -> r.getRankingSource().equalsIgnoreCase(source))
                .collect(Collectors.toList());
    }
    
    public List<Ranking> findByUniversityId(String universityId) {
        return rankings.stream()
                .filter(r -> r.getUniversityId().equals(universityId))
                .collect(Collectors.toList());
    }
}
