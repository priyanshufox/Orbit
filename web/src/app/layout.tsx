import type { Metadata, Viewport } from "next";
import { Bangers, Fraunces, Inter, Montserrat } from "next/font/google";
import "./globals.css";

import { ServiceWorker } from "@/components/service-worker";
import { ThemeToggle, themeBootScript } from "@/components/theme-toggle";

// Display: short shouts only. Heading/UI: heavy geometric sans. Body: clean sans. Accent: italic serif.
const display = Bangers({ variable: "--font-bangers", weight: "400", subsets: ["latin"] });
const heading = Montserrat({
  variable: "--font-montserrat",
  weight: ["700", "800"],
  subsets: ["latin"],
});
const body = Inter({ variable: "--font-inter", subsets: ["latin"] });
const accent = Fraunces({ variable: "--font-fraunces", style: "italic", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Orbit",
  description: "See who's in your orbit.",
  appleWebApp: { capable: true, title: "Orbit", statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#2f6b3d" },
    { media: "(prefers-color-scheme: dark)", color: "#16241a" },
  ],
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${display.variable} ${heading.variable} ${body.variable} ${accent.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className="flex min-h-full flex-col font-sans">
        <ThemeToggle />
        {children}
        <ServiceWorker />
      </body>
    </html>
  );
}
