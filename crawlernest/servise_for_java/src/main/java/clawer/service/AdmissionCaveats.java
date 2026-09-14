package clawer.service;

import clawer.repository.AdmissionSummaryRow;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * The caveats admission requirements carry, from a university's summary row.
 *
 * <p>The strings are {@link AnalyticsService#IELTS_MISSING_CAVEAT} and the two
 * {@code ADMISSION_STALE_*_TEMPLATE}s, referenced rather than repeated; this
 * class only decides which apply. Same rule as {@code admission_caveats} in
 * crawlernest/core/caveats.py.
 */
public final class AdmissionCaveats {

    private AdmissionCaveats() {
    }

    /**
     * {@code CAVEAT_IELTS_MISSING} when no IELTS figure is stored at any scope --
     * including when the university has no admission row, which is absence of the
     * summary row -- and {@code CAVEAT_ADMISSION_DATA_STALE} whenever there is data.
     */
    public static List<String> forSummary(Optional<AdmissionSummaryRow> summary) {
        List<String> caveats = new ArrayList<>();
        if (summary.isEmpty()) {
            caveats.add(AnalyticsService.IELTS_MISSING_CAVEAT);
            return caveats;
        }
        AdmissionSummaryRow row = summary.get();
        if (row.ieltsMissing()) {
            caveats.add(AnalyticsService.IELTS_MISSING_CAVEAT);
        }
        String stale = AnalyticsService.admissionStaleCaveat(
                row.fetchDatesRecorded(), row.oldestFetchedOn(), row.oldestExtractedOn());
        if (stale != null) {
            caveats.add(stale);
        }
        return caveats;
    }
}
