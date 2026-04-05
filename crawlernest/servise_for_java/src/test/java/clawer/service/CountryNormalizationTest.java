package clawer.service;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

class CountryNormalizationTest {

    @Test
    void normalizesKnownAliasesToCanonicalNames() {
        assertEquals("China", CountryNormalization.normalizeCountry("China (mainland)"));
        assertEquals("China", CountryNormalization.normalizeCountry(" china "));
        assertEquals("United States", CountryNormalization.normalizeCountry("USA"));
        assertEquals("United Kingdom", CountryNormalization.normalizeCountry("uk"));
        assertEquals("Hong Kong", CountryNormalization.normalizeCountry("Hong Kong SAR"));
        assertEquals("Macau", CountryNormalization.normalizeCountry("Macao"));
        assertEquals("Russia", CountryNormalization.normalizeCountry("Russian Federation"));
    }

    @Test
    void returnsNullForBlankInput() {
        assertNull(CountryNormalization.normalizeCountry("   "));
        assertNull(CountryNormalization.normalizeCountry(null));
    }
}
