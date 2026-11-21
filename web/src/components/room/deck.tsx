"use client";

/**
 * The self-paced round on a phone (task 4.5): one card at a time, a countdown, and every answer
 * or reaction saved through the outbox so a flaky connection loses nothing (4.6).
 */
import { useEffect, useMemo, useRef, useState } from "react";

import { Button, Card, MarkerCircle, Sparkles } from "@/components/ui";
import { mmss, useCountdown } from "@/lib/room/hooks";
import { Outbox } from "@/lib/room/outbox";
import type { ContentCard, DeckView, QuestionCard, Reaction } from "@/lib/room/types";

const REACTIONS: { value: Reaction; label: string }[] = [
  { value: "laugh", label: "😂 Haha" },
  { value: "like", label: "👍 Like" },
  { value: "send", label: "📤 Send" },
  { value: "skip", label: "⏭ Skip" },
];

export function Deck({
  code,
  deck,
  onFinish,
}: {
  code: string;
  deck: DeckView;
  onFinish: () => void;
}) {
  const [pending, setPending] = useState(0);
  const outbox = useRef<Outbox | null>(null);
  useEffect(() => {
    outbox.current = new Outbox(code, setPending);
  }, [code]);

  const done = useMemo(() => {
    const s = new Set<string>([...Object.keys(deck.answers), ...Object.keys(deck.reactions)]);
    return s;
  }, [deck]);
  // Resume at the first card not yet answered (after a reload or reconnect).
  const [index, setIndex] = useState(() => {
    const first = deck.cards.findIndex((c) => !done.has(c.id));
    return first === -1 ? deck.cards.length : first;
  });
  const left = useCountdown(deck.ends_at);
  const card = deck.cards[index];
  const next = () => setIndex((i) => i + 1);

  if (!card || left === 0) {
    return (
      <div className="sticker bg-surface animate-pop space-y-4 p-6 text-center">
        <Sparkles className="justify-center" />
        <p className="font-display text-5xl uppercase">{left === 0 ? "Time's up!" : "All done!"}</p>
        <p className="text-foreground/75">
          {pending > 0
            ? `Saving ${pending} answer${pending > 1 ? "s" : ""}…`
            : "Everything is saved."}
        </p>
        <Button onClick={onFinish} disabled={pending > 0}>
          I&apos;m finished
        </Button>
      </div>
    );
  }

  const questionNo = deck.cards.slice(0, index + 1).filter((c) => c.kind === "question").length;
  const questionTotal = deck.cards.filter((c) => c.kind === "question").length;
  const label =
    card.kind === "question"
      ? `Question ${questionNo}/${questionTotal}`
      : { fact: "Fact", meme: "Meme", news: "Headline" }[card.content_type];

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3 text-sm">
        <div
          className="border-ink bg-surface h-4 flex-1 overflow-hidden rounded-full border-[2.5px]"
          role="progressbar"
          aria-valuenow={index}
          aria-valuemax={deck.cards.length}
          aria-label="Cards done"
        >
          <div
            className="bg-highlight border-ink h-full border-r-[2.5px] transition-all duration-[240ms]"
            style={{ width: `${(index / deck.cards.length) * 100}%` }}
          />
        </div>
        <span className="font-heading font-extrabold tabular-nums">
          {index + 1}/{deck.cards.length}
        </span>
        {left !== null && (
          <span
            className={`font-heading rounded-[6px] border-2 px-1.5 font-extrabold tabular-nums ${left < 30 ? "border-danger text-danger" : "border-transparent"}`}
            aria-label={`${left} seconds left`}
          >
            {left < 30 && "⏰ "}
            {mmss(left)}
          </span>
        )}
      </div>

      <Card key={card.id} label={label}>
        {card.kind === "question" ? (
          <Question
            card={card}
            initial={deck.answers[card.id]}
            onAnswer={(value) => {
              outbox.current?.put({ kind: "answer", id: card.id, value });
              next();
            }}
          />
        ) : (
          <Content
            card={card}
            onReact={(reaction) => {
              outbox.current?.put({ kind: "reaction", id: card.id, reaction });
              next();
            }}
          />
        )}
      </Card>
      {pending > 0 && <p className="text-foreground/60 text-center text-xs">Saving… ({pending})</p>}
    </div>
  );
}

const choiceStyle =
  "sticker-sm press bg-background hover:bg-highlight hover:text-on-highlight px-4 py-3 text-left text-base font-medium";

function Question({
  card,
  initial,
  onAnswer,
}: {
  card: QuestionCard;
  initial?: Record<string, unknown>;
  onAnswer: (value: Record<string, unknown>) => void;
}) {
  const choices = (card.options.choices as string[] | undefined) ?? [];
  const [multi, setMulti] = useState<number[]>((initial?.choices as number[]) ?? []);
  const [slider, setSlider] = useState<number>(((initial?.value as number) ?? 0.5) * 100);

  return (
    <div className="space-y-5">
      <h2 className="font-heading text-2xl leading-snug font-extrabold">{card.prompt}</h2>
      {card.question_kind === "single" && (
        <div className="grid gap-3">
          {choices.map((c, i) => (
            <button key={c} onClick={() => onAnswer({ choice: i })} className={choiceStyle}>
              {c}
            </button>
          ))}
        </div>
      )}
      {card.question_kind === "multi" && (
        <>
          <p className="font-accent text-foreground/70 text-sm italic">Pick all that apply.</p>
          <div className="flex flex-wrap gap-3">
            {choices.map((c, i) => {
              const on = multi.includes(i);
              return (
                <button
                  key={c}
                  aria-pressed={on}
                  onClick={() => setMulti((m) => (on ? m.filter((x) => x !== i) : [...m, i]))}
                  className={`press border-ink relative rounded-full border-[2.5px] px-4 py-2 font-medium ${on ? "bg-highlight shadow-hard-xs" : "bg-background"}`}
                >
                  {on && "✓ "}
                  {c}
                  {on && <MarkerCircle />}
                </button>
              );
            })}
          </div>
          <Button onClick={() => onAnswer({ choices: multi })}>Next</Button>
        </>
      )}
      {card.question_kind === "slider" && (
        <>
          <input
            type="range"
            min={0}
            max={100}
            value={slider}
            onChange={(e) => setSlider(Number(e.target.value))}
            className="accent-tomato-700 h-3 w-full"
            aria-label={card.prompt}
          />
          <div className="font-heading flex justify-between text-xs font-extrabold tracking-wide uppercase">
            <span>{String(card.options.min_label)}</span>
            <span>{String(card.options.max_label)}</span>
          </div>
          <Button onClick={() => onAnswer({ value: slider / 100 })}>Next</Button>
        </>
      )}
    </div>
  );
}

function Content({ card, onReact }: { card: ContentCard; onReact: (r: Reaction) => void }) {
  const p = card.payload as Record<string, string | undefined>;
  return (
    <div className="space-y-5">
      {card.content_type === "meme" && p.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={p.image_url}
          alt={p.caption ?? "Meme"}
          className="border-ink w-full rounded-[8px] border-[2.5px]"
        />
      ) : card.content_type === "news" ? (
        <div className="space-y-2">
          <p className="font-accent text-foreground/70 text-sm italic">{p.outlet}</p>
          <p className="font-heading text-xl leading-snug font-extrabold">{p.headline}</p>
          {card.source_url && (
            <a
              href={card.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="text-action-text text-sm font-semibold underline"
            >
              Read the story
            </a>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <p className="font-accent text-foreground/70 text-sm italic">Did you know?</p>
          <p className="text-xl leading-snug font-medium">{p.text}</p>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3">
        {REACTIONS.map((r) => (
          <button
            key={r.value}
            onClick={() => onReact(r.value)}
            className="sticker-sm press bg-background hover:bg-highlight hover:text-on-highlight font-heading py-3 text-sm font-extrabold tracking-wide uppercase"
          >
            {r.label}
          </button>
        ))}
      </div>
    </div>
  );
}
