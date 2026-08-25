package clawer.dto;

import java.util.List;

/**
 * A university's admission requirements as the API exposes them: the full
 * per-degree-level breakdown, plus a flattened summary for compact surfaces
 * like a recommendation card.
 *
 * <p>{@code summary} is the lowest published bar across every degree level, so
 * it answers "could I get in anywhere here" rather than "what does this specific
 * programme want". A card showing the summary alongside {@code degreeLevelCount}
 * greater than one should say which level it is quoting, or say "from".
 *
 * <p>{@code hasData} exists so a client can tell "this university has no crawled
 * admission page" apart from "it has one and every field on it was blank". The
 * two look identical once you only inspect the requirement values.
 */
public class AdmissionRequirementsDTO {

    private boolean hasData;
    private int degreeLevelCount;
    private AdmissionRequirementDTO summary;
    private List<AdmissionRequirementDTO> byDegreeLevel;

    public boolean isHasData() { return hasData; }
    public void setHasData(boolean hasData) { this.hasData = hasData; }

    public int getDegreeLevelCount() { return degreeLevelCount; }
    public void setDegreeLevelCount(int degreeLevelCount) { this.degreeLevelCount = degreeLevelCount; }

    /** Lowest published value per requirement across all degree levels; never null, fields may be. */
    public AdmissionRequirementDTO getSummary() { return summary; }
    public void setSummary(AdmissionRequirementDTO summary) { this.summary = summary; }

    public List<AdmissionRequirementDTO> getByDegreeLevel() { return byDegreeLevel; }
    public void setByDegreeLevel(List<AdmissionRequirementDTO> byDegreeLevel) { this.byDegreeLevel = byDegreeLevel; }

    /** The shape returned for a university with no crawled admission record at all. */
    public static AdmissionRequirementsDTO empty() {
        AdmissionRequirementsDTO dto = new AdmissionRequirementsDTO();
        dto.setHasData(false);
        dto.setDegreeLevelCount(0);
        dto.setSummary(new AdmissionRequirementDTO());
        dto.setByDegreeLevel(List.of());
        return dto;
    }
}
