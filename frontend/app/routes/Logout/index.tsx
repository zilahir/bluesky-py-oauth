import { Loader2 } from "lucide-react";
import { useEffect, type ReactElement } from "react";
import { useNavigate } from "react-router";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import apiClient from "~/utils/api";

function LogOutPage(): ReactElement {
  const navigate = useNavigate();
  useEffect(() => {
    async function logout() {
      try {
        const response = await apiClient.get("auth/oauth/logout");

        return response.data;
      } catch (error) {
        console.error("Logout failed:", error);
      }
    }

    logout().then(() => {
      navigate("/login");
    });
  }, []);

  return (
    <div className="w-full max-w-sm">
      <Card>
        <CardHeader>
          <CardTitle>Logging out</CardTitle>
          <CardDescription>
            You are being logged out of the application...
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center">
            <Loader2 className="animate-spin w-10 h-10" />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default LogOutPage;
