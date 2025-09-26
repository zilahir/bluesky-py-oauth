export interface User {
  access_token: string;
  authserver_iss: string;
  did: string;
  dpop_authserver_nonce: string;
  dpop_pds_nonce?: string;
  dpop_private_jwk: string;
  handle: string;
  pds_url: string;
  refresh_token: string;
  avatar: string;
  display_name: string;
  created_at: string;
  description: string;
}
