package clawer.security;

import java.time.Clock;
import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Counts events per key in fixed windows, in this process's memory.
 *
 * <p>In memory on purpose: it needs no shared store, and the cost is that each API instance counts on
 * its own, so N instances allow N times the limit. That is stated in docs/AUTH_LIMITATIONS.md rather than
 * hidden. Stale windows are swept when the map grows, so a scan from many addresses cannot grow it without
 * bound.
 */
public final class FixedWindowRateLimiter {

    /** What one call decided. {@code retryAfterSeconds} is 0 when allowed. */
    public record Decision(boolean allowed, long retryAfterSeconds) {
    }

    private record Window(long startMillis, int count) {
    }

    private static final int SWEEP_THRESHOLD = 10_000;

    private final int limit;
    private final long windowMillis;
    private final Clock clock;
    private final Map<String, Window> windows = new ConcurrentHashMap<>();

    public FixedWindowRateLimiter(int limit, Duration window, Clock clock) {
        if (limit < 1) {
            throw new IllegalArgumentException("limit must be at least 1, got " + limit);
        }
        this.limit = limit;
        this.windowMillis = window.toMillis();
        this.clock = clock;
    }

    /** Counts one event for {@code key} and says whether it is within the limit. */
    public Decision tryAcquire(String key) {
        long now = clock.millis();
        Window updated = windows.compute(key, (k, current) ->
                current == null || now - current.startMillis() >= windowMillis
                        ? new Window(now, 1)
                        : new Window(current.startMillis(), current.count() + 1));
        if (windows.size() > SWEEP_THRESHOLD) {
            windows.values().removeIf(window -> now - window.startMillis() >= windowMillis);
        }
        if (updated.count() <= limit) {
            return new Decision(true, 0);
        }
        return new Decision(false, retryAfter(updated, now));
    }

    /** Whether {@code key} is already over the limit, without counting anything. */
    public Decision peek(String key) {
        long now = clock.millis();
        Window current = windows.get(key);
        if (current == null || now - current.startMillis() >= windowMillis || current.count() < limit) {
            return new Decision(true, 0);
        }
        return new Decision(false, retryAfter(current, now));
    }

    /** Forgets {@code key}, e.g. after a successful sign-in ends a run of failures. */
    public void reset(String key) {
        windows.remove(key);
    }

    private long retryAfter(Window window, long now) {
        long remaining = window.startMillis() + windowMillis - now;
        return Math.max(1, (remaining + 999) / 1000);
    }
}
