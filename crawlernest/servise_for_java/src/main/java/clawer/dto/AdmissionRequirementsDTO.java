package clawer.dto;

import java.util.List;

/**
 * A university's admission requirements as the API exposes them: the
 * university-level breakdown per degree level, the programme-specific
 * requirements beside it, a flattened summary for compact surfaces, and the
 * caveats that must travel with any of them.
 *
 * <p>{@code byDegreeLevel} and {@code summary} are built only from rows that
 * apply to the institution; programme rows are in
 * {@code programmeRequirements} and are never folded into either. Folding them
 * in would report the least demanding programme's IELTS as the university's.
 *
 * <p>{@code summary} is the lowest university-level bar across every degree
 * level, so it answers "could I get in anywhere here" rather than "what does
 * this specific programme want". A card showing the summary alongside
 * {@code degreeLevelCount} greater than one should say which level it is
 * quoting, or say "from".
 *
 * <p>{@code hasData} exists so a client can tell "this university has no crawled
 * admission page" apart from "it has one and every field on it was blank". The
 * two look identical once you only inspect the requirement values.
 *
 * <p>{@code caveats} is never null: {@code CAVEAT_IELTS_MISSING} when no stored
 * IELTS figure exists at any scope, and {@code CAVEAT_ADMISSION_DATA_STALE}
 * naming the oldest fetch (or, when fetch dates were not recorded, extraction)
 * date whenever there is data.
 */
public class AdmissionRequirementsDTO {

    private boolean hasData;
    private int degreeLevelCount;
    private AdmissionRequirementDTO summary;
    private List<AdmissionRequirementDTO> byDegreeLevel;
    private List<AdmissionRequirementDTO> programmeRequirements = List.of();
    private List<String> caveats = List.of();
    private Boolean fetchDatesRecorded;
    private String oldestFetchedOn;
    private String oldestExtractedOn;

    public boolean isHasData() { return hasData; }
    public void setHasData(boolean hasData) { this.hasData = hasData; }

    public int getDegreeLevelCount() { return degreeLevelCount; }
    public void setDegreeLevelCount(int degreeLevelCount) { this.degreeLevelCount = degreeLevelCount; }

    /** Lowest university-level value per requirement across all degree levels; never null, fields may be. */
    public AdmissionRequirementDTO getSummary() { return summary; }
    public void setSummary(AdmissionRequirementDTO summary) { this.summary = summary; }

    public List<AdmissionRequirementDTO> getByDegreeLevel() { return byDegreeLevel; }
    public void setByDegreeLevel(List<AdmissionRequirementDTO> byDegreeLevel) { this.byDegreeLevel = byDegreeLevel; }

    /** Requirements a source attributed to a named programme or faculty; empty for every source so far. */
    public List<AdmissionRequirementDTO> getProgrammeRequirements() { return programmeRequirements; }
    public void setProgrammeRequirements(List<AdmissionRequirementDTO> programmeRequirements) { this.programmeRequirements = programmeRequirements; }

    public List<String> getCaveats() { return caveats; }
    public void setCaveats(List<String> caveats) { this.caveats = caveats; }

    /** Whether every row behind these requirements records when its page was fetched; null without data. */
    public Boolean getFetchDatesRecorded() { return fetchDatesRecorded; }
    public void setFetchDatesRecorded(Boolean fetchDatesRecorded) { this.fetchDatesRecorded = fetchDatesRecorded; }

    /** Oldest page fetch behind these requirements, UTC {@code yyyy-MM-dd}; null when not recorded. */
    public String getOldestFetchedOn() { return oldestFetchedOn; }
    public void setOldestFetchedOn(String oldestFetchedOn) { this.oldestFetchedOn = oldestFetchedOn; }

    /** Oldest extraction behind these requirements, UTC {@code yyyy-MM-dd}. */
    public String getOldestExtractedOn() { return oldestExtractedOn; }
    public void setOldestExtractedOn(String oldestExtractedOn) { this.oldestExtractedOn = oldestExtractedOn; }

    /** The shape returned for a university with no crawled admission record at all. Caveats are the caller's. */
    public static AdmissionRequirementsDTO empty() {
        AdmissionRequirementsDTO dto = new AdmissionRequirementsDTO();
        dto.setHasData(false);
        dto.setDegreeLevelCount(0);
        dto.setSummary(new AdmissionRequirementDTO());
        dto.setByDegreeLevel(List.of());
        return dto;
    }
}
