import { act, render, screen } from "@testing-library/react";
import { useApiResource } from "@/hooks/useApiResource";

function Probe({ path }: { path: string }) {
  const state = useApiResource<{ v: string }>(path);
  return <p data-testid="s">{state.status === "ok" ? `ok:${state.data.v}:${state.caveats.join(",")}` : state.status === "error" ? `error:${state.message}` : "loading"}</p>;
}

function deferred() {
  let resolve!: (value: unknown) => void;
  const promise = new Promise((r) => (resolve = r));
  return { promise, resolve };
}

describe("useApiResource", () => {
  it("is loading until its own path answers, then shows the data and caveats", async () => {
    global.fetch = jest.fn(async () => ({ ok: true, status: 200, json: async () => ({ success: true, data: { v: "a" }, metadata: { caveats: ["c1"] } }) })) as unknown as typeof fetch;
    render(<Probe path="/api/a" />);
    expect(screen.getByTestId("s")).toHaveTextContent("loading");
    expect(await screen.findByText("ok:a:c1")).toBeInTheDocument();
  });

  it("never shows a slow answer for an old path under a new one", async () => {
    const slow = deferred();
    global.fetch = jest.fn((path: string) =>
      path === "/api/old"
        ? slow.promise.then(() => ({ ok: true, status: 200, json: async () => ({ success: true, data: { v: "old" } }) }))
        : Promise.resolve({ ok: true, status: 200, json: async () => ({ success: true, data: { v: "new" } }) })
    ) as unknown as typeof fetch;
    const { rerender } = render(<Probe path="/api/old" />);
    rerender(<Probe path="/api/new" />);
    expect(await screen.findByText("ok:new:")).toBeInTheDocument();
    await act(async () => {
      slow.resolve(undefined);
      await slow.promise;
    });
    expect(screen.getByTestId("s")).toHaveTextContent("ok:new:");
  });

  it("reports the API's error", async () => {
    global.fetch = jest.fn(async () => ({ ok: false, status: 503, json: async () => ({ success: false, error: "down" }) })) as unknown as typeof fetch;
    render(<Probe path="/api/x" />);
    expect(await screen.findByText("error:down")).toBeInTheDocument();
  });
});
