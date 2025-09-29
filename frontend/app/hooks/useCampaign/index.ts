import { useQuery } from "@tanstack/react-query";
import type { Campaign } from "~/types/Campaigns";
import apiClient from "~/utils/api";

interface IUSeCampagin {
  id: string;
}

interface CampaignResponse {
  data: Campaign;
}

export async function getCampaign(id: string) {
  const response = await apiClient.get<CampaignResponse>(`/api/campaign/${id}`);

  return response.data;
}

function useCampaign({ id }: IUSeCampagin) {
  const query = useQuery({
    queryKey: ["campaign", id],
    queryFn: async () => {
      const campaign = await getCampaign(id);
      return campaign.data;
    },
  });

  return query;
}

export default useCampaign;
