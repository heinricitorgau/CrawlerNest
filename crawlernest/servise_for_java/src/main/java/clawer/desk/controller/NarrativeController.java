package clawer.desk.controller;

import clawer.desk.story.NarrativeService;
import clawer.desk.support.DeskAuth;
import clawer.dto.ApiResponse;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Narrative themes and resonance. Under /api/v1/user/ like the rest of the desk.
 * Every response is the whole narrative, so the page never shows a theme list
 * and a resonance list from two different moments.
 */
@RestController
@RequestMapping("/api/v1/user/desk/story")
public class NarrativeController {

    private final NarrativeService narrative;

    public NarrativeController(NarrativeService narrative) {
        this.narrative = narrative;
    }

    @GetMapping("/narrative")
    public ResponseEntity<?> get(@RequestParam(defaultValue = "false") boolean includeDismissed) {
        return ResponseEntity.ok(ApiResponse.success(narrative.narrative(DeskAuth.currentUserId(), includeDismissed)));
    }

    /** The themes alone (suggested and accepted; dismissed too with includeDismissed). */
    @GetMapping("/themes")
    public ResponseEntity<?> themes(@RequestParam(defaultValue = "false") boolean includeDismissed) {
        return ResponseEntity.ok(ApiResponse.success(narrative.themes(DeskAuth.currentUserId(), includeDismissed)));
    }

    /** Accepted themes' 1-5 resonance with each school, with the reasons and where the school side came from. */
    @GetMapping("/resonance")
    public ResponseEntity<?> resonance() {
        return ResponseEntity.ok(ApiResponse.success(narrative.resonance(DeskAuth.currentUserId())));
    }

    /**
     * Draws one or two themes from the user's drafts and stores them as suggestions;
     * replaces open suggestions, keeps accepted themes. {@code /generate} and
     * {@code /themes/generate} are one handler: the first is the documented path,
     * the second what the desk page already calls.
     */
    @PostMapping({"/generate", "/themes/generate"})
    public ResponseEntity<?> generateThemes() {
        return ResponseEntity.ok(ApiResponse.success(narrative.generateThemes(DeskAuth.currentUserId())));
    }

    /** Body: {"status": "accepted" | "dismissed"}. */
    @PatchMapping("/themes/{id}")
    public ResponseEntity<?> decide(@PathVariable long id, @RequestBody JsonNode body) {
        return ResponseEntity.ok(ApiResponse.success(narrative.decideTheme(DeskAuth.currentUserId(), id, body)));
    }

    /** Judges accepted themes against the user's open schools; replaces earlier judgements. */
    @PostMapping("/resonance/generate")
    public ResponseEntity<?> generateResonance() {
        return ResponseEntity.ok(ApiResponse.success(narrative.generateResonance(DeskAuth.currentUserId())));
    }
}
