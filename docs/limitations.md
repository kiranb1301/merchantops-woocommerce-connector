# Limitations

- One merchant store per connector process.
- Demo credential storage is an encrypted local file, not a production secret vault.
- SSRF validation does not prevent DNS rebinding; production should use an egress proxy/resolved-IP pinning.
- No webhook/event ingestion in v1.
- No persistent cache.
- Variation-SKU resolution is not implemented.
- No write/refund/mutation tools.
- The connector does not join WooCommerce orders to Razorpay payment records.
