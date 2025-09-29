import type { ReactElement } from "react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { Button } from "../ui/button";
import useDeleteCampaign from "~/hooks/useDeleteCampaign";
import { useNavigate } from "react-router";

interface IConfirmDeleteCampaignDialog {
  campaignId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm?: () => void;
}

function ConfirmDeleteCampaignDialog({
  open,
  onOpenChange,
  campaignId,
}: IConfirmDeleteCampaignDialog): ReactElement {
  const navigate = useNavigate();
  const { mutate: deleteCampaign } = useDeleteCampaign({
    campaignId,
    onSuccess: () => {
      onOpenChange(false);
      toast.success("Campaign deleted successfully!");
      navigate("/");
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Confirm Delete Campaign</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete this campaign? This action cannot be
            undone.
          </DialogDescription>
        </DialogHeader>

        <div className="flex justify-end space-x-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              deleteCampaign();
            }}
          >
            Delete Campaign
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default ConfirmDeleteCampaignDialog;
