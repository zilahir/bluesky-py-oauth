import { useMutation } from "@tanstack/react-query";
import apiClient from "~/utils/api";

interface NewPostContentDto {
  post: string;
}

async function createNewPost({ post }: NewPostContentDto) {
  const response = await apiClient.post("/posts/create", {
    post,
  });

  return response.data;
}

function useNewPost() {
  const mutation = useMutation({
    mutationKey: ["newPost"],
    mutationFn: async ({ post }: NewPostContentDto) => {
      const data = await createNewPost({ post });

      return data;
    },
  });

  return mutation;
}

export default useNewPost;
