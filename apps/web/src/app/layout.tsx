import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DarkForge Channel OS",
  description: "Estacao local de inteligencia editorial e gestao de canais YouTube",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
