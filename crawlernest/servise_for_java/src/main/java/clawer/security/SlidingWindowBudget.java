package clawer.security;

import java.time.Clock;
import java.time.Duration;
import java.util.ArrayDeque;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * A weighted budget per key over a sliding window: at any moment, the weights spent in the last {@code window} never
 * exceed {@code limit}.
 *
 * <p>{@link FixedWindowRateLimiter} resets on a boundary, so a caller who spends the whole limit just before it and
 * again just after gets twice the limit in a few seconds. That is tolerable for cheap requests and not for model
 * calls, which is what this is for. Here every spend is remembered with its time, and only the spends older than the
 * window stop counting, so there is no boundary to straddle.
 *
 * <p>The price is memory: one entry per spend still inside the window, where the fixed window keeps one counter. It is
 * bounded by {@code limit} entries per key (every entry weighs at least 1), which is why this is used for small
 * limits keyed by signed-in user and not for the 600-a-minute general limit keyed by address.
 *
 * <p>A request that would not fit is refused and spends nothing, so being refused never pushes the next allowed
 * moment further away.
 */
public final class SlidingWindowBudget {

    private record Spend(long atMillis, int weight) {
    }

    private static final class Ledger {
        private final ArrayDeque<Spend> spends = new ArrayDeque<>();
        private int total;
    }

    private static final int SWEEP_THRESHOLD = 10_000;

    private final int limit;
    private final long windowMillis;
    private final Clock clock;
    private final Map<String, Ledger> ledgers = new ConcurrentHashMap<>();

    public SlidingWindowBudget(int limit, Duration window, Clock clock) {
        if (limit < 1) {
            throw new IllegalArgumentException("limit must be at least 1, got " + limit);
        }
        this.limit = limit;
        this.windowMillis = window.toMillis();
        this.clock = clock;
    }

    public int limit() {
        return limit;
    }

    // Every read and write of a ledger happens inside ConcurrentHashMap.compute for its key, which holds that key's
    // lock: two requests for one user cannot both fit into the last unit, and the sweep cannot drop a ledger a
    // request is writing to.

    /** What {@code key} has spent inside the window as of now. */
    public int spent(String key) {
        int[] total = {0};
        long now = clock.millis();
        ledgers.computeIfPresent(key, (k, ledger) -> {
            expire(ledger, now);
            total[0] = ledger.total;
            return ledger.spends.isEmpty() ? null : ledger;
        });
        return total[0];
    }

    /**
     * Whether {@code weight} more would fit for {@code key} right now, without spending it. When it would not, the
     * decision carries the seconds until enough earlier spends leave the window for it to fit.
     */
    public FixedWindowRateLimiter.Decision check(String key, int weight) {
        return apply(key, weight, false);
    }

    /** Spends {@code weight} for {@code key} if it fits; otherwise spends nothing and says how long to wait. */
    public FixedWindowRateLimiter.Decision trySpend(String key, int weight) {
        FixedWindowRateLimiter.Decision decision = apply(key, weight, true);
        if (ledgers.size() > SWEEP_THRESHOLD) {
            long now = clock.millis();
            for (String other : ledgers.keySet()) {
                ledgers.computeIfPresent(other, (k, ledger) -> {
                    expire(ledger, now);
                    return ledger.spends.isEmpty() ? null : ledger;
                });
            }
        }
        return decision;
    }

    private FixedWindowRateLimiter.Decision apply(String key, int weight, boolean spend) {
        requireWeight(weight);
        long now = clock.millis();
        FixedWindowRateLimiter.Decision[] out = new FixedWindowRateLimiter.Decision[1];
        ledgers.compute(key, (k, existing) -> {
            Ledger ledger = existing != null ? existing : new Ledger();
            expire(ledger, now);
            out[0] = decide(ledger, weight, now);
            if (spend && out[0].allowed()) {
                ledger.spends.addLast(new Spend(now, weight));
                ledger.total += weight;
            }
            return ledger.spends.isEmpty() ? null : ledger;
        });
        return out[0];
    }

    /** Gives back the most recent spend, for a request another budget then refused. */
    public void refund(String key, int weight) {
        ledgers.computeIfPresent(key, (k, ledger) -> {
            Spend last = ledger.spends.peekLast();
            if (last != null && last.weight() == weight) {
                ledger.spends.removeLast();
                ledger.total -= weight;
            }
            return ledger.spends.isEmpty() ? null : ledger;
        });
    }

    private void requireWeight(int weight) {
        if (weight < 1 || weight > limit) {
            throw new IllegalArgumentException("weight must be between 1 and the limit " + limit + ", got " + weight);
        }
    }

    private FixedWindowRateLimiter.Decision decide(Ledger ledger, int weight, long now) {
        if (ledger.total + weight <= limit) {
            return new FixedWindowRateLimiter.Decision(true, 0);
        }
        // Walk the oldest spends until enough of them would have left the window.
        int freed = 0;
        long fitsAt = now;
        for (Spend spend : ledger.spends) {
            freed += spend.weight();
            fitsAt = spend.atMillis() + windowMillis;
            if (ledger.total - freed + weight <= limit) {
                break;
            }
        }
        return new FixedWindowRateLimiter.Decision(false, Math.max(1, (fitsAt - now + 999) / 1000));
    }

    private void expire(Ledger ledger, long now) {
        while (!ledger.spends.isEmpty() && now - ledger.spends.peekFirst().atMillis() >= windowMillis) {
            ledger.total -= ledger.spends.removeFirst().weight();
        }
    }
}
