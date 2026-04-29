package clawer.api;

import clawer.dto.ApiResponse;
import clawer.dto.SubjectOptionDTO;
import clawer.service.SubjectRankingService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1")
public class SubjectRankingController {
    private final SubjectRankingService subjectRankingService;

    public SubjectRankingController(SubjectRankingService subjectRankingService) {
        this.subjectRankingService = subjectRankingService;
    }

    @GetMapping("/subject-rankings/subjects")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getSubjects() {
        List<SubjectOptionDTO> subjects = subjectRankingService.getSubjects();
        return ResponseEntity.ok(ApiResponse.success(Map.of("items", subjects)));
    }

    @GetMapping("/subject-rankings")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getSubjectRankings(
            @RequestParam String subject,
            @RequestParam(required = false) Integer year,
            @RequestParam(required = false) String source,
            @RequestParam(required = false) String country,
            @RequestParam(required = false) String search,
            @RequestParam(required = false, defaultValue = "1") Integer page,
            @RequestParam(required = false, defaultValue = "20") Integer pageSize
    ) {
        try {
            return ResponseEntity.ok(ApiResponse.success(subjectRankingService.getSubjectRankings(
                    subject,
                    year,
                    source,
                    country,
                    search,
                    page,
                    pageSize
            )));
        } catch (IllegalArgumentException exc) {
            return validationError(exc.getMessage());
        }
    }

    @GetMapping("/subject-rankings/{subjectKey}")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getSubjectRankingByPath(
            @PathVariable String subjectKey,
            @RequestParam(required = false) Integer year,
            @RequestParam(required = false) String source,
            @RequestParam(required = false) String country,
            @RequestParam(required = false) String search,
            @RequestParam(required = false, defaultValue = "1") Integer page,
            @RequestParam(required = false, defaultValue = "20") Integer pageSize
    ) {
        try {
            return ResponseEntity.ok(ApiResponse.success(subjectRankingService.getSubjectRankings(
                    subjectKey,
                    year,
                    source,
                    country,
                    search,
                    page,
                    pageSize
            )));
        } catch (IllegalArgumentException exc) {
            return validationError(exc.getMessage());
        }
    }

    @GetMapping("/universities/{id}/subject-rankings")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getUniversitySubjectRankings(
            @PathVariable Long id,
            @RequestParam(required = false) Integer year,
            @RequestParam(required = false) String source
    ) {
        try {
            return ResponseEntity.ok(ApiResponse.success(
                    subjectRankingService.getUniversitySubjectRankings(id, year, source)
            ));
        } catch (IllegalArgumentException exc) {
            return validationError(exc.getMessage());
        }
    }

    private ResponseEntity<ApiResponse<Map<String, Object>>> validationError(String message) {
        ApiResponse<Map<String, Object>> response = new ApiResponse<>();
        response.setSuccess(false);
        response.setData(Map.of(
                "items", List.of(),
                "error", message == null ? "Invalid subject ranking request." : message
        ));
        return ResponseEntity.badRequest().body(response);
    }
}
