"""Shared ARBHOPS0 message compilation; no RPC, wallet files or signing."""
from solders.address_lookup_table_account import AddressLookupTableAccount
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.instruction import AccountMeta, Instruction
from solders.message import MessageV0
from solders.pubkey import Pubkey


def compile_message(payer, program, keys, data, alts, cu_limit, blockhash, cu_price=1):
    if not keys or keys[0] != payer:
        raise ValueError("First route account must be the payer")
    if len(data) != 40 or data[:8] != b"ARBHOPS0":
        raise ValueError("Invalid ARBHOPS0 payload")
    # Preserve the current host compiler's flags, including broad hop writability.
    metas = [AccountMeta(Pubkey.from_string(key), i == 0,
                         i in (0, 1, 2, 3) or i >= 9)
             for i, key in enumerate(keys)]
    lookups = [AddressLookupTableAccount(Pubkey.from_string(a["pubkey"]),
               [Pubkey.from_string(k) for k in a["addresses"]]) for a in alts]
    return MessageV0.try_compile(Pubkey.from_string(payer), [
        set_compute_unit_limit(cu_limit), set_compute_unit_price(cu_price),
        Instruction(Pubkey.from_string(program), data, metas),
    ], lookups, blockhash)


def net_economics(gross, success_fee, failed_fee, success_tip=0, failed_tip=0,
                  fixed_cost=0, success_bps=None, charged_failure_bps=None):
    """Lamports only. Probabilities are unconditional, mutually exclusive outcomes.

    RPC message fees already include priority fees: never add priority twice.
    Uncharged/dropped probability is the remainder. No probability is inferred
    from simulation. gross must already include venue fees and token rounding.
    """
    costs = (success_fee, failed_fee, success_tip, failed_tip, fixed_cost)
    if any(type(x) is not int or x < 0 for x in costs):
        raise ValueError("Costs must be nonnegative integer lamports")
    if gross is not None and type(gross) is not int:
        raise ValueError("Gross must be integer lamports or unknown")
    result = {"success_cost": success_fee + success_tip,
              "charged_failure_cost": failed_fee + failed_tip,
              "fixed_cost": fixed_cost,
              "conditional_success_net": None if gross is None else gross-success_fee-success_tip-fixed_cost,
              "expected_net": None, "break_even_gross": None,
              "probabilities_measured": False}
    if success_bps is None or charged_failure_bps is None:
        return result
    if any(type(x) is not int or not 0 <= x <= 10000
           for x in (success_bps, charged_failure_bps)) or success_bps+charged_failure_bps > 10000:
        raise ValueError("Invalid mutually exclusive outcome probabilities")
    numerator_cost = (success_bps*(success_fee+success_tip)
                      + charged_failure_bps*(failed_fee+failed_tip) + 10000*fixed_cost)
    if success_bps:
        result["break_even_gross"] = (numerator_cost+success_bps-1)//success_bps
    if gross is not None:
        result["expected_net"] = (success_bps*gross-numerator_cost)//10000
    return result
