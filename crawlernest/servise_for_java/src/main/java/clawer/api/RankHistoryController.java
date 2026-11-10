package clawer.api;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import clawer.dto.ApiResponse;
import clawer.service.RankHistoryService;

/**
 * GET /api/v1/universities/{id}/rank-history -- read-only.
 *
 * <p>Its own controller so the university controller's test slice does not need another mock.
 */
@RestController
@RequestMapping("/api/v1/universities")
public class RankHistoryController {

    private final RankHistoryService rankHistoryService;

    public RankHistoryController(RankHistoryService rankHistoryService) {
        this.rankHistoryService = rankHistoryService;
    }

    /**
     * Each source's printed rank for every held edition, every gap labelled as an edition this warehouse
     * does not hold or one that does not include the university here. {@code data.caveats} is always present.
     */
    @GetMapping("/{id}/rank-history")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getRankHistory(@PathVariable Long id) {
        Map<String, Object> history = rankHistoryService.history(id);
        return history == null ? ResponseEntity.notFound().build() : ResponseEntity.ok(ApiResponse.success(history));
    }
}
