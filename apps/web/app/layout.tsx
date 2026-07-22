import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fit Check — Private AI Wardrobe & Outfit Copilot",
  description: "What to wear today, from clothes you actually own. Powered by Backblaze B2 & GMI Cloud.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
