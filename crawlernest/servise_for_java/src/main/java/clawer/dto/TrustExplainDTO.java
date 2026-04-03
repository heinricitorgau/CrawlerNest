package clawer.dto;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class TrustExplainDTO {
    private Map<String, Integer> sources = new LinkedHashMap<>();
    private double coverageScore;
    private double consistencyScore;
    private double stdDeviation;
    private List<String> notes = List.of();

    public Map<String, Integer> getSources() {
        return sources;
    }

    public void setSources(Map<String, Integer> sources) {
        this.sources = sources;
    }

    public double getCoverageScore() {
        return coverageScore;
    }

    public void setCoverageScore(double coverageScore) {
        this.coverageScore = coverageScore;
    }

    public double getConsistencyScore() {
        return consistencyScore;
    }

    public void setConsistencyScore(double consistencyScore) {
        this.consistencyScore = consistencyScore;
    }

    public double getStdDeviation() {
        return stdDeviation;
    }

    public void setStdDeviation(double stdDeviation) {
        this.stdDeviation = stdDeviation;
    }

    public List<String> getNotes() {
        return notes;
    }

    public void setNotes(List<String> notes) {
        this.notes = notes;
    }
}
