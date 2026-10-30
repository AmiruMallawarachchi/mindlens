import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MindLensSocket } from "@/lib/websocket";

class MockWebSocket {
  static OPEN = 1;
  static instances: MockWebSocket[] = [];

  readyState = MockWebSocket.OPEN;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(
    readonly url: string,
    readonly protocols?: string | string[],
  ) {
    MockWebSocket.instances.push(this);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.readyState = 3;
  }
}

describe("MindLensSocket", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("connects with the session URL and JWT subprotocol", () => {
    const socket = new MindLensSocket(
      "session-1",
      () => "token-123",
      { onFrame: vi.fn() },
      async () => true,
    );

    socket.connect();

    const ws = MockWebSocket.instances[0];
    expect(ws.url).toBe("ws://localhost:8000/ws/chat/session-1");
    expect(ws.protocols).toEqual(["mindlens.jwt.token-123"]);
  });

  it("sends the message frame the backend expects", () => {
    const socket = new MindLensSocket(
      "session-1",
      () => "token-123",
      { onFrame: vi.fn() },
      async () => true,
    );
    socket.connect();
    const ws = MockWebSocket.instances[0];

    socket.sendMessage("I'm anxious about exams");

    expect(ws.sent).toHaveLength(1);
    expect(JSON.parse(ws.sent[0])).toEqual({
      type: "message",
      text: "I'm anxious about exams",
      session_id: "session-1",
      timestamp: expect.any(String),
    });
  });
});
