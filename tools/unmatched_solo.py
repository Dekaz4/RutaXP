"""Apply the individual solo-levelling decisions for quests absent from all three comparisons."""
import json
from pathlib import Path

# These short continuations become worthwhile as soon as the expensive
# prerequisite has been handed in. A quest actually in the log takes priority.
AFTER_OPTIONAL = {
    247: [2, 23, 24], 4966: [4881], 506: [503], 517: [515], 524: [517],
    5941: [5206], 3127: [3126], 3129: [3127, 3128], 95885: [95883],
}


def decisions():
    reviews = {}
    for part in ("a", "b", "c"):
        path = Path(__file__).with_name(f"solo_review_unmatched_{part}.json")
        for key, case in json.loads(path.read_bytes()).items():
            qid = int(key)
            if qid in reviews or case["policy"] not in {"keep", "existing", "detour"}:
                raise ValueError(f"Invalid solo review for quest {qid}")
            reviews[qid] = case
    return reviews


# Goals in the original itinerary that have no quest ID. Match their actual
# contents as well as the chapter so shared purchases and flights stay usable.
def apply_auxiliary(guide, step, goal, cases):
    gid = guide["id"]
    kind = goal["t"]
    linked = None
    quests = {g["quest"] for g in step["goals"] if g.get("quest")}
    if kind == "collect":
        starter = next((g for g in step["goals"] if g["t"] == "accept" and g.get("item")
                        and g["item"] == goal.get("item") and g.get("quest") in cases), None)
        if starter and cases[starter["quest"]]["policy"] == "detour":
            linked = starter["quest"]
            goal["starterItem"] = goal["item"]
        elif gid.endswith("/human/01-elwynn-forest") and goal.get("item") == 247824:
            linked = 91738
            goal["starterItem"] = 247824
        elif gid.endswith("horde/40-50/02-feralas") and goal.get("item") == 8483 and 1707 in quests:
            linked = 1878
            goal["starterItem"] = 8483
        elif gid.endswith("horde/50-60/05-eastern-plaguelands") and goal.get("item") == 15447:
            linked = 6022
    elif kind == "kill" and goal.get("npc") == 5477 and 1392 in quests:
        linked = 1392
        goal["starterItem"] = 6196
    elif kind == "kill" and goal.get("npc") == 8529 and 5206 in quests:
        linked = 5206
    elif kind == "buy" and gid.endswith("/human/01-elwynn-forest") and goal.get("item") == 4536:
        linked = 91736
    elif kind == "goto":
        linked = next((q for q in (515, 3128, 95885, 1172) if q in quests), None)
    elif kind == "hearth" and gid.endswith("horde/30-40/01-desolace") and 517 in quests:
        goal.update(levelingDetour=True, detourOffers=[
            {"t":"turnin", "quest":q, "levelingDetour":True} for q in (517, 524)])
    elif kind == "fly":
        if gid.endswith("horde/50-60/04-azshara") and goal.get("location") == "El Cruce":
            goal.update(levelingDetour=True, detourOffers=[
                {"t": "accept", "quest": q, "levelingDetour": True, "detourItems": cases[q]["materials"]}
                for q in (91899, 91904)])
        elif goal.get("location") == "Campamento Mojache" and 2741 in quests:
            linked = 2741
            goal.update(workForQuest=2741, workVisit=True)
        elif goal.get("location") == "Gadgetzan" and any(g.get("quest") == 2741 and g["t"] == "turnin" for g in step["goals"]):
            goal.update(levelingDetour=True, detourOffers=[{"t":"turnin", "quest":2741, "levelingDetour":True}])
    if linked:
        goal.update(detourQuest=linked, levelingDetour=True)
        if kind in ("goto", "kill", "collect") and linked in (515, 3128, 5206, 1172, 6022):
            goal["workForQuest"] = linked
            if kind == "goto":
                goal["workVisit"] = True
        if linked in (1172, 95885):
            goal.pop("levelingDetour")
            goal.pop("group", None)
            if linked == 95885:
                goal["groupVisitFor"] = linked
                goal["soloAfter"] = AFTER_OPTIONAL[linked]


def apply(document):
    cases = decisions()
    for guide in document["guides"]:
        for step in guide["steps"]:
            for goal in step["goals"]:
                if not goal.get("quest"):
                    apply_auxiliary(guide, step, goal, cases)
                qid = goal.get("quest") or goal.get("workForQuest")
                if qid is None:
                    continue
                case = cases.get(qid)
                if not case:
                    continue
                if case["policy"] == "detour":
                    goal["levelingDetour"] = True
                    if case.get("materials"):
                        goal["detourItems"] = case["materials"]
                after = case.get("preferAfter") or AFTER_OPTIONAL.get(qid)
                if after:
                    goal["soloAfter"] = after
                if case.get("offerLimits"):
                    goal["offerLimits"] = case["offerLimits"]
                if qid == 79536 and goal["t"] == "accept":
                    goal["soloWhenOffered"] = True
