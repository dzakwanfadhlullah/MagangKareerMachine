"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookmarkIcon,
  BriefcaseIcon,
  HomeIcon,
  KanbanIcon,
  LogoMark,
  SettingsIcon,
  StarIcon,
} from "./icons";

const navItems = [
  { href: "/dashboard", label: "Ringkasan", icon: HomeIcon },
  { href: "/dashboard/lowongan", label: "Cari Lowongan", icon: BriefcaseIcon },
  { href: "/dashboard/tersimpan", label: "Tersimpan", icon: BookmarkIcon },
  { href: "/dashboard/lamaran", label: "Lamaran Saya", icon: KanbanIcon },
  { href: "/dashboard/watchlist", label: "Watchlist", icon: StarIcon },
  { href: "/dashboard/pengaturan", label: "Pengaturan", icon: SettingsIcon },
];

function isActive(pathname: string, href: string) {
  if (href === "/dashboard") {
    return pathname === href;
  }
  return pathname.startsWith(href);
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <Link href="/dashboard" className="brand" aria-label="MagangKareer">
        <span className="brand-mark">
          <LogoMark />
        </span>
        <span>MagangKareer</span>
      </Link>

      <nav className="sidebar-nav" aria-label="Navigasi dashboard">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`sidebar-link ${isActive(pathname, item.href) ? "active" : ""}`}
            >
              <Icon />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="upgrade-card">
        <h3>Upgrade ke Premium</h3>
        <p>Dapatkan akses ke filter lanjutan, skor lebih akurat, dan peluang eksklusif.</p>
        <Link href="/dashboard/pengaturan" className="secondary-button">
          Upgrade Sekarang
        </Link>
      </div>
    </aside>
  );
}
