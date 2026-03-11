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
  title: "悟空 Wukong | 高性能 AI Agent CLI 工具",
  description: "专为开发者设计的终端 AI 助手，支持多模型、上下文管理和自动化代码操作。",
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
