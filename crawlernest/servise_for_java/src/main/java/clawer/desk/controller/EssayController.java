package clawer.desk.controller;

import clawer.desk.essay.EssayService;
import clawer.desk.support.DeskAuth;
import clawer.desk.support.DeskException;
import clawer.dto.ApiResponse;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * Essay review: score a draft against the rubric, list past reviews, read or
 * delete one. Under /api/v1/user/ like the rest of the desk, so the filter chain
 * refuses an anonymous caller first.
 *
 * <p>The scores come from the model this API calls itself. No endpoint accepts
 * scores from a caller, so a review cannot be written with numbers the model
 * never gave.
 */
@RestController
@RequestMapping("/api/v1/user/desk/essays")
public class EssayController {

    private final EssayService essays;

    public EssayController(EssayService essays) {
        this.essays = essays;
    }

    /** 200 with the stored review; 200 with {@code cached: true} when this exact draft was scored before. */
    @PostMapping("/evaluate")
    public ResponseEntity<?> evaluate(@RequestBody JsonNode body) {
        return ResponseEntity.ok(ApiResponse.success(essays.evaluate(DeskAuth.currentUserId(), body)));
    }

    @GetMapping
    public ResponseEntity<?> list() {
        return ResponseEntity.ok(ApiResponse.success(essays.list(DeskAuth.currentUserId())));
    }

    @GetMapping("/{id}")
    public ResponseEntity<?> get(@PathVariable long id) {
        return ResponseEntity.ok(ApiResponse.success(
                essays.detail(DeskAuth.currentUserId(), id, true).orElseThrow(DeskException::notFound)));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<?> delete(@PathVariable long id) {
        if (!essays.delete(DeskAuth.currentUserId(), id)) {
            throw DeskException.notFound();
        }
        return ResponseEntity.ok(ApiResponse.success(Map.of("deleted", true)));
    }
}
