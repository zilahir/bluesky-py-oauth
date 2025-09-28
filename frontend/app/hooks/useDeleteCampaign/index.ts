import { useMutation } from "@tanstack/react-query";
import apiClient from "~/utils/api";

interface IUseDeleteCampaign {
  campaignId: string;
  onSuccess?: () => void;
  onError?: (error: Error) => void;
}

async function deleteCampaign(campaignId: string): Promise<void> {
  const response = await apiClient.delete(`/api/campaign/${campaignId}`);
  return response.data;
}

function useDeleteCampaign({
  campaignId,
  onSuccess,
  onError,
}: IUseDeleteCampaign) {
  const mutation = useMutation({
    mutationKey: ["deleteCampaign", campaignId],
    mutationFn: async () => {
      const data = await deleteCampaign(campaignId);

      return data;
    },
  });

  return mutation;
}

export default useDeleteCampaign;
