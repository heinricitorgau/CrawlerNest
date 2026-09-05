/**
 * @jest-environment node
 *
 * The reader touches no DOM. jsdom is also missing TextEncoder and
 * ReadableStream, so running this suite there would be testing the polyfills
 * rather than the parser.
 */
import {
  readExplainStream,
  splitParagraphs,
  type ExplainFrame,
} from "@/lib/agentExplainStream";

/**
 * Build a ReadableStream that hands out exactly the byte slices given.
 *
 * The slicing is the point. A chunk from the network is not a frame, and the
 * bug this guards against — treating each read() as one message — passes every
 * test that feeds the body in one piece.
 */
function streamOf(pieces: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (i >= pieces.length) {
        controller.close();
        return;
      }
      controller.enqueue(encoder.encode(pieces[i++]));
    },
  });
}

function frame(payload: unknown): string {
  return `data: ${JSON.stringify(payload)}\n\n`;
}

async function collect(stream: ReadableStream<Uint8Array>): Promise<ExplainFrame[]> {
  const out: ExplainFrame[] = [];
  for await (const f of readExplainStream(stream)) {
    out.push(f);
  }
  return out;
}

const BODY = [
  frame({ type: "status", phase: "generating" }),
  frame({ type: "delta", text: "National Taiwan " }),
  frame({ type: "delta", text: "University is ranked 68." }),
  frame({
    type: "done",
    success: true,
    source: "llm",
    modelName: "deepseek-v4-flash",
    paragraphs: ["National Taiwan University is ranked 68."],
  }),
  "data: [DONE]\n\n",
].join("");

describe("readExplainStream", () => {
  it("parses status, delta and done frames in order", async () => {
    const frames = await collect(streamOf([BODY]));

    expect(frames.map((f) => f.type)).toEqual(["status", "delta", "delta", "done"]);
  });

  it("reassembles deltas that arrive split mid-frame", async () => {
    // Cut the body at awkward offsets: inside a JSON payload, inside a word,
    // and right after a "data:" prefix.
    const cuts = [7, 31, 64, 120, 190];
    const pieces: string[] = [];
    let previous = 0;
    for (const cut of cuts) {
      pieces.push(BODY.slice(previous, cut));
      previous = cut;
    }
    pieces.push(BODY.slice(previous));

    const frames = await collect(streamOf(pieces));
    const text = frames
      .filter((f): f is Extract<ExplainFrame, { type: "delta" }> => f.type === "delta")
      .map((f) => f.text)
      .join("");

    expect(text).toBe("National Taiwan University is ranked 68.");
  });

  it("survives a multi-byte character split across two chunks", async () => {
    const body = frame({ type: "delta", text: "臺灣大學" });
    const bytes = new TextEncoder().encode(body);
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        // Split inside the UTF-8 encoding of a character.
        controller.enqueue(bytes.slice(0, 20));
        controller.enqueue(bytes.slice(20));
        controller.close();
      },
    });

    const frames = await collect(stream);

    expect(frames).toEqual([{ type: "delta", text: "臺灣大學" }]);
  });

  it("skips the [DONE] sentinel and unparseable frames without losing the rest", async () => {
    const body = [
      "data: not json at all\n\n",
      ": keep-alive comment\n\n",
      frame({ type: "delta", text: "kept" }),
      "data: [DONE]\n\n",
    ].join("");

    const frames = await collect(streamOf([body]));

    expect(frames).toEqual([{ type: "delta", text: "kept" }]);
  });

  it("yields a final frame when the body ends without a trailing newline", async () => {
    const frames = await collect(
      streamOf([`data: ${JSON.stringify({ type: "delta", text: "tail" })}`])
    );

    expect(frames).toEqual([{ type: "delta", text: "tail" }]);
  });

  it("emits only the terminal frame for a fallback answer", async () => {
    // No deltas: the deterministic reply is not shown, so nothing is streamed.
    const body = [
      frame({ type: "status", phase: "generating" }),
      frame({ type: "done", success: true, source: "fallback", paragraphs: [] }),
      "data: [DONE]\n\n",
    ].join("");

    const frames = await collect(streamOf([body]));

    expect(frames.filter((f) => f.type === "delta")).toEqual([]);
    expect(frames.at(-1)).toMatchObject({ type: "done", source: "fallback" });
  });
});

describe("splitParagraphs", () => {
  it("splits on blank lines and drops empties", () => {
    expect(splitParagraphs("one\n\ntwo\n\n\n\nthree")).toEqual(["one", "two", "three"]);
  });

  it("returns nothing for whitespace-only text", () => {
    expect(splitParagraphs("   \n\n  ")).toEqual([]);
  });
});
