import { useQuery } from "@tanstack/react-query";
import type { Campaign } from "~/types/Campaigns";
import apiClient from "~/utils/api";

interface CampaignResponse {
  data: Campaign[];
}

async function getAllCampaigns() {
  const response = await apiClient.get<CampaignResponse>("/api/campaigns");

  return response.data.data;
}

function useCampaigns() {
  const query = useQuery({
    queryKey: ["campaigns"],
    queryFn: async () => {
      const campaigns = await getAllCampaigns();
      return campaigns;
    },
    initialData: [],
  });

  return query;
}

export default useCampaigns;
