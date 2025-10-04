import { zodResolver } from "@hookform/resolvers/zod";
import type { ReactElement } from "react";
import { useForm } from "react-hook-form";
import z from "zod";
import { Button } from "~/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "~/components/ui/form";
import { Textarea } from "~/components/ui/textarea";
import useNewPost from "~/hooks/useNewPost";

const newPostSchema = z.object({
  post: z.string().min(1, "Post is required"),
});

function NewPostPage(): ReactElement {
  const form = useForm<z.infer<typeof newPostSchema>>({
    resolver: zodResolver(newPostSchema),
    defaultValues: {
      post: "",
    },
  });

  const { mutateAsync: createNewPost } = useNewPost();

  async function handleSubmit(values: z.infer<typeof newPostSchema>) {
    console.log("Form submitted with values:", values);
    // Here you would typically send the data to your API
    createNewPost({
      post: values.post,
    });
  }
  return (
    <div>
      <Card>
        <CardHeader>
          <CardTitle>New Post</CardTitle>
          <CardDescription>
            Create a new post to share with your followers.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleSubmit)}>
              <FormField
                control={form.control}
                name="post"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Post</FormLabel>
                    <FormControl>
                      <Textarea {...field} />
                    </FormControl>
                  </FormItem>
                )}
              />
              <div className="flex justify-end mt-4">
                <Button size="sm">Make post</Button>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}

export default NewPostPage;
