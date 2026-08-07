import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Omniboost RAG",
  description: "Accuracy-first, Confluence-native RAG chatbot.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-surface text-text font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
