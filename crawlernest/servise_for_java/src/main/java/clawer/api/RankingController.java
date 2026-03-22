package clawer.api;

import clawer.dto.RankingDTO;
import clawer.service.RankingService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestParam;
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
    public List<RankingDTO> getAllRankings(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size
    ) {
        int safePage = Math.max(page, 0);
        int safeSize = Math.min(Math.max(size, 1), 100);
        return rankingService.getAllRankings(safePage, safeSize);
    }

    /**
     * Retrieves rankings from a specific source (e.g., "qs", "the").
     * @param source The ranking source identifier
     * @return List of RankingDTO objects from that source
     */
    @GetMapping("/{source}")
    public List<RankingDTO> getRankingsBySource(
            @PathVariable String source,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size
    ) {
        int safePage = Math.max(page, 0);
        int safeSize = Math.min(Math.max(size, 1), 100);
        return rankingService.getRankingsBySource(source, safePage, safeSize);
    }
}
