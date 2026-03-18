package clawer.service;

import clawer.dto.RankingDTO;
import clawer.model.Ranking;
import clawer.repository.RankingRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.stream.Collectors;

/**
 * Service for handling university rankings business logic.
 */
@Service
public class RankingService {

    private final RankingRepository rankingRepository;

    public RankingService(RankingRepository rankingRepository) {
        this.rankingRepository = rankingRepository;
    }

    public List<RankingDTO> getAllRankings() {
        return rankingRepository.findAll().stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    public List<RankingDTO> getRankingsBySource(String source) {
        return rankingRepository.findByRankingSource(source).stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }
    
    public List<RankingDTO> getRankingsForUniversity(Long universityId) {
        // Since we don't have a direct findByUniversityId (which requires a University object usually),
        // we can fetch via university object if needed or add it to repo.
        // For now, let's assume we want to find by the ID of the university.
        return rankingRepository.findAll().stream()
                .filter(r -> r.getUniversity().getId().equals(universityId))
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    private RankingDTO convertToDTO(Ranking ranking) {
        RankingDTO dto = new RankingDTO();
        dto.setSource(ranking.getRankingSource());
        dto.setType(ranking.getRankingType());
        dto.setYear(ranking.getRankingYear());
        dto.setRankStart(ranking.getRankStart());
        dto.setRankEnd(ranking.getRankEnd());
        dto.setScore(ranking.getScore());
        return dto;
    }
}
