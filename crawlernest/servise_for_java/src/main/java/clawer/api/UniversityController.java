package clawer.api;

import clawer.model.University;
import clawer.service.UniversityService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

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
     * @return List of University objects
     */
    @GetMapping
    public List<University> getAllUniversities() {
        return universityService.getAllUniversities();
    }

    /**
     * Retrieves a specific university by its ID.
     * @param id The university ID
     * @return University object if found, 404 otherwise
     */
    @GetMapping("/{id}")
    public ResponseEntity<University> getUniversityById(@PathVariable String id) {
        University university = universityService.getUniversityById(id);
        if (university != null) {
            return ResponseEntity.ok(university);
        } else {
            return ResponseEntity.notFound().build();
        }
    }
}
