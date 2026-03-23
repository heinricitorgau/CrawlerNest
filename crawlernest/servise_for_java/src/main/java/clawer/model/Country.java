package clawer.model;

import jakarta.persistence.*;

@Entity
@Table(name = "countries", schema = "warehouse")
public class Country {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "country_id")
    private Long id;

    @Column(name = "country_code", unique = true)
    private String countryCode;

    @Column(name = "country_name", unique = true, nullable = false)
    private String countryName;

    @Column(name = "region_name")
    private String regionName;

    @Column(name = "created_at")
    private String createdAt;

    public Country() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getCountryCode() { return countryCode; }
    public void setCountryCode(String countryCode) { this.countryCode = countryCode; }

    public String getCountryName() { return countryName; }
    public void setCountryName(String countryName) { this.countryName = countryName; }

    public String getRegionName() { return regionName; }
    public void setRegionName(String regionName) { this.regionName = regionName; }
    
    public String getCreatedAt() { return createdAt; }
    public void setCreatedAt(String createdAt) { this.createdAt = createdAt; }
}
