/** The Orbit mark for generated icons (next/og ImageResponse supports a subset of CSS). */
export function OrbitMark({ size, padding = 0 }: { size: number; padding?: number }) {
  const inner = size - padding * 2;
  const ring = Math.round(inner * 0.07);
  return (
    <div
      style={{
        width: size,
        height: size,
        background: "#2F6B3D",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          width: inner * 0.78,
          height: inner * 0.78,
          borderRadius: "50%",
          border: `${ring}px solid #F3EBD3`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
        }}
      >
        <div
          style={{
            width: inner * 0.26,
            height: inner * 0.26,
            borderRadius: "50%",
            background: "#E8483A",
            border: `${Math.max(2, ring / 2)}px solid #111111`,
          }}
        />
        <div
          style={{
            position: "absolute",
            top: -ring * 1.6,
            right: inner * 0.08,
            width: inner * 0.16,
            height: inner * 0.16,
            borderRadius: "50%",
            background: "#F2D24B",
            border: `${Math.max(2, ring / 2)}px solid #111111`,
          }}
        />
      </div>
    </div>
  );
}
