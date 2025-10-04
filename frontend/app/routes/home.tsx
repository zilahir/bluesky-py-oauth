import type { ReactElement } from "react";
import type { Route } from "../+types/root";

export function meta({}: Route.MetaArgs) {
  return [
    { title: "Dashboard" },
    { name: "description", content: "Dashboard" },
  ];
}

export default function Home(): ReactElement {
  return (
    <div>
      <p>Placeholder for home</p>
    </div>
  );
}
