"use client";

import {
  BookOpen,
  Bot,
  Command,
  Frame,
  GalleryVerticalEnd,
  Map,
  PencilIcon,
  PieChart,
  PlusIcon,
  Settings2,
  SquareTerminal,
} from "lucide-react";

import { NavMain } from "~/components/nav-main";
import { NavProjects } from "~/components/nav-projects";
import { NavUser } from "~/components/nav-user";
import { TeamSwitcher } from "~/components/team-switcher";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarRail,
} from "~/components/ui/sidebar";
import type { User } from "~/types/User";
import useUser from "~/hooks/useUser";
import useCampaigns from "~/hooks/useCampaigns";
import type { Campaign } from "~/types/Campaigns";
import { useMemo } from "react";

const menuData = (user: User, campaigns: Campaign[]) => ({
  user: {
    name: user.handle,
    avatar: user.avatar,
  },
  teams: [
    {
      name: "BlueSkyne",
      logo: GalleryVerticalEnd,
      plan: "Enterprise",
    },
  ],
  navMain: [
    {
      title: "Campaigns",
      url: "#",
      icon: SquareTerminal,
      isActive: true,
      items: [
        {
          title: "New campaign",
          url: "/campaigns/new",
          icon: PlusIcon,
        },
        ...campaigns.map((campaign) => ({
          title: campaign.name,
          url: `/campaigns/${campaign.id}`,
          icon: Command,
        })),
      ],
    },
    {
      title: "New post",
      url: "/post/new",
      icon: PencilIcon,
    },
  ],
});

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { data: userData } = useUser();

  const { data: campaigns } = useCampaigns();

  const data = useMemo(() => {
    if (!userData || !campaigns) {
      return {
        user: { name: "", avatar: "" },
        teams: [],
        navMain: [],
        projects: [],
      };
    }
    return menuData(userData, campaigns);
  }, [userData, campaigns]);

  return (
    <Sidebar collapsible="icon" {...props}>
      <SidebarHeader>
        <TeamSwitcher teams={data.teams} />
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={data.navMain} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser user={data.user} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
