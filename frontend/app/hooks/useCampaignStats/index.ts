import { useQuery } from "@tanstack/react-query";
import apiClient from "~/utils/api";

interface UseCampaignStats {
  campaignId: string;
}

interface UseCampaignStatsResponse {
  campaign_id: string;
  campaign_name: string;
  stats: {
    total_followed_accounts: number;
    total_followers_gained: number;
    total_unfollowed_accounts: number;
    total_targets: number;
    setup_complete: boolean;
  };
}

async function getCampaignStats(campaignId: string) {
  const response = await apiClient.get<UseCampaignStatsResponse>(
    `/campaign/${campaignId}/stats`,
  );

  return response.data;
}

function useCampaignStats({ campaignId }: UseCampaignStats) {
  const query = useQuery({
    queryKey: ["campaignStats", campaignId],
    queryFn: async () => {
      const data = await getCampaignStats(campaignId);

      return data;
    },
  });

  return query;
}

export default useCampaignStats;
