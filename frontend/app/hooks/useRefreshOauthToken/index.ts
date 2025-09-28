import { useMutation } from "@tanstack/react-query";
import apiClient from "~/utils/api";

export async function oauthRefreshToken() {
  const response = await apiClient.post("/auth/oauth/refresh");

  return response.data;
}

function useOauthRefreshToken() {
  const mutation = useMutation({
    mutationKey: ["oauthRefreshToken"],
    mutationFn: async () => {
      const data = oauthRefreshToken();

      return data;
    },
  });

  return mutation;
}

export default useOauthRefreshToken;
