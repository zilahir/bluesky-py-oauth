import type { ReactElement } from "react";
import { Link, Outlet, useMatches } from "react-router";
import { AppSidebar } from "~/components/app-sidebar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "~/components/ui/breadcrumb";
import { Separator } from "~/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "~/components/ui/sidebar";

function Sidebar(): ReactElement {
  const matches = useMatches();

  function getBreadcrumbTarget(match: any) {
    const matchId = typeof match === "string" ? match : match.id;

    if (matchId === "root") {
      return "Home";
    }
    if (matchId === "routes/Dashboard/index") {
      return "Dashboard";
    }
    if (matchId === "routes/Campaigns/index") {
      return "Campaigns";
    }
    if (matchId === "routes/Campaigns/Details/index") {
      const thisMatch = matches.find(({ id }) => id === matchId);
      if (thisMatch && thisMatch.loaderData && thisMatch.loaderData.campaign) {
        return thisMatch.loaderData.campaign.name;
      }
      return "Campaign Details";
    }
    if (matchId === "routes/NewCampaign/index") {
      return "New Campaign";
    }
    if (matchId === "routes/Account/index") {
      return "Account";
    }

    return matchId;
  }
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-data-[collapsible=icon]/sidebar-wrapper:h-12">
          <div className="flex items-center gap-2 px-4">
            <SidebarTrigger className="-ml-1" />
            <Separator
              orientation="vertical"
              className="mr-2 data-[orientation=vertical]:h-4"
            />
            <Breadcrumb>
              <BreadcrumbList>
                {matches
                  .filter(
                    (match) =>
                      !match.id.includes("layouts/Auth") &&
                      match.id !== "routes/Dashboard/Home/index" &&
                      match.id !== "root" &&
                      match.id !== "routes/home",
                  )
                  .map((match, index, filteredMatches) => (
                    <div key={match.id} className="flex items-center">
                      <BreadcrumbItem className="hidden md:block">
                        {index === filteredMatches.length - 1 ? (
                          <BreadcrumbPage className="capitalize">
                            {getBreadcrumbTarget(match)}
                          </BreadcrumbPage>
                        ) : (
                          <BreadcrumbLink asChild>
                            <Link to={match.pathname || "/"}>
                              {getBreadcrumbTarget(match)}
                            </Link>
                          </BreadcrumbLink>
                        )}
                      </BreadcrumbItem>
                      {index < filteredMatches.length - 1 && (
                        <BreadcrumbSeparator className="hidden md:block" />
                      )}
                    </div>
                  ))}
              </BreadcrumbList>
            </Breadcrumb>
          </div>
        </header>
        <div className="p-4">
          <Outlet />
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}

export default Sidebar;
