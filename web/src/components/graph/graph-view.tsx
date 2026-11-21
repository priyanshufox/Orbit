"use client";

/**
 * The closeness graph in 3D (tasks 7.1-7.4): players are planets in an X-Y-Z space with a
 * starfield. Positions come from the API (graph/layout.py): the distance between two planets
 * follows their closeness for every pair, so closer always means more alike. Group colour per planet, link thickness and label by score, follows as particles
 * flowing from follower to followed. Drag to orbit, scroll to zoom, tap a link for reasons.
 * Built on 3d-force-graph (three.js). Used on the host TV, phones and in history.
 */
import { useEffect, useRef } from "react";
import type * as THREE from "three";

import type { components } from "@/lib/api/types";

export type GraphData = Pick<components["schemas"]["GraphView"], "nodes" | "edges" | "follows">;
export type GraphEdge = components["schemas"]["GraphEdge"];

// Group colours from the brand palette; green and sky first so red-green colour-blind players
// can tell the two biggest groups apart. A legend names groups, so colour is never the only cue.
export const COMMUNITY_COLOURS = [
  "#3E8A4F", // grid-green-500
  "#5BB8E8", // sky-400
  "#D9A93B", // gold-500
  "#E8483A", // tomato-500
  "#F2D24B", // mustard-400
  "#9B4A4A", // maroon, lifted to read on the dark sky
  "#2F6B3D", // grid-green-700
  "#C2352A", // tomato-700
];

export const pct = (v: number) => `${Math.round(v * 100)}%`;

const SPACE = "#0b130e";
const CREAM = "#F3EBD3";
const TOMATO = "#E8483A";

type Node = {
  id: string;
  name: string;
  colour: string;
  me: boolean;
  fx?: number;
  fy?: number;
  fz?: number;
};
type Link = {
  id: string;
  source: string | Node;
  target: string | Node;
  kind: "close" | "follow";
  total: number;
  edge?: GraphEdge;
};
type Fg = {
  graphData: (d: { nodes: Node[]; links: Link[] }) => unknown;
  _destructor: () => void;
};

function toGraph(data: GraphData, me: string | undefined, nodes: Map<string, Node>) {
  // Reuse node objects so positions survive updates (e.g. a follow arriving after the reveal).
  const keep = new Map<string, Node>();
  const placed = data.nodes.some((n) => n.x || n.y || n.z);
  for (const n of data.nodes) {
    const node = nodes.get(n.id) ?? { id: n.id, name: n.name, colour: "", me: false };
    node.name = n.name;
    node.colour = COMMUNITY_COLOURS[n.community % COMMUNITY_COLOURS.length]!;
    node.me = n.id === me;
    // Pin planets where the closeness layout put them (older snapshots have no positions and
    // fall back to the force layout).
    if (placed) {
      node.fx = n.x;
      node.fy = n.y;
      node.fz = n.z;
    }
    keep.set(n.id, node);
  }
  nodes.clear();
  keep.forEach((v, k) => nodes.set(k, v));
  const links: Link[] = [
    ...data.edges.map((e) => ({
      id: `c:${e.a}:${e.b}`,
      source: e.a,
      target: e.b,
      kind: "close" as const,
      total: e.total,
      edge: e,
    })),
    ...data.follows.map((f) => ({
      id: `f:${f.from_user}:${f.to_user}`,
      source: f.from_user,
      target: f.to_user,
      kind: "follow" as const,
      total: 0,
    })),
  ].filter((l) => keep.has(l.source) && keep.has(l.target));
  return { nodes: [...keep.values()], links };
}

export function GraphView({
  data,
  me,
  size = "phone",
  onSelectEdge,
  className = "",
}: {
  data: GraphData;
  me?: string;
  size?: "phone" | "tv";
  onSelectEdge?: (edge: GraphEdge | null) => void;
  className?: string;
}) {
  const container = useRef<HTMLDivElement>(null);
  const graph = useRef<Fg | null>(null);
  const nodes = useRef(new Map<string, Node>());
  const select = useRef(onSelectEdge);
  const latest = useRef({ data, me });
  useEffect(() => {
    select.current = onSelectEdge;
    latest.current = { data, me };
  });

  // Build the scene once per size.
  useEffect(() => {
    let destroyed = false;
    let observer: ResizeObserver | null = null;
    const el = container.current;
    (async () => {
      const [{ default: ForceGraph3D }, THREE, { default: SpriteText }] = await Promise.all([
        import("3d-force-graph"),
        import("three"),
        import("three-spritetext"),
      ]);
      if (destroyed || !el) return;
      const tv = size === "tv";
      const planet = tv ? 9 : 8;
      const font = "Montserrat, Arial, sans-serif";

      const fg = new ForceGraph3D(el, { controlType: "orbit" })
        .backgroundColor(SPACE)
        .cooldownTime(3500) // settle fast, then frame the planets
        .showNavInfo(false)
        // Planets sit where their closeness puts them; dragging one would make distances lie.
        // Viewers can still orbit and zoom the camera.
        .enableNodeDrag(false)
        .width(el.clientWidth)
        .height(el.clientHeight)
        .nodeThreeObject((obj) => {
          const n = obj as unknown as Node;
          const group = new THREE.Group();
          const radius = n.me ? planet * 1.25 : planet;
          group.add(
            new THREE.Mesh(
              new THREE.SphereGeometry(radius, 32, 24),
              new THREE.MeshStandardMaterial({ color: n.colour, roughness: 0.55, metalness: 0.15 }),
            ),
          );
          // A faint atmosphere so planets read against the dark sky.
          group.add(
            new THREE.Mesh(
              new THREE.SphereGeometry(radius * 1.18, 24, 16),
              new THREE.MeshBasicMaterial({ color: n.colour, transparent: true, opacity: 0.18 }),
            ),
          );
          if (n.me) {
            const ring = new THREE.Mesh(
              new THREE.TorusGeometry(radius * 1.8, radius * 0.12, 8, 48),
              new THREE.MeshBasicMaterial({ color: TOMATO }),
            );
            ring.rotation.x = Math.PI / 2.6;
            group.add(ring);
          }
          const label = new SpriteText(n.me ? `${n.name} (you)` : n.name, tv ? 6 : 5.5, CREAM);
          label.fontFace = font;
          label.fontWeight = "800";
          label.position.y = -(radius * 1.9 + (tv ? 6 : 4));
          group.add(label);
          return group;
        })
        .linkColor((l) => ((l as unknown as Link).kind === "follow" ? TOMATO : CREAM))
        .linkOpacity(0.55)
        .linkWidth((l) => {
          const link = l as unknown as Link;
          return link.kind === "follow" ? 0 : 0.4 + link.total * (tv ? 3.2 : 2.2);
        })
        .linkCurvature((l) => ((l as unknown as Link).kind === "follow" ? 0.25 : 0))
        .linkDirectionalParticles((l) => ((l as unknown as Link).kind === "follow" ? 3 : 0))
        .linkDirectionalParticleWidth(tv ? 2.6 : 1.8)
        .linkDirectionalParticleColor(() => TOMATO)
        .linkThreeObjectExtend(true)
        .linkThreeObject((l) => {
          const link = l as unknown as Link;
          if (link.kind !== "close") return new THREE.Object3D();
          const s = new SpriteText(pct(link.total), tv ? 4.5 : 4, "#111111");
          s.backgroundColor = CREAM;
          s.padding = 1.2;
          s.borderRadius = 2;
          s.fontFace = font;
          s.fontWeight = "800";
          return s;
        })
        .linkPositionUpdate((obj, { start, end }) => {
          obj.position.set((start.x + end.x) / 2, (start.y + end.y) / 2, (start.z + end.z) / 2);
          return false;
        })
        .onLinkClick((l) => {
          const link = l as unknown as Link;
          if (link.kind === "close" && link.edge) select.current?.(link.edge);
        })
        .onBackgroundClick(() => select.current?.(null));

      const scene: THREE.Scene = fg.scene();
      // Starfield: points scattered on a far shell.
      const count = tv ? 2500 : 1200;
      const pos = new Float32Array(count * 3);
      for (let i = 0; i < count; i++) {
        const r = 700 + Math.random() * 900;
        const t = Math.random() * Math.PI * 2;
        const p = Math.acos(2 * Math.random() - 1);
        pos.set(
          [r * Math.sin(p) * Math.cos(t), r * Math.sin(p) * Math.sin(t), r * Math.cos(p)],
          i * 3,
        );
      }
      const stars = new THREE.BufferGeometry();
      stars.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      scene.add(
        new THREE.Points(
          stars,
          new THREE.PointsMaterial({
            color: CREAM,
            size: tv ? 2.2 : 1.6,
            sizeAttenuation: true,
            transparent: true,
            opacity: 0.85,
          }),
        ),
      );
      // X-Y-Z planes: faint grids through the origin, with axis labels.
      const addGrid = (rotate: (g: THREE.GridHelper) => void) => {
        const g = new THREE.GridHelper(360, 12, 0x3e8a4f, 0x24372a);
        const m = g.material as THREE.Material;
        m.transparent = true;
        m.opacity = 0.35;
        rotate(g);
        scene.add(g);
      };
      addGrid(() => undefined); // XZ
      addGrid((g) => (g.rotation.x = Math.PI / 2)); // XY
      addGrid((g) => (g.rotation.z = Math.PI / 2)); // YZ
      const axes: [string, number, number, number][] = [
        ["X", 195, 0, 0],
        ["Y", 0, 195, 0],
        ["Z", 0, 0, 195],
      ];
      for (const [text, x, y, z] of axes) {
        const axis = new SpriteText(text, 9, "#F2D24B");
        axis.fontFace = "Bangers, Impact, sans-serif";
        axis.position.set(x, y, z);
        scene.add(axis);
      }

      const controls = fg.controls() as { autoRotate?: boolean; autoRotateSpeed?: number };
      controls.autoRotate = true;
      controls.autoRotateSpeed = tv ? 0.6 : 0.8;
      fg.cameraPosition({ x: 0, y: 60, z: tv ? 360 : 230 });

      // Frame the planets once the layout settles; only once, so it never fights the viewer.
      let framed = false;
      fg.onEngineStop(() => {
        if (framed) return;
        framed = true;
        fg.zoomToFit(900, tv ? 80 : 30);
      });

      graph.current = fg as unknown as Fg;
      graph.current.graphData(toGraph(latest.current.data, latest.current.me, nodes.current));

      // With pinned planets, frame the bounding sphere so every planet stays in view at any
      // rotation angle (portrait phones are limited by the horizontal field of view).
      const pinned = [...nodes.current.values()].filter((n) => n.fx !== undefined);
      if (pinned.length) {
        const r =
          Math.max(...pinned.map((n) => Math.hypot(n.fx ?? 0, n.fy ?? 0, n.fz ?? 0))) + planet * 3;
        const halfTan =
          Math.tan(((40 / 2) * Math.PI) / 180) * Math.min(1, el.clientWidth / el.clientHeight);
        framed = true;
        fg.cameraPosition({ x: 0, y: r * 0.25, z: (r * 1.15) / halfTan }, { x: 0, y: 0, z: 0 });
      }

      observer = new ResizeObserver(() => fg.width(el.clientWidth).height(el.clientHeight));
      observer.observe(el);
    })();
    return () => {
      destroyed = true;
      observer?.disconnect();
      graph.current?._destructor();
      graph.current = null;
      if (el) el.innerHTML = "";
    };
  }, [size]);

  // New data (e.g. a follow after the reveal) without resetting positions.
  useEffect(() => {
    graph.current?.graphData(toGraph(data, me, nodes.current));
  }, [data, me]);

  return (
    <div
      ref={container}
      className={`h-full w-full overflow-hidden ${className}`}
      aria-label="Closeness graph in 3D: drag to rotate, scroll or pinch to zoom, tap a link for details"
      role="img"
    />
  );
}
