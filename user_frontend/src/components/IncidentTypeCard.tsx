import Link from "next/link";
import type { IncidentTypeInfo } from "@/types/incident";
import { ICON_MAP } from "./icons";

export function IncidentTypeCard({ type }: { type: IncidentTypeInfo }) {
  const Icon = ICON_MAP[type.icon];

  return (
    <Link href={type.href} className="card card-interactive fade-up" style={{ display: "block" }}>
      <div
        style={{
          width: 52,
          height: 52,
          borderRadius: 14,
          background: "var(--color-accent-muted)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: 16,
          color: "var(--color-accent)",
        }}
      >
        {Icon ? <Icon size={26} /> : null}
      </div>
      <div style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>{type.label}</div>
      <div style={{ fontSize: 13, color: "var(--color-text-2)", lineHeight: 1.5 }}>
        {type.description}
      </div>
    </Link>
  );
}
