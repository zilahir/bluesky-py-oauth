import {
  type RouteConfig,
  index,
  route,
  layout,
  prefix,
} from "@react-router/dev/routes";

export default [
  layout("./layouts/UnAuth/index.tsx", [
    route("/login", "routes/Login/index.tsx"),
    route("/oauth/callback", "routes/Auth/Callback/index.tsx"),
    route("/logout", "./routes/Logout/index.tsx"),
  ]),

  layout("./layouts/Auth/index.tsx", [
    index("./routes/Dashboard/index.tsx"),
    route("/logout", "routes/LogOut/index.tsx"),
    route("account", "./routes/Account/index.tsx"),

    ...prefix("/campaigns", [
      index("./routes/Campaigns/index.tsx"),
      route("/new", "./routes/NewCampaign/index.tsx"),
      route("/:id", "./routes/Campaigns/Details/index.tsx"),
    ]),
  ]),
] satisfies RouteConfig;
