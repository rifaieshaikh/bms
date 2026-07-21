# Project integrations (Wave 8 stubs)

Webhook-oriented contracts for GST filing, bank reconciliation feeds, and
e-invoice / e-way bill adapters. Payloads are illustrative; no live connectors
are wired yet.

## Common envelope

```json
{
  "event_id": "uuid",
  "event_type": "gst.return.submitted | bank.statement.received | einvoice.irn.created",
  "occurred_at": "2026-07-21T10:00:00Z",
  "tenant_id": "org-id",
  "project_id": "optional-project-id",
  "payload": {}
}
```

### Auth

- `Authorization: Bearer <integration-token>`
- Optional HMAC header `X-VayBooks-Signature: sha256=<hex>` over raw body

---

## GST return webhook

**Event:** `gst.return.submitted`

```json
{
  "return_type": "GSTR1 | GSTR3B",
  "period": "2026-06",
  "gstin": "29AAAAA0000A1Z5",
  "status": "filed | acknowledged | error",
  "reference": "ARN-…",
  "document_refs": ["INV-1001", "CN-12"]
}
```

**Outbound (VayBooks → GST partner):** `POST /webhooks/gst/prepare` with invoice
summaries for a filing period; expect `202 Accepted` + `job_id`.

---

## Bank statement / payment match

**Event:** `bank.statement.received`

```json
{
  "account_ref": "bank-ledger-id",
  "statement_date": "2026-07-20",
  "currency": "INR",
  "entries": [
    {
      "txn_id": "UTR123",
      "value_date": "2026-07-19",
      "amount": 150000.0,
      "direction": "credit | debit",
      "narration": "NEFT ACME",
      "suggested_project_id": null,
      "suggested_voucher_id": null
    }
  ]
}
```

**Match callback:** `POST /webhooks/bank/match-result` with `{txn_id, voucher_id, project_id, confidence}`.

---

## E-invoice / IRN

**Event:** `einvoice.irn.created`

```json
{
  "voucher_id": "…",
  "invoice_number": "INV-1001",
  "irn": "…",
  "ack_no": "…",
  "ack_date": "2026-07-21T09:30:00Z",
  "signed_qr": "base64-or-url",
  "status": "generated | cancelled"
}
```

**Request IRN:** `POST /webhooks/einvoice/generate` with seller/buyer GSTIN,
line items, and taxable values; response includes IRN fields above.

---

## Status

| Integration | Contract | Implementation |
|-------------|----------|----------------|
| GST         | Stub     | Pending        |
| Bank        | Stub     | Pending        |
| E-invoice   | Stub     | Pending        |
