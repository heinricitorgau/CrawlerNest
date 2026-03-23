package clawer.model;

import java.util.List;
import java.util.Map;

public class UniversityComparisonResult {
    private String better;
    private String summary;
    private List<String> order;
    private Map<String, Object> comparison;

    public UniversityComparisonResult() {
    }

    public UniversityComparisonResult(String better, String summary, List<String> order, Map<String, Object> comparison) {
        this.better = better;
        this.summary = summary;
        this.order = order;
        this.comparison = comparison;
    }

    public String getBetter() {
        return better;
    }

    public void setBetter(String better) {
        this.better = better;
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
