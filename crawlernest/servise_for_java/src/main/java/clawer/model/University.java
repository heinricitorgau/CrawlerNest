package clawer.model;

import jakarta.persistence.*;
import java.util.List;

@Entity
@Table(name = "universities", schema = "warehouse")
public class University {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "university_id")
    private Long id;

    @Column(name = "school_slug", unique = true, nullable = false)
    private String schoolSlug;

    @Column(name = "display_name", nullable = false)
    private String displayName;

    @Column(name = "canonical_name")
    private String canonicalName;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "country_id")
    private Country country;

    @Column(name = "city_name")
    private String cityName;

    @Column(name = "website_url")
    private String websiteUrl;

    @Column(name = "qs_profile_path")
    private String qsProfilePath;

    @OneToMany(mappedBy = "university", fetch = FetchType.LAZY)
    private List<Ranking> rankings;

    @OneToMany(mappedBy = "university", fetch = FetchType.LAZY)
    private List<Program> programs;

    public University() {
    }

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getSchoolSlug() { return schoolSlug; }
    public void setSchoolSlug(String schoolSlug) { this.schoolSlug = schoolSlug; }

    public String getDisplayName() { return displayName; }
    public void setDisplayName(String displayName) { this.displayName = displayName; }

    public String getCanonicalName() { return canonicalName; }
    public void setCanonicalName(String canonicalName) { this.canonicalName = canonicalName; }

    public Country getCountry() { return country; }
    public void setCountry(Country country) { this.country = country; }

    public String getCityName() { return cityName; }
    public void setCityName(String cityName) { this.cityName = cityName; }

    public String getWebsiteUrl() { return websiteUrl; }
    public void setWebsiteUrl(String websiteUrl) { this.websiteUrl = websiteUrl; }

    public String getQsProfilePath() { return qsProfilePath; }
    public void setQsProfilePath(String qsProfilePath) { this.qsProfilePath = qsProfilePath; }

    public List<Ranking> getRankings() { return rankings; }
    public void setRankings(List<Ranking> rankings) { this.rankings = rankings; }

    public List<Program> getPrograms() { return programs; }
    public void setPrograms(List<Program> programs) { this.programs = programs; }
}
