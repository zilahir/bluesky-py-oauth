import { create } from "zustand";
import type { BlueSkyAccount } from "~/types/BlyeSkyAccount";

interface BlueskyAccounts {
  accounts: {
    account: BlueSkyAccount;
    followers_count: number;
  }[];
  addAccount: (account: BlueSkyAccount, followers_count: number) => void;
  removeAccount: (handler: string) => void;
  clearAccounts: () => void;
}

const useBlueskyAccounts = create<BlueskyAccounts>((set) => ({
  accounts: [],
  addAccount: (account, followers_count) =>
    set((state) => ({
      accounts: [
        ...state.accounts,
        { account, followers_count: followers_count },
      ],
    })),
  removeAccount: (handler) =>
    set((state) => ({
      accounts: state.accounts.filter(
        (account) => account.account.handle !== handler,
      ),
    })),
  clearAccounts: () => set({ accounts: [] }),
}));

export default useBlueskyAccounts;
