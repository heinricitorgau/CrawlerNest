package clawer.dto;

import java.util.List;

public class DataAvailabilityDTO {
    private boolean hasRankingData;
    private boolean hasAdmissionData;
    private List<String> missingSections = List.of();

    public boolean isHasRankingData() {
        return hasRankingData;
    }

    public void setHasRankingData(boolean hasRankingData) {
        this.hasRankingData = hasRankingData;
    }

    public boolean isHasAdmissionData() {
        return hasAdmissionData;
    }

    public void setHasAdmissionData(boolean hasAdmissionData) {
        this.hasAdmissionData = hasAdmissionData;
    }

    public List<String> getMissingSections() {
        return missingSections;
    }

    public void setMissingSections(List<String> missingSections) {
        this.missingSections = missingSections;
    }
}
