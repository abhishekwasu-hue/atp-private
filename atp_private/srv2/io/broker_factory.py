"""Stand-in for Trade's `broker_factory` (other brokers' adapters, LIVE multi-account) - owner order SRV2, 18 Nov. Not wired: LIVE goes
through ATP's own order path when the owner says so. Empty lists = Trade's result with no account configured."""
__srv2_io__ = True


def get_adapters_for_accounts(account_ids):
    return []


def get_all_active_adapters():
    return []
