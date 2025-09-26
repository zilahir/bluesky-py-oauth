import { useState, type ReactElement } from "react";
import { cn } from "~/lib/utils";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "../ui/card";
import { Input } from "../ui/input";
import { Button } from "../ui/button";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Form, FormControl, FormField, FormItem, FormLabel } from "../ui/form";
import apiClient from "~/utils/api";
import { Loader2 } from "lucide-react";

interface AuthError {}

interface AuthResponse {
  message: string;
  redirect_url: string;
}

const loginFormSchema = z.object({
  username: z.string().min(3),
});

export function LoginForm({
  className,
  ...props
}: React.ComponentProps<"div">): ReactElement {
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const form = useForm<z.infer<typeof loginFormSchema>>({
    resolver: zodResolver(loginFormSchema),
    defaultValues: {
      username: "",
    },
  });

  async function handleBlueSkyLogin(values: z.infer<typeof loginFormSchema>) {
    setIsLoading(true);
    const formData = new URLSearchParams();
    const username = values.username.trim();
    formData.append("username", username);

    try {
      const response = await apiClient.post<AuthResponse>(
        "auth/oauth/login",
        formData.toString(),
        {
          withCredentials: true,
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
        },
      );
      console.log(response.data);

      window.location.href = response.data.redirect_url;
    } catch (err: any) {
      // TODO: type generic axios API error
      console.error(err.response?.data || err.message);
      setIsLoading(false);
    }
  }

  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <Card>
        <CardHeader>
          <CardTitle>Login to your account</CardTitle>
          <CardDescription>
            Enter your email below to login to your account
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(handleBlueSkyLogin)}>
              <div className="flex flex-col gap-6">
                <FormField
                  control={form.control}
                  name="username"
                  render={({ field }) => (
                    <FormItem>
                      <div className="flex items-center gap-2">
                        <img
                          alt="blusky logo"
                          src="/bsky-logo.png"
                          className="h-5 w-5"
                        />

                        <FormLabel className="text-sm">
                          Bluesky Username
                        </FormLabel>
                      </div>
                      <FormControl>
                        <Input {...field} placeholder="@name.bsky.social" />
                      </FormControl>
                    </FormItem>
                  )}
                />
                <div className="flex flex-col gap-3">
                  <Button disabled={isLoading} type="submit" className="w-full">
                    {isLoading && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Login
                  </Button>
                </div>
              </div>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
}
