"""Error tracking (task 10.3). Sentry is optional: on only when SENTRY_DSN is set.

Personal data stays out: no request bodies, no user emails, and the default PII off.
"""

import sentry_sdk

from orbit.core.config import Settings


def init_sentry(settings: Settings, *, component: str) -> bool:
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        send_default_pii=False,
        max_request_body_size="never",
        traces_sample_rate=0.05,
    )
    sentry_sdk.set_tag("component", component)
    return True
