import { ImageResponse } from "next/og";

import { OrbitMark } from "@/components/brand/logo";

export function GET() {
  return new ImageResponse(<OrbitMark size={192} padding={0} />, { width: 192, height: 192 });
}
