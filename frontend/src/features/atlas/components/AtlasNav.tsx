import { Boxes, Clock3, LayoutDashboard, Network } from "lucide-react";
import { NavLink } from "react-router-dom";

type AtlasNavProps = { repositoryId: string };

export function AtlasNav({ repositoryId }: AtlasNavProps) {
  const links = [
    ["overview", "Overview", LayoutDashboard],
    ["architecture", "Architecture", Network],
    ["subsystems", "Subsystems", Boxes],
    ["timeline", "Timeline", Clock3],
  ] as const;

  return (
    <nav className="atlas-nav" aria-label="Software Atlas sections">
      {links.map(([path, label, Icon]) => (
        <NavLink
          key={path}
          to={`/repositories/${repositoryId}/${path}`}
          className={({ isActive }) => (isActive ? "is-active" : undefined)}
        >
          <Icon size={15} aria-hidden="true" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
