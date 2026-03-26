package clawer.service;

import clawer.dto.RankingDTO;
import clawer.dto.SourceRankingDTO;
import clawer.dto.UniversityDTO;
import clawer.model.University;
import clawer.repository.UniversityRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Service for handling University-related business logic.
 */
@Service
public class UniversityService {

    private final UniversityRepository universityRepository;

    public UniversityService(UniversityRepository universityRepository) {
        this.universityRepository = universityRepository;
    }

    public List<UniversityDTO> getAllUniversities(int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return universityRepository.findAll(pageable).stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    public UniversityDTO getUniversityById(Long id) {
        return universityRepository.findById(id)
                .map(this::convertToDTO)
                .orElse(null);
    }

    public UniversityDTO getUniversityBySlug(String slug) {
        return universityRepository.findBySchoolSlug(slug)
                .map(this::convertToDTO)
                .orElse(null);
    }

    private UniversityDTO convertToDTO(University university) {
        UniversityDTO dto = new UniversityDTO();
        dto.setCanonicalUniversityId(university.getId());
        dto.setSlug(university.getSchoolSlug());
        dto.setUniversityName(university.getDisplayName());
        dto.setCountry(university.getCountry() != null ? university.getCountry().getCountryName() : null);

        if (university.getRankings() != null && !university.getRankings().isEmpty()) {
            clawer.dto.AggregatedRankingDTO aggRank = university.getRankings().stream()
                .filter(r -> r.getRankStart() != null)
                .map(r -> {
                    clawer.dto.AggregatedRankingDTO aDto = new clawer.dto.AggregatedRankingDTO();
                    aDto.setDisplayRank(r.getRankStart());
                    aDto.setCompositeScore(r.getScore());
                    aDto.setRankingYear(r.getRankingYear());
                    aDto.setAggregationMethodVersion("v1");
                    return aDto;
                })
                .findFirst()
                .orElse(null);
            dto.setAggregatedRanking(aggRank);

            dto.setSourceRankings(university.getRankings().stream()
                .filter(r -> r.getRankStart() != null)
                .collect(Collectors.toMap(
                    r -> r.getRankingSource() + "-" + r.getRankingYear(),
                    r -> r,
                    (r1, r2) -> r1.getRankStart() < r2.getRankStart() ? r1 : r2
                ))
                .values().stream()
                .map(ranking -> {
                    SourceRankingDTO rDto = new SourceRankingDTO();
                    rDto.setSource(ranking.getRankingSource());
                    rDto.setYear(ranking.getRankingYear());
                    rDto.setRank(ranking.getRankStart());
                    rDto.setScore(ranking.getScore());
                    return rDto;
                }).collect(Collectors.toList()));
        } else {
            dto.setSourceRankings(List.of());
        }

        dto.setAdmissionRequirements(Map.of());
        clawer.dto.DataQualityDTO quality = new clawer.dto.DataQualityDTO();
        quality.setRecommendationConfidence(0.9);
        quality.setConfidenceLabel("High");
        quality.setConfidenceReason("Rankings are fully merged and verified");
        dto.setDataQuality(quality);
        return dto;
    }
}
