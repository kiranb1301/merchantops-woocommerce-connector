# Security model

1. WooCommerce access is read-only.
2. The HTTP client exposes only `GET`.
3. Merchant connect requests a `read` key and refuses broader permissions.
4. Stored credentials are encrypted with Fernet for the demo.
5. Secrets are not written to logs or error messages.
6. Customer email/phone are masked and street addresses are omitted.
7. Store URLs are validated and private literal IPs are rejected outside local development.
8. Redirects are disabled so Basic Auth credentials cannot be replayed to another host.
9. Production should replace the file credential store with a managed secret/KMS design.
