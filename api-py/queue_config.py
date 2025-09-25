import redis
from rq import Queue
from settings import get_settings


def get_redis_connection():
    """Get Redis connection instance"""
    settings = get_settings()

    print(
        f"Connecting to Redis at {settings.redis_host}:{settings.redis_port} with DB {settings.redis_db}"
    )
    connection_params = {
        "host": settings.redis_host,
        "port": settings.redis_port,
        "db": settings.redis_db,
        "decode_responses": False,
    }

    # Only add password if it's not empty
    if settings.redis_password:
        connection_params["password"] = settings.redis_password

    return redis.Redis(**connection_params)


def get_queue(name="default"):
    """Get RQ queue instance"""
    redis_conn = get_redis_connection()
    return Queue(name, connection=redis_conn)

