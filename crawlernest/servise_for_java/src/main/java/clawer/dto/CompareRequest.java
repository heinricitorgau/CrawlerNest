package clawer.dto;

import java.util.List;

public class CompareRequest {
    private Integer leftUniversityId;
    private Integer rightUniversityId;
    private List<Integer> universityIds;
    private Integer rankingYear;

    public Integer getLeftUniversityId() {
        return leftUniversityId;
    }

    public void setLeftUniversityId(Integer leftUniversityId) {
        this.leftUniversityId = leftUniversityId;
    }

    public Integer getRightUniversityId() {
        return rightUniversityId;
    }

    public void setRightUniversityId(Integer rightUniversityId) {
        this.rightUniversityId = rightUniversityId;
    }

    public List<Integer> getUniversityIds() {
        return universityIds;
    }

    public void setUniversityIds(List<Integer> universityIds) {
        this.universityIds = universityIds;
    }

    public Integer getRankingYear() {
        return rankingYear;
    }

    public void setRankingYear(Integer rankingYear) {
        this.rankingYear = rankingYear;
    }
}
