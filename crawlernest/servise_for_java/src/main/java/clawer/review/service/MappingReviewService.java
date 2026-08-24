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
import java.util.stream.Stream;

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

    /**
     * Added to the decided list only.
     *
     * <p>A decided entry describes the pair as it stood at review time, because
     * that snapshot is what the verdict was passed on. The live mapping row has
     * usually been rewritten since -- that rewrite is the decision taking
     * effect -- so saying the list is historical is the difference between a
     * reviewer reading it as an audit trail and mistaking it for current state.
     */
    private static final List<String> DECIDED_CAVEATS = Stream.concat(
            CAVEATS.stream(),
            Stream.of("Each entry shows the match as it stood when it was reviewed, not as it stands now. Applying a decision rewrites or retires the mapping row it was made about."))
            .toList();

    private final MappingReviewRepository repository;

    public MappingReviewService(MappingReviewRepository repository) {
        this.repository = repository;
    }

    public Map<String, Object> listPending(int limit) {
        return Map.of(
                "items", repository.findPending(clampLimit(limit)),
                "totalPending", repository.countPending(),
                "totalDecided", repository.countDecided(),
                "caveats", CAVEATS);
    }

    /**
     * Verdicts already on record, newest first.
     *
     * <p>Both totals are reported here as well as on the pending list, so the
     * screen can label either tab without having to fetch the other one.
     */
    public Map<String, Object> listDecided(int limit) {
        return Map.of(
                "items", repository.findDecided(clampLimit(limit)),
                "totalPending", repository.countPending(),
                "totalDecided", repository.countDecided(),
                "caveats", DECIDED_CAVEATS);
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
