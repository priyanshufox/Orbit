"use client";

import { useEffect, useRef, useState } from "react";

import { getApiToken } from "@/lib/api/browser";
import { API_URL } from "@/lib/api/config";
import type { components } from "@/lib/api/types";

export type RoomEvent = components["schemas"]["RoomEvent"];
export type SocketStatus = "connecting" | "live" | "offline" | "removed";

const WS_URL = API_URL.replace(/^http/, "ws");

/**
 * Live room events over `/ws/rooms/{code}` (task 3.4). Authenticates with the first message,
 * reconnects with backoff, and pings to keep proxies from closing an idle socket.
 */
export function useRoomSocket(code: string, onEvent: (event: RoomEvent) => void): SocketStatus {
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const handler = useRef(onEvent);
  useEffect(() => {
    handler.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!code) return;
    let ws: WebSocket | null = null;
    let stopped = false;
    let retry = 500;
    let ping: ReturnType<typeof setInterval> | undefined;
    let reconnect: ReturnType<typeof setTimeout> | undefined;

    async function connect() {
      const token = await getApiToken();
      if (stopped) return;
      if (!token) {
        setStatus("offline");
        return;
      }
      ws = new WebSocket(`${WS_URL}/ws/rooms/${code}`);
      ws.onopen = () => ws?.send(JSON.stringify({ type: "auth", token }));
      ws.onmessage = (msg) => {
        if (msg.data === "pong") return;
        const data = JSON.parse(msg.data as string);
        if (data.type === "ready") {
          setStatus("live");
          retry = 500;
          ping = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send("ping"), 25_000);
          return;
        }
        handler.current(data as RoomEvent);
      };
      ws.onclose = (e) => {
        clearInterval(ping);
        if (stopped) return;
        if (e.code === 4410 || e.code === 4403 || e.code === 4404) {
          setStatus("removed");
          return;
        }
        setStatus("offline");
        reconnect = setTimeout(connect, retry);
        retry = Math.min(retry * 2, 10_000);
      };
    }

    connect();
    return () => {
      stopped = true;
      clearInterval(ping);
      clearTimeout(reconnect);
      ws?.close();
    };
  }, [code]);

  return status;
}
