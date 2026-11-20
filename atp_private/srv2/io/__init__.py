"""atp_private.srv2.io - stand-ins for Trade's IO modules (cloud_db, upstox_api, notifications, broker_factory, ...), installed by
`atp_private.srv2.host.install()` under Trade's module names. Same function names and signatures as Trade; the IO itself is ATP's
(registered callables). Every non-IO body (defaults, merges, formats) is copied verbatim from Trade 813358b and says where from."""
