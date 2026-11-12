package clawer.desk.controller;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import clawer.desk.model.ModelUsageLedger;
import clawer.desk.support.DeskAuth;
import clawer.dto.ApiResponse;
import clawer.security.ModelCallBudgetFilter;
import clawer.security.RateLimits;

/**
 * GET /api/v1/user/desk/usage: the signed-in user's own model calls over the last 24 hours, against their budget.
 * Read-only, and only ever the caller's own rows (the id comes from the token).
 */
@RestController
@RequestMapping("/api/v1/user/desk/usage")
public class ModelUsageController {

    static final List<String> NOTES = List.of(
            "The day is the last 24 hours, not a calendar day: each call stops counting 24 hours after it was made.",
            "Calls the model provider did not answer (it was unreachable) are listed but do not count against the budget.",
            "reservedPerRequest is the most model calls each endpoint may make. It is held against the per-minute "
                    + "budget before the request runs; the day counts only the calls actually made.",
            "Token totals are the provider's own figures, summed over the calls that reported them; callsWithoutUsage "
                    + "counts the calls that did not, so the totals are a lower bound when it is above zero.");

    private final ModelUsageLedger ledger;
    private final RateLimits limits;

    public ModelUsageController(ModelUsageLedger ledger, ObjectProvider<RateLimits> limits) {
        this.ledger = ledger;
        this.limits = limits.getIfAvailable();
    }

    @GetMapping
    public ResponseEntity<?> usage() {
        long userId = DeskAuth.currentUserId();
        Map<String, Object> last24h = ledger.summary(userId, Duration.ofDays(1));
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("last24Hours", last24h);
        Map<String, Object> budget = new LinkedHashMap<>();
        boolean enforced = limits != null && limits.enabled();
        budget.put("enforced", enforced);
        if (enforced) {
            budget.put("modelCallsPerDay", limits.modelCallsPerDay());
            budget.put("modelCallsLeft", Math.max(0, limits.modelCallsPerDay() - (long) last24h.get("modelCalls")));
        }
        budget.put("reservedPerRequest", ModelCallBudgetFilter.MODEL_CALLS);
        out.put("budget", budget);
        out.put("notes", NOTES);
        return ResponseEntity.ok(ApiResponse.success(out));
    }
}
