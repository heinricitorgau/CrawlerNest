package clawer.desk.controller;

import clawer.auth.jwt.AuthenticatedUser;
import clawer.desk.service.DeskProfileService;
import clawer.desk.service.DeskSkillService;
import clawer.desk.service.DeskSprintService;
import clawer.desk.service.DeskTargetService;
import clawer.desk.service.DeskTaskService;
import clawer.desk.support.DeskException;
import clawer.dto.ApiResponse;
import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * CRUD for the desk: tasks, sprints, targets, skills and the profile.
 *
 * <p>Under /api/v1/user/ so the filter chain refuses an anonymous caller before
 * this class runs (SecurityConfig). The user id comes from the verified token,
 * never from the body or the path, and every statement in the services is
 * filtered by it, so another account's id answers 404.
 *
 * <p>Writes reach the desk schema only. No warehouse, analytics or pipeline
 * table is written from here; the one warehouse read is the university name
 * joined onto a target.
 */
@RestController
@RequestMapping("/api/v1/user/desk")
public class DeskController {

    private final DeskTaskService tasks;
    private final DeskSprintService sprints;
    private final DeskTargetService targets;
    private final DeskSkillService skills;
    private final DeskProfileService profiles;

    public DeskController(DeskTaskService tasks, DeskSprintService sprints, DeskTargetService targets,
                          DeskSkillService skills, DeskProfileService profiles) {
        this.tasks = tasks;
        this.sprints = sprints;
        this.targets = targets;
        this.skills = skills;
        this.profiles = profiles;
    }

    // ─── Tasks ────────────────────────────────────────────────────────────────

    @GetMapping("/tasks")
    public ResponseEntity<?> listTasks(@RequestParam(required = false) String status,
                                       @RequestParam(required = false) Long sprintId) {
        return ok(tasks.list(userId(), status, sprintId));
    }

    @GetMapping("/tasks/{id}")
    public ResponseEntity<?> getTask(@PathVariable long id) {
        return ok(tasks.find(userId(), id).orElseThrow(DeskException::notFound));
    }

    @PostMapping("/tasks")
    public ResponseEntity<?> createTask(@RequestBody JsonNode body) {
        return created(tasks.create(userId(), body));
    }

    @PatchMapping("/tasks/{id}")
    public ResponseEntity<?> updateTask(@PathVariable long id, @RequestBody JsonNode body) {
        return ok(tasks.update(userId(), id, body));
    }

    @DeleteMapping("/tasks/{id}")
    public ResponseEntity<?> deleteTask(@PathVariable long id) {
        return deleted(tasks.delete(userId(), id));
    }

    // ─── Sprints ──────────────────────────────────────────────────────────────

    @GetMapping("/sprints")
    public ResponseEntity<?> listSprints() {
        return ok(sprints.list(userId()));
    }

    /** {@code data} is null when no sprint covers today: an empty desk, not an error. */
    @GetMapping("/sprints/current")
    public ResponseEntity<?> currentSprint() {
        return ok(sprints.current(userId()).orElse(null));
    }

    @GetMapping("/sprints/{id}")
    public ResponseEntity<?> getSprint(@PathVariable long id) {
        return ok(sprints.detail(userId(), id).orElseThrow(DeskException::notFound));
    }

    @PostMapping("/sprints")
    public ResponseEntity<?> createSprint(@RequestBody JsonNode body) {
        return created(sprints.create(userId(), body));
    }

    @PatchMapping("/sprints/{id}")
    public ResponseEntity<?> updateSprint(@PathVariable long id, @RequestBody JsonNode body) {
        return ok(sprints.update(userId(), id, body));
    }

    @DeleteMapping("/sprints/{id}")
    public ResponseEntity<?> deleteSprint(@PathVariable long id) {
        return deleted(sprints.delete(userId(), id));
    }

    // ─── Targets ──────────────────────────────────────────────────────────────

    @GetMapping("/targets")
    public ResponseEntity<?> listTargets(@RequestParam(required = false) String stage) {
        return ok(targets.list(userId(), stage));
    }

    @GetMapping("/targets/{id}")
    public ResponseEntity<?> getTarget(@PathVariable long id) {
        return ok(targets.find(userId(), id).orElseThrow(DeskException::notFound));
    }

    @PostMapping("/targets")
    public ResponseEntity<?> createTarget(@RequestBody JsonNode body) {
        return created(targets.create(userId(), body));
    }

    @PatchMapping("/targets/{id}")
    public ResponseEntity<?> updateTarget(@PathVariable long id, @RequestBody JsonNode body) {
        return ok(targets.update(userId(), id, body));
    }

    @DeleteMapping("/targets/{id}")
    public ResponseEntity<?> deleteTarget(@PathVariable long id) {
        return deleted(targets.delete(userId(), id));
    }

    // ─── Skills ───────────────────────────────────────────────────────────────

    @GetMapping("/skills")
    public ResponseEntity<?> listSkills(@RequestParam(required = false) String subject) {
        return ok(skills.list(userId(), subject));
    }

    /** Adds a practice result to a unit's counts, creating the unit on first use. */
    @PostMapping("/skills/results")
    public ResponseEntity<?> recordSkillResult(@RequestBody JsonNode body) {
        return ok(skills.recordResult(userId(), body));
    }

    @DeleteMapping("/skills/{id}")
    public ResponseEntity<?> deleteSkill(@PathVariable long id) {
        return deleted(skills.delete(userId(), id));
    }

    // ─── Profile ──────────────────────────────────────────────────────────────

    @GetMapping("/profile")
    public ResponseEntity<?> getProfile() {
        return ok(profiles.get(userId()));
    }

    @PutMapping("/profile")
    public ResponseEntity<?> putProfile(@RequestBody JsonNode body) {
        return ok(profiles.put(userId(), body));
    }

    // ─── Helpers ──────────────────────────────────────────────────────────────

    /**
     * The signed-in user. The filter chain already refuses an anonymous caller on
     * this prefix; the check stays so a routing change cannot quietly open it.
     */
    private static long userId() {
        Long id = AuthenticatedUser.currentId();
        if (id == null) {
            throw DeskException.unauthenticated();
        }
        return id;
    }

    private static ResponseEntity<?> ok(Object data) {
        return ResponseEntity.ok(ApiResponse.success(data));
    }

    private static ResponseEntity<?> created(Object data) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.success(data));
    }

    private static ResponseEntity<?> deleted(boolean deleted) {
        if (!deleted) {
            throw DeskException.notFound();
        }
        return ResponseEntity.ok(ApiResponse.success(Map.of("deleted", true)));
    }
}
