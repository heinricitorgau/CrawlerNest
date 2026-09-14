package clawer.dto;

import java.util.List;

public class AdmissionPreviewSummaryDTO {
    private int rowCount;
    private int sourceUrlCount;
    private List<String> countries = List.of();
    private Double bestIeltsRequirement;
    private Integer bestToeflRequirement;
    private String latestExtractedAt;
    private int programmeRowCount;
    private boolean valuesDiffer;

    /** Rows attributed to a named programme or faculty; never part of the best-requirement figures. */
    public int getProgrammeRowCount() {
        return programmeRowCount;
    }

    public void setProgrammeRowCount(int programmeRowCount) {
        this.programmeRowCount = programmeRowCount;
    }

    /** True when university-level rows disagree and the best figures are the lowest of them. */
    public boolean isValuesDiffer() {
        return valuesDiffer;
    }

    public void setValuesDiffer(boolean valuesDiffer) {
        this.valuesDiffer = valuesDiffer;
    }

    public int getRowCount() {
        return rowCount;
    }

    public void setRowCount(int rowCount) {
        this.rowCount = rowCount;
    }

    public int getSourceUrlCount() {
        return sourceUrlCount;
    }

    public void setSourceUrlCount(int sourceUrlCount) {
        this.sourceUrlCount = sourceUrlCount;
    }

    public List<String> getCountries() {
        return countries;
    }

    public void setCountries(List<String> countries) {
        this.countries = countries;
    }

    public Double getBestIeltsRequirement() {
        return bestIeltsRequirement;
    }

    public void setBestIeltsRequirement(Double bestIeltsRequirement) {
        this.bestIeltsRequirement = bestIeltsRequirement;
    }

    public Integer getBestToeflRequirement() {
        return bestToeflRequirement;
    }

    public void setBestToeflRequirement(Integer bestToeflRequirement) {
        this.bestToeflRequirement = bestToeflRequirement;
    }

    public String getLatestExtractedAt() {
        return latestExtractedAt;
    }

    public void setLatestExtractedAt(String latestExtractedAt) {
        this.latestExtractedAt = latestExtractedAt;
    }
}
