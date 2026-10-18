/**
 * @jest-environment node
 *
 * The desk catch-all proxy: which paths reach the Java API, and which stop here.
 */
import { NextRequest } from "next/server";

import { GET, PATCH } from "@/app/api/user/desk/[...path]/route";

const originalFetch = global.fetch;

function upstreamOk() {
  return jest.fn(async () => new Response(JSON.stringify({ success: true, data: [] }), { status: 200 })) as unknown as jest.Mock;
}

function context(path: string[]) {
  return { params: Promise.resolve({ path }) };
}

afterEach(() => {
  global.fetch = originalFetch;
});

describe("desk proxy route", () => {
  it("forwards an allowed path, the cookie and the allowed query parameters", async () => {
    const fetchMock = upstreamOk();
    global.fetch = fetchMock;
    const request = new NextRequest("http://localhost:3000/api/user/desk/tasks?status=open&sprintId=4&evil=1", {
      headers: { cookie: "crawlernest_token=abc" },
    });

    const response = await GET(request, context(["tasks"]));

    expect(response.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/user\/desk\/tasks\?status=open&sprintId=4$/);
    expect(init.headers.Cookie).toBe("crawlernest_token=abc");
  });

  it("forwards a PATCH body unchanged", async () => {
    const fetchMock = upstreamOk();
    global.fetch = fetchMock;
    const request = new NextRequest("http://localhost:3000/api/user/desk/tasks/12", {
      method: "PATCH",
      body: JSON.stringify({ status: "done" }),
    });

    await PATCH(request, context(["tasks", "12"]));

    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/api\/v1\/user\/desk\/tasks\/12$/);
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe('{"status":"done"}');
  });

  it.each([
    [["..", "admin"]],
    [["tasks", "..%2Fadmin"]],
    [["Tasks"]],
    [["chat", "actions", "1", "2", "3"]],
    [[]],
  ])("answers 404 for %j without calling the API", async (path) => {
    const fetchMock = upstreamOk();
    global.fetch = fetchMock;

    const response = await GET(new NextRequest("http://localhost:3000/api/user/desk/x"), context(path));

    expect(response.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
