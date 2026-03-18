package clawer.dto;

import java.util.List;

public class UniversityDTO {
    private Long id;
    private String schoolSlug;
    private String displayName;
    private String countryName;
    private String cityName;
    private String websiteUrl;
    private List<RankingDTO> rankings;

    public UniversityDTO() {}

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getSchoolSlug() { return schoolSlug; }
    public void setSchoolSlug(String schoolSlug) { this.schoolSlug = schoolSlug; }

    public String getDisplayName() { return displayName; }
    public void setDisplayName(String displayName) { this.displayName = displayName; }

    public String getCountryName() { return countryName; }
    public void setCountryName(String countryName) { this.countryName = countryName; }

    public String getCityName() { return cityName; }
    public void setCityName(String cityName) { this.cityName = cityName; }

    public String getWebsiteUrl() { return websiteUrl; }
    public void setWebsiteUrl(String websiteUrl) { this.websiteUrl = websiteUrl; }

    public List<RankingDTO> getRankings() { return rankings; }
    public void setRankings(List<RankingDTO> rankings) { this.rankings = rankings; }
}
