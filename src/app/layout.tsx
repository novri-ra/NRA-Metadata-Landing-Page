import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "NRA Portfolio",
  description: "Senior Fullstack Developer Portfolio",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${inter.className} min-h-screen flex flex-col`} suppressHydrationWarning>
        <main className="flex-1 w-full max-w-5xl mx-auto px-6 py-12 md:py-24">
          {children}
        </main>
      </body>
    </html>
  );
}
