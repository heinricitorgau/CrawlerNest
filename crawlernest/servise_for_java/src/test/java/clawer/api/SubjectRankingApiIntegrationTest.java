package clawer.api;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlGroup;
import org.springframework.test.web.servlet.MockMvc;

import org.springframework.beans.factory.annotation.Autowired;

import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.hasItems;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest
@AutoConfigureMockMvc
@SqlGroup({
        @Sql(
                scripts = {
                        "classpath:sql/rankings_integration_setup.sql",
                        "classpath:sql/rankings_integration_seed.sql",
                        "classpath:sql/subject_rankings_integration_setup.sql",
                        "classpath:sql/subject_rankings_integration_seed.sql"
                },
                executionPhase = Sql.ExecutionPhase.BEFORE_TEST_METHOD
        ),
        @Sql(
                scripts = {
                        "classpath:sql/subject_rankings_integration_cleanup.sql",
                        "classpath:sql/rankings_integration_cleanup.sql"
                },
                executionPhase = Sql.ExecutionPhase.AFTER_TEST_METHOD
        )
})
class SubjectRankingApiIntegrationTest {
    @Autowired
    private MockMvc mockMvc;

    @Test
    void subjectsListReturnsSupportedSubjects() throws Exception {
        mockMvc.perform(get("/api/v1/subject-rankings/subjects")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON))
                .andExpect(jsonPath("$.success").value(true))
                // Assert the supported subjects by slug, not by count: this endpoint returns every
                // active row in warehouse.ranking_subject, so a bare count neither identifies which
                // subjects came back nor survives a new subject being added.
                .andExpect(jsonPath("$.data.items[*].subjectKey",
                        hasItems("business-management", "computer-science", "electrical-engineering")))
                .andExpect(jsonPath("$.data.items[?(@.subjectKey == 'business-management')].subjectName",
                        contains("Business & Management")))
                .andExpect(jsonPath("$.data.items[?(@.subjectKey == 'computer-science')].subjectName",
                        contains("Computer Science")))
                .andExpect(jsonPath("$.data.items[?(@.subjectKey == 'electrical-engineering')].subjectName",
                        contains("Electrical Engineering")));
    }

    @Test
    void subjectQueryReturnsSortedRowsAndMetadata() throws Exception {
        mockMvc.perform(get("/api/v1/subject-rankings")
                        .param("subject", "computer-science")
                        .param("year", "2099")
                        .param("page", "1")
                        .param("pageSize", "20")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.metadata.totalCount").value(3))
                .andExpect(jsonPath("$.data.metadata.subject").value("computer-science"))
                .andExpect(jsonPath("$.data.metadata.year").value(2099))
                .andExpect(jsonPath("$.data.items[0].canonicalUniversityId").value(990002))
                .andExpect(jsonPath("$.data.items[0].universityName").value("Massachusetts Institute of Technology"))
                .andExpect(jsonPath("$.data.items[0].rankPosition").value(1))
                .andExpect(jsonPath("$.data.items[0].rankDisplay").value("1"))
                .andExpect(jsonPath("$.data.items[0].score").value(96.7))
                .andExpect(jsonPath("$.data.items[0].sourceCode").value("QS"));
    }

    @Test
    void subjectPathShortcutMatchesQueryEndpoint() throws Exception {
        mockMvc.perform(get("/api/v1/subject-rankings/computer-science")
                        .param("year", "2099")
                        .param("pageSize", "1")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.items.length()").value(1))
                .andExpect(jsonPath("$.data.items[0].subjectKey").value("computer-science"));
    }

    @Test
    void paginationUsesStrictLimitAndOffset() throws Exception {
        mockMvc.perform(get("/api/v1/subject-rankings")
                        .param("subject", "computer-science")
                        .param("year", "2099")
                        .param("page", "2")
                        .param("pageSize", "1")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.metadata.page").value(2))
                .andExpect(jsonPath("$.data.metadata.pageSize").value(1))
                .andExpect(jsonPath("$.data.metadata.totalCount").value(3))
                .andExpect(jsonPath("$.data.items.length()").value(1))
                .andExpect(jsonPath("$.data.items[0].universityName").value("Delft University of Technology"));
    }

    @Test
    void countryFilterUsesCanonicalCountryName() throws Exception {
        mockMvc.perform(get("/api/v1/subject-rankings")
                        .param("subject", "computer-science")
                        .param("year", "2099")
                        .param("country", "United States")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.metadata.totalCount").value(1))
                .andExpect(jsonPath("$.data.items[0].countryName").value("United States"));
    }

    @Test
    void searchFilterMatchesUniversityName() throws Exception {
        mockMvc.perform(get("/api/v1/subject-rankings")
                        .param("subject", "computer-science")
                        .param("year", "2099")
                        .param("search", "Delft")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.metadata.totalCount").value(1))
                .andExpect(jsonPath("$.data.items[0].universityName").value("Delft University of Technology"));
    }

    @Test
    void invalidSubjectReturnsBadRequest() throws Exception {
        mockMvc.perform(get("/api/v1/subject-rankings")
                        .param("subject", "mathematics")
                        .param("year", "2099")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.success").value(false))
                .andExpect(jsonPath("$.data.items.length()").value(0))
                .andExpect(jsonPath("$.data.error").value("Unsupported subject."));
    }

    @Test
    void universitySubjectRankingsReturnsRowsForUniversity() throws Exception {
        mockMvc.perform(get("/api/v1/universities/990002/subject-rankings")
                        .param("year", "2099")
                        .accept(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.success").value(true))
                .andExpect(jsonPath("$.data.metadata.totalCount").value(2))
                .andExpect(jsonPath("$.data.items[0].canonicalUniversityId").value(990002));
    }
}
