package clawer.desk.story;

import clawer.auth.jwt.JwtCookieAuthenticationFilter;
import clawer.auth.jwt.JwtService;
import clawer.desk.model.DeskModelClient;
import clawer.service.AnalyticsService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.Cookie;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * /api/v1/user/desk/story/* through the filter chain to PostgreSQL, with the model mocked.
 *
 * <p>The model is given every chance to overreach -- a quote the student never
 * wrote, a school id that is not theirs, "from your notes" for a school with no
 * notes, a level of 7 -- and each test checks what reached the database.
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
class NarrativeApiIntegrationTest {

    private static final long OWNER = 990401L;
    private static final long OTHER_USER = 990402L;
    private static final String DRAFT = "I rebuilt the arm three times before I let the freshmen touch it. "
            + "Now I run a weekend club where the broken prototypes go on the table first.";

    @Autowired private MockMvc mvc;
    @Autowired private JwtService jwtService;
    @Autowired private JdbcTemplate jdbc;
    @MockBean private DeskModelClient model;

    private final ObjectMapper json = new ObjectMapper();
    private long draftId;

    @BeforeEach
    void seedDraft() {
        draftId = jdbc.queryForObject("""
                INSERT INTO desk.essay_review (user_id, essay_title, draft_text, word_count, draft_sha256, rubric_version,
                    dimension_scores, overall_score, model_name)
                VALUES (?, 'Personal statement', ?, 30, repeat('a', 64), 'essay-rubric-2026.1', '{}', 70, 'm')
                RETURNING id
                """, Long.class, OWNER, DRAFT);
    }

    private ResultActions send(long userId, MockHttpServletRequestBuilder request) throws Exception {
        return mvc.perform(request.cookie(new Cookie(JwtCookieAuthenticationFilter.COOKIE_NAME,
                jwtService.issue(userId, userId + "@t.test"))));
    }

    private void modelSays(String... replies) {
        var stub = when(model.complete(anyString(), anyString()));
        for (String reply : replies) {
            stub = stub.thenReturn(new DeskModelClient.Reply(reply, "test-model"));
        }
    }

    private String themesReply() {
        return """
                {"themes": [
                  {"title": "The Builder Who Teaches", "summary": "You build, then you teach.", "traits": ["Maker", "Mentor"],
                   "evidence": [{"quote": "I rebuilt the arm three times before I let the freshmen touch it.", "draftId": %d},
                                {"quote": "I won the state championship.", "draftId": %d}]},
                  {"title": "Invented Thread", "summary": "Not in the drafts.", "traits": ["x"],
                   "evidence": [{"quote": "I founded a startup.", "draftId": %d}]}
                ]}
                """.formatted(draftId, draftId, draftId);
    }

    private long acceptFirstTheme() throws Exception {
        modelSays(themesReply());
        JsonNode body = json.readTree(send(OWNER, post("/api/v1/user/desk/story/themes/generate"))
                .andReturn().getResponse().getContentAsString());
        long id = body.path("data").path("themes").path(0).path("id").asLong();
        send(OWNER, patch("/api/v1/user/desk/story/themes/" + id).contentType(MediaType.APPLICATION_JSON)
                .content("{\"status\": \"accepted\"}")).andExpect(status().isOk());
        return id;
    }

    private long addTarget(long userId, String name, String notes) {
        return jdbc.queryForObject("INSERT INTO desk.target_entity (user_id, custom_name, notes) VALUES (?, ?, ?) RETURNING id",
                Long.class, userId, name, notes);
    }

    @Test
    void keepsOnlyThemesTiedToTheStudentsOwnWords() throws Exception {
        modelSays(themesReply());
        send(OWNER, post("/api/v1/user/desk/story/themes/generate"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.themes", hasSize(1)))
                .andExpect(jsonPath("$.data.themes[0].title").value("The Builder Who Teaches"))
                .andExpect(jsonPath("$.data.themes[0].status").value("suggested"))
                .andExpect(jsonPath("$.data.themes[0].evidence", hasSize(1)))
                .andExpect(jsonPath("$.data.themes[0].evidence[0].refId").value(String.valueOf(draftId)))
                .andExpect(jsonPath("$.data.themes[0].isEstimated").value(true))
                .andExpect(jsonPath("$.data.caveats").value(contains(AnalyticsService.NARRATIVE_ESTIMATE_CAVEAT)));
    }

    @Test
    void needsADraftToWorkFrom() throws Exception {
        send(OTHER_USER, post("/api/v1/user/desk/story/themes/generate")).andExpect(status().isBadRequest());
        verify(model, never()).complete(anyString(), anyString());
    }

    @Test
    void regeneratingReplacesSuggestionsButKeepsAcceptedThemes() throws Exception {
        long accepted = acceptFirstTheme();
        modelSays(themesReply().replace("The Builder Who Teaches", "A Second Look"));
        send(OWNER, post("/api/v1/user/desk/story/themes/generate"))
                .andExpect(jsonPath("$.data.themes[*].title").value(contains("The Builder Who Teaches", "A Second Look")))
                .andExpect(jsonPath("$.data.themes[0].id").value(accepted))
                .andExpect(jsonPath("$.data.themes[0].status").value("accepted"));
    }

    @Test
    void anotherUsersThemeLooksAbsent() throws Exception {
        long theme = acceptFirstTheme();
        send(OTHER_USER, patch("/api/v1/user/desk/story/themes/" + theme).contentType(MediaType.APPLICATION_JSON)
                .content("{\"status\": \"dismissed\"}")).andExpect(status().isNotFound());
        send(OTHER_USER, get("/api/v1/user/desk/story/narrative")).andExpect(jsonPath("$.data.themes", hasSize(0)));
    }

    @Test
    void resonanceDecidesItsOwnBasisAndIgnoresWhatIsNotTheStudents() throws Exception {
        long theme = acceptFirstTheme();
        long withNotes = addTarget(OWNER, "Notes College", "Big on hands-on engineering and peer teaching.");
        long noNotes = addTarget(OWNER, "Quiet University", null);
        long othersSchool = addTarget(OTHER_USER, "Not Yours", "x");
        modelSays("""
                {"resonance": [
                  {"themeId": %d, "targetEntityId": %d, "level": 5, "rationale": "Your notes fit.", "basis": "user_notes"},
                  {"themeId": %d, "targetEntityId": %d, "level": 3, "rationale": "General fit.", "basis": "user_notes"},
                  {"themeId": %d, "targetEntityId": %d, "level": 4, "rationale": "Not theirs.", "basis": "user_notes"},
                  {"themeId": %d, "targetEntityId": %d, "level": 7, "rationale": "Off the scale.", "basis": "user_notes"}
                ]}
                """.formatted(theme, withNotes, theme, noNotes, theme, othersSchool, theme, withNotes));

        send(OWNER, post("/api/v1/user/desk/story/resonance/generate"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.resonance", hasSize(2)))
                .andExpect(jsonPath("$.data.resonance[0].institution").value("Notes College"))
                .andExpect(jsonPath("$.data.resonance[0].institutionBasis").value("user_notes"))
                .andExpect(jsonPath("$.data.resonance[0].levelLabel").value("Strong"))
                .andExpect(jsonPath("$.data.resonance[1].institution").value("Quiet University"))
                // The model said "user_notes"; there are none, so it cannot be.
                .andExpect(jsonPath("$.data.resonance[1].institutionBasis").value("model_general_knowledge"))
                .andExpect(jsonPath("$.data.missingPairs").value(0))
                .andExpect(jsonPath("$.data.caveats").value(contains(
                        AnalyticsService.NARRATIVE_ESTIMATE_CAVEAT, AnalyticsService.RESONANCE_GENERAL_KNOWLEDGE_CAVEAT)));
        assertEquals(0, jdbc.queryForObject(
                "SELECT count(*) FROM desk.entity_resonance WHERE target_entity_id = ?", Long.class, othersSchool));
    }

    @Test
    void resonanceNeedsAnAcceptedThemeAndASchool() throws Exception {
        send(OWNER, post("/api/v1/user/desk/story/resonance/generate")).andExpect(status().isBadRequest());
        acceptFirstTheme();
        send(OWNER, post("/api/v1/user/desk/story/resonance/generate")).andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.error").value("Add a school to your list first."));
    }

    @Test
    void dismissingAThemeDropsItsResonance() throws Exception {
        long theme = acceptFirstTheme();
        long school = addTarget(OWNER, "Notes College", "notes");
        modelSays("""
                {"resonance": [{"themeId": %d, "targetEntityId": %d, "level": 4, "rationale": "Fits.", "basis": "user_notes"}]}
                """.formatted(theme, school));
        send(OWNER, post("/api/v1/user/desk/story/resonance/generate")).andExpect(jsonPath("$.data.resonance", hasSize(1)));
        send(OWNER, patch("/api/v1/user/desk/story/themes/" + theme).contentType(MediaType.APPLICATION_JSON)
                .content("{\"status\": \"dismissed\"}"))
                .andExpect(jsonPath("$.data.themes", hasSize(0)))
                .andExpect(jsonPath("$.data.resonance", hasSize(0)));
    }

    @Test
    void anUnreadableReplyStoresNothing() throws Exception {
        modelSays("Your theme is leadership!", "{\"themes\": \"leadership\"}");
        send(OWNER, post("/api/v1/user/desk/story/themes/generate"))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.code").value("MODEL_REPLY_UNREADABLE"));
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM desk.user_theme WHERE user_id = ?", Long.class, OWNER));
    }

    @Test
    void themesWithNoVerifiableQuoteAreRefusedNotStored() throws Exception {
        modelSays("""
                {"themes": [{"title": "Invented", "summary": "x", "traits": [], "evidence": [{"quote": "Never written.", "draftId": %d}]}]}
                """.formatted(draftId));
        send(OWNER, post("/api/v1/user/desk/story/themes/generate")).andExpect(status().isBadGateway());
        assertEquals(0, jdbc.queryForObject("SELECT count(*) FROM desk.user_theme WHERE user_id = ?", Long.class, OWNER));
    }

    @Test
    void theModelNeverSeesAnotherUsersDraft() throws Exception {
        jdbc.update("""
                INSERT INTO desk.essay_review (user_id, essay_title, draft_text, word_count, draft_sha256, rubric_version,
                    dimension_scores, overall_score, model_name)
                VALUES (?, 'Theirs', 'A secret draft of someone else.', 6, repeat('b', 64), 'essay-rubric-2026.1', '{}', 70, 'm')
                """, OTHER_USER);
        var captured = org.mockito.ArgumentCaptor.forClass(String.class);
        modelSays(themesReply());
        send(OWNER, post("/api/v1/user/desk/story/themes/generate")).andExpect(status().isOk());
        verify(model).complete(anyString(), captured.capture());
        assertTrue(captured.getValue().contains(DRAFT));
        assertTrue(!captured.getValue().contains("A secret draft"));
    }

    @Test
    void needsAToken() throws Exception {
        mvc.perform(get("/api/v1/user/desk/story/narrative")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/user/desk/story/themes")).andExpect(status().isUnauthorized());
        mvc.perform(get("/api/v1/user/desk/story/resonance")).andExpect(status().isUnauthorized());
        mvc.perform(post("/api/v1/user/desk/story/generate")).andExpect(status().isUnauthorized());
        verify(model, never()).complete(anyString(), anyString());
    }

    // ─── The split reads and the documented generate path ─────────────────────

    @Test
    void postGenerateIsTheSameAsThemesGenerate() throws Exception {
        modelSays(themesReply());
        send(OWNER, post("/api/v1/user/desk/story/generate"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.themes", hasSize(1)))
                .andExpect(jsonPath("$.data.themes[0].status").value("suggested"));
    }

    @Test
    void getThemesListsThemesWithTheirCaveatAndNoResonance() throws Exception {
        acceptFirstTheme();
        send(OWNER, get("/api/v1/user/desk/story/themes"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.themes", hasSize(1)))
                .andExpect(jsonPath("$.data.themes[0].title").value("The Builder Who Teaches"))
                .andExpect(jsonPath("$.data.themes[0].status").value("accepted"))
                .andExpect(jsonPath("$.data.themes[0].isEstimated").value(true))
                .andExpect(jsonPath("$.data.resonance").doesNotExist())
                .andExpect(jsonPath("$.data.caveats").value(contains(AnalyticsService.NARRATIVE_ESTIMATE_CAVEAT)));
        send(OTHER_USER, get("/api/v1/user/desk/story/themes")).andExpect(jsonPath("$.data.themes", hasSize(0)));
    }

    @Test
    void getThemesHidesDismissedUnlessAsked() throws Exception {
        long theme = acceptFirstTheme();
        send(OWNER, patch("/api/v1/user/desk/story/themes/" + theme).contentType(MediaType.APPLICATION_JSON)
                .content("{\"status\": \"dismissed\"}"));
        send(OWNER, get("/api/v1/user/desk/story/themes")).andExpect(jsonPath("$.data.themes", hasSize(0)));
        send(OWNER, get("/api/v1/user/desk/story/themes").param("includeDismissed", "true"))
                .andExpect(jsonPath("$.data.themes[0].status").value("dismissed"));
    }

    @Test
    void getResonanceGivesOneToFiveLevelsWithReasonsAndTheScale() throws Exception {
        long theme = acceptFirstTheme();
        long school = addTarget(OWNER, "Notes College", "Hands-on engineering.");
        modelSays("""
                {"resonance": [{"themeId": %d, "targetEntityId": %d, "level": 4, "rationale": "Your notes name hands-on work.", "basis": "user_notes"}]}
                """.formatted(theme, school));
        send(OWNER, post("/api/v1/user/desk/story/resonance/generate")).andExpect(status().isOk());

        send(OWNER, get("/api/v1/user/desk/story/resonance"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.resonance", hasSize(1)))
                .andExpect(jsonPath("$.data.resonance[0].level").value(4))
                .andExpect(jsonPath("$.data.resonance[0].levelLabel").value("Strong"))
                .andExpect(jsonPath("$.data.resonance[0].rationale").value("Your notes name hands-on work."))
                .andExpect(jsonPath("$.data.resonance[0].institutionBasis").value("user_notes"))
                .andExpect(jsonPath("$.data.scale.min").value(1))
                .andExpect(jsonPath("$.data.scale.max").value(5))
                .andExpect(jsonPath("$.data.themes").doesNotExist())
                // From the user's notes: the general-knowledge caveat is not needed.
                .andExpect(jsonPath("$.data.caveats").value(contains(AnalyticsService.NARRATIVE_ESTIMATE_CAVEAT)));
        send(OTHER_USER, get("/api/v1/user/desk/story/resonance")).andExpect(jsonPath("$.data.resonance", hasSize(0)));
    }

    @Test
    void theDatabaseRefusesALevelOffTheScale() {
        long theme = jdbc.queryForObject("""
                INSERT INTO desk.user_theme (user_id, title, summary, evidence, model_name, prompt_version)
                VALUES (?, 't', 's', '[{"kind": "user_note"}]', 'm', 'v1') RETURNING id
                """, Long.class, OWNER);
        long school = addTarget(OWNER, "Any", null);
        for (int level : new int[]{0, 6, 73}) {
            org.junit.jupiter.api.Assertions.assertThrows(org.springframework.dao.DataIntegrityViolationException.class,
                    () -> jdbc.update("""
                            INSERT INTO desk.entity_resonance (user_id, theme_id, target_entity_id, level, rationale,
                                institution_basis, model_name, prompt_version)
                            VALUES (?, ?, ?, ?, 'r', 'user_notes', 'm', 'v1')
                            """, OWNER, theme, school, level));
        }
    }
}
