export interface BlueSkyAccount {
  did: string;
  handle: string;
  displayName: string;
  avatar: string;
  associated: {
    allowSubscriptions: boolean;
  };
  labels: any[];
  createdAt: string;
  description: string;
  indexedAt: string;
  banner: string;
  folowersCount: number;
  followingCount: number;
  postsCount: number;
}
