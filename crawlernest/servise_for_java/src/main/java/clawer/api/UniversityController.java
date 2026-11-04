package clawer.api;

import clawer.dto.UniversityDTO;
import clawer.dto.WikipediaArticleDTO;
import clawer.repository.UniversityWikipediaRepository;
import clawer.service.SourceIntelligenceService;
import clawer.service.UniversityService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import clawer.dto.ApiResponse;
import java.util.List;
import java.util.Map;

/**
 * REST Controller for accessing University data.
 */
@RestController
@RequestMapping("/api/v1/universities")
public class UniversityController {

    private final UniversityService universityService;
    private final SourceIntelligenceService sourceIntelligenceService;
    private final UniversityWikipediaRepository universityWikipediaRepository;

    public UniversityController(
            UniversityService universityService,
            SourceIntelligenceService sourceIntelligenceService,
            UniversityWikipediaRepository universityWikipediaRepository
    ) {
        this.universityService = universityService;
        this.sourceIntelligenceService = sourceIntelligenceService;
        this.universityWikipediaRepository = universityWikipediaRepository;
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

    @GetMapping("/{id}/source-comparison")
    public ResponseEntity<ApiResponse<Map<String, Object>>> getSourceComparison(@PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success(sourceIntelligenceService.getSourceComparison(id)));
    }

    /**
     * The Wikipedia article matched to a university, for its introduction.
     *
     * <p>Its own endpoint rather than a field of {@link UniversityDTO}: an article
     * runs to tens of kilobytes, and the comparison and shortlist reads that reuse
     * that DTO have no use for it.
     *
     * @param id The canonical university ID
     * @return the article, or {@code data: null} when none is matched -- a 200
     *         either way, since "no article held" is an answer and says nothing
     *         about whether the university exists
     */
    @GetMapping("/{id}/wikipedia")
    public ResponseEntity<ApiResponse<WikipediaArticleDTO>> getWikipediaArticle(@PathVariable Long id) {
        return ResponseEntity.ok(ApiResponse.success(
                universityWikipediaRepository.findByCanonicalUniversityId(id).orElse(null)));
    }

    /**
     * Retrieves a specific university by its URL slug, as one ranking edition shows it.
     * @param slug The university slug
     * @param year The edition; the default when omitted. A year the release does not hold is a 400.
     * @return UniversityDTO object if found, 404 otherwise
     */
    /**
     * The university pages worth indexing, for the web app's sitemap.xml. Read-only, public,
     * and only slugs and dates: the same facts the pages themselves show.
     */
    @GetMapping("/sitemap-entries")
    public ApiResponse<List<UniversityService.SitemapEntry>> getSitemapEntries() {
        return ApiResponse.success(universityService.sitemapEntries());
    }

    @GetMapping("/by-slug/{slug}")
    public ResponseEntity<ApiResponse<UniversityDTO>> getUniversityBySlug(
            @PathVariable String slug,
            @RequestParam(required = false) Integer year
    ) {
        UniversityDTO university;
        try {
            university = universityService.getUniversityBySlug(slug, year);
        } catch (IllegalArgumentException ex) {
            throw new org.springframework.web.server.ResponseStatusException(
                    org.springframework.http.HttpStatus.BAD_REQUEST, ex.getMessage(), ex);
        }
        if (university != null) {
            return ResponseEntity.ok(ApiResponse.success(university));
        } else {
            return ResponseEntity.notFound().build();
        }
    }
}
