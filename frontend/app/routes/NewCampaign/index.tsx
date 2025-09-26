import { useState, type ReactElement } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "~/components/ui/card";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
} from "~/components/ui/form";
import { Input } from "~/components/ui/input";
import { z } from "zod";
import { Label } from "~/components/ui/label";
import { Button } from "~/components/ui/button";
import { CircleXIcon, Loader2, PlusIcon } from "lucide-react";
import useBlueskyAccounts from "~/store/useBlueskyAccounts";
import { Avatar } from "@radix-ui/react-avatar";
import { AvatarFallback, AvatarImage } from "~/components/ui/avatar";
import apiClient from "~/utils/api";
import type { BlueSkyAccount } from "~/types/BlyeSkyAccount";
import useNewCampaign from "~/hooks/useNewCampaign";

interface GetBlueskyProfileResponse {
  followers_count: number;
  account: BlueSkyAccount;
}

const newCampaignSchema = z.object({
  name: z.string().min(1, "Campaign name is required"),
});

function NewCampaignPage(): ReactElement {
  const form = useForm<z.infer<typeof newCampaignSchema>>({
    resolver: zodResolver(newCampaignSchema),
    defaultValues: {
      name: "",
    },
  });

  const { mutateAsync, isPending } = useNewCampaign();

  console.log("form errors:", form.formState.errors);

  const [newAccountHandle, setNewAccountHandle] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const { addAccount, accounts, removeAccount, clearAccounts } =
    useBlueskyAccounts();

  async function getBlueskyProfile(handle: string) {
    const responnse = await apiClient.get<GetBlueskyProfileResponse>(
      `/api/get-bluesky-profile/${handle}`,
    );

    return responnse.data;
  }

  async function handleCreateCampaign(
    values: z.infer<typeof newCampaignSchema>,
  ) {
    const { name } = values;

    mutateAsync({
      name,
      accountsToFollow: accounts.map((account) => ({
        handle: account.account.handle,
        did: account.account.did,
      })),
    }).then(() => {
      form.reset();
      clearAccounts();

      toast.success("Campaign created successfully!");
    });
  }

  async function handleNewAccount(handle: string) {
    if (!handle) {
      console.error("Invalid handle. It should start with '@'.");
      return;
    }

    setIsLoading(true);
    const trimmedHandle = handle.trim();

    const blueSkyProfile = await getBlueskyProfile(trimmedHandle);
    setIsLoading(false);

    addAccount(blueSkyProfile.account, blueSkyProfile.followers_count);
    setNewAccountHandle("");
  }

  return (
    <div>
      <div>
        <Card>
          <CardHeader>
            <CardTitle>Create new campaign</CardTitle>
            <CardDescription>
              Creating a campaign will auto-follow BlueSky accounts on your
              behalf, to help you grow your network.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Form {...form}>
                <form onSubmit={form.handleSubmit(handleCreateCampaign)}>
                  <FormField
                    control={form.control}
                    name="name"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Campaign Name</FormLabel>
                        <FormControl>
                          <Input {...field} placeholder="Enter campaign name" />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                  <Button disabled={isPending || isLoading} type="submit">
                    {isPending && (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    )}
                    Create Campaign
                  </Button>
                </form>
              </Form>
              <div className="space-y-2">
                <Label>
                  Bluesky handle of accouts whos followers you want to follow
                  you:
                </Label>
                <div className="flex flex-row items-center gap-2">
                  <Input
                    value={newAccountHandle}
                    onChange={(e) => setNewAccountHandle(e.target.value)}
                    placeholder="@example"
                    className=""
                  />
                  <Button
                    onClick={(): Promise<void> =>
                      handleNewAccount(newAccountHandle)
                    }
                    disabled={isLoading}
                  >
                    {!isLoading && <PlusIcon />}
                    {isLoading && <Loader2 className="animate-spin h-4 w-4" />}
                    Add
                  </Button>
                </div>
              </div>
              {accounts.length > 0 && (
                <div className="space-y-3">
                  <Label>Added Accounts:</Label>
                  <ul className="flex flex-row flex-wrap gap-2">
                    {accounts.map((account) => (
                      <li
                        className="flex flex-row gap-2 items-center border p-1 rounded-md"
                        key={account.account.handle}
                      >
                        <Avatar className="h-5 w-5 rounded-full">
                          <AvatarImage
                            src={account.account.avatar}
                            alt={account.account.handle}
                          />
                          <AvatarFallback className="rounded-lg">
                            {account.account.handle.slice(1, 3).toUpperCase()}
                          </AvatarFallback>
                        </Avatar>

                        <span className="text-sm text-foreground">
                          {account.account.handle} | {account.followers_count}{" "}
                          followers
                        </span>
                        <button
                          className="hover:bg-muted py-1 px-2 rounded-md"
                          onClick={() => removeAccount(account.account.handle)}
                        >
                          <CircleXIcon className="size-3" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default NewCampaignPage;
