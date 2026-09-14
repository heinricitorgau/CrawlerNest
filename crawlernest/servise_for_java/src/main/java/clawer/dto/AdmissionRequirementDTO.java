package clawer.dto;

/**
 * Entry requirements from {@code warehouse.admission_record}: either one degree
 * level's university-level requirements, or one programme's.
 *
 * <p>Every requirement is nullable on purpose. A crawled admission page often
 * publishes a TOEFL score and no IELTS score, or a deadline and no GPA bar, and
 * the warehouse stores that gap as NULL rather than inventing a value. Callers
 * must treat null as "not published by the source", never as zero.
 *
 * <p>{@code requirementScope} says what the numbers apply to:
 * {@code institution_minimum} (a stated floor for every programme),
 * {@code unspecified} (one figure whose scope the page did not establish),
 * {@code programme} or {@code faculty} (named in {@code programmeName} /
 * {@code faculty}). A university-level entry is never built from programme rows;
 * see {@code warehouse.v_admission_requirement_institution}.
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
    private String requirementScope;
    private String faculty;
    private String programmeName;
    private Integer intakeYear;
    private String intakeYearBasis;
    private Boolean valuesDiffer;

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

    public String getRequirementScope() { return requirementScope; }
    public void setRequirementScope(String requirementScope) { this.requirementScope = requirementScope; }

    public String getFaculty() { return faculty; }
    public void setFaculty(String faculty) { this.faculty = faculty; }

    public String getProgrammeName() { return programmeName; }
    public void setProgrammeName(String programmeName) { this.programmeName = programmeName; }

    /** The intake these requirements are for, or null when no source stated or implied one. */
    public Integer getIntakeYear() { return intakeYear; }
    public void setIntakeYear(Integer intakeYear) { this.intakeYear = intakeYear; }

    /** {@code page_stated}, {@code deadline_inferred} or {@code unknown}. */
    public String getIntakeYearBasis() { return intakeYearBasis; }
    public void setIntakeYearBasis(String intakeYearBasis) { this.intakeYearBasis = intakeYearBasis; }

    /**
     * True when several university-level rows for this entry disagree and the
     * lowest bar is shown. Null on programme entries and on the cross-level summary.
     */
    public Boolean getValuesDiffer() { return valuesDiffer; }
    public void setValuesDiffer(Boolean valuesDiffer) { this.valuesDiffer = valuesDiffer; }
}
