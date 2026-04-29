package clawer.dto;

public class SubjectOptionDTO {
    private String subjectKey;
    private String subjectName;

    public SubjectOptionDTO() {}

    public SubjectOptionDTO(String subjectKey, String subjectName) {
        this.subjectKey = subjectKey;
        this.subjectName = subjectName;
    }

    public String getSubjectKey() {
        return subjectKey;
    }

    public void setSubjectKey(String subjectKey) {
        this.subjectKey = subjectKey;
    }

    public String getSubjectName() {
        return subjectName;
    }

    public void setSubjectName(String subjectName) {
        this.subjectName = subjectName;
    }
}
