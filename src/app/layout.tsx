import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({ subsets: ["latin"], weight: ["400", "500", "700", "800"] });

export const metadata: Metadata = {
  title: "EMPEROR | Creative Studio",
  description: "Cinematic dark theme portfolio",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body className={`${jakarta.className} bg-[#0A0A0A] text-neutral-300 antialiased min-h-screen flex flex-col`} suppressHydrationWarning>
        <main className="flex-1 w-full max-w-6xl mx-auto px-6 py-12 md:py-24">
          {children}
        </main>
      </body>
    </html>
  );
}
