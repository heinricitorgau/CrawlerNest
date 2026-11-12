package clawer.security;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.ZoneOffset;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** The property the fixed window lacks: no stretch of one window's length ever holds more than the limit. */
class SlidingWindowBudgetTest {

    private static final class MovableClock extends Clock {
        private Instant now = Instant.parse("2026-11-12T00:00:00Z");

        void advance(Duration by) {
            now = now.plus(by);
        }

        @Override public ZoneOffset getZone() { return ZoneOffset.UTC; }
        @Override public Clock withZone(ZoneId zone) { return this; }
        @Override public Instant instant() { return now; }
    }

    private final MovableClock clock = new MovableClock();

    @Test
    void spendingAroundAWindowBoundaryDoesNotDoubleTheLimit() {
        SlidingWindowBudget sliding = new SlidingWindowBudget(10, Duration.ofMinutes(1), clock);
        FixedWindowRateLimiter fixed = new FixedWindowRateLimiter(10, Duration.ofMinutes(1), clock);
        fixed.tryAcquire("u");            // opens the fixed window at t=0
        clock.advance(Duration.ofSeconds(59));
        int slidingAllowed = 0;
        int fixedAllowed = 1;
        for (int i = 0; i < 9; i++) {      // the rest of the fixed window's limit, at t=59s
            fixedAllowed += fixed.tryAcquire("u").allowed() ? 1 : 0;
        }
        for (int i = 0; i < 10; i++) {     // the sliding budget's whole limit, at t=59s
            slidingAllowed += sliding.trySpend("u", 1).allowed() ? 1 : 0;
        }
        clock.advance(Duration.ofSeconds(2));   // t=61s: a new fixed window, the same sliding one
        for (int i = 0; i < 10; i++) {
            fixedAllowed += fixed.tryAcquire("u").allowed() ? 1 : 0;
            slidingAllowed += sliding.trySpend("u", 1).allowed() ? 1 : 0;
        }
        assertEquals(20, fixedAllowed, "the fixed window lets twice the limit through in two seconds");
        assertEquals(10, slidingAllowed, "the sliding budget does not");
    }

    @Test
    void weightsAreCountedAndARefusalSpendsNothing() {
        SlidingWindowBudget budget = new SlidingWindowBudget(10, Duration.ofMinutes(1), clock);
        assertTrue(budget.trySpend("u", 4).allowed());
        assertTrue(budget.trySpend("u", 4).allowed());
        assertFalse(budget.trySpend("u", 4).allowed());   // 8 + 4 > 10
        assertEquals(8, budget.spent("u"));               // the refusal cost nothing
        assertTrue(budget.trySpend("u", 2).allowed());    // and a smaller request still fits
        assertTrue(budget.trySpend("other", 4).allowed());
    }

    @Test
    void retryAfterIsWhenEnoughOldSpendsLeaveTheWindow() {
        SlidingWindowBudget budget = new SlidingWindowBudget(10, Duration.ofMinutes(1), clock);
        budget.trySpend("u", 4);                 // t=0
        clock.advance(Duration.ofSeconds(20));
        budget.trySpend("u", 4);                 // t=20
        clock.advance(Duration.ofSeconds(10));   // t=30, spent 8
        // 2 more fit now; 4 need the first spend gone (t=60): 30 s. 8 need both gone (t=80): 50 s.
        assertTrue(budget.check("u", 2).allowed());
        assertEquals(30, budget.check("u", 4).retryAfterSeconds());
        assertEquals(50, budget.check("u", 8).retryAfterSeconds());
        clock.advance(Duration.ofSeconds(30));
        assertTrue(budget.trySpend("u", 4).allowed());
        assertEquals(8, budget.spent("u"));
    }

    @Test
    void aRefundGivesBackTheLastSpend() {
        SlidingWindowBudget budget = new SlidingWindowBudget(10, Duration.ofMinutes(1), clock);
        budget.trySpend("u", 4);
        budget.refund("u", 4);
        assertEquals(0, budget.spent("u"));
        budget.refund("u", 4);   // nothing left to refund: no effect, no error
        assertEquals(0, budget.spent("u"));
    }

    @Test
    void concurrentRequestsForOneUserNeverOverspend() throws Exception {
        SlidingWindowBudget budget = new SlidingWindowBudget(50, Duration.ofMinutes(1), clock);
        ExecutorService pool = Executors.newFixedThreadPool(16);
        AtomicInteger allowed = new AtomicInteger();
        CountDownLatch start = new CountDownLatch(1);
        for (int i = 0; i < 400; i++) {
            pool.submit(() -> {
                start.await();
                if (budget.trySpend("u", 1).allowed()) {
                    allowed.incrementAndGet();
                }
                return null;
            });
        }
        start.countDown();
        pool.shutdown();
        assertTrue(pool.awaitTermination(30, TimeUnit.SECONDS));
        assertEquals(50, allowed.get());
        assertEquals(50, budget.spent("u"));
    }

    @Test
    void aWeightAboveTheLimitIsAProgrammingError() {
        SlidingWindowBudget budget = new SlidingWindowBudget(3, Duration.ofMinutes(1), clock);
        assertThrows(IllegalArgumentException.class, () -> budget.trySpend("u", 4));
        assertThrows(IllegalArgumentException.class, () -> budget.trySpend("u", 0));
    }
}
