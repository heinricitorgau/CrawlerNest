package clawer.model;

import java.util.List;
import java.util.Map;

public class UniversityComparisonResult {
    private Map<String, Object> betterUniversity;
    private String summary;
    private List<String> order;
    private Map<String, Object> comparison;

    public UniversityComparisonResult() {
    }

    public UniversityComparisonResult(Map<String, Object> betterUniversity, String summary, List<String> order, Map<String, Object> comparison) {
        this.betterUniversity = betterUniversity;
        this.summary = summary;
        this.order = order;
        this.comparison = comparison;
    }

    public Map<String, Object> getBetterUniversity() {
        return betterUniversity;
    }

    public void setBetterUniversity(Map<String, Object> betterUniversity) {
        this.betterUniversity = betterUniversity;
    }

    public String getSummary() {
        return summary;
    }

    public void setSummary(String summary) {
        this.summary = summary;
    }

    public List<String> getOrder() {
        return order;
    }

    public void setOrder(List<String> order) {
        this.order = order;
    }

    public Map<String, Object> getComparison() {
        return comparison;
    }

    public void setComparison(Map<String, Object> comparison) {
        this.comparison = comparison;
    }
}
