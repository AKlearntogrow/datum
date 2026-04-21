"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/admin", label: "Admin Home" },
  { href: "/admin/data-sources", label: "Data Sources" },
  { href: "/admin/scopes", label: "Scopes" },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <header className="border-b border-neutral-800 px-8 py-4">
        <div className="max-w-5xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/" className="text-lg font-bold hover:text-neutral-300">
              Datum
            </Link>
            <span className="text-xs px-2 py-0.5 rounded bg-neutral-800 text-neutral-400 border border-neutral-700">
              Admin
            </span>
          </div>
          <nav className="flex gap-4">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={
                  "text-sm px-3 py-1 rounded " +
                  (pathname === item.href
                    ? "bg-neutral-200 text-neutral-900"
                    : "text-neutral-400 hover:text-neutral-200")
                }
              >
                {item.label}
              </Link>
            ))}
            <Link
              href="/"
              className="text-sm px-3 py-1 rounded text-neutral-500 hover:text-neutral-300"
            >
              Review UI
            </Link>
          </nav>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-8 py-8">{children}</main>
    </div>
  );
}
