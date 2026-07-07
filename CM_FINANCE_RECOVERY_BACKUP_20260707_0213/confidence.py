def score_match(row):
    score = 0
    reasons = []

    contact = str(row.get("matched_contact_name", "")).strip()
    ledger = str(row.get("ledger", "")).strip()
    vendor = str(row.get("extracted_vendor", "")).strip()

    if contact:
        score += 40
    else:
        reasons.append("Geen contactmatch")

    if ledger and ledger != "REVIEW":
        score += 35
    else:
        reasons.append("Geen betrouwbare ledger")

    if vendor:
        score += 15
    else:
        reasons.append("Geen vendor extractie")

    if contact and vendor and contact.lower() in vendor.lower():
        score += 10

    if score >= 95:
        action = "AUTO"
    elif score >= 80:
        action = "REVIEW"
    else:
        action = "MANUAL"

    return {
        "score": score,
        "action": action,
        "reasons": reasons,
    }