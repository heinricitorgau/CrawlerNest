package clawer.dto;

import java.util.List;

public class UniversityDTO {
    private Long canonicalUniversityId;
    private String slug;
    private String universityName;
    private String country;
    private AggregatedRankingDTO aggregatedRanking;
    private List<SourceRankingDTO> sourceRankings;
    private List<SourceRankingDTO> rankingEvidence;
    private AdmissionRequirementsDTO admissionRequirements;
    private DataQualityDTO dataQuality;

    public UniversityDTO() {}

    public Long getCanonicalUniversityId() { return canonicalUniversityId; }
    public void setCanonicalUniversityId(Long canonicalUniversityId) { this.canonicalUniversityId = canonicalUniversityId; }

    public String getSlug() { return slug; }
    public void setSlug(String slug) { this.slug = slug; }

    public String getUniversityName() { return universityName; }
    public void setUniversityName(String universityName) { this.universityName = universityName; }

    public String getCountry() { return country; }
    public void setCountry(String country) { this.country = country; }

    public AggregatedRankingDTO getAggregatedRanking() { return aggregatedRanking; }
    public void setAggregatedRanking(AggregatedRankingDTO aggregatedRanking) { this.aggregatedRanking = aggregatedRanking; }

    public List<SourceRankingDTO> getSourceRankings() { return sourceRankings; }
    public void setSourceRankings(List<SourceRankingDTO> sourceRankings) { this.sourceRankings = sourceRankings; }

    public List<SourceRankingDTO> getRankingEvidence() { return rankingEvidence; }
    public void setRankingEvidence(List<SourceRankingDTO> rankingEvidence) { this.rankingEvidence = rankingEvidence; }

    public AdmissionRequirementsDTO getAdmissionRequirements() { return admissionRequirements; }
    public void setAdmissionRequirements(AdmissionRequirementsDTO admissionRequirements) { this.admissionRequirements = admissionRequirements; }

    public DataQualityDTO getDataQuality() { return dataQuality; }
    public void setDataQuality(DataQualityDTO dataQuality) { this.dataQuality = dataQuality; }
}
