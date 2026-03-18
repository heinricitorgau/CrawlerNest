package clawer.service;

import clawer.model.Ranking;
import clawer.model.RecommendationResult;
import clawer.model.University;
import clawer.repository.UniversityRepository;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Service for generating University recommendations based on scoring logic.
 */
@Service
public class RecommendationService {

    private final UniversityRepository universityRepository;

    public RecommendationService(UniversityRepository universityRepository) {
        this.universityRepository = universityRepository;
    }

    /**
     * Generates a list of recommended universities based on preferred subject and the student's admission score.
     * Score calculation algorithm:
     * score = ranking_weight + subject_match + admission_probability
     */
    public List<RecommendationResult> getRecommendations(String preferredSubject, Double studentScore) {
        List<University> allUniversities = universityRepository.findAll();
        List<RecommendationResult> results = new ArrayList<>();

        for (University u : allUniversities) {
            double score = calculateScore(u, preferredSubject, studentScore);
            
            // Only recommend if they have a decent score (e.g. > 0 context match)
            if (score > 10.0) {
                String rationale = String.format("Calculated match score of %.2f based on ranking, subject, and score probability.", score);
                results.add(new RecommendationResult(u, score, rationale));
            }
        }

        // Sort descending by match score
        return results.stream()
                .sorted(Comparator.comparing(RecommendationResult::getMatchScore).reversed())
                .collect(Collectors.toList());
    }

    private double calculateScore(University university, String preferredSubject, Double studentScore) {
        double subjectMatch = 0.0;
        if (preferredSubject != null && university.getPrograms() != null) {
            boolean hasProgram = university.getPrograms().stream()
                .anyMatch(p -> p.getProgramName().equalsIgnoreCase(preferredSubject) || 
                               (p.getStudyField() != null && p.getStudyField().equalsIgnoreCase(preferredSubject)));
            if (hasProgram) {
                subjectMatch = 50.0;
            }
        }

        double rankingWeight = 0.0;
        if (university.getRankings() != null && !university.getRankings().isEmpty()) {
            // Use the best rank found across all records
            Integer bestRank = university.getRankings().stream()
                .map(Ranking::getRankStart)
                .filter(r -> r != null && r > 0)
                .min(Integer::compare)
                .orElse(null);
                
            if (bestRank != null) {
                rankingWeight = Math.max(0, 30.0 - (bestRank * 0.2));
            }
        }

        // Simplifying admission probability for now as we don't scale it per program here yet
        double admissionProbability = 0.0;
        // In a real scenario, we'd check AdmissionRequirement table
        // For baseline mature connection, we'll give a static boost if a studentScore is provided
        if (studentScore != null && studentScore > 80.0) {
            admissionProbability = 20.0;
        }

        return rankingWeight + subjectMatch + admissionProbability;
    }
}
