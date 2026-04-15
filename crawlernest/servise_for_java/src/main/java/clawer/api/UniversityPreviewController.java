package clawer.api;

import clawer.dto.ApiResponse;
import clawer.dto.CanonicalUniversityDetailPreviewDTO;
import clawer.service.UniversityPreviewService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/preview/universities")
public class UniversityPreviewController {
    private final UniversityPreviewService universityPreviewService;

    public UniversityPreviewController(UniversityPreviewService universityPreviewService) {
        this.universityPreviewService = universityPreviewService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<Object>> getUniversityPreview(
            @RequestParam(required = false) Long canonicalUniversityId,
            @RequestParam(required = false) String universityName
    ) {
        if (canonicalUniversityId == null && (universityName == null || universityName.isBlank())) {
            return ResponseEntity.badRequest().body(errorResponse("canonicalUniversityId or universityName is required."));
        }

        try {
            Optional<CanonicalUniversityDetailPreviewDTO> preview = universityPreviewService.getPreview(canonicalUniversityId, universityName);
            if (preview.isEmpty()) {
                return ResponseEntity.status(404).body(errorResponse("University preview not found."));
            }

            Map<String, Object> metadata = new LinkedHashMap<>();
            metadata.put("timestamp", Instant.now().toString());
            metadata.put("mode", "preview");
            metadata.put("lookup", canonicalUniversityId != null ? "canonicalUniversityId" : "universityName");

            return ResponseEntity.ok(ApiResponse.success(preview.get(), metadata));
        } catch (Exception ex) {
            return ResponseEntity.internalServerError().body(errorResponse("University preview failed."));
        }
    }

    private ApiResponse<Object> errorResponse(String errorMessage) {
        ApiResponse<Object> response = new ApiResponse<>();
        response.setSuccess(false);
        response.setData(Map.of("error", errorMessage));
        response.setMetadata(Map.of("timestamp", Instant.now().toString(), "mode", "preview"));
        return response;
    }
}
