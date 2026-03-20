package clawer.dto;

public class AdmissionDTO {

    private Long id;
    private Long universityId;
    private String universityName;
    private Double gpaMin;
    private Double ieltsMin;
    private Double toeflMin;
    private Double greMin;
    private Double gmatMin;

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getUniversityId() {
        return universityId;
    }

    public void setUniversityId(Long universityId) {
        this.universityId = universityId;
    }

    public String getUniversityName() {
        return universityName;
    }

    public void setUniversityName(String universityName) {
        this.universityName = universityName;
    }

    public Double getGpaMin() {
        return gpaMin;
    }

    public void setGpaMin(Double gpaMin) {
        this.gpaMin = gpaMin;
    }

    public Double getIeltsMin() {
        return ieltsMin;
    }

    public void setIeltsMin(Double ieltsMin) {
        this.ieltsMin = ieltsMin;
    }

    public Double getToeflMin() {
        return toeflMin;
    }

    public void setToeflMin(Double toeflMin) {
        this.toeflMin = toeflMin;
    }

    public Double getGreMin() {
        return greMin;
    }

    public void setGreMin(Double greMin) {
        this.greMin = greMin;
    }

    public Double getGmatMin() {
        return gmatMin;
    }

    public void setGmatMin(Double gmatMin) {
        this.gmatMin = gmatMin;
    }
}
