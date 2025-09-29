export interface Campaign {
  id: string;
  name: string;
  is_campaign_running: boolean;
  is_setup_job_running: boolean;
  created_at: string;
  followers: CampaignFollowers[];
}

export interface CampaignFollowers {
  id: string;
  account_handle: string;
  me_following: string;
  is_following_me: string;
  created_at: string;
  updated_at: string;
}
