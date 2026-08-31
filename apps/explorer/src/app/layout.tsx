import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { ApiStatusProvider } from "@/components/ApiStatusProvider";
import { SearchQueryProvider } from "@/components/SearchQueryProvider";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { copy } from "@/lib/copy";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: copy.defaultTitle,
    template: copy.titleTemplate,
  },
  description: copy.description,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="pt-BR"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-canvas text-foreground">
        <ApiStatusProvider>
          <SearchQueryProvider>
            <SiteHeader />
            <main className="flex-1">{children}</main>
            <SiteFooter />
          </SearchQueryProvider>
        </ApiStatusProvider>
      </body>
    </html>
  );
}
