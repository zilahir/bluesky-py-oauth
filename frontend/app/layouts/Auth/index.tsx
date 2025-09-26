import type { ReactElement } from "react";
import { Navigate } from "react-router";
import Sidebar from "~/components/Sidebar";
import { Toaster } from "~/components/ui/sonner";
import useUser from "~/hooks/useUser";

function AuthLayout(): ReactElement {
  const { data: user, error, isLoading } = useUser();

  if ((!isLoading && error) || (!user && !isLoading)) {
    return <Navigate to="/login" replace />;
  }

  return (
    <main>
      <Sidebar />
      <Toaster position="bottom-right" />
    </main>
  );
}

export default AuthLayout;
