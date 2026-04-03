package clawer.model;

public class RecommendationExplainDimensions {
    private Double rankingFit;
    private Double riskFit;
    private Double languageFit;
    private Double dataConfidence;

    public Double getRankingFit() {
        return rankingFit;
    }

    public void setRankingFit(Double rankingFit) {
        this.rankingFit = rankingFit;
    }

    public Double getRiskFit() {
        return riskFit;
    }

    public void setRiskFit(Double riskFit) {
        this.riskFit = riskFit;
    }

    public Double getLanguageFit() {
        return languageFit;
    }

    public void setLanguageFit(Double languageFit) {
        this.languageFit = languageFit;
    }

    public Double getDataConfidence() {
        return dataConfidence;
    }

    public void setDataConfidence(Double dataConfidence) {
        this.dataConfidence = dataConfidence;
    }
}
