package clawer.model;

/**
 * Represents a University in the Clawer Education Data Platform.
 * Features various metrics used for recommendations and rankings.
 */
public class University {
    private String id;
    private String name;
    private String country;
    private Integer ranking;
    private String subject;
    private Double admissionScore;
    private Double tuition;

    public University() {
    }

    public University(String id, String name, String country, Integer ranking, String subject, Double admissionScore, Double tuition) {
        this.id = id;
        this.name = name;
        this.country = country;
        this.ranking = ranking;
        this.subject = subject;
        this.admissionScore = admissionScore;
        this.tuition = tuition;
    }

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getCountry() { return country; }
    public void setCountry(String country) { this.country = country; }

    public Integer getRanking() { return ranking; }
    public void setRanking(Integer ranking) { this.ranking = ranking; }

    public String getSubject() { return subject; }
    public void setSubject(String subject) { this.subject = subject; }

    public Double getAdmissionScore() { return admissionScore; }
    public void setAdmissionScore(Double admissionScore) { this.admissionScore = admissionScore; }

    public Double getTuition() { return tuition; }
    public void setTuition(Double tuition) { this.tuition = tuition; }
}
