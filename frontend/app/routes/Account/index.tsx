import type { ReactElement } from "react";
import { Button } from "~/components/ui/button";
import useOauthRefreshToken from "~/hooks/useRefreshOauthToken";

function AccountPage(): ReactElement {
  const { mutate: refreshToken } = useOauthRefreshToken();
  return (
    <div>
      <div>
        <h1>
          Refresh token
          <Button onClick={() => refreshToken()}>Refresh Token</Button>
        </h1>
      </div>
    </div>
  );
}

export default AccountPage;
