import type { ReactElement } from "react";
import { Outlet } from "react-router";

function Dashboard(): ReactElement {
  return <Outlet />;
}

export default Dashboard;
