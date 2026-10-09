import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NOVEL AI TRANSLATOR — Dịch truyện từ URL sang tiếng Việt bằng AI",
  description:
    "Công cụ dịch tiểu thuyết, web novel từ URL sang tiếng Việt bằng AI. Tự động chia đoạn, bảo toàn ngữ cảnh thoại, quản lý thuật ngữ Glossary và trình đọc truyện hiện đại.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className="dark">
      <body className="bg-[#080B11] text-slate-100 antialiased selection:bg-indigo-500 selection:text-white min-h-screen">
        {children}
      </body>
    </html>
  );
}
