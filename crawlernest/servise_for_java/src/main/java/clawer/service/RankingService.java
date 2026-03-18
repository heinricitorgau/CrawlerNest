package clawer.service;

import clawer.model.Ranking;
import clawer.repository.RankingRepository;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * Service for handling university rankings business logic.
 */
@Service
public class RankingService {

    private final RankingRepository rankingRepository;

    public RankingService(RankingRepository rankingRepository) {
        this.rankingRepository = rankingRepository;
    }

    public List<Ranking> getAllRankings() {
        return rankingRepository.findAll();
    }

    public List<Ranking> getRankingsBySource(String source) {
        return rankingRepository.findBySource(source);
    }
    
    public List<Ranking> getRankingsForUniversity(String universityId) {
        return rankingRepository.findByUniversityId(universityId);
    }
}
