package clawer.api;

import clawer.dto.ApiResponse;
import clawer.service.OperationalStatusService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/diagnostics/operational-status")
public class OperationalStatusController {

    private final OperationalStatusService operationalStatusService;

    public OperationalStatusController(OperationalStatusService operationalStatusService) {
        this.operationalStatusService = operationalStatusService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<Map<String, Object>>> getOperationalStatus() {
        return ResponseEntity.ok(ApiResponse.success(operationalStatusService.getOperationalStatus()));
    }
}
