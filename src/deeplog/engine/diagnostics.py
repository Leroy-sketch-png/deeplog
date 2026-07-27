def diagnose_track_a(row: dict) -> tuple[str, str, str]:
    """
    Returns (category, causal_explanation, uncertainty) based on Track A scores.
    """
    dur = float(row.get("duration_deviation", 0.0))
    struct = float(row.get("structural_violation", 0.0))
    ctx = float(row.get("context_inconsistency", 0.0))
    length = float(row.get("length_deviation", 0.0))
    eff_sig = int(row.get("effective_signal_count", 1))

    seq = row.get("sequence_context", "").split(" -> ")
    last_op = seq[-1] if seq else "UNKNOWN"

    if eff_sig >= 2:
        uncertainty = "HIGH_CONFIDENCE"
    elif eff_sig == 1 and struct == 1.0:
        uncertainty = "LOW_CONFIDENCE"
    elif eff_sig == 1:
        uncertainty = "MODERATE"
    else:
        uncertainty = "UNCLASSIFIED"

    if ctx > 0:
        return (
            "Lateral Boundary Crossing",
            f"CorrelationId unexpectedly traversed distinct resource groups or providers during `{last_op}`.",
            uncertainty,
        )
    elif struct == 1.0 and dur > 0.8:
        return (
            "Critical Deployment/Migration Shift",
            f"Unseen sequence path combined with massive latency, likely indicating a failed backend deployment involving `{last_op}`.",
            uncertainty,
        )
    elif struct == 1.0:
        return (
            "New Microservice Routine",
            f"Strictly unseen workflow path to `{last_op}`, likely an unmodeled script or manual intervention.",
            uncertainty,
        )
    elif dur > 0.8:
        return (
            "Latency / Retry Loop",
            f"Standard workflow path, but extreme timing delay indicative of a backend retry loop terminating at `{last_op}`.",
            uncertainty,
        )
    elif length > 0.8:
        return (
            "Stalled Operation",
            f"Abnormal volume of events within the same CorrelationId cycle.",
            uncertainty,
        )
    else:
        return (
            "Unclassified Structural Anomaly",
            "Sequence violates historical n-gram priors.",
            uncertainty,
        )


def diagnose_track_b(row: dict) -> tuple[str, str, str]:
    """
    Returns (category, causal_explanation, uncertainty) based on Track B scores.
    """
    new_ip = float(row.get("new_ip", 0.0))
    new_op = float(row.get("new_op", 0.0))
    new_rg = float(row.get("new_rg", 0.0))
    new_prov = float(row.get("new_prov", 0.0))
    act_dev = float(row.get("activity_dev", 0.0))
    hour_dev = float(row.get("hour_dev", 0.0))
    eff_sig = int(row.get("effective_signal_count", 1))

    if eff_sig >= 2:
        uncertainty = "HIGH_CONFIDENCE"
    elif eff_sig == 1 and new_op == 1.0:
        uncertainty = "LOW_CONFIDENCE"
    elif eff_sig == 1:
        uncertainty = "MODERATE"
    else:
        uncertainty = "UNCLASSIFIED"

    ops = row.get("session_context", "").split(", ")
    first_op = ops[0] if ops else "UNKNOWN"

    if new_ip == 1.0 and new_op == 1.0 and act_dev > 0.5:
        return (
            "Possible Credential/Token Compromise",
            f"Identity used a brand new IP to execute unseen operations (`{first_op}`) at an unusually high volume.",
            uncertainty,
        )
    elif new_ip == 1.0 and new_op == 0.0 and new_prov == 0.0:
        return (
            "VPN / Routing Shift",
            "Identity executed standard business operations from a previously unseen IP space.",
            uncertainty,
        )
    elif new_op == 1.0 and act_dev > 0.8 and new_ip == 0.0:
        return (
            "Automation / Batch Script Change",
            f"Massive volume spike of unseen operations (`{first_op}`) from a known IP, indicating a cron job or automation change.",
            uncertainty,
        )
    elif (new_rg == 1.0 or new_prov == 1.0) and new_ip == 0.0:
        return (
            "RBAC Role Expansion",
            f"Identity began operating in previously unseen resource groups or providers, suggesting a recent permissions grant.",
            uncertainty,
        )
    elif hour_dev > 0.8 and new_op == 1.0:
        return (
            "Off-Hours Deviation",
            f"Identity executed unseen operations during an historically inactive hour.",
            uncertainty,
        )
    else:
        return (
            "Unclassified Behavioral Drift",
            "Session deviates from standard historical actor baseline.",
            uncertainty,
        )
