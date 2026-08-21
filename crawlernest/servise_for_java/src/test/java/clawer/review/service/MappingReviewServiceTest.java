package clawer.review.service;

import clawer.review.dto.MappingReviewDecisionRequest;
import clawer.review.repository.MappingReviewRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class MappingReviewServiceTest {

    @Mock
    private MappingReviewRepository repository;

    private MappingReviewService service;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        service = new MappingReviewService(repository);
        when(repository.mappingExists(anyInt(), anyString())).thenReturn(true);
        when(repository.canonicalExists(anyLong())).thenReturn(true);
    }

    private MappingReviewDecisionRequest request(
            String decision, Long decidedCanonicalUniversityId) {
        return new MappingReviewDecisionRequest(402, "846", decision, decidedCanonicalUniversityId, null);
    }

    // ─── Accepted verdicts ────────────────────────────────────────────────────

    @Test
    void rejectionNeedsNoTarget() {
        assertNull(service.validate(request("rejected", null)));
    }

    @Test
    void confirmationNeedsATarget() {
        assertNull(service.validate(request("confirmed", 260L)));
    }

    @Test
    void remapNeedsATarget() {
        assertNull(service.validate(request("remapped", 777L)));
    }

    @Test
    void decisionIsCaseAndWhitespaceInsensitive() {
        assertNull(service.validate(request("  REJECTED ", null)));
    }

    // ─── Refused verdicts ─────────────────────────────────────────────────────

    @Test
    void aRejectionMayNotNameAUniversity() {
        // Otherwise the row would violate ck_mapping_review_target and the
        // failure would surface as a 500 rather than a readable message.
        assertNotNull(service.validate(request("rejected", 260L)));
    }

    @Test
    void aConfirmationWithoutATargetIsRefused() {
        assertNotNull(service.validate(request("confirmed", null)));
    }

    @Test
    void anUnknownDecisionIsRefused() {
        assertNotNull(service.validate(request("maybe", 260L)));
    }

    @Test
    void aMissingMappingIsRefused() {
        when(repository.mappingExists(anyInt(), anyString())).thenReturn(false);
        assertNotNull(service.validate(request("rejected", null)));
    }

    @Test
    void anUnknownCanonicalUniversityIsRefused() {
        when(repository.canonicalExists(anyLong())).thenReturn(false);
        assertNotNull(service.validate(request("remapped", 999999L)));
    }

    @Test
    void missingIdentityIsRefused() {
        assertNotNull(service.validate(
                new MappingReviewDecisionRequest(null, "846", "rejected", null, null)));
        assertNotNull(service.validate(
                new MappingReviewDecisionRequest(402, " ", "rejected", null, null)));
        assertNotNull(service.validate(null));
    }

    @Test
    void anOverlongNoteIsRefused() {
        String note = "x".repeat(1001);
        assertNotNull(service.validate(
                new MappingReviewDecisionRequest(402, "846", "rejected", null, note)));
    }

    // ─── Storage ──────────────────────────────────────────────────────────────

    @Test
    void savingNormalizesTheDecisionAndRecordsTheReviewer() {
        when(repository.saveDecision(
                anyInt(), anyString(), anyString(), isNull(), anyString(), isNull()))
                .thenReturn(1);

        Map<String, Object> result = service.save(
                new MappingReviewDecisionRequest(402, "846", " Rejected ", null, null),
                "reviewer@example.test");

        verify(repository).saveDecision(
                eq(402), eq("846"), eq("rejected"), isNull(), eq("reviewer@example.test"), isNull());
        assertEquals(Boolean.TRUE, result.get("stored"));
        assertEquals("rejected", result.get("decision"));
    }

    @Test
    void everyResponseDisclosesThatDecisionsAreNotYetApplied() {
        // The screen would otherwise imply the warehouse changed on save, when
        // nothing changes until the next ingestion reads the decision.
        when(repository.saveDecision(
                anyInt(), anyString(), anyString(), isNull(), anyString(), isNull()))
                .thenReturn(1);
        when(repository.findPending(anyInt())).thenReturn(List.of());
        when(repository.countPending()).thenReturn(0);

        Object savedCaveats = service.save(request("rejected", null), "reviewer@example.test")
                .get("caveats");
        Object listedCaveats = service.listPending(10).get("caveats");

        for (Object caveats : List.of(savedCaveats, listedCaveats)) {
            assertTrue(caveats instanceof List<?>);
            assertTrue(((List<?>) caveats).stream()
                    .anyMatch(text -> String.valueOf(text).contains("next source ingestion")));
        }
    }

    // ─── Query guards ─────────────────────────────────────────────────────────

    @Test
    void aShortCanonicalSearchReturnsNothingRatherThanEverything() {
        assertEquals(List.of(), service.searchCanonical("a", 20));
        assertEquals(List.of(), service.searchCanonical(null, 20));
    }

    @Test
    void theListLimitIsClamped() {
        when(repository.findPending(anyInt())).thenReturn(List.of());
        when(repository.countPending()).thenReturn(0);

        service.listPending(100000);
        verify(repository).findPending(200);

        service.listPending(0);
        verify(repository).findPending(50);
    }
}
