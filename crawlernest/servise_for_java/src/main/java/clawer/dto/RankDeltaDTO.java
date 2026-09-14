package clawer.dto;

/**
 * One source's movement between two editions, as {@code SourceRankDelta} computed it.
 *
 * <p>Present only when there is a movement to state; otherwise the owning
 * {@link SourceRankingDTO#getRankDeltaReason()} says why it is absent. The shape
 * matches the {@code rankDelta} record field the agent layer reads
 * ({@code crawlernest/agent/web_agent/dataset_context.py}: {@code direction},
 * {@code priorYear}, {@code currentYear}), so the same evidence unlocks the same
 * wording in both places.
 *
 * <p>{@code value} is current minus prior and is set only for two exact ranks;
 * negative means the university moved up. {@code min}/{@code max} bound a banded
 * movement (either may be null on an open side). Render {@code direction}.
 */
public class RankDeltaDTO {
    private Integer priorYear;
    private Integer currentYear;
    private String priorRankDisplay;
    private Integer value;
    private Integer min;
    private Integer max;
    private String direction;

    public RankDeltaDTO() {}

    public Integer getPriorYear() { return priorYear; }
    public void setPriorYear(Integer priorYear) { this.priorYear = priorYear; }

    public Integer getCurrentYear() { return currentYear; }
    public void setCurrentYear(Integer currentYear) { this.currentYear = currentYear; }

    public String getPriorRankDisplay() { return priorRankDisplay; }
    public void setPriorRankDisplay(String priorRankDisplay) { this.priorRankDisplay = priorRankDisplay; }

    public Integer getValue() { return value; }
    public void setValue(Integer value) { this.value = value; }

    public Integer getMin() { return min; }
    public void setMin(Integer min) { this.min = min; }

    public Integer getMax() { return max; }
    public void setMax(Integer max) { this.max = max; }

    public String getDirection() { return direction; }
    public void setDirection(String direction) { this.direction = direction; }
}
