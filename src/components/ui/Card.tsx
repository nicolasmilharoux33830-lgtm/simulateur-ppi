import { HTMLAttributes } from "react";
import { clsx } from "clsx";

interface CardProps extends HTMLAttributes<HTMLDivElement> { hover?: boolean; }

export default function Card({ hover = false, className, children, ...props }: CardProps) {
  return (
    <div className={clsx("rounded-2xl shadow-sm border border-ink/5 bg-card", hover && "hover:shadow-md transition-shadow", className)} {...props}>
      {children}
    </div>
  );
}
