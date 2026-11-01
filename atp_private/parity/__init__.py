"""atp_private.parity: the parity runner for the imported Trade engine (owner order M79, W3).

It feeds the trade-data parity fixtures (`parity/engine-snapshot-v2/`, kept in the private fixtures store on the host,
never in git) through the imported engine and compares the result byte for byte with the expected outputs. A difference
is a port bug; the fixtures are never changed.
"""
