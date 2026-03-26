package clawer.api;

import clawer.dto.UniversityDTO;
import clawer.service.UniversityService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import clawer.dto.ApiResponse;
import java.util.List;

/**
 * REST Controller for accessing University data.
 */
@RestController
@RequestMapping("/api/v1/universities")
public class UniversityController {

    private final UniversityService universityService;

    public UniversityController(UniversityService universityService) {
        this.universityService = universityService;
    }

    /**
     * Retrieves a list of all universities.
     * @return List of UniversityDTO objects
     */
    @GetMapping
    public ApiResponse<List<UniversityDTO>> getAllUniversities(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size
    ) {
        int safePage = Math.max(page, 0);
        int safeSize = Math.min(Math.max(size, 1), 100);
        return ApiResponse.success(universityService.getAllUniversities(safePage, safeSize));
    }

    /**
     * Retrieves a specific university by its ID.
     * @param id The university ID
     * @return UniversityDTO object if found, 404 otherwise
     */
    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<UniversityDTO>> getUniversityById(@PathVariable Long id) {
        UniversityDTO university = universityService.getUniversityById(id);
        if (university != null) {
            return ResponseEntity.ok(ApiResponse.success(university));
        } else {
            return ResponseEntity.notFound().build();
        }
    }

    /**
     * Retrieves a specific university by its URL slug.
     * @param slug The university slug
     * @return UniversityDTO object if found, 404 otherwise
     */
    @GetMapping("/by-slug/{slug}")
    public ResponseEntity<ApiResponse<UniversityDTO>> getUniversityBySlug(@PathVariable String slug) {
        UniversityDTO university = universityService.getUniversityBySlug(slug);
        if (university != null) {
            return ResponseEntity.ok(ApiResponse.success(university));
        } else {
            return ResponseEntity.notFound().build();
        }
    }
}
