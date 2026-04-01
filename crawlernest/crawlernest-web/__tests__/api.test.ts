import { getApiBaseUrl, fetchJson, fetchAppJson } from "@/lib/api";

const originalEnv = process.env;

beforeEach(() => {
  jest.resetModules();
  process.env = { ...originalEnv };
  global.fetch = jest.fn();
});

afterEach(() => {
  process.env = originalEnv;
  jest.restoreAllMocks();
});

describe("getApiBaseUrl", () => {
  it("returns default URL when no env vars are set", () => {
    delete process.env.API_BASE_URL;
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    expect(getApiBaseUrl()).toBe("http://localhost:8080");
  });

  it("prefers API_BASE_URL over NEXT_PUBLIC_API_BASE_URL", () => {
    process.env.API_BASE_URL = "http://server:9000";
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://public:9001";
    expect(getApiBaseUrl()).toBe("http://server:9000");
  });

  it("uses NEXT_PUBLIC_API_BASE_URL when API_BASE_URL is absent", () => {
    delete process.env.API_BASE_URL;
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://public:9001";
    expect(getApiBaseUrl()).toBe("http://public:9001");
  });
});

describe("fetchJson", () => {
  it("returns parsed JSON on success", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true, data: [] }),
    });

    const result = await fetchJson<{ success: boolean; data: unknown[] }>("/universities");
    expect(result).toEqual({ success: true, data: [] });
  });

  it("throws an error when response is not ok", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    await expect(fetchJson("/universities")).rejects.toThrow("Request failed with status 500");
  });

  it("calls fetch with the full API base URL", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    await fetchJson("/rankings");
    const calledUrl = (global.fetch as jest.Mock).mock.calls[0][0];
    expect(calledUrl).toMatch(/\/rankings$/);
  });

  it("passes no-store cache option", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    await fetchJson("/rankings");
    const calledOptions = (global.fetch as jest.Mock).mock.calls[0][1];
    expect(calledOptions.cache).toBe("no-store");
  });

  it("throws on 404", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({}),
    });

    await expect(fetchJson("/missing")).rejects.toThrow("Request failed with status 404");
  });
});

describe("fetchAppJson", () => {
  it("returns parsed JSON on success", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    });

    const result = await fetchAppJson<{ success: boolean }>("/api/rankings");
    expect(result).toEqual({ success: true });
  });

  it("throws on non-ok response", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({}),
    });

    await expect(fetchAppJson("/api/rankings")).rejects.toThrow("Request failed with status 503");
  });

  it("calls fetch with the path directly (not prepended with base URL)", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({}),
    });

    await fetchAppJson("/api/recommendations");
    const calledUrl = (global.fetch as jest.Mock).mock.calls[0][0];
    expect(calledUrl).toBe("/api/recommendations");
  });
});
