package clawer.service;

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
        if (preferredSubject != null && preferredSubject.equalsIgnoreCase(university.getSubject())) {
            subjectMatch = 50.0; // Strong weight for exact subject match
        }

        double rankingWeight = 0.0;
        if (university.getRanking() != null) {
            // Higher rank (lower number) yields higher weight. Max 30 points.
            rankingWeight = Math.max(0, 30.0 - (university.getRanking() * 0.2));
        }

        double admissionProbability = 0.0;
        if (studentScore != null && university.getAdmissionScore() != null) {
            // Difference between student score and required score
            double diff = studentScore - university.getAdmissionScore();
            if (diff >= 0) {
                admissionProbability = 20.0; // High probability
            } else if (diff >= -5.0) {
                admissionProbability = 10.0; // Borderline
            } else {
                admissionProbability = 0.0; // Out of reach
            }
        }

        return rankingWeight + subjectMatch + admissionProbability;
    }
}
