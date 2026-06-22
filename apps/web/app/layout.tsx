import type { Metadata } from "next";
import "./globals.css";
import { RealtimeProvider } from "@/lib/ws";

export const metadata: Metadata = {
  title: "JourneySync AI",
  description: "Omnichannel customer experience platform"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {/*
          RealtimeProvider opens a single shared WebSocket connection and
          fans server-sent events to all components that call useRealtime().
          The login page itself does not connect (no token in localStorage).
        */}
        <RealtimeProvider>
          {children}
        </RealtimeProvider>
      </body>
    </html>
  );
}
