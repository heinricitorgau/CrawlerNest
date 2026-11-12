package clawer.security;

import clawer.auth.jwt.JwtCookieAuthenticationFilter;
import clawer.auth.jwt.JwtService;
import clawer.desk.model.DeskModelClient;
import clawer.service.AnalyticsService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.Cookie;
import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.annotation.DirtiesContext;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.ResultActions;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasSize;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;

/**
 * The model budget through the real filter chain: a real token, the real essay endpoint, a stubbed model. Past the
 * budget the answer is 429 and the model is not called.
 */
@SpringBootTest
@AutoConfigureMockMvc
// The minute's budget lives in the RateLimits bean; a fresh context per test keeps one test's spends out of the next.
@DirtiesContext(classMode = DirtiesContext.ClassMode.AFTER_EACH_TEST_METHOD)
@TestPropertySource(properties = {
        "crawlernest.jwt.secret=an-integration-test-secret-long-enough-for-hs256",
        "crawlernest.rate-limit.model-calls-per-minute=4",
        "crawlernest.rate-limit.model-calls-per-day=100"
})
@SqlGroup({
        @Sql(scripts = {"classpath:sql/desk_integration_setup.sql", "classpath:sql/desk_integration_seed.sql"},
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD),
        @Sql(scripts = "classpath:sql/desk_integration_cleanup.sql",
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD)
})
class ModelCallBudgetIntegrationTest {

    private static final long OWNER = 990401L;
    private static final long OTHER_USER = 990402L;
    private static final String BODY = "{\"essayTitle\": \"Personal statement\", \"draftText\": "
            + "\"The first time the robot arm failed, I blamed the motor. I learned that failure is part of engineering.\"}";
    private static final String REPLY = """
            {"dimensions": {
              "impact": {"score": 80, "rationale": "Concrete stakes.", "evidence": ["I blamed the motor."]},
              "introspection": {"score": 64, "rationale": "States the lesson.", "evidence": []},
              "passion": {"score": 78, "rationale": "Time spent.", "evidence": []},
              "originality": {"score": 71, "rationale": "Specific.", "evidence": []}
            },
            "suggestions": []}
            """;

    @Autowired
    private MockMvc mvc;

    @Autowired
    private JwtService jwtService;

    @Autowired
    private JdbcTemplate jdbc;

    @MockBean
    private DeskModelClient model;

    private ResultActions evaluate(Long userId) throws Exception {
        var request = post("/api/v1/user/desk/essays/evaluate").contentType(MediaType.APPLICATION_JSON).content(BODY);
        if (userId != null) {
            request = request.cookie(new Cookie(JwtCookieAuthenticationFilter.COOKIE_NAME,
                    jwtService.issue(userId, userId + "@t.test")));
        }
        return mvc.perform(request);
    }

    @Test
    void pastTheBudgetTheAnswerIs429AndTheModelIsNotCalled() throws Exception {
        when(model.complete(anyString(), anyString())).thenReturn(new DeskModelClient.Reply(REPLY, "test-model"));

        // An evaluation may make two model calls, so it costs 2 of the 4 a minute.
        evaluate(OWNER).andExpect(status().isOk()).andExpect(header().string("X-Model-Calls-Left-Today", "98"));
        // The minute holds what a request may cost, up front. The day counts calls actually made (desk.model_call),
        // and this stubbed model makes none, so the day's figure settles back.
        evaluate(OWNER).andExpect(status().isOk()).andExpect(header().string("X-Model-Calls-Left-Today", "98"));
        int callsBeforeRefusal = org.mockito.Mockito.mockingDetails(model).getInvocations().size();
        evaluate(OWNER).andExpect(status().isTooManyRequests())
                .andExpect(header().exists("Retry-After"))
                .andExpect(jsonPath("$.success").value(false));
        org.junit.jupiter.api.Assertions.assertEquals(callsBeforeRefusal,
                org.mockito.Mockito.mockingDetails(model).getInvocations().size(), "a refused request reached the model");

        // The budget is the account's: another user is unaffected, and an anonymous caller is simply not signed in.
        evaluate(OTHER_USER).andExpect(status().isOk());
        evaluate(null).andExpect(status().isUnauthorized());
        verify(model, times(callsBeforeRefusal + 1)).complete(anyString(), anyString());
    }

    @Test
    void theDayIsCountedFromTheLedgerSoARestartDoesNotResetIt() throws Exception {
        // 99 calls this user made an hour ago and earlier -- as a previous process, or another instance, saw them --
        // and 10 the provider never answered, which do not count.
        Instant now = Instant.now();
        for (int i = 0; i < 99; i++) {
            insertCall(OWNER, "ok", now.minus(Duration.ofHours(1)).minusSeconds(99 - i));
        }
        for (int i = 0; i < 10; i++) {
            insertCall(OWNER, "unreachable", now.minus(Duration.ofMinutes(5)));
        }

        // An evaluation may make 2; 99 + 2 > 100. It fits once the oldest call leaves the day, ~23 hours from now.
        String retryAfter = evaluate(OWNER).andExpect(status().isTooManyRequests())
                .andExpect(header().string("X-Model-Calls-Left-Today", "1"))
                .andReturn().getResponse().getHeader("Retry-After");
        verify(model, never()).complete(anyString(), anyString());
        long seconds = Long.parseLong(retryAfter);
        org.junit.jupiter.api.Assertions.assertTrue(seconds > 22 * 3600 && seconds <= 23 * 3600,
                "Retry-After " + seconds + " should be when the oldest call leaves the day");

        // The usage endpoint reads the same rows, and only the caller's own.
        mvc.perform(get("/api/v1/user/desk/usage").cookie(cookie(OWNER)))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.last24Hours.modelCalls").value(99))
                .andExpect(jsonPath("$.data.last24Hours.unreachableCalls").value(10))
                .andExpect(jsonPath("$.data.budget.modelCallsPerDay").value(100))
                .andExpect(jsonPath("$.data.budget.modelCallsLeft").value(1))
                .andExpect(jsonPath("$.data.budget.reservedPerRequest['/api/v1/user/desk/chat/message']").value(4));
        mvc.perform(get("/api/v1/user/desk/usage").cookie(cookie(OTHER_USER)))
                .andExpect(jsonPath("$.data.last24Hours.modelCalls").value(0));
        mvc.perform(get("/api/v1/user/desk/usage")).andExpect(status().isUnauthorized());
    }

    private Cookie cookie(long userId) {
        return new Cookie(JwtCookieAuthenticationFilter.COOKIE_NAME, jwtService.issue(userId, userId + "@t.test"));
    }

    private void insertCall(long userId, String outcome, Instant at) {
        jdbc.update("INSERT INTO desk.model_call (user_id, endpoint, outcome, called_at) VALUES (?, ?, ?, ?)",
                userId, "/api/v1/user/desk/essays/evaluate", outcome, Timestamp.from(at));
    }
}
