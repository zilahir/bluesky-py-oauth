import { type ReactElement } from "react";
import { LoginForm } from "~/components/LoginForm";

function LoginPage(): ReactElement {
  return (
    <div className="w-full max-w-sm">
      <LoginForm />
    </div>
  );
}

export function meta() {
  return [
    { title: "Login" },
    { name: "description", content: "Login with your Bluesky account" },
  ];
}

export default LoginPage;
