import React from "react";
import type { LucideIcon } from "lucide-react";
interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  text: string;
  action?: React.ReactNode;
}
export function EmptyState({
  icon: Icon,
  title,
  text,
  action
}: EmptyStateProps) {
  return <div className="empty-state">
      <div className="empty-icon">
        <Icon size={20} />
      </div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action}
    </div>;
}