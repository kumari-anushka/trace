import type { PropsWithChildren } from "react";

type PageContainerProps = PropsWithChildren<{
  className?: string;
}>;

export function PageContainer({
  children,
  className = "",
}: PageContainerProps) {
  return <div className={`page-container ${className}`.trim()}>{children}</div>;
}
