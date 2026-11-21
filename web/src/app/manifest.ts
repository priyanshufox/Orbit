import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Orbit",
    short_name: "Orbit",
    description:
      "See who's in your orbit. Play a 5-minute round with friends and see how close you are.",
    start_url: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#f3ebd3",
    theme_color: "#2f6b3d",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icon-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
