package clawer.model;

import jakarta.persistence.*;

@Entity
@Table(name = "admission_requirements")
public class AdmissionRequirement {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "requirement_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "university_id", nullable = false)
    private University university;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "program_id")
    private Program program;

    @Column(name = "gpa_min")
    private Double gpaMin;

    @Column(name = "ielts_min")
    private Double ieltsMin;

    @Column(name = "toefl_min")
    private Double toeflMin;

    @Column(name = "gre_min")
    private Double greMin;

    @Column(name = "gmat_min")
    private Double gmatMin;

    public AdmissionRequirement() {}

    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public University getUniversity() { return university; }
    public void setUniversity(University university) { this.university = university; }

    public Program getProgram() { return program; }
    public void setProgram(Program program) { this.program = program; }

    public Double getGpaMin() { return gpaMin; }
    public void setGpaMin(Double gpaMin) { this.gpaMin = gpaMin; }

    public Double getIeltsMin() { return ieltsMin; }
    public void setIeltsMin(Double ieltsMin) { this.ieltsMin = ieltsMin; }

    public Double getToeflMin() { return toeflMin; }
    public void setToeflMin(Double toeflMin) { this.toeflMin = toeflMin; }

    public Double getGreMin() { return greMin; }
    public void setGreMin(Double greMin) { this.greMin = greMin; }

    public Double getGmatMin() { return gmatMin; }
    public void setGmatMin(Double gmatMin) { this.gmatMin = gmatMin; }
}
