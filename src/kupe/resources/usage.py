from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class UsageResource(APIResource):
    """Cost summary and daily usage only — not per-service breakdown."""

    def cost_summary(
        self,
        *,
        org_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        currency: str | None = None,
    ) -> Any:
        org_id = self._org(org_id)
        return self._get(
            f"orgs/{org_id}/usage/cost-summary",
            params=drop_none({"start_date": start_date, "end_date": end_date, "currency": currency}),
        )

    def daily(
        self,
        *,
        start_date: str,
        end_date: str,
        org_id: str | None = None,
        currency: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        org_id = self._org(org_id)
        return self._get(
            f"orgs/{org_id}/usage/daily",
            params=drop_none(
                {
                    "start_date": start_date,
                    "end_date": end_date,
                    "currency": currency,
                    "limit": limit,
                    "offset": offset,
                }
            ),
        )
