package clawer.dto;

import java.util.List;

public class CanonicalUniversityDetailPreviewDTO {
    private Long canonicalUniversityId;
    private String universityDisplayName;
    private String normalizedUniversityName;
    private List<String> aliases = List.of();
    private IdentitySummaryDTO identitySummary;
    private RankingPreviewSummaryDTO rankingSummary;
    private AdmissionPreviewSummaryDTO admissionSummary;
    private DataAvailabilityDTO dataAvailability;

    public Long getCanonicalUniversityId() {
        return canonicalUniversityId;
    }

    public void setCanonicalUniversityId(Long canonicalUniversityId) {
        this.canonicalUniversityId = canonicalUniversityId;
    }

    public String getUniversityDisplayName() {
        return universityDisplayName;
    }

    public void setUniversityDisplayName(String universityDisplayName) {
        this.universityDisplayName = universityDisplayName;
    }

    public String getNormalizedUniversityName() {
        return normalizedUniversityName;
    }

    public void setNormalizedUniversityName(String normalizedUniversityName) {
        this.normalizedUniversityName = normalizedUniversityName;
    }

    public List<String> getAliases() {
        return aliases;
    }

    public void setAliases(List<String> aliases) {
        this.aliases = aliases;
    }

    public IdentitySummaryDTO getIdentitySummary() {
        return identitySummary;
    }

    public void setIdentitySummary(IdentitySummaryDTO identitySummary) {
        this.identitySummary = identitySummary;
    }

    public RankingPreviewSummaryDTO getRankingSummary() {
        return rankingSummary;
    }

    public void setRankingSummary(RankingPreviewSummaryDTO rankingSummary) {
        this.rankingSummary = rankingSummary;
    }

    public AdmissionPreviewSummaryDTO getAdmissionSummary() {
        return admissionSummary;
    }

    public void setAdmissionSummary(AdmissionPreviewSummaryDTO admissionSummary) {
        this.admissionSummary = admissionSummary;
    }

    public DataAvailabilityDTO getDataAvailability() {
        return dataAvailability;
    }

    public void setDataAvailability(DataAvailabilityDTO dataAvailability) {
        this.dataAvailability = dataAvailability;
    }
}
