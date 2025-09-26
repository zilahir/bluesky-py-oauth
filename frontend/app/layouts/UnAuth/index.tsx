import type { ReactElement } from "react";
import { Outlet } from "react-router";

function UnAuthLayout(): ReactElement {
  return (
    <div className="flex min-h-svh w-full items-center justify-center p-6 md:p-10">
      <Outlet />
    </div>
  );
}

export default UnAuthLayout;
