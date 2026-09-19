package clawer.review.controller;

import clawer.dto.ApiResponse;
import clawer.auth.jwt.AuthenticatedUser;
import clawer.review.dto.MappingReviewDecisionRequest;
import clawer.review.service.MappingReviewService;
import clawer.review.service.ReviewerAuthorization;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.Optional;

/**
 * Internal review of fuzzy entity-resolution matches.
 *
 * <p>Not an analytics endpoint, and deliberately not under /analytics: those
 * stay strictly read-only. The only thing written here is
 * warehouse.mapping_review, which the API owns outright. No pipeline table is
 * touched and no pipeline run is triggered.
 */
@RestController
@RequestMapping("/api/v1/admin/mapping-reviews")
public class MappingReviewController {

    private final MappingReviewService mappingReviewService;
    private final ReviewerAuthorization reviewerAuthorization;

    public MappingReviewController(
            MappingReviewService mappingReviewService,
            ReviewerAuthorization reviewerAuthorization) {
        this.mappingReviewService = mappingReviewService;
        this.reviewerAuthorization = reviewerAuthorization;
    }

    @GetMapping
    public ResponseEntity<?> list(
            @RequestParam(defaultValue = "pending") String status,
            @RequestParam(defaultValue = "50") int limit) {
        Optional<String> reviewer = resolveReviewer();
        if (reviewer.isEmpty()) {
            return forbidden();
        }
        Map<String, Object> payload = "decided".equalsIgnoreCase(status)
                ? mappingReviewService.listDecided(limit)
                : mappingReviewService.listPending(limit);
        return ResponseEntity.ok(ApiResponse.success(payload));
    }

    @GetMapping("/canonical-search")
    public ResponseEntity<?> searchCanonical(
            @RequestParam(name = "q", defaultValue = "") String query,
            @RequestParam(defaultValue = "20") int limit) {
        if (resolveReviewer().isEmpty()) {
            return forbidden();
        }
        return ResponseEntity.ok(
                ApiResponse.success(Map.of("items", mappingReviewService.searchCanonical(query, limit))));
    }

    @PostMapping
    public ResponseEntity<?> decide(
            @RequestBody(required = false) MappingReviewDecisionRequest request) {
        Optional<String> reviewer = resolveReviewer();
        if (reviewer.isEmpty()) {
            return forbidden();
        }
        String problem = mappingReviewService.validate(request);
        if (problem != null) {
            return ResponseEntity.badRequest()
                    .body(Map.of("success", false, "error", problem));
        }
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(mappingReviewService.save(request, reviewer.get())));
    }

    private Optional<String> resolveReviewer() {
        return AuthenticatedUser.current()
                .flatMap(user -> reviewerAuthorization.reviewerEmail(user.id()));
    }

    /**
     * One response for "not signed in", "not a reviewer" and "nobody is
     * configured as a reviewer", so the endpoint cannot be used to discover who
     * holds review rights.
     */
    private ResponseEntity<?> forbidden() {
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(Map.of(
                        "success", false,
                        "error", "Entity review is restricted to configured reviewers."));
    }
}
