package clawer.api;

import clawer.model.UniversityComparisonResult;
import clawer.service.ComparisonService;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.List;

@RestController
@RequestMapping("/compare")
public class ComparisonController {

    private final ComparisonService comparisonService;

    public ComparisonController(ComparisonService comparisonService) {
        this.comparisonService = comparisonService;
    }

    @GetMapping
    public UniversityComparisonResult compare(
            @RequestParam String u1,
            @RequestParam String u2,
            @RequestParam(required = false) List<String> u,
            @RequestParam(required = false) Integer rankingYear
    ) {
        List<String> identifiers = new ArrayList<>();
        identifiers.add(u1);
        identifiers.add(u2);
        if (u != null) {
            identifiers.addAll(u);
        }
        try {
            return comparisonService.compareUniversities(identifiers, rankingYear);
        } catch (IllegalArgumentException ex) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, ex.getMessage(), ex);
        }
    }
}
