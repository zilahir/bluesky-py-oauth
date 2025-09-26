import type { ReactElement } from "react";
import { Link } from "react-router";

function Header(): ReactElement {
  return (
    <header>
      <Link to="/logout">Logout</Link>
    </header>
  );
}

export default Header;
