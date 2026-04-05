package clawer.api;

import clawer.dto.ApiResponse;
import clawer.dto.CompareRequest;
import clawer.model.UniversityComparisonResult;
import clawer.service.ComparisonService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@RestController
@RequestMapping("/api/v1/compare")
public class ComparisonController {

    private final ComparisonService comparisonService;

    public ComparisonController(ComparisonService comparisonService) {
        this.comparisonService = comparisonService;
    }

    @PostMapping
    public ApiResponse<UniversityComparisonResult> compare(@RequestBody CompareRequest request) {
        List<String> identifiers;
        if (request.getUniversityIds() != null && !request.getUniversityIds().isEmpty()) {
            identifiers = request.getUniversityIds().stream()
                    .filter(java.util.Objects::nonNull)
                    .map(String::valueOf)
                    .toList();
        } else if (request.getLeftUniversityId() != null && request.getRightUniversityId() != null) {
            identifiers = List.of(request.getLeftUniversityId().toString(), request.getRightUniversityId().toString());
        } else {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Provide at least two universityIds or both leftUniversityId and rightUniversityId.");
        }
        if (identifiers.size() < 2 || identifiers.size() > 4) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Comparison supports 2 to 4 universities.");
        }
        try {
            return ApiResponse.success(comparisonService.compareUniversities(identifiers, request.getRankingYear()));
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage(), ex);
        }
    }
}
