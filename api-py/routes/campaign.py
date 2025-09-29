from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from routes.utils.get_user import get_logged_in_user
from routes.utils.postgres_connection import get_db, Campaign, FollowersToGet

router = APIRouter(prefix="/campaign", include_in_schema=False)


@router.get("/{campaign_id}/stats")
async def get_campaign_stats(
    campaign_id: int,
    request: Request,
    user=Depends(get_logged_in_user),
    db: Session = Depends(get_db),
):
    try:
        # Verify campaign exists and belongs to user
        campaign = (
            db.query(Campaign)
            .filter(Campaign.id == campaign_id, Campaign.user_did == user.did)
            .first()
        )

        if not campaign:
            return {"error": "Campaign not found"}, 404

        # 1. Total followed accounts - accounts where me_following is not null
        total_followed_accounts = (
            db.query(FollowersToGet)
            .filter(
                FollowersToGet.campaign_id == campaign_id,
                FollowersToGet.me_following.isnot(None),
            )
            .count()
        )

        # 2. Total followers gained - accounts that followed us back (is_following_me is not null)
        total_follers_gained = (
            db.query(FollowersToGet)
            .filter(
                FollowersToGet.campaign_id == campaign_id,
                FollowersToGet.is_following_me.isnot(None),
            )
            .count()
        )

        # 3. Total unfollowed accounts - accounts where unfollowed_at is not null
        total_unfollowed_accounts = (
            db.query(FollowersToGet)
            .filter(
                FollowersToGet.campaign_id == campaign_id,
                FollowersToGet.unfollowed_at.isnot(None),
            )
            .count()
        )

        total_targets = (
            db.query(FollowersToGet)
            .filter(FollowersToGet.campaign_id == campaign_id)
            .count()
        )

        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "stats": {
                "total_followed_accounts": total_followed_accounts,
                "total_followers_gained": total_follers_gained,
                "total_unfollowed_accounts": total_unfollowed_accounts,
                "total_targets": total_targets,
                "setup_complete": not campaign.is_setup_job_running,
            },
        }

    except Exception as e:
        return {"error": f"Error fetching campaign stats: {str(e)}"}, 500
    finally:
        db.close()
