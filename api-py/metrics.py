"""
Prometheus metrics configuration for the Bluesky API
"""
import time
from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from fastapi.responses import Response as FastAPIResponse

# Prometheus metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

active_campaigns = Gauge(
    'active_campaigns_total',
    'Number of active campaigns'
)

rq_jobs_total = Counter(
    'rq_jobs_total',
    'Total number of RQ jobs processed',
    ['queue', 'status']
)

rq_workers_total = Gauge(
    'rq_workers_total',
    'Number of active RQ workers'
)

followers_processed_total = Counter(
    'followers_processed_total',
    'Total number of followers processed',
    ['campaign_id']
)

# Middleware for tracking HTTP requests
async def metrics_middleware(request: Request, call_next):
    """FastAPI middleware to collect HTTP metrics"""
    start_time = time.time()

    # Get the endpoint path template (e.g., /api/campaigns/{id})
    endpoint = request.url.path
    method = request.method

    # Process the request
    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Record metrics
    http_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status=response.status_code
    ).inc()

    http_request_duration_seconds.labels(
        method=method,
        endpoint=endpoint
    ).observe(duration)

    return response

# Custom functions to track business metrics
def track_campaign_created():
    """Track when a new campaign is created"""
    active_campaigns.inc()

def track_campaign_completed():
    """Track when a campaign is completed"""
    active_campaigns.dec()

def track_rq_job(queue_name: str, status: str):
    """Track RQ job completion"""
    rq_jobs_total.labels(queue=queue_name, status=status).inc()

def track_followers_processed(campaign_id: str, count: int = 1):
    """Track followers processed for a campaign"""
    followers_processed_total.labels(campaign_id=campaign_id).inc(count)

def update_worker_count(count: int):
    """Update the number of active workers"""
    rq_workers_total.set(count)

# Metrics endpoint
def get_metrics():
    """Return Prometheus metrics in text format"""
    return FastAPIResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )