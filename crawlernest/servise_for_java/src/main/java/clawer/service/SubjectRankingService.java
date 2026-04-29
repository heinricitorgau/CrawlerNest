package clawer.service;

import clawer.dto.SubjectOptionDTO;
import clawer.dto.SubjectRankingDTO;
import clawer.repository.SubjectRankingRepository;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Service
public class SubjectRankingService {
    private static final int DEFAULT_PAGE_SIZE = 20;
    private static final int MAX_PAGE_SIZE = 100;

    private final SubjectRankingRepository subjectRankingRepository;

    public SubjectRankingService(SubjectRankingRepository subjectRankingRepository) {
        this.subjectRankingRepository = subjectRankingRepository;
    }

    public List<SubjectOptionDTO> getSubjects() {
        return subjectRankingRepository.findSubjects();
    }

    public Map<String, Object> getSubjectRankings(
            String subjectKey,
            Integer year,
            String source,
            String country,
            String search,
            Integer page,
            Integer pageSize
    ) {
        String safeSubject = validateSubject(subjectKey);
        String safeSource = normalizeSource(source);
        Integer resolvedYear = resolveYear(safeSubject, safeSource, year);
        int safePage = Math.max(page == null ? 1 : page, 1);
        int safePageSize = Math.min(Math.max(pageSize == null ? DEFAULT_PAGE_SIZE : pageSize, 1), MAX_PAGE_SIZE);
        String safeCountry = trimToNull(country);
        String safeSearch = trimToNull(search);

        List<SubjectRankingDTO> items = subjectRankingRepository.findSubjectRankings(
                safeSubject,
                resolvedYear,
                safeSource,
                safeCountry,
                safeSearch,
                safePage - 1,
                safePageSize
        );
        long totalCount = subjectRankingRepository.countSubjectRankings(
                safeSubject,
                resolvedYear,
                safeSource,
                safeCountry,
                safeSearch
        );

        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("page", safePage);
        metadata.put("pageSize", safePageSize);
        metadata.put("totalCount", totalCount);
        metadata.put("subject", safeSubject);
        metadata.put("year", resolvedYear);
        metadata.put("source", safeSource);

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("items", items);
        data.put("metadata", metadata);
        return data;
    }

    public Map<String, Object> getUniversitySubjectRankings(Long canonicalUniversityId, Integer year, String source) {
        if (canonicalUniversityId == null || canonicalUniversityId <= 0) {
            throw new IllegalArgumentException("canonical university id must be positive.");
        }
        String safeSource = normalizeSource(source);
        List<SubjectRankingDTO> items = subjectRankingRepository.findUniversitySubjectRankings(
                canonicalUniversityId,
                year,
                safeSource
        );
        Map<String, Object> metadata = new LinkedHashMap<>();
        metadata.put("canonicalUniversityId", canonicalUniversityId);
        metadata.put("year", year);
        metadata.put("source", safeSource);
        metadata.put("totalCount", items.size());

        Map<String, Object> data = new LinkedHashMap<>();
        data.put("items", items);
        data.put("metadata", metadata);
        return data;
    }

    private String validateSubject(String subjectKey) {
        String safeSubject = trimToNull(subjectKey);
        if (safeSubject == null) {
            throw new IllegalArgumentException("subject is required.");
        }
        if (!subjectRankingRepository.subjectExists(safeSubject)) {
            throw new IllegalArgumentException("Unsupported subject.");
        }
        return safeSubject;
    }

    private Integer resolveYear(String subjectKey, String source, Integer requestedYear) {
        if (requestedYear != null) {
            return requestedYear;
        }
        return subjectRankingRepository.findLatestYear(subjectKey, source)
                .orElseThrow(() -> new IllegalArgumentException("No subject ranking year is available."));
    }

    private String normalizeSource(String source) {
        String safeSource = trimToNull(source);
        if (safeSource == null) {
            return "QS";
        }
        if (!"QS".equalsIgnoreCase(safeSource)) {
            throw new IllegalArgumentException("Only source=QS is supported for subject rankings.");
        }
        return "QS";
    }

    private String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }
}
