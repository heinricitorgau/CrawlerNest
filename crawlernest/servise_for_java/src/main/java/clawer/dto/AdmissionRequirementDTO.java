package clawer.dto;

/**
 * One university's entry requirements for a single degree level, read straight
 * from the structured columns of {@code warehouse.admission_record}.
 *
 * <p>Every requirement is nullable on purpose. A crawled admission page often
 * publishes a TOEFL score and no IELTS score, or a deadline and no GPA bar, and
 * the warehouse stores that gap as NULL rather than inventing a value. Callers
 * must treat null as "not published by the source", never as zero.
 *
 * <p>Not to be confused with {@code clawer.model.AdmissionRequirement}, the JPA
 * entity for the older {@code warehouse.admission_requirements} table.
 */
public class AdmissionRequirementDTO {

    private String degreeLevel;
    private Double ieltsRequirement;
    private Integer toeflRequirement;
    private Integer duolingoRequirement;
    private Double gpaRequirement;
    private String applicationDeadline;
    private String sourceUrl;

    public String getDegreeLevel() { return degreeLevel; }
    public void setDegreeLevel(String degreeLevel) { this.degreeLevel = degreeLevel; }

    public Double getIeltsRequirement() { return ieltsRequirement; }
    public void setIeltsRequirement(Double ieltsRequirement) { this.ieltsRequirement = ieltsRequirement; }

    public Integer getToeflRequirement() { return toeflRequirement; }
    public void setToeflRequirement(Integer toeflRequirement) { this.toeflRequirement = toeflRequirement; }

    public Integer getDuolingoRequirement() { return duolingoRequirement; }
    public void setDuolingoRequirement(Integer duolingoRequirement) { this.duolingoRequirement = duolingoRequirement; }

    public Double getGpaRequirement() { return gpaRequirement; }
    public void setGpaRequirement(Double gpaRequirement) { this.gpaRequirement = gpaRequirement; }

    /** ISO-8601 date ({@code yyyy-MM-dd}), or null when the source published none. */
    public String getApplicationDeadline() { return applicationDeadline; }
    public void setApplicationDeadline(String applicationDeadline) { this.applicationDeadline = applicationDeadline; }

    public String getSourceUrl() { return sourceUrl; }
    public void setSourceUrl(String sourceUrl) { this.sourceUrl = sourceUrl; }
}
