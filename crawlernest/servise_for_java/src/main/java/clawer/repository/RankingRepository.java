package clawer.repository;

import clawer.model.Ranking;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface RankingRepository extends JpaRepository<Ranking, Long> {
    List<Ranking> findByRankingSource(String rankingSource);
    Page<Ranking> findByRankingSource(String rankingSource, Pageable pageable);
    List<Ranking> findByRankingType(String rankingType);
    List<Ranking> findByUniversity_Id(Long universityId);
}
