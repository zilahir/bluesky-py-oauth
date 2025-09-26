import { useMutation } from "@tanstack/react-query";
import apiClient from "~/utils/api";

interface AccountsToFollow {
  handle: string;
  did: string;
}

interface NewCampaignDTO {
  name: string;
  accountsToFollow: AccountsToFollow[];
}

async function createNewCampaig(dto: NewCampaignDTO) {
  const response = await apiClient.post("/api/new-campaign", dto);

  return response.data;
}

function useNewCampaign() {
  const mutation = useMutation({
    mutationKey: ["newCampaign"],
    mutationFn: createNewCampaig,
  });

  return mutation;
}

export default useNewCampaign;
