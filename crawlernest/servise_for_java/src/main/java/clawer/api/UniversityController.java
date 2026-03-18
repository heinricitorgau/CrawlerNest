package clawer.api;

import clawer.dto.UniversityDTO;
import clawer.service.UniversityService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * REST Controller for accessing University data.
 */
@RestController
@RequestMapping("/universities")
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
    public List<UniversityDTO> getAllUniversities() {
        return universityService.getAllUniversities();
    }

    /**
     * Retrieves a specific university by its ID.
     * @param id The university ID
     * @return UniversityDTO object if found, 404 otherwise
     */
    @GetMapping("/{id}")
    public ResponseEntity<UniversityDTO> getUniversityById(@PathVariable Long id) {
        UniversityDTO university = universityService.getUniversityById(id);
        if (university != null) {
            return ResponseEntity.ok(university);
        } else {
            return ResponseEntity.notFound().build();
        }
    }
}
