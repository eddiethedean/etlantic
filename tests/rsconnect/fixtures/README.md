# Local TLS fixture

`tls-cert.pem` and `tls-key.pem` are a public, test-only self-signed certificate
and key for `127.0.0.1`. They are trusted only by the loopback transport tests.
They have no production use. Tests read these fixtures directly, without a
certificate-generation dependency or external service.
