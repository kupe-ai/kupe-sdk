from __future__ import annotations

from typing import Any

from kupe.resources._base import APIResource, drop_none


class BillingResource(APIResource):
    """Wallet and invoices. Checkout / credit purchase is not exposed."""

    def wallet(self, *, org_id: str | None = None, currency: str | None = None) -> Any:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/billing/wallet", params=drop_none({"currency": currency}))

    def invoices(
        self,
        *,
        org_id: str | None = None,
        currency: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Any:
        org_id = self._org(org_id)
        return self._get(
            f"orgs/{org_id}/billing/invoices",
            params=drop_none({"currency": currency, "limit": limit, "offset": offset}),
        )

    def invoice_pdf(self, invoice_id: str, *, org_id: str | None = None) -> bytes:
        org_id = self._org(org_id)
        return self._get(f"orgs/{org_id}/billing/invoices/{invoice_id}/pdf", raw=True)
