# scoring.py
from math import floor


def compute_points_table(total_entries: int) -> int:
    """Return the maximum points for 1st place. Others get -1 each position.
    Example: with 9 total_entries, points for 1st=9, 2nd=8, 3rd=7, ... no negatives.
    """
    return max(int(total_entries), 0)


def default_payouts(entries: int):
    """Return a list of payout percentage tiers depending on number of entries.
    You can adjust this mapping to your group's rules.
    """
    if entries <= 6:
        return [1.0]  # winner takes all
    elif entries <= 12:
        return [0.65, 0.35]
    elif entries <= 25:
        return [0.5, 0.3, 0.2]
    else:
        return [0.45, 0.27, 0.18, 0.10]


def compute_payouts(entries: int, prize_pool: float):
    tiers = default_payouts(entries)
    payouts = [round(prize_pool * p, 2) for p in tiers]
    # Adjust rounding residual to first place
    diff = round(prize_pool - sum(payouts), 2)
    if payouts:
        payouts[0] = round(payouts[0] + diff, 2)
    return payouts