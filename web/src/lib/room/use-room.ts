"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api/browser";
import { type RoomEvent, type SocketStatus, useRoomSocket } from "@/lib/room/socket";
import type { GraphViewData, RoomView } from "@/lib/room/types";

export type RoomState = {
  room: RoomView | null;
  error: string | null;
  graph: GraphViewData | null;
  closingAt: string | null;
  removed: boolean;
  socket: SocketStatus;
  reload: () => Promise<RoomView | null>;
  setRoom: (r: RoomView) => void;
};

/** Room state kept live by the room's WebSocket events (host and members). */
export function useRoom(code: string, me: string): RoomState {
  const [room, setRoom] = useState<RoomView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [graph, setGraph] = useState<GraphViewData | null>(null);
  const [closingAt, setClosingAt] = useState<string | null>(null);
  const [removed, setRemoved] = useState(false);

  const reload = useCallback(async () => {
    const { data, response } = await api.GET("/rooms/{code}", { params: { path: { code } } });
    if (!data) {
      setError(
        response.status === 404
          ? "This room doesn't exist (or has expired)."
          : "Couldn't load the room.",
      );
      return null;
    }
    setRoom(data);
    setError(null);
    return data;
  }, [code]);

  const loadGraph = useCallback(async () => {
    const { data } = await api.GET("/rooms/{code}/graph", { params: { path: { code } } });
    if (data) setGraph(data);
  }, [code]);

  // Initial load: state is set in the promise callback, never synchronously in the effect.
  useEffect(() => {
    let live = true;
    api.GET("/rooms/{code}", { params: { path: { code } } }).then(({ data, response }) => {
      if (!live) return;
      if (data) setRoom(data);
      else
        setError(
          response.status === 404
            ? "This room doesn't exist (or has expired)."
            : "Couldn't load the room.",
        );
    });
    return () => {
      live = false;
    };
  }, [code]);

  const revealed = room?.state === "REVEALED";
  useEffect(() => {
    if (!revealed) return;
    let live = true;
    api.GET("/rooms/{code}/graph", { params: { path: { code } } }).then(({ data }) => {
      if (live && data) setGraph(data);
    });
    return () => {
      live = false;
    };
  }, [revealed, code]);

  const onEvent = useCallback(
    (e: RoomEvent) => {
      switch (e.type) {
        case "member_left":
          if (e.user_id === me) setRemoved(true);
          reload();
          break;
        case "reveal":
          reload().then(loadGraph);
          break;
        case "social_added":
          if (e.kind === "follow")
            setGraph((g) =>
              g && !g.follows.some((f) => f.from_user === e.from && f.to_user === e.to)
                ? { ...g, follows: [...g.follows, { from_user: e.from, to_user: e.to }] }
                : g,
            );
          break;
        case "room_closing":
          setClosingAt(e.expires_at);
          break;
        default:
          reload();
      }
    },
    [me, reload, loadGraph],
  );

  const listening = Boolean(room && (room.is_member || room.is_host) && !removed);
  const socket = useRoomSocket(listening ? code : "", onEvent);

  return {
    room,
    error,
    graph,
    closingAt,
    removed,
    socket: listening ? socket : "offline",
    reload,
    setRoom,
  };
}
