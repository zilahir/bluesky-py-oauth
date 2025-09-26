import { useQuery } from "@tanstack/react-query";
import type { User } from "~/types/User";
import apiClient from "~/utils/api";

interface MeApiResponse {
  message: string;
  user: User;
}

async function getUser(): Promise<MeApiResponse> {
  const response = await apiClient.get<MeApiResponse>("/me");

  return response.data;
}

function useUser() {
  const query = useQuery({
    queryKey: ["user"],
    queryFn: async () => {
      const user = await getUser();
      return user;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    select: (data) => {
      return data.user;
    },
  });

  return query;
}

export default useUser;
