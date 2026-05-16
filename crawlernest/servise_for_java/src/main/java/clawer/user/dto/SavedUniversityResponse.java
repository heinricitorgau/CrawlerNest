package clawer.user.dto;

import java.time.Instant;

public class SavedUniversityResponse {
    private long canonicalUniversityId;
    private String universityName;
    private String slug;
    private String country;
    private Instant savedAt;

    public long getCanonicalUniversityId() { return canonicalUniversityId; }
    public void setCanonicalUniversityId(long canonicalUniversityId) { this.canonicalUniversityId = canonicalUniversityId; }

    public String getUniversityName() { return universityName; }
    public void setUniversityName(String universityName) { this.universityName = universityName; }

    public String getSlug() { return slug; }
    public void setSlug(String slug) { this.slug = slug; }

    public String getCountry() { return country; }
    public void setCountry(String country) { this.country = country; }

    public Instant getSavedAt() { return savedAt; }
    public void setSavedAt(Instant savedAt) { this.savedAt = savedAt; }
}
