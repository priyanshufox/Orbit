import type { components } from "@/lib/api/types";

export type RoomView = components["schemas"]["RoomView"];
export type Member = components["schemas"]["Member"];
export type DeckView = components["schemas"]["DeckView"];
export type Card = DeckView["cards"][number];
export type QuestionCard = Extract<Card, { kind: "question" }>;
export type ContentCard = Extract<Card, { kind: "content" }>;
export type GraphViewData = components["schemas"]["GraphView"];
export type Reaction = "like" | "laugh" | "skip" | "send";
