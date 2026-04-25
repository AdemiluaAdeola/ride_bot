"""
Fraud scoring engine.
Returns risk_score (0.0-1.0) and RiskLevel.
Replace heuristics with ML model or third-party API in production.
"""
import random
from models import RiskLevel

SUSPICIOUS_TERMS = ["unknown", "test", "none", "xxx"]

def score_ride(pickup: str, destination: str, user_id: str) -> dict:
    score = 0.0
    flags = []

    if any(s in pickup.lower() for s in SUSPICIOUS_TERMS):
        score += 0.4
        flags.append("suspicious_pickup")

    if any(s in destination.lower() for s in SUSPICIOUS_TERMS):
        score += 0.4
        flags.append("suspicious_destination")

    if pickup.strip().lower() == destination.strip().lower():
        score += 0.3
        flags.append("same_pickup_destination")

    # Simulated behavioural noise — replace with velocity/device checks
    score = min(score + random.uniform(0.0, 0.1), 1.0)

    if score < 0.35:
        level = RiskLevel.low
    elif score < 0.65:
        level = RiskLevel.medium
    else:
        level = RiskLevel.high

    return {"risk_score": round(score, 3), "risk_level": level, "flags": flags}
