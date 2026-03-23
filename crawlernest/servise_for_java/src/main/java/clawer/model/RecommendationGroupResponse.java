package clawer.model;

import java.util.List;
import java.util.Map;

public class RecommendationGroupResponse {
    private List<RecommendationResult> reach;
    private List<RecommendationResult> target;
    private List<RecommendationResult> safety;
    private Map<String, Object> metadata;

    public RecommendationGroupResponse() {
    }

    public RecommendationGroupResponse(
            List<RecommendationResult> reach,
            List<RecommendationResult> target,
            List<RecommendationResult> safety,
            Map<String, Object> metadata
    ) {
        this.reach = reach;
        this.target = target;
        this.safety = safety;
        this.metadata = metadata;
    }

    public List<RecommendationResult> getReach() {
        return reach;
    }

    public void setReach(List<RecommendationResult> reach) {
        this.reach = reach;
    }

    public List<RecommendationResult> getTarget() {
        return target;
    }

    public void setTarget(List<RecommendationResult> target) {
        this.target = target;
    }

    public List<RecommendationResult> getSafety() {
        return safety;
    }

    public void setSafety(List<RecommendationResult> safety) {
        this.safety = safety;
    }

    public Map<String, Object> getMetadata() {
        return metadata;
    }

    public void setMetadata(Map<String, Object> metadata) {
        this.metadata = metadata;
    }
}
