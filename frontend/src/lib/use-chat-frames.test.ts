import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useChatFrames } from "@/lib/use-chat-frames";
import type { EosSnapshot } from "@/lib/types";

const eos: EosSnapshot = {
  surface_emotion: "anxious",
  distress_level: 0.6,
};

describe("useChatFrames", () => {
  it("builds one provisional bubble from stream chunks", () => {
    const { result } = renderHook(() => useChatFrames());

    act(() => {
      result.current.handleFrame({ type: "stream_chunk", chunk: "Hello ", index: 0 });
      result.current.handleFrame({ type: "stream_chunk", chunk: "there", index: 1 });
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({
      role: "assistant",
      text: "Hello there",
      pending: true,
    });
  });

  it("replaces the provisional bubble with the authoritative response", () => {
    const { result } = renderHook(() => useChatFrames());

    act(() => {
      result.current.handleFrame({ type: "stream_chunk", chunk: "partial", index: 0 });
    });
    const provisionalId = result.current.messages[0].id;

    act(() => {
      result.current.handleFrame({
        type: "response",
        text: "final text",
        agents_used: ["assess", "finalize"],
        eos_snapshot: eos,
        crisis_flag: false,
      });
    });

    expect(result.current.messages).toHaveLength(1);
    expect(result.current.messages[0]).toMatchObject({
      id: provisionalId,
      text: "final text",
      pending: false,
      eos,
    });
    expect(result.current.thinking).toBe(false);
  });

  it("attaches the read to the last user message, not the assistant", () => {
    const { result } = renderHook(() => useChatFrames());

    act(() => {
      result.current.setMessages([
        { id: "u1", role: "user", text: "first" },
        { id: "a1", role: "assistant", text: "reply" },
        { id: "u2", role: "user", text: "second" },
      ]);
    });

    act(() => {
      result.current.handleFrame({
        type: "thinking_update",
        agents_active: ["assess"],
        eos,
        memory_recalled: ["Amaya — friend"],
      });
    });

    const [u1, a1, u2] = result.current.messages;
    expect(u1.eos).toBeUndefined();
    expect(a1.eos).toBeUndefined();
    expect(u2.eos).toEqual(eos);
    expect(u2.memoryRecalled).toEqual(["Amaya — friend"]);
  });

  it("marks a crisis reply and exposes the resources", () => {
    const { result } = renderHook(() => useChatFrames());
    const resources = [{ name: "Emergency", number: "119" }];

    act(() => {
      result.current.handleFrame({
        type: "crisis_response",
        text: "Please reach out now.",
        crisis_flag: true,
        resources,
        session_paused: true,
      });
    });

    expect(result.current.messages[0]).toMatchObject({
      role: "assistant",
      crisis: true,
    });
    expect(result.current.crisis).toEqual({
      text: "Please reach out now.",
      resources,
    });
  });
});
