package clawer.api;

import clawer.dto.RankingDTO;
import clawer.service.RankingService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * REST Controller for accessing Ranking data.
 */
@RestController
@RequestMapping("/rankings")
public class RankingController {

    private final RankingService rankingService;

    public RankingController(RankingService rankingService) {
        this.rankingService = rankingService;
    }

    /**
     * Retrieves all rankings across all sources.
     * @return List of RankingDTO objects
     */
    @GetMapping
    public List<RankingDTO> getAllRankings() {
        return rankingService.getAllRankings();
    }

    /**
     * Retrieves rankings from a specific source (e.g., "qs", "the").
     * @param source The ranking source identifier
     * @return List of RankingDTO objects from that source
     */
    @GetMapping("/{source}")
    public List<RankingDTO> getRankingsBySource(@PathVariable String source) {
        return rankingService.getRankingsBySource(source);
    }
}
