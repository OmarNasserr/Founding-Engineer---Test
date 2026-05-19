import redis
from django.conf import settings
from redis import BlockingConnectionPool

pool = BlockingConnectionPool.from_url(
    settings.REDIS_URL,
    max_connections=50,
    timeout=5,
    decode_responses=True,
)
REDIS_CLIENT = redis.Redis(connection_pool=pool)
