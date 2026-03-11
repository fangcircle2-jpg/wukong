import type { Metadata } from "next";
import { DM_Sans, Noto_Serif_SC, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
});

const notoSerifSC = Noto_Serif_SC({
  variable: "--font-noto-serif",
  subsets: ["latin"],
  weight: ["400", "500", "700", "900"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Wukong | High-Performance AI Agent CLI",
  description: "Terminal AI assistant for developers. Multi-model support, context management, and automated code operations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="light">
      <body
        className={`${dmSans.variable} ${notoSerifSC.variable} ${jetbrainsMono.variable} font-sans antialiased selection:bg-primary/20 selection:text-primary`}
      >
        <div className="noise-overlay" />
        {children}
      </body>
    </html>
  );
}
