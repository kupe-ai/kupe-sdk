from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class PhonesResource(APIResource):
    """Phone search / buy (Plivo) and telephony-account delete."""

    def search(
        self,
        *,
        country_iso: str,
        org_id: str | None = None,
        pattern: str | None = None,
    ) -> Any:
        org_id = self._org(org_id)
        return self._get(
            f"orgs/{org_id}/plivo/numbers/search",
            params=drop_none({"country_iso": country_iso, "pattern": pattern}),
        )

    def buy(self, **body: Any) -> Any:
        org_id = self._org(body.pop("org_id", None))
        return self._post(f"orgs/{org_id}/plivo/numbers/purchase", json=body)

    def list(self, *, org_id: str | None = None) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/telephony-accounts")

    def retrieve(self, account_id: str) -> Any:
        return self._get(f"telephony-accounts/{account_id}")

    def create_account(self, **body: Any) -> Any:
        org_id = self._org(body.pop("org_id", None))
        return self._post(f"orgs/{org_id}/telephony-accounts", json=body)

    def update(self, account_id: str, **body: Any) -> Any:
        return self._patch(f"telephony-accounts/{account_id}", json=body)

    def delete(self, account_id: str) -> None:
        """Release a purchased number (or drop a BYOK telephony account)."""
        self._delete(f"telephony-accounts/{account_id}")

    def compliance_requirements(self, *, org_id: str | None = None) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/plivo/compliance/requirements")

    def compliance_status(self, *, org_id: str | None = None) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/plivo/compliance")

    def submit_compliance(self, **body: Any) -> Any:
        org_id = self._org(body.pop("org_id", None))
        return self._post(f"orgs/{org_id}/plivo/compliance", json=body)

    def refresh_compliance(self, *, org_id: str | None = None) -> Any:
        org_id = self._org(org_id)
        return self._post(f"orgs/{org_id}/plivo/compliance/refresh")
