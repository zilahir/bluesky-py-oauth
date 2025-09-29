import { type ReactElement, useState } from "react";
import type { Route } from "./+types";
import useCampaign from "~/hooks/useCampaign";
import { EllipsisIcon, Loader2 } from "lucide-react";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { Button } from "~/components/ui/button";
import { Badge } from "~/components/ui/badge";
import AccountsToFollowTable from "~/components/AccountsToFollowTable";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "~/components/ui/dropdown-menu";
import ConfirmDeleteCampaignDialog from "~/components/ConfirmDeletCampaignDialog";
import useCampaignStats from "~/hooks/useCampaignStats";
import { Progress } from "~/components/ui/progress";
import { format, formatRelative, intervalToDuration } from "date-fns";

function CampaignDetailsPage({ params }: Route.ComponentProps): ReactElement {
  const { id } = params;
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);

  const { data, isLoading } = useCampaign({
    id,
  });

  const { data: campaignStat, isLoading: isCampaignStatsLoading } =
    useCampaignStats({
      campaignId: id,
    });

  if (isLoading) {
    return (
      <div>
        <Loader2 className="animate-spin h-6 w-6 text-gray-500" />
      </div>
    );
  }

  console.log("Campaign Stats", campaignStat);

  return (
    <>
      <div>
        {!isLoading && data?.is_setup_job_running && (
          <Card>
            <CardHeader>
              <CardTitle>Hang tight!</CardTitle>
              <CardDescription>
                Your campaign is currently being set up
              </CardDescription>
            </CardHeader>

            <CardContent>
              <Loader2 className="animate-spin h-10 w-10 text-gray-500" />
            </CardContent>
          </Card>
        )}
        {!isLoading && data && !data?.is_setup_job_running && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="capitalize flex items-center flex-row gap-2">
                  <span>{data?.name}</span>
                  <span>
                    {data?.is_campaign_running && (
                      <Badge>
                        <Loader2 className="animate-spin" />
                        Running
                      </Badge>
                    )}
                  </span>
                </CardTitle>
                <CardDescription>
                  <p className="flex flex-row items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {format(new Date(data?.created_at), "dd MMM yyyy HH:mm")}
                    </span>
                    |
                    <span className="text-xs text-muted-foreground">
                      {Object.keys(
                        intervalToDuration({
                          start: new Date(data?.created_at),
                          end: new Date(),
                        }),
                      )
                        .map((key) => {
                          const value = intervalToDuration({
                            start: new Date(data?.created_at),
                            end: new Date(),
                          })[
                            key as keyof ReturnType<typeof intervalToDuration>
                          ];
                          return value ? `${value} ${key} ` : "";
                        })
                        .join(" ")}
                    </span>
                  </p>
                </CardDescription>
                <CardAction>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" className="h-8 w-8 p-0">
                        <span className="sr-only">Open menu</span>
                        <EllipsisIcon />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuLabel>Actions</DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={(e) => {
                          e.preventDefault();
                          setIsDeleteDialogOpen(true);
                        }}
                      >
                        Delete Campaign
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </CardAction>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-3">
                  <Card>
                    <CardHeader>
                      <CardTitle>Total accounts to get</CardTitle>
                      <CardDescription>
                        {isCampaignStatsLoading ? (
                          <Loader2 className="animate-spin h-4 w-4 text-gray-500" />
                        ) : (
                          campaignStat?.stats.total_targets || 0
                        )}
                      </CardDescription>
                    </CardHeader>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle>Followers gained</CardTitle>
                      <CardDescription>
                        {isCampaignStatsLoading ? (
                          <Loader2 className="animate-spin h-4 w-4 text-gray-500" />
                        ) : (
                          campaignStat?.stats.total_followers_gained || 0
                        )}
                      </CardDescription>
                    </CardHeader>
                  </Card>
                  <Card>
                    <CardHeader>
                      <CardTitle>Unfollowed</CardTitle>
                      <CardDescription>
                        {isCampaignStatsLoading ? (
                          <Loader2 className="animate-spin h-4 w-4 text-gray-500" />
                        ) : (
                          campaignStat?.stats.total_unfollowed_accounts || 0
                        )}
                      </CardDescription>
                    </CardHeader>
                  </Card>
                </div>
              </CardContent>
              <CardFooter>
                {!isCampaignStatsLoading && campaignStat && (
                  <Progress
                    value={
                      (campaignStat?.stats.total_followers_gained /
                        campaignStat?.stats.total_targets) *
                        100 || 0
                    }
                  />
                )}
              </CardFooter>
            </Card>
            <div className="space-y-3">
              <h1 className="text-xl font-semibold text-foreground">
                Accounts to follow
              </h1>
              <AccountsToFollowTable data={data.followers} />
            </div>
          </div>
        )}
      </div>

      <ConfirmDeleteCampaignDialog
        open={isDeleteDialogOpen}
        onOpenChange={setIsDeleteDialogOpen}
        campaignId={id}
      />
    </>
  );
}

export default CampaignDetailsPage;
