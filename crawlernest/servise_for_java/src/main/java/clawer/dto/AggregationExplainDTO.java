package clawer.dto;

import java.util.LinkedHashMap;
import java.util.Map;

public class AggregationExplainDTO {
    private Map<String, Integer> sources = new LinkedHashMap<>();
    private Map<String, Double> weights = new LinkedHashMap<>();
    private Double aggregatedRankValue;
    private Integer availableSourceCount;
    private String aggregationMethodVersion;
    private Double coverageRatio;
    private Double compositeScore;
    private String note;

    public Map<String, Integer> getSources() {
        return sources;
    }

    public void setSources(Map<String, Integer> sources) {
        this.sources = sources;
    }

    public Map<String, Double> getWeights() {
        return weights;
    }

    public void setWeights(Map<String, Double> weights) {
        this.weights = weights;
    }

    public Double getAggregatedRankValue() {
        return aggregatedRankValue;
    }

    public void setAggregatedRankValue(Double aggregatedRankValue) {
        this.aggregatedRankValue = aggregatedRankValue;
    }

    public Integer getAvailableSourceCount() {
        return availableSourceCount;
    }

    public void setAvailableSourceCount(Integer availableSourceCount) {
        this.availableSourceCount = availableSourceCount;
    }

    public String getAggregationMethodVersion() {
        return aggregationMethodVersion;
    }

    public void setAggregationMethodVersion(String aggregationMethodVersion) {
        this.aggregationMethodVersion = aggregationMethodVersion;
    }

    public Double getCoverageRatio() {
        return coverageRatio;
    }

    public void setCoverageRatio(Double coverageRatio) {
        this.coverageRatio = coverageRatio;
    }

    public Double getCompositeScore() {
        return compositeScore;
    }

    public void setCompositeScore(Double compositeScore) {
        this.compositeScore = compositeScore;
    }

    public String getNote() {
        return note;
    }

    public void setNote(String note) {
        this.note = note;
    }
}
