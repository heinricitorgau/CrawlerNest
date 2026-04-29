package clawer.repository;

import clawer.dto.SubjectOptionDTO;
import clawer.dto.SubjectRankingDTO;

import java.util.List;
import java.util.Optional;

public interface SubjectRankingRepository {
    List<SubjectOptionDTO> findSubjects();

    boolean subjectExists(String subjectKey);

    Optional<Integer> findLatestYear(String subjectKey, String sourceCode);

    List<SubjectRankingDTO> findSubjectRankings(
            String subjectKey,
            Integer year,
            String sourceCode,
            String country,
            String search,
            int page,
            int pageSize
    );

    long countSubjectRankings(String subjectKey, Integer year, String sourceCode, String country, String search);

    List<SubjectRankingDTO> findUniversitySubjectRankings(Long canonicalUniversityId, Integer year, String sourceCode);
}
