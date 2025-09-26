import type { ReactElement } from "react";
import type { Route } from "./+types";
import useCampaign from "~/hooks/useCampaign";
import { EllipsisIcon, Loader2 } from "lucide-react";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "~/components/ui/popover";
import { Button } from "~/components/ui/button";
import { Badge } from "~/components/ui/badge";
import AccountsToFollowTable from "~/components/AccountsToFollowTable";

function CampaignDetailsPage({ params }: Route.ComponentProps): ReactElement {
  console.log("CampaignDetailsPage params:", params);

  const { id } = params;

  const { data, isLoading } = useCampaign({
    id,
  });

  if (isLoading) {
    return (
      <div>
        <Loader2 className="animate-spin h-6 w-6 text-gray-500" />
      </div>
    );
  }

  console.log("CampaignDetailsPage data:", data);
  return (
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
                {new Date(data?.created_at).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </CardDescription>
              <CardAction>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button variant="ghost" size="icon">
                      <EllipsisIcon className="h-4 w-4" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent>
                    <Button size="sm" variant="destructive">
                      Stop Campaign
                    </Button>
                  </PopoverContent>
                </Popover>
              </CardAction>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-3">
                <Card>
                  <CardHeader>
                    <CardTitle>Total accounts to get</CardTitle>
                    <CardDescription>{data?.followers.length}</CardDescription>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Followers gained</CardTitle>
                    <CardDescription>{data?.followers.length}</CardDescription>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle>Unfollowed</CardTitle>
                    <CardDescription>{data?.followers.length}</CardDescription>
                  </CardHeader>
                </Card>
              </div>
            </CardContent>
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
  );
}

export default CampaignDetailsPage;
