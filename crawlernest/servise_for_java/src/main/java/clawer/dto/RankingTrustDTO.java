package clawer.dto;

public class RankingTrustDTO {
    private double trustScore;
    private String trustLevel;
    private TrustExplainDTO trustExplain;

    public double getTrustScore() {
        return trustScore;
    }

    public void setTrustScore(double trustScore) {
        this.trustScore = trustScore;
    }

    public String getTrustLevel() {
        return trustLevel;
    }

    public void setTrustLevel(String trustLevel) {
        this.trustLevel = trustLevel;
    }

    public TrustExplainDTO getTrustExplain() {
        return trustExplain;
    }

    public void setTrustExplain(TrustExplainDTO trustExplain) {
        this.trustExplain = trustExplain;
    }
}
