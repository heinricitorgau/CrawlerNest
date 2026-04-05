export const REGION_MAP: Record<string, string[]> = {
  Africa: [
    "Algeria",
    "Botswana",
    "Egypt",
    "Ethiopia",
    "Ghana",
    "Kenya",
    "Morocco",
    "Nigeria",
    "South Africa",
    "Tunisia",
    "Uganda",
  ],
  "Arab Region": [
    "Algeria",
    "Bahrain",
    "Egypt",
    "Iraq",
    "Jordan",
    "Kuwait",
    "Lebanon",
    "Morocco",
    "Oman",
    "Qatar",
    "Saudi Arabia",
    "Tunisia",
    "United Arab Emirates",
  ],
  Asia: [
    "Bangladesh",
    "Brunei",
    "China",
    "Hong Kong",
    "India",
    "Indonesia",
    "Japan",
    "Kazakhstan",
    "Macau",
    "Malaysia",
    "Pakistan",
    "Philippines",
    "Singapore",
    "South Korea",
    "Taiwan",
    "Thailand",
    "Vietnam",
  ],
  Europe: [
    "Austria",
    "Belgium",
    "Czech Republic",
    "Denmark",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Hungary",
    "Iceland",
    "Ireland",
    "Italy",
    "Netherlands",
    "Norway",
    "Poland",
    "Portugal",
    "Russia",
    "Spain",
    "Sweden",
    "Switzerland",
    "Turkey",
    "Ukraine",
    "United Kingdom",
  ],
  "Latin America": [
    "Argentina",
    "Brazil",
    "Chile",
    "Colombia",
    "Costa Rica",
    "Ecuador",
    "Mexico",
    "Peru",
    "Uruguay",
    "Venezuela",
  ],
  "North America": [
    "Canada",
    "Mexico",
    "Puerto Rico",
    "United States",
  ],
  Oceania: [
    "Australia",
    "New Zealand",
  ],
};

export function normalizeCountryName(country: string): string {
  const normalized = country
    .trim()
    .replace(/\./g, "")
    .replace(/[()]/g, " ")
    .replace(/\s+/g, " ")
    .toLowerCase();

  if (!normalized) {
    return "";
  }

  if (
    normalized === "china" ||
    normalized === "china mainland" ||
    normalized === "china (mainland)"
  ) {
    return "China";
  }

  if (
    normalized === "united states" ||
    normalized === "united states of america" ||
    normalized === "usa" ||
    normalized === "us" ||
    normalized === "u s a" ||
    normalized === "u s"
  ) {
    return "United States";
  }

  if (
    normalized === "united kingdom" ||
    normalized === "uk" ||
    normalized === "u k" ||
    normalized === "great britain" ||
    normalized === "britain"
  ) {
    return "United Kingdom";
  }

  if (
    normalized === "hong kong sar" ||
    normalized === "hong kong sar china" ||
    normalized === "hong kong sar, china"
  ) {
    return "Hong Kong";
  }

  if (
    normalized === "macao" ||
    normalized === "macau sar" ||
    normalized === "macao sar"
  ) {
    return "Macau";
  }

  if (normalized === "russian federation") {
    return "Russia";
  }

  return normalized
    .split(" ")
    .filter(Boolean)
    .map((token) => token.charAt(0).toUpperCase() + token.slice(1))
    .join(" ");
}

export function countryBelongsToRegion(country: string, region: string): boolean {
  const normalizedCountry = normalizeCountryName(country);
  const regionCountries = REGION_MAP[region] ?? [];
  return regionCountries.includes(normalizedCountry);
}
