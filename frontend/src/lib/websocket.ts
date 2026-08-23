/**
 * WebSocket client for backend/app/routers/chat.py's /ws/chat/{session_id}.
 *
 * Auth: the server reads the JWT from a cookie, an Authorization header, or
 * the `mindlens.jwt.<token>` subprotocol (see chat.py:_extract_token). The
 * browser WebSocket API can't set headers or cookies cross-origin, so the
 * subprotocol is the only one of those three a browser client can actually
 * use here.
 */

import type { ConnectionStatus, ServerFrame } from "./types";

function wsBaseUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_WS_BASE_URL;
  if (explicit) return explicit.replace(/\/+$/, "");
  const api = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  return api.replace(/^http/, "ws").replace(/\/+$/, "");
}

export interface MindLensSocketHandlers {
  onFrame: (frame: ServerFrame) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
}

const MAX_RECONNECT_DELAY_MS = 15_000;

// Codes the server uses for auth/authorization failures it will not recover
// from on retry (chat.py: 4001 missing/invalid token, 4003 origin/ownership).
const TERMINAL_CLOSE_CODES = new Set([4001, 4003]);

export class MindLensSocket {
  private ws: WebSocket | null = null;
  private status: ConnectionStatus = "idle";
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private closedByClient = false;
  /** True once a handshake has succeeded at least once on the current token.
   * A close *before* any open is how a rejected handshake presents to the
   * browser, which is the signal that the token — not the network — is the
   * problem. */
  private openedSinceLastAttempt = false;
  private refreshing = false;

  constructor(
    private readonly sessionId: string,
    /** Read fresh on every attempt, never captured. Access tokens expire
     * after `jwt_expire_minutes` (15 by default); holding the string from
     * construction meant that once it aged out, every reconnect re-sent the
     * same dead token and the server rejected the handshake forever, so
     * chat stayed down until a manual page reload. */
    private readonly getToken: () => string | null,
    private readonly handlers: MindLensSocketHandlers,
    /** Exchanges the httpOnly refresh cookie for a new access token.
     * Returns false when the refresh token itself has expired, which is a
     * genuine "sign in again", not something retrying can fix. */
    private readonly refreshToken: () => Promise<boolean>,
  ) {}

  connect(): void {
    this.closedByClient = false;
    this.open();
  }

  private open(): void {
    this.setStatus(this.reconnectAttempt > 0 ? "reconnecting" : "connecting");

    const token = this.getToken();
    if (!token) {
      this.setStatus("closed");
      return;
    }

    this.openedSinceLastAttempt = false;
    const url = `${wsBaseUrl()}/ws/chat/${this.sessionId}`;
    const socket = new WebSocket(url, [`mindlens.jwt.${token}`]);
    this.ws = socket;

    socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.openedSinceLastAttempt = true;
      this.setStatus("open");
    };

    socket.onmessage = (event) => {
      let frame: ServerFrame;
      try {
        frame = JSON.parse(event.data);
      } catch {
        return;
      }
      // The server's heartbeat sends {"type": "ping"} on an interval and
      // does not itself require a reply, but chat.py's message loop already
      // handles a client-sent "ping" -> "pong", so answering keeps the
      // exchange symmetric in case that ever becomes a liveness check.
      if (frame.type === "ping") {
        socket.send(JSON.stringify({ type: "pong" }));
      }
      this.handlers.onFrame(frame);
    };

    socket.onclose = (event) => {
      this.ws = null;
      if (this.closedByClient || TERMINAL_CLOSE_CODES.has(event.code)) {
        this.setStatus("closed");
        return;
      }
      this.setStatus("reconnecting");
      // A close with no preceding open is a rejected handshake. The server
      // answers an expired token with an HTTP 403 during the upgrade rather
      // than a 4001 close frame, so TERMINAL_CLOSE_CODES above never catches
      // it — without this branch the socket just retried the same expired
      // token until the user reloaded the page.
      if (!this.openedSinceLastAttempt && !this.refreshing) {
        this.refreshing = true;
        this.refreshToken()
          .then((ok) => {
            this.refreshing = false;
            if (this.closedByClient) return;
            if (!ok) {
              // The refresh token is gone too — retrying cannot fix this.
              this.setStatus("closed");
              return;
            }
            this.reconnectAttempt = 0;
            this.open();
          })
          .catch(() => {
            this.refreshing = false;
            if (!this.closedByClient) this.scheduleReconnect();
          });
        return;
      }
      this.scheduleReconnect();
    };

    // onclose always fires after onerror for a connection failure, and the
    // retry decision lives there — nothing to do here but let it happen.
    socket.onerror = () => {};
  }

  private scheduleReconnect(): void {
    const delay = Math.min(
      1000 * 2 ** this.reconnectAttempt,
      MAX_RECONNECT_DELAY_MS,
    );
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => {
      if (!this.closedByClient) this.open();
    }, delay);
  }

  sendMessage(text: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(
      JSON.stringify({
        type: "message",
        text,
        session_id: this.sessionId,
        timestamp: new Date().toISOString(),
      }),
    );
  }

  close(): void {
    this.closedByClient = true;
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close(1000, "Client closed");
    this.ws = null;
    this.setStatus("closed");
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.handlers.onStatusChange?.(status);
  }
}
