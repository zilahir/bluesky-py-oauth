export interface Campaign {
  id: string;
  name: string;
  is_campaign_running: boolean;
  is_setup_job_running: boolean;
  created_at: string;
  followers: {
    id: string;
    account_handle: string;
    me_following: boolean;
    is_following_me: boolean;
    created_at: string;
    updated_at: string;
  }[];
}

export interface CampaignFollowers {
  id: string;
  account_handle: string;
  me_following: boolean;
  is_following_me: boolean;
  created_at: string;
  updated_at: string;
}
