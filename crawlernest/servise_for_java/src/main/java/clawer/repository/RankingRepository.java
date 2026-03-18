package clawer.repository;

import clawer.model.Ranking;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface RankingRepository extends JpaRepository<Ranking, Long> {
    List<Ranking> findByRankingSource(String rankingSource);
    List<Ranking> findByRankingType(String rankingType);
}
