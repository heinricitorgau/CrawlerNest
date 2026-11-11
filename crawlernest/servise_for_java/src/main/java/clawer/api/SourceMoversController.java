package clawer.api;

import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import clawer.dto.ApiResponse;
import clawer.service.SourceMoversService;

/**
 * GET /api/v1/analytics/source-movers?source=THE&year=2026&limit=20 -- read-only.
 *
 * <p>The largest exact rank movements of one source between an edition and the held edition before it. Its own
 * controller so the analytics controller's test slice needs no new mock. {@code data.caveats} is always present.
 */
@RestController
@RequestMapping("/api/v1/analytics")
public class SourceMoversController {

    private final SourceMoversService moversService;

    public SourceMoversController(SourceMoversService moversService) {
        this.moversService = moversService;
    }

    @GetMapping("/source-movers")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getSourceMovers(
            @RequestParam String source,
            @RequestParam(name = "year", required = false) Integer year,
            @RequestParam(name = "limit", required = false) Integer limit
    ) {
        try {
            return ResponseEntity.ok(ApiResponse.success(moversService.movers(source, year, limit)));
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage(), ex);
        }
    }
}
