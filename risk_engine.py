"""
risk_engine.py
All the calculations for my risk assessment calculator are in this file.
I kept them separate from assess.py so I can test them on their own.

Two parts:
  1. Risk level using NIST SP 800-30 (likelihood + impact -> Very Low to Very High)
  2. Money: SLE and ALE (how much a risk could cost per year)
"""

import math


# ===== NIST scales =====

# NIST uses 5 levels. In my CSV I type them as numbers 1 to 5.
NIST_LEVELS = {
    1: "Very Low",
    2: "Low",
    3: "Moderate",
    4: "High",
    5: "Very High",
}
LIKELIHOOD_LABELS = NIST_LEVELS
IMPACT_LABELS = NIST_LEVELS

# This is Table I-2 from NIST SP 800-30 Rev. 1 (Appendix I).
# Row = likelihood (5 at the top), column = impact (Very Low to Very High).
# I copied it exactly so my risk levels follow the standard.
NIST_RISK_TABLE = {
    5: ["Very Low", "Low",      "Moderate", "High",     "Very High"],
    4: ["Very Low", "Low",      "Moderate", "High",     "Very High"],
    3: ["Very Low", "Low",      "Moderate", "Moderate", "High"],
    2: ["Very Low", "Low",      "Low",      "Low",      "Moderate"],
    1: ["Very Low", "Very Low", "Very Low", "Low",      "Low"],
}

# What each level means, from NIST Table I-3 (in my own words)
LEVEL_MEANING = {
    "Very High": "Could have multiple severe or catastrophic adverse effects.",
    "High": "Could have a severe or catastrophic adverse effect.",
    "Moderate": "Could have a serious adverse effect.",
    "Low": "Could have a limited adverse effect.",
    "Very Low": "Could have a negligible adverse effect.",
}

# Suggested response for each level.
# NIST SP 800-39 gives 5 options: accept, avoid, mitigate, share, transfer.
# These are only suggestions - the real decision depends on the organisation.
TREATMENT = {
    "Very High": "Mitigate as a priority, or avoid (stop the activity) if it cannot be reduced.",
    "High": "Mitigate: add or improve controls to reduce the risk.",
    "Moderate": "Mitigate, or share/transfer (e.g. outsourcing, insurance).",
    "Low": "Accept if within risk tolerance, and monitor.",
    "Very Low": "Accept and monitor.",
}


def _check_range(name, value, low, high):
    # stop the program with a clear message if a number is out of range
    if value < low or value > high:
        raise ValueError(f"{name} must be between {low} and {high}, got {value}")


# ===== Part 1: risk level =====

def cia_impact(confidentiality, integrity, availability):
    # impact = the worst of C, I and A
    # (if any one of them is badly hit, the damage is already serious)
    for name, v in (("confidentiality", confidentiality),
                    ("integrity", integrity),
                    ("availability", availability)):
        _check_range(name, v, 1, 5)
    return max(confidentiality, integrity, availability)


def risk_score(likelihood, impact):
    # likelihood x impact gives 1-25
    # I only use this number to sort risks, the level comes from the NIST table
    _check_range("likelihood", likelihood, 1, 5)
    _check_range("impact", impact, 1, 5)
    return likelihood * impact


def risk_level(likelihood, impact):
    # look up the level in the NIST table
    # impact - 1 because Python lists start counting from 0
    _check_range("likelihood", likelihood, 1, 5)
    _check_range("impact", impact, 1, 5)
    return NIST_RISK_TABLE[likelihood][impact - 1]


def residual_likelihood(likelihood, control_effectiveness_pct):
    # existing controls make the attack less likely
    # e.g. likelihood 5 with a 20% effective control: 5 x 0.8 = 4
    # I round UP because it's safer to over-estimate a risk than under-estimate it
    # and it can never go below 1 (no risk is zero)
    _check_range("likelihood", likelihood, 1, 5)
    _check_range("control_effectiveness", control_effectiveness_pct, 0, 100)
    reduced = likelihood * (1 - control_effectiveness_pct / 100)
    # Python sometimes gives 3.0000000000000004 instead of 3,
    # so I round to 6 decimals first, otherwise ceil() would give 4
    return max(1, math.ceil(round(reduced, 6)))


# ===== Part 2: money =====

def sle(asset_value, exposure_factor_pct):
    # SLE = asset value x exposure factor
    # = how much ONE incident would cost
    if asset_value < 0:
        raise ValueError("asset_value cannot be negative")
    _check_range("exposure_factor", exposure_factor_pct, 0, 100)
    return asset_value * exposure_factor_pct / 100


def ale(single_loss, aro):
    # ALE = SLE x ARO (how many times per year)
    # = how much this risk costs per YEAR
    if aro < 0:
        raise ValueError("aro cannot be negative")
    return single_loss * aro


# ===== Put everything together for one risk =====

def assess(row):
    # row = one risk from the CSV (numbers already converted)
    # returns the same risk with all the results added
    impact = cia_impact(row["confidentiality"], row["integrity"], row["availability"])

    inherent = risk_score(row["likelihood"], impact)            # before controls
    res_l = residual_likelihood(row["likelihood"], row["control_effectiveness"])
    residual = risk_score(res_l, impact)                         # after controls

    single = sle(row["asset_value"], row["exposure_factor"])
    ale_before = ale(single, row["aro"])
    ale_after = ale_before * (1 - row["control_effectiveness"] / 100)

    result = dict(row)
    result.update({
        "impact": impact,
        "inherent_score": inherent,
        "inherent_level": risk_level(row["likelihood"], impact),
        "residual_likelihood": res_l,
        "residual_score": residual,
        "residual_level": risk_level(res_l, impact),
        "meaning": LEVEL_MEANING[risk_level(res_l, impact)],
        "treatment": TREATMENT[risk_level(res_l, impact)],
        "sle": single,
        "ale_before": ale_before,
        "ale_after": ale_after,
    })
    return result
