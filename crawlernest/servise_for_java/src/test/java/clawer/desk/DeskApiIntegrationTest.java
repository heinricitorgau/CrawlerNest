package clawer.desk;

import clawer.auth.jwt.JwtCookieAuthenticationFilter;
import clawer.auth.jwt.JwtService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import java.time.LocalDate;
import java.time.ZoneOffset;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.nullValue;

/**
 * The desk CRUD endpoints end to end: filter chain, controller, services and the
 * V003 tables on a real PostgreSQL.
 *
 * <p>The recurring assertion is ownership. Each test that creates something as
 * one user then tries to read, change or reference it as the other, and expects
 * the same 404 / 400 a missing row gets.
 */
@SpringBootTest
@AutoConfigureMockMvc
@TestPropertySource(properties = "crawlernest.jwt.secret=an-integration-test-secret-long-enough-for-hs256")
@SqlGroup({
        @Sql(scripts = {"classpath:sql/desk_integration_setup.sql", "classpath:sql/desk_integration_seed.sql"},
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD),
        @Sql(scripts = "classpath:sql/desk_integration_cleanup.sql",
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD)
})
class DeskApiIntegrationTest {

    private static final long OWNER = 990401L;
    private static final long OTHER_USER = 990402L;
    private static final long ACTIVE_UNIVERSITY = 990401L;
    private static final long MERGED_UNIVERSITY = 990402L;

    @Autowired
    private MockMvc mvc;

    @Autowired
    private JwtService jwtService;

    private final ObjectMapper json = new ObjectMapper();

    private Cookie as(long userId) {
        return new Cookie(JwtCookieAuthenticationFilter.COOKIE_NAME, jwtService.issue(userId, userId + "@integration.test"));
    }

    private ResultActions send(long userId, MockHttpServletRequestBuilder request) throws Exception {
        return mvc.perform(request.cookie(as(userId)));
    }

    private ResultActions send(long userId, MockHttpServletRequestBuilder request, String body) throws Exception {
        return mvc.perform(request.cookie(as(userId)).contentType(MediaType.APPLICATION_JSON).content(body));
    }

    private long createdId(ResultActions result) throws Exception {
        JsonNode body = json.readTree(result.andExpect(status().isCreated()).andReturn().getResponse().getContentAsString());
        JsonNode data = body.path("data");
        return data.has("sprint") ? data.path("sprint").path("id").asLong() : data.path("id").asLong();
    }

    private long createTask(long userId, String body) throws Exception {
        return createdId(send(userId, post("/api/v1/user/desk/tasks"), body));
    }

    // ─── Auth ─────────────────────────────────────────────────────────────────

    @Test
    void everyDeskEndpointNeedsAToken() throws Exception {
        mvc.perform(get("/api/v1/user/desk/tasks")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/user/desk/tasks").contentType(MediaType.APPLICATION_JSON).content("{\"title\":\"x\"}"))
                .andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/user/desk/profile")).andExpect(status().isUnauthorized());
    }

    // ─── Tasks ────────────────────────────────────────────────────────────────

    @Test
    void createsListsAndCompletesATask() throws Exception {
        long late = createTask(OWNER, "{\"title\": \"Submit EA application\", \"dueDate\": \"2026-11-01\", \"priority\": \"high\"}");
        long soon = createTask(OWNER, "{\"title\": \"Final draft\", \"dueDate\": \"2026-10-22\"}");
        long undated = createTask(OWNER, "{\"title\": \"  Ask about fee waiver  \"}");

        send(OWNER, get("/api/v1/user/desk/tasks"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[*].id").value(contains((int) soon, (int) late, (int) undated)))
                .andExpect(jsonPath("$.data[2].title").value("Ask about fee waiver"))
                .andExpect(jsonPath("$.data[0].createdBy").value("user"))
                .andExpect(jsonPath("$.data[1].priority").value("high"));

        send(OWNER, patch("/api/v1/user/desk/tasks/" + soon), "{\"status\": \"done\"}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.status").value("done"))
                .andExpect(jsonPath("$.data.completedAt").isNotEmpty());
        send(OWNER, get("/api/v1/user/desk/tasks")).andExpect(jsonPath("$.data", hasSize(2)));
        send(OWNER, get("/api/v1/user/desk/tasks").param("status", "done")).andExpect(jsonPath("$.data", hasSize(1)));

        // Reopening clears the completion time.
        send(OWNER, patch("/api/v1/user/desk/tasks/" + soon), "{\"status\": \"todo\"}")
                .andExpect(jsonPath("$.data.completedAt").value(nullValue()));
    }

    @Test
    void aPatchLeavesAbsentFieldsAloneAndClearsNullOnes() throws Exception {
        long id = createTask(OWNER, "{\"title\": \"Essay\", \"dueDate\": \"2026-10-30\", \"category\": \"Essay\"}");
        send(OWNER, patch("/api/v1/user/desk/tasks/" + id), "{\"dueDate\": null}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.dueDate").value(nullValue()))
                .andExpect(jsonPath("$.data.category").value("Essay"));
    }

    @Test
    void refusesBadTaskBodies() throws Exception {
        send(OWNER, post("/api/v1/user/desk/tasks"), "{}").andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("title is required."));
        send(OWNER, post("/api/v1/user/desk/tasks"), "{\"title\": \"x\", \"dueDte\": \"2026-10-30\"}")
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.error").value("Unknown field: dueDte."));
        send(OWNER, post("/api/v1/user/desk/tasks"), "{\"title\": \"x\", \"dueDate\": \"30/10/2026\"}")
                .andExpect(status().isBadRequest());
        send(OWNER, post("/api/v1/user/desk/tasks"), "{\"title\": \"x\", \"priority\": \"urgent\"}")
                .andExpect(status().isBadRequest());
        send(OWNER, post("/api/v1/user/desk/tasks"), "{\"title\": \"" + "x".repeat(201) + "\"}")
                .andExpect(status().isBadRequest());
        send(OWNER, post("/api/v1/user/desk/tasks"), "not json").andExpect(status().isBadRequest());
        send(OWNER, get("/api/v1/user/desk/tasks").param("status", "sometimes")).andExpect(status().isBadRequest());
    }

    @Test
    void anotherUsersTaskLooksAbsent() throws Exception {
        long id = createTask(OWNER, "{\"title\": \"Mine\"}");
        send(OTHER_USER, get("/api/v1/user/desk/tasks/" + id)).andExpect(status().isNotFound());
        send(OTHER_USER, patch("/api/v1/user/desk/tasks/" + id), "{\"title\": \"Theirs now\"}").andExpect(status().isNotFound());
        send(OTHER_USER, delete("/api/v1/user/desk/tasks/" + id)).andExpect(status().isNotFound());
        send(OTHER_USER, get("/api/v1/user/desk/tasks")).andExpect(jsonPath("$.data", hasSize(0)));
        send(OWNER, get("/api/v1/user/desk/tasks/" + id)).andExpect(jsonPath("$.data.title").value("Mine"));
    }

    @Test
    void aTaskCannotBeFiledUnderAnotherUsersSprintOrTarget() throws Exception {
        long othersSprint = createdId(send(OTHER_USER, post("/api/v1/user/desk/sprints"),
                "{\"title\": \"Theirs\", \"startDate\": \"2026-10-01\", \"endDate\": \"2026-10-31\"}"));
        long othersTarget = createdId(send(OTHER_USER, post("/api/v1/user/desk/targets"), "{\"customName\": \"Their school\"}"));
        send(OWNER, post("/api/v1/user/desk/tasks"), "{\"title\": \"x\", \"sprintId\": " + othersSprint + "}")
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.error").value("No such sprint."));
        send(OWNER, post("/api/v1/user/desk/tasks"), "{\"title\": \"x\", \"targetEntityId\": " + othersTarget + "}")
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.error").value("No such target."));
    }

    // ─── Sprints ──────────────────────────────────────────────────────────────

    @Test
    void theCurrentSprintCarriesItsTasksAndCounts() throws Exception {
        LocalDate today = LocalDate.now(ZoneOffset.UTC);
        long sprint = createdId(send(OWNER, post("/api/v1/user/desk/sprints"), """
                {"title": "Early Action push", "goal": "Lock the essay", "startDate": "%s", "endDate": "%s"}
                """.formatted(today.minusDays(3), today.plusDays(10))));
        createTask(OWNER, "{\"title\": \"a\", \"sprintId\": " + sprint + ", \"status\": \"done\"}");
        createTask(OWNER, "{\"title\": \"b\", \"sprintId\": " + sprint + "}");
        createTask(OWNER, "{\"title\": \"not in the sprint\"}");

        send(OWNER, get("/api/v1/user/desk/sprints/current"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.sprint.title").value("Early Action push"))
                .andExpect(jsonPath("$.data.sprint.taskCount").value(2))
                .andExpect(jsonPath("$.data.sprint.doneCount").value(1))
                .andExpect(jsonPath("$.data.tasks", hasSize(2)));
        send(OTHER_USER, get("/api/v1/user/desk/sprints/current"))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data").value(nullValue()));
    }

    @Test
    void sprintDatesMustBeOrderedOnCreateAndOnPatch() throws Exception {
        send(OWNER, post("/api/v1/user/desk/sprints"), "{\"title\": \"x\", \"startDate\": \"2026-10-10\", \"endDate\": \"2026-10-01\"}")
                .andExpect(status().isBadRequest());
        long id = createdId(send(OWNER, post("/api/v1/user/desk/sprints"),
                "{\"title\": \"x\", \"startDate\": \"2026-10-01\", \"endDate\": \"2026-10-10\"}"));
        // Only one side sent: the table's check compares it with the stored end date.
        send(OWNER, patch("/api/v1/user/desk/sprints/" + id), "{\"startDate\": \"2026-10-20\"}")
                .andExpect(status().isBadRequest());
    }

    @Test
    void deletingASprintKeepsItsTasks() throws Exception {
        long sprint = createdId(send(OWNER, post("/api/v1/user/desk/sprints"),
                "{\"title\": \"x\", \"startDate\": \"2026-10-01\", \"endDate\": \"2026-10-10\"}"));
        long task = createTask(OWNER, "{\"title\": \"kept\", \"sprintId\": " + sprint + "}");
        send(OWNER, delete("/api/v1/user/desk/sprints/" + sprint)).andExpect(status().isOk());
        send(OWNER, get("/api/v1/user/desk/tasks/" + task))
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.sprintId").value(nullValue()));
    }

    @Test
    void aTaskPatchAtAStaleRevisionIsRefusedAndChangesNothing() throws Exception {
        long task = createTask(OWNER, "{\"title\": \"Draft essay\"}");
        send(OWNER, get("/api/v1/user/desk/tasks/" + task)).andExpect(jsonPath("$.data.revision").value(1));

        send(OWNER, patch("/api/v1/user/desk/tasks/" + task), "{\"status\": \"done\", \"expectedRevision\": 1}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.revision").value(2));
        send(OWNER, patch("/api/v1/user/desk/tasks/" + task), "{\"title\": \"Stale tab\", \"expectedRevision\": 1}")
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.success").value(false));
        send(OWNER, get("/api/v1/user/desk/tasks/" + task))
                .andExpect(jsonPath("$.data.title").value("Draft essay"))
                .andExpect(jsonPath("$.data.status").value("done"))
                .andExpect(jsonPath("$.data.revision").value(2));

        // Without expectedRevision the PATCH is unconditional, and still counts.
        send(OWNER, patch("/api/v1/user/desk/tasks/" + task), "{\"title\": \"Final essay\"}")
                .andExpect(jsonPath("$.data.revision").value(3));

        // Another user's task stays a 404, not a 409 that would confirm it exists.
        send(OTHER_USER, patch("/api/v1/user/desk/tasks/" + task), "{\"title\": \"x\", \"expectedRevision\": 1}")
                .andExpect(status().isNotFound());
        send(OWNER, patch("/api/v1/user/desk/tasks/" + task), "{\"expectedRevision\": 3}").andExpect(status().isBadRequest());
        send(OWNER, patch("/api/v1/user/desk/tasks/" + task), "{\"title\": \"x\", \"expectedRevision\": 0}")
                .andExpect(status().isBadRequest());
        send(OWNER, post("/api/v1/user/desk/tasks"), "{\"title\": \"x\", \"expectedRevision\": 1}")
                .andExpect(status().isBadRequest());
    }

    @Test
    void aSprintPatchAtAStaleRevisionIsRefusedAndItsTasksDoNotCount() throws Exception {
        long sprint = createdId(send(OWNER, post("/api/v1/user/desk/sprints"),
                "{\"title\": \"EA push\", \"startDate\": \"2026-10-01\", \"endDate\": \"2026-10-10\"}"));
        send(OWNER, get("/api/v1/user/desk/sprints/" + sprint)).andExpect(jsonPath("$.data.sprint.revision").value(1));

        // Adding and ticking a task changes the task, not the sprint.
        long task = createTask(OWNER, "{\"title\": \"t\", \"sprintId\": " + sprint + "}");
        send(OWNER, patch("/api/v1/user/desk/tasks/" + task), "{\"status\": \"done\"}").andExpect(status().isOk());
        send(OWNER, get("/api/v1/user/desk/sprints/" + sprint)).andExpect(jsonPath("$.data.sprint.revision").value(1));

        send(OWNER, patch("/api/v1/user/desk/sprints/" + sprint), "{\"goal\": \"Tab A\", \"expectedRevision\": 1}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.sprint.revision").value(2));
        send(OWNER, patch("/api/v1/user/desk/sprints/" + sprint), "{\"goal\": \"Tab B\", \"expectedRevision\": 1}")
                .andExpect(status().isConflict());
        send(OWNER, get("/api/v1/user/desk/sprints/" + sprint))
                .andExpect(jsonPath("$.data.sprint.goal").value("Tab A"))
                .andExpect(jsonPath("$.data.sprint.revision").value(2));

        send(OTHER_USER, patch("/api/v1/user/desk/sprints/" + sprint), "{\"goal\": \"x\", \"expectedRevision\": 2}")
                .andExpect(status().isNotFound());
        send(OWNER, post("/api/v1/user/desk/sprints"),
                "{\"title\": \"x\", \"startDate\": \"2026-10-01\", \"endDate\": \"2026-10-10\", \"expectedRevision\": 1}")
                .andExpect(status().isBadRequest());
        // The date-order check still answers 400 at the right revision.
        send(OWNER, patch("/api/v1/user/desk/sprints/" + sprint), "{\"startDate\": \"2026-10-20\", \"expectedRevision\": 2}")
                .andExpect(status().isBadRequest());
    }

    @Test
    void deletingASprintChangesItsTasksRevisionSoAStaleTabIsRefused() throws Exception {
        long sprint = createdId(send(OWNER, post("/api/v1/user/desk/sprints"),
                "{\"title\": \"x\", \"startDate\": \"2026-10-01\", \"endDate\": \"2026-10-10\"}"));
        long task = createTask(OWNER, "{\"title\": \"kept\", \"sprintId\": " + sprint + "}");
        // The foreign key clears sprint_id without going through the service; the trigger still counts it.
        send(OWNER, delete("/api/v1/user/desk/sprints/" + sprint)).andExpect(status().isOk());
        send(OWNER, get("/api/v1/user/desk/tasks/" + task)).andExpect(jsonPath("$.data.revision").value(2));
        send(OWNER, patch("/api/v1/user/desk/tasks/" + task), "{\"title\": \"edit\", \"expectedRevision\": 1}")
                .andExpect(status().isConflict());
    }

    // ─── Targets ──────────────────────────────────────────────────────────────

    @Test
    void aTargetPatchAtAStaleRevisionIsRefusedAndChangesNothing() throws Exception {
        long id = createdId(send(OWNER, post("/api/v1/user/desk/targets"), "{\"customName\": \"Northwestern\"}"));
        send(OWNER, patch("/api/v1/user/desk/targets/" + id), "{\"notes\": \"Tab A\", \"expectedRevision\": 1}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.revision").value(2));
        send(OWNER, patch("/api/v1/user/desk/targets/" + id), "{\"notes\": \"Tab B\", \"expectedRevision\": 1}")
                .andExpect(status().isConflict());
        send(OWNER, get("/api/v1/user/desk/targets/" + id))
                .andExpect(jsonPath("$.data.notes").value("Tab A"))
                .andExpect(jsonPath("$.data.revision").value(2));
        send(OTHER_USER, patch("/api/v1/user/desk/targets/" + id), "{\"notes\": \"x\", \"expectedRevision\": 2}")
                .andExpect(status().isNotFound());
        send(OWNER, patch("/api/v1/user/desk/targets/987654321"), "{\"notes\": \"x\", \"expectedRevision\": 1}")
                .andExpect(status().isNotFound());
    }

    @Test
    void aTargetLinkedToAUniversityShowsItsWarehouseName() throws Exception {
        long id = createdId(send(OWNER, post("/api/v1/user/desk/targets"),
                "{\"canonicalUniversityId\": " + ACTIVE_UNIVERSITY + ", \"programmeName\": \"Computer Science\", \"userBand\": \"reach\"}"));
        send(OWNER, get("/api/v1/user/desk/targets/" + id))
                .andExpect(jsonPath("$.data.name").value("Desk Test University"))
                .andExpect(jsonPath("$.data.canonicalSlug").value("desk-test-active-university"))
                .andExpect(jsonPath("$.data.stage").value("researching"))
                .andExpect(jsonPath("$.data.userBand").value("reach"));
    }

    @Test
    void theSameUniversityAndProgrammeIsRefusedTwiceWhateverTheSpacing() throws Exception {
        send(OWNER, post("/api/v1/user/desk/targets"),
                "{\"canonicalUniversityId\": " + ACTIVE_UNIVERSITY + ", \"programmeName\": \"Computer Science\"}")
                .andExpect(status().isCreated());
        send(OWNER, post("/api/v1/user/desk/targets"),
                "{\"canonicalUniversityId\": " + ACTIVE_UNIVERSITY + ", \"programmeName\": \"  computer   science \"}")
                .andExpect(status().isConflict());
        // Another programme at the same school is a separate target, and another user may add the same pair.
        send(OWNER, post("/api/v1/user/desk/targets"),
                "{\"canonicalUniversityId\": " + ACTIVE_UNIVERSITY + ", \"programmeName\": \"Physics\"}")
                .andExpect(status().isCreated());
        send(OTHER_USER, post("/api/v1/user/desk/targets"),
                "{\"canonicalUniversityId\": " + ACTIVE_UNIVERSITY + ", \"programmeName\": \"Computer Science\"}")
                .andExpect(status().isCreated());
    }

    @Test
    void refusesUnknownAndMergedUniversities() throws Exception {
        send(OWNER, post("/api/v1/user/desk/targets"), "{\"canonicalUniversityId\": 987654321}")
                .andExpect(status().isBadRequest()).andExpect(jsonPath("$.error").value("No such university."));
        send(OWNER, post("/api/v1/user/desk/targets"), "{\"canonicalUniversityId\": " + MERGED_UNIVERSITY + "}")
                .andExpect(status().isBadRequest());
        send(OWNER, post("/api/v1/user/desk/targets"), "{}")
                .andExpect(status().isBadRequest());
    }

    @Test
    void aTargetCannotLoseItsOnlyName() throws Exception {
        long id = createdId(send(OWNER, post("/api/v1/user/desk/targets"), "{\"customName\": \"Local college\"}"));
        send(OWNER, patch("/api/v1/user/desk/targets/" + id), "{\"customName\": null}").andExpect(status().isBadRequest());
        send(OWNER, patch("/api/v1/user/desk/targets/" + id), "{\"stage\": \"applying\"}")
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.stage").value("applying"));
    }

    @Test
    void notesAndRoundAreEditableByTheOwnerOnly() throws Exception {
        long id = createdId(send(OWNER, post("/api/v1/user/desk/targets"), "{\"customName\": \"Northwestern\"}"));
        send(OWNER, patch("/api/v1/user/desk/targets/" + id),
                "{\"notes\": \"Loves interdisciplinary programs; Medill journalism.\", \"applicationRound\": \"RD\"}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.notes").value("Loves interdisciplinary programs; Medill journalism."))
                .andExpect(jsonPath("$.data.applicationRound").value("RD"))
                .andExpect(jsonPath("$.data.name").value("Northwestern"));

        // Another account: the same 404 a missing row gets, and nothing changes.
        send(OTHER_USER, patch("/api/v1/user/desk/targets/" + id), "{\"notes\": \"overwritten\"}").andExpect(status().isNotFound());
        send(OWNER, get("/api/v1/user/desk/targets/" + id))
                .andExpect(jsonPath("$.data.notes").value("Loves interdisciplinary programs; Medill journalism."));

        send(OWNER, patch("/api/v1/user/desk/targets/" + id), "{\"applicationRound\": \"Early\"}").andExpect(status().isBadRequest());
        send(OWNER, patch("/api/v1/user/desk/targets/" + id), "{\"notes\": \"" + "x".repeat(4001) + "\"}").andExpect(status().isBadRequest());

        send(OWNER, patch("/api/v1/user/desk/targets/" + id), "{\"notes\": null, \"applicationRound\": null}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.notes").value(nullValue()))
                .andExpect(jsonPath("$.data.applicationRound").value(nullValue()));
    }

    // ─── Skills ───────────────────────────────────────────────────────────────

    @Test
    void resultsAddUpAndTheDatabaseComputesMastery() throws Exception {
        send(OWNER, post("/api/v1/user/desk/skills/results"),
                "{\"subject\": \"SAT Math\", \"unit\": \"Algebra\", \"attempted\": 30, \"correct\": 28}")
                .andExpect(status().isOk()).andExpect(jsonPath("$.data.masteryPct").value(93.3));
        send(OWNER, post("/api/v1/user/desk/skills/results"),
                "{\"subject\": \"SAT Math\", \"unit\": \"Algebra\", \"attempted\": 20, \"correct\": 19}")
                .andExpect(jsonPath("$.data.questionsAttempted").value(50))
                .andExpect(jsonPath("$.data.questionsCorrect").value(47))
                .andExpect(jsonPath("$.data.masteryPct").value(94.0));
        send(OTHER_USER, get("/api/v1/user/desk/skills")).andExpect(jsonPath("$.data", hasSize(0)));
    }

    @Test
    void refusesImpossibleOrMixedResults() throws Exception {
        send(OWNER, post("/api/v1/user/desk/skills/results"),
                "{\"subject\": \"SAT Math\", \"unit\": \"Algebra\", \"attempted\": 5, \"correct\": 6}")
                .andExpect(status().isBadRequest());
        send(OWNER, post("/api/v1/user/desk/skills/results"),
                "{\"subject\": \"SAT Math\", \"unit\": \"Algebra\", \"attempted\": 5, \"correct\": 4, \"masteryPct\": 99}")
                .andExpect(status().isBadRequest());
        send(OWNER, post("/api/v1/user/desk/skills/results"),
                "{\"subject\": \"SAT Math\", \"unit\": \"Algebra\", \"attempted\": 5, \"correct\": 4}")
                .andExpect(status().isOk());
        send(OWNER, post("/api/v1/user/desk/skills/results"),
                "{\"subject\": \"SAT Math\", \"unit\": \"Algebra\", \"attempted\": 5, \"correct\": 4, \"source\": \"mock_test\"}")
                .andExpect(status().isConflict());
    }

    // ─── Profile ──────────────────────────────────────────────────────────────

    @Test
    void theProfileHasDefaultsUntilSavedAndIsReplacedWhole() throws Exception {
        send(OWNER, get("/api/v1/user/desk/profile"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.timezone").value("UTC"))
                .andExpect(jsonPath("$.data.updatedAt").value(nullValue()));

        send(OWNER, put("/api/v1/user/desk/profile"), """
                {"displayName": "Mei", "timezone": "Asia/Taipei",
                 "selfReported": {"gpa": 3.8, "gpaScale": 4.0, "ielts": 7.5}, "preferences": {"defaultTab": "desk"}}
                """)
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.selfReported.ielts").value(7.5))
                .andExpect(jsonPath("$.data.preferences.defaultTab").value("desk"));

        // PUT replaces: what is left out is cleared.
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"displayName\": \"Mei\"}")
                .andExpect(jsonPath("$.data.timezone").value("UTC"))
                .andExpect(jsonPath("$.data.selfReported.gpa").value(nullValue()));

        send(OTHER_USER, get("/api/v1/user/desk/profile")).andExpect(jsonPath("$.data.displayName").value(nullValue()));
    }

    @Test
    void aStaleExpectedRevisionIsRefusedInsteadOfOverwritingAnotherTab() throws Exception {
        send(OWNER, get("/api/v1/user/desk/profile")).andExpect(jsonPath("$.data.revision").value(0));

        // Both tabs saw "no profile". The first creates it; the second must not replace it.
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"displayName\": \"Tab A\", \"expectedRevision\": 0}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.revision").value(1));
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"displayName\": \"Tab B\", \"expectedRevision\": 0}")
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.success").value(false));

        send(OWNER, put("/api/v1/user/desk/profile"), "{\"displayName\": \"Tab A again\", \"expectedRevision\": 1}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.revision").value(2));
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"displayName\": \"Tab B late\", \"expectedRevision\": 1}")
                .andExpect(status().isConflict());

        // The refused writes changed nothing.
        send(OWNER, get("/api/v1/user/desk/profile"))
                .andExpect(jsonPath("$.data.displayName").value("Tab A again"))
                .andExpect(jsonPath("$.data.revision").value(2));

        // Without expectedRevision the write is unconditional, and still counts as a revision.
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"displayName\": \"Mei\"}")
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.revision").value(3));

        // Another user's revision numbers are their own.
        send(OTHER_USER, put("/api/v1/user/desk/profile"), "{\"displayName\": \"Other\", \"expectedRevision\": 3}")
                .andExpect(status().isConflict());
        send(OTHER_USER, get("/api/v1/user/desk/profile")).andExpect(jsonPath("$.data.revision").value(0));
    }

    @Test
    void refusesBadProfiles() throws Exception {
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"expectedRevision\": -1}").andExpect(status().isBadRequest());
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"expectedRevision\": \"1\"}").andExpect(status().isBadRequest());
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"expectedRevision\": 1.5}").andExpect(status().isBadRequest());
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"timezone\": \"Mars/Olympus\"}").andExpect(status().isBadRequest());
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"selfReported\": {\"gpa\": 3.8}}").andExpect(status().isBadRequest());
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"selfReported\": {\"gpa\": 4.5, \"gpaScale\": 4.0}}").andExpect(status().isBadRequest());
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"selfReported\": {\"ielts\": 7.3}}").andExpect(status().isBadRequest());
        send(OWNER, put("/api/v1/user/desk/profile"), "{\"selfReported\": {\"verified\": true}}").andExpect(status().isBadRequest());
    }
}
