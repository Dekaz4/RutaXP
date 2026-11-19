"""Apply the reviewed Forever Alliance leveling choices to the pinned catalog."""
if __package__:
    from .solo_hillsbrad_route import apply_hillsbrad_detours
    from .solo_mid_route import apply_mid_detours
    from .solo_late_route import apply_late_detours
else:
    from solo_hillsbrad_route import apply_hillsbrad_detours
    from solo_mid_route import apply_mid_detours
    from solo_late_route import apply_late_detours


def apply_solo_leveling(document):
    if document.get("provenance", {}).get("commit") == "5d207e28e82e2c529143b21ace74fe88692f0067":
        apply_hillsbrad_detours(document)
        apply_mid_detours(document)
        apply_late_detours(document)
