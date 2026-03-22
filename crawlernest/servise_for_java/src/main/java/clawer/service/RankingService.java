package clawer.service;

import clawer.dto.RankingDTO;
import clawer.model.Ranking;
import clawer.repository.RankingRepository;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
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

    public List<RankingDTO> getAllRankings(int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return rankingRepository.findAll(pageable).stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }

    public List<RankingDTO> getRankingsBySource(String source, int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return rankingRepository.findByRankingSource(source, pageable).stream()
                .map(this::convertToDTO)
                .collect(Collectors.toList());
    }
    
    public List<RankingDTO> getRankingsForUniversity(Long universityId) {
        return rankingRepository.findByUniversity_Id(universityId).stream()
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
