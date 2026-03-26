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
        if (request.getLeftUniversityId() == null || request.getRightUniversityId() == null) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "leftUniversityId and rightUniversityId are required.");
        }
        List<String> identifiers = List.of(request.getLeftUniversityId().toString(), request.getRightUniversityId().toString());
        try {
            return ApiResponse.success(comparisonService.compareUniversities(identifiers, request.getRankingYear()));
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage(), ex);
        }
    }
}
