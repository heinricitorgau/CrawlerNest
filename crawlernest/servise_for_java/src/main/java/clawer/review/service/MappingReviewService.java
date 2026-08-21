package clawer.review.service;

import clawer.review.dto.CanonicalOption;
import clawer.review.dto.MappingReviewCandidate;
import clawer.review.dto.MappingReviewDecisionRequest;
import clawer.review.repository.MappingReviewRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

@Service
public class MappingReviewService {

    public static final String CONFIRMED = "confirmed";
    public static final String REJECTED = "rejected";
    public static final String REMAPPED = "remapped";

    private static final Set<String> VALID_DECISIONS = Set.of(CONFIRMED, REJECTED, REMAPPED);

    private static final int MAX_LIMIT = 200;
    private static final int MAX_NOTE_LENGTH = 1000;

    /**
     * Disclosed on every response. A decision does not take effect when it is
     * saved, and saying so up front is the difference between a reviewer
     * trusting this screen and being misled by it.
     */
    private static final List<String> CAVEATS = List.of(
            "Decisions are stored, not applied. They take effect on the next source ingestion, when the pipeline reads them.",
            "Only fuzzy and fuzzy_review matches appear here. Exact and normalized matches are deterministic and are not offered for review.",
            "A rejection withdraws the source's rank from the matched university. Coverage and confidence may fall as a result, which is a correction, not a regression.",
            "Confidence levels remain derived from source count. A review decides whether a source counts, never how confident the result is.");

    private final MappingReviewRepository repository;

    public MappingReviewService(MappingReviewRepository repository) {
        this.repository = repository;
    }

    public Map<String, Object> listPending(int limit) {
        List<MappingReviewCandidate> items = repository.findPending(clampLimit(limit));
        return Map.of(
                "items", items,
                "totalPending", repository.countPending(),
                "caveats", CAVEATS);
    }

    public Map<String, Object> listDecided(int limit) {
        List<MappingReviewCandidate> items = repository.findDecided(clampLimit(limit));
        return Map.of(
                "items", items,
                "totalPending", repository.countPending(),
                "caveats", CAVEATS);
    }

    public List<CanonicalOption> searchCanonical(String query, int limit) {
        String trimmed = query == null ? "" : query.trim();
        if (trimmed.length() < 2) {
            return List.of();
        }
        return repository.searchCanonical(trimmed, clampLimit(limit));
    }

    /**
     * Validate and store one verdict.
     *
     * @return null when accepted, otherwise the reason to report back
     */
    public String validate(MappingReviewDecisionRequest request) {
        if (request == null) {
            return "Request body is required.";
        }
        if (request.rankingSourceId() == null) {
            return "rankingSourceId is required.";
        }
        if (request.sourceEntityId() == null || request.sourceEntityId().isBlank()) {
            return "sourceEntityId is required.";
        }
        String decision = normalizeDecision(request.decision());
        if (!VALID_DECISIONS.contains(decision)) {
            return "decision must be one of confirmed, rejected, remapped.";
        }
        if (REJECTED.equals(decision) && request.decidedCanonicalUniversityId() != null) {
            return "A rejection cannot name a canonical university.";
        }
        if (!REJECTED.equals(decision) && request.decidedCanonicalUniversityId() == null) {
            return "decidedCanonicalUniversityId is required for " + decision + ".";
        }
        if (request.note() != null && request.note().length() > MAX_NOTE_LENGTH) {
            return "note is too long. Limit is " + MAX_NOTE_LENGTH + " characters.";
        }
        if (!repository.mappingExists(request.rankingSourceId(), request.sourceEntityId())) {
            return "No such source mapping.";
        }
        if (request.decidedCanonicalUniversityId() != null
                && !repository.canonicalExists(request.decidedCanonicalUniversityId())) {
            return "No such canonical university.";
        }
        return null;
    }

    public Map<String, Object> save(MappingReviewDecisionRequest request, String reviewerEmail) {
        String decision = normalizeDecision(request.decision());
        int rows = repository.saveDecision(
                request.rankingSourceId(),
                request.sourceEntityId(),
                decision,
                request.decidedCanonicalUniversityId(),
                reviewerEmail,
                request.note());
        return Map.of(
                "stored", rows > 0,
                "decision", decision,
                "sourceEntityId", request.sourceEntityId(),
                "appliesOn", "next source ingestion",
                "caveats", CAVEATS);
    }

    private String normalizeDecision(String decision) {
        return decision == null ? "" : decision.trim().toLowerCase(Locale.ROOT);
    }

    private int clampLimit(int limit) {
        if (limit <= 0) {
            return 50;
        }
        return Math.min(limit, MAX_LIMIT);
    }
}
