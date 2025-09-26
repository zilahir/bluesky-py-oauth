import { useEffect, type ReactElement } from "react";
import { Loader2 } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { useNavigate } from "react-router";

function OauthCallBackPage(): ReactElement {
  const navigate = useNavigate();
  useEffect(() => {
    async function fakeTimer() {
      return new Promise((resolve) => setTimeout(resolve, 5000));
    }

    fakeTimer().then(() => {
      navigate("/");
    });
  }, []);
  return (
    <div className="w-screen h-screen flex items-center justify-center">
      <Card className="w-md">
        <CardHeader>
          <CardTitle>Login Successful</CardTitle>
          <CardDescription>
            You are being redirected to the app...
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

export default OauthCallBackPage;
