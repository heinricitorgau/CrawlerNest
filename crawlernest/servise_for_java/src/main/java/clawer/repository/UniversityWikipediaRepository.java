package clawer.repository;

import clawer.dto.WikipediaArticleDTO;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.sql.Timestamp;
import java.util.List;
import java.util.Optional;

/** Reads {@code warehouse.university_wikipedia_article}. */
@Repository
public class UniversityWikipediaRepository {
    private static final Logger LOGGER = LoggerFactory.getLogger(UniversityWikipediaRepository.class);

    public static final String LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/";
    /** Sent with every article so each client says the same thing about whose text this is. */
    public static final String NOTICE =
            "This text is from Wikipedia and is not CrawlerNest data. Rankings or figures it quotes are "
                    + "Wikipedia's and can differ from the editions shown on this page.";

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false);
    private static final TypeReference<List<WikipediaArticleDTO.Section>> SECTIONS = new TypeReference<>() {};

    private final JdbcTemplate jdbcTemplate;

    public UniversityWikipediaRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    /**
     * The article matched to this university, or empty when none is held.
     *
     * <p>Empty, with a warning, on a database bootstrapped before the table
     * existed: the page then shows no introduction, which is what it shows for
     * any university without a match.
     */
    public Optional<WikipediaArticleDTO> findByCanonicalUniversityId(Long canonicalUniversityId) {
        if (canonicalUniversityId == null) {
            return Optional.empty();
        }
        Boolean present = jdbcTemplate.queryForObject(
                "SELECT to_regclass('warehouse.university_wikipedia_article') IS NOT NULL", Boolean.class);
        if (present == null || !present) {
            LOGGER.warn("warehouse.university_wikipedia_article is missing; apply crawlernest-schema/wikipedia_article_postgresql.sql");
            return Optional.empty();
        }
        return jdbcTemplate.query("""
                SELECT canonical_university_id, language_code, wikidata_id, page_title, page_url,
                       revision_id, revision_timestamp, match_method, license, fetched_at,
                       sections::text AS sections
                FROM warehouse.university_wikipedia_article
                WHERE canonical_university_id = ?
                """,
                (rs, rowNum) -> {
                    String language = rs.getString("language_code");
                    String title = rs.getString("page_title");
                    long revisionId = rs.getLong("revision_id");
                    return new WikipediaArticleDTO(
                            rs.getLong("canonical_university_id"),
                            language,
                            rs.getString("wikidata_id"),
                            title,
                            rs.getString("page_url"),
                            revisionId,
                            revisionUrl(language, title, revisionId),
                            instant(rs.getTimestamp("revision_timestamp")),
                            rs.getString("match_method"),
                            rs.getString("license"),
                            LICENSE_URL,
                            instant(rs.getTimestamp("fetched_at")),
                            NOTICE,
                            parseSections(rs.getString("sections")));
                },
                canonicalUniversityId).stream().findFirst();
    }

    /** The permanent link to the revision the text was read at, which is what the licence asks a reuser to cite. */
    static String revisionUrl(String language, String title, long revisionId) {
        return "https://" + language + ".wikipedia.org/w/index.php?title="
                + URLEncoder.encode(title.replace(' ', '_'), StandardCharsets.UTF_8) + "&oldid=" + revisionId;
    }

    static List<WikipediaArticleDTO.Section> parseSections(String json) {
        try {
            return MAPPER.readValue(json, SECTIONS);
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("warehouse.university_wikipedia_article.sections is not the expected array", ex);
        }
    }

    private static String instant(Timestamp value) {
        return value == null ? null : value.toInstant().toString();
    }
}
