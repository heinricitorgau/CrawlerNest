package clawer.dto;

public class IdentitySummaryDTO {
    private String canonicalSlug;
    private String status;
    private int aliasCount;
    private Integer countryId;
    private String cityName;
    private String websiteUrl;
    private String matchedBy;
    private String matchedValue;

    public String getCanonicalSlug() {
        return canonicalSlug;
    }

    public void setCanonicalSlug(String canonicalSlug) {
        this.canonicalSlug = canonicalSlug;
    }

    public String getStatus() {
        return status;
    }

    public void setStatus(String status) {
        this.status = status;
    }

    public int getAliasCount() {
        return aliasCount;
    }

    public void setAliasCount(int aliasCount) {
        this.aliasCount = aliasCount;
    }

    public Integer getCountryId() {
        return countryId;
    }

    public void setCountryId(Integer countryId) {
        this.countryId = countryId;
    }

    public String getCityName() {
        return cityName;
    }

    public void setCityName(String cityName) {
        this.cityName = cityName;
    }

    public String getWebsiteUrl() {
        return websiteUrl;
    }

    public void setWebsiteUrl(String websiteUrl) {
        this.websiteUrl = websiteUrl;
    }

    public String getMatchedBy() {
        return matchedBy;
    }

    public void setMatchedBy(String matchedBy) {
        this.matchedBy = matchedBy;
    }

    public String getMatchedValue() {
        return matchedValue;
    }

    public void setMatchedValue(String matchedValue) {
        this.matchedValue = matchedValue;
    }
}
