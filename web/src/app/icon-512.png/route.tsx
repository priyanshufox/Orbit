import { ImageResponse } from "next/og";

import { OrbitMark } from "@/components/brand/logo";

export function GET() {
  return new ImageResponse(<OrbitMark size={512} padding={0} />, { width: 512, height: 512 });
}
