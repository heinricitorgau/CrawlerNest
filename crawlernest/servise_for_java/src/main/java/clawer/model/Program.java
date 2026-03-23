package clawer.model;

import jakarta.persistence.*;

@Entity
@Table(name = "programs", schema = "warehouse")
public class Program {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "program_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "university_id", nullable = false)
    private University university;

    @Column(name = "program_name", nullable = false)
    private String programName;

    @Column(name = "canonical_program_name")
    private String canonicalProgramName;

    @Column(name = "program_category")
    private String programCategory;

    @Column(name = "department_name")
    private String departmentName;

    @Column(name = "study_field")
    private String studyField;

    @Column(name = "source_url")
    private String sourceUrl;

    public Program() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public University getUniversity() { return university; }
    public void setUniversity(University university) { this.university = university; }

    public String getProgramName() { return programName; }
    public void setProgramName(String programName) { this.programName = programName; }

    public String getCanonicalProgramName() { return canonicalProgramName; }
    public void setCanonicalProgramName(String canonicalProgramName) { this.canonicalProgramName = canonicalProgramName; }

    public String getProgramCategory() { return programCategory; }
    public void setProgramCategory(String programCategory) { this.programCategory = programCategory; }

    public String getDepartmentName() { return departmentName; }
    public void setDepartmentName(String departmentName) { this.departmentName = departmentName; }

    public String getStudyField() { return studyField; }
    public void setStudyField(String studyField) { this.studyField = studyField; }

    public String getSourceUrl() { return sourceUrl; }
    public void setSourceUrl(String sourceUrl) { this.sourceUrl = sourceUrl; }
}
