package clawer.api;

import clawer.dto.ApiResponse;
import clawer.service.FreshnessService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/freshness")
public class FreshnessController {
    private final FreshnessService freshnessService;

    public FreshnessController(FreshnessService freshnessService) {
        this.freshnessService = freshnessService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<Map<String, Object>>> getFreshness() {
        return ResponseEntity.ok(ApiResponse.success(freshnessService.getFreshness()));
    }
}
