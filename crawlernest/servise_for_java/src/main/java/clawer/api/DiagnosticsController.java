package clawer.api;

import clawer.dto.ApiResponse;
import clawer.service.DiagnosticsService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/diagnostics")
public class DiagnosticsController {
    private final DiagnosticsService diagnosticsService;

    public DiagnosticsController(DiagnosticsService diagnosticsService) {
        this.diagnosticsService = diagnosticsService;
    }

    @GetMapping("/rankings")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getRankingsDiagnostics() {
        return ResponseEntity.ok(ApiResponse.success(diagnosticsService.getRankingsDiagnostics()));
    }

    @GetMapping("/subjects")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getSubjectsDiagnostics() {
        return ResponseEntity.ok(ApiResponse.success(diagnosticsService.getSubjectsDiagnostics()));
    }
}
