import type { ReactElement } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";

interface IConfirmDeleteCampaignDialog {
  dialogTrigger: ReactElement;
}

function ConfirmDeleteCampaignDialog({
  dialogTrigger,
}: IConfirmDeleteCampaignDialog): ReactElement {
  return (
    <Dialog>
      <DialogTrigger asChild>{dialogTrigger}</DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Confirm Delete Campaign</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete this campaign? This action cannot be
            undone.
          </DialogDescription>
        </DialogHeader>

        <div></div>
      </DialogContent>
    </Dialog>
  );
}

export default ConfirmDeleteCampaignDialog;
