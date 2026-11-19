"""Apply reviewed solo leveling choices to the pinned Forever catalog."""
if __package__:
    from . import route_review_alliance_late, route_review_alliance_start, route_review_horde, unmatched_solo
    from .solo_hillsbrad_route import apply_hillsbrad_detours
    from .solo_mid_route import apply_mid_detours
    from .solo_late_route import apply_late_detours
else:
    import route_review_alliance_late, route_review_alliance_start, route_review_horde, unmatched_solo
    from solo_hillsbrad_route import apply_hillsbrad_detours
    from solo_mid_route import apply_mid_detours
    from solo_late_route import apply_late_detours


def apply_solo_leveling(document):
    if document.get("provenance", {}).get("commit") == "5d207e28e82e2c529143b21ace74fe88692f0067":
        apply_hillsbrad_detours(document)
        apply_mid_detours(document)
        apply_late_detours(document)
        for review in (route_review_alliance_start, route_review_alliance_late, route_review_horde):
            review.apply(document)
        unmatched_solo.apply(document)
