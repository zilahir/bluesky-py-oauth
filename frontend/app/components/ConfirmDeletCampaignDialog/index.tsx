import type { ReactElement } from "react";
import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { Button } from "../ui/button";

interface IConfirmDeleteCampaignDialog {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm?: () => void;
}

function ConfirmDeleteCampaignDialog({
  open,
  onOpenChange,
  onConfirm,
}: IConfirmDeleteCampaignDialog): ReactElement {
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
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              onConfirm?.();
              onOpenChange(false);
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
