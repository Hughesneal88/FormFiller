"""Weighted answer generation per project guidelines."""

from __future__ import annotations

import random
import re
from typing import Any


# Ga & Fante names
GA_FIRST = [
    "Nii", "Naa", "Tetteh", "Odoi", "Ashong", "Bonnie", "Quaye", "Lomotey", "Adjei", "Ablade",
    "Mensah", "Tawiah", "Laryea", "Okai", "Agbo", "Tettey", "Narh", "Ankrah",
]
FANTE_FIRST = [
    "Kofi", "Kwame", "Yaw", "Kojo", "Kwesi", "Ama", "Efua", "Akosua", "Esi", "Araba",
    "Adjoa", "Fiifi", "Papa", "Ebo", "Kweku", "Abena", "Yaa", "Akua",
]
SURNAMES = [
    "Mensah", "Annan", "Boateng", "Osei", "Asante", "Darko", "Quaye", "Tetteh",
    "Laryea", "Aggrey", "Aidoo", "Baidoo", "Sowah", "Nortey", "Ashong", "Amoah",
]

Q49_THEMES = [
    "Reduced catch", "Increased costs", "Irregular income", "Loss of fishing days", "Lower prices",
]

Q67_BROKEN_ENGLISH = [
    "Govment shud help with fuel and premix becos price too high",
    "We need more money and support for fishing gear",
    "Training from govment will help us small",
    "Fuel cost dey kill us, we need reduction",
    "Pollution for sea dey spoil fish, govment must stop am",
    "Harbour need repair, boats cant land proper",
    "Credit hard to get, we need loan for canoe and net",
    "Cold store no dey here, fish spoil quick",
    "Premix fuel shortage delay our trip every time",
    "Better policy from govment will help fisherman",
]

Q79_TEMPLATES = [
    "Govment should reduce fuel price and give premix on time",
    "We need harbour repair and cold store for fish",
    "Training for fisherman and help with net and canoe",
    "Stop illegal fishing and pollution for sea",
    "Give credit and small loan to help us fish",
    "Harbour too congest, we need better landing place",
    "Fuel too cost, profit small, govment must help",
    "More support for fisherman association and cooperative",
]


def pick_yes(yes_pct: float) -> str:
    return "Yes" if random.random() < yes_pct else "No"


def pick_weighted(options: list[str], weights: list[float]) -> str:
    return random.choices(options, weights=weights, k=1)[0]


def pick_from_ranking(options: list[str], ranking: list[int], count: int = 1) -> list[str]:
    """Ranking is 1-based indices into options by descending frequency."""
    ordered = [options[i - 1] for i in ranking if 0 < i <= len(options)]
    rest = [o for o in options if o not in ordered]
    ordered.extend(rest)
    weights = [len(ordered) - i for i in range(len(ordered))]
    k = min(count, len(ordered))
    return random.choices(ordered, weights=weights[: len(ordered)], k=k)


def pick_multiple_weighted(
    options: list[str],
    weights: list[float] | None = None,
    *,
    min_count: int = 1,
    max_count: int | None = None,
    exclude: list[str] | None = None,
) -> list[str]:
    exclude = set(exclude or [])
    pool = [o for o in options if o not in exclude]
    if not pool:
        return []
    w = weights
    if w is None:
        w = [1.0] * len(pool)
    else:
        w = [weights[options.index(o)] if o in options else 1.0 for o in pool]

    max_count = max_count or min(4, len(pool))
    count = random.randint(min_count, max_count)
    chosen: list[str] = []
    for _ in range(count):
        remaining = [o for o in pool if o not in chosen]
        if not remaining:
            break
        rw = [w[pool.index(o)] for o in remaining]
        choice = random.choices(remaining, weights=rw, k=1)[0]
        chosen.append(choice)
    return chosen


def ghana_phone() -> str:
    prefixes = ["024", "020", "050", "054", "055", "059", "027", "057"]
    return random.choice(prefixes) + str(random.randint(1000000, 9999999))


def ga_fante_name() -> str:
    if random.random() < 0.5:
        first = random.choice(GA_FIRST + FANTE_FIRST)
    else:
        first = random.choice(GA_FIRST) if random.random() < 0.5 else random.choice(FANTE_FIRST)
    surname = random.choice(SURNAMES)
    if random.random() < 0.3:
        return f"{first} {random.choice(SURNAMES)} {surname}"
    return f"{first} {surname}"


def fishing_experience_for_age(age: int) -> int:
    """Q17: 6–30 years, correlated with age."""
    started = random.randint(16, min(22, age - 5))
    exp = max(6, age - started)
    return min(30, exp)


def income_for_age(age: int) -> float:
    """Q52: 3000–7000 GHS, correlates with age."""
    base = 3000 + (age - 25) * random.uniform(80, 150)
    return round(min(7000, max(3000, base + random.uniform(-400, 400))), 2)


def gear_ownership_for_status(status: str) -> str:
    """Q19 correlates with Q18."""
    if status in ("Canoe owner", "Both owner and crew member"):
        return pick_yes(0.88)
    return pick_yes(0.25)


def degrade_english(text: str) -> str:
    """Make text sound less polished."""
    text = text.lower()
    replacements = {
        "government": "govment", "the": "", "should": "shud", "because": "becos",
        "very": "veri", "they": "dem", "them": "dem", "there": "der",
        "help": "help", "fishing": "fishing", "fish": "fish",
    }
    for a, b in replacements.items():
        text = re.sub(rf"\b{a}\b", b, text)
    return text.strip().capitalize() if text else text


class AnswerEngine:
    """Generates one complete respondent profile following project guidelines."""

    def generate(self, respondent_index: int) -> dict[str, Any]:
        a: dict[str, Any] = {}

        # --- Section A ---
        a["q1"] = ga_fante_name()
        a["q2"] = ghana_phone()
        a["q3"] = "Male"
        age = random.randint(25, 48)
        a["q4"] = age

        a["q5"] = random.choice(["Single", "Married", "Divorced", "Widowed", "Separated"])

        a["q6"] = pick_weighted(
            ["No formal education", "Primary education", "Junior High School",
             "Senior High School", "Vocational/Technical", "Tertiary education"],
            [35, 30, 25, 5, 3, 2],
        )

        a["q7"] = pick_from_ranking(
            ["Christianity", "Islam", "Traditional religion", "Other (Specify)"],
            [3, 1, 4, 2],
            count=1,
        )[0]
        if a["q7"] == "Other (Specify)":
            a["q7a"] = "No religion"

        a["q8"] = pick_weighted(
            ["Greater Accra", "Central", "Volta", "Western", "Eastern", "Ashanti", "Northern", "Other (Specify)"],
            [80, 5, 4, 3, 3, 2, 2, 1],
        )
        if a["q8"] == "Other (Specify)":
            a["q8a"] = "Oti Region"

        a["q9"] = pick_weighted(
            [
                "Jamestown", "Chorkor", "Korle Gonno", "Bukom", "Akoto Lante",
                "Ussher Town", "Ngleshie", "Mamprobi",
            ],
            [82, 5, 4, 3, 2, 2, 1, 1],
        )

        a["q10"] = pick_weighted(
            ["Native resident", "Migrant resident", "Temporary resident"],
            [75, 18, 7],
        )

        a["q11"] = pick_from_ranking(
            ["Compound house", "Self-contained house", "Wooden structure", "Kiosk/container", "Other (Specify)"],
            [1, 3, 4, 2],
            count=1,
        )[0]
        if a["q11"] == "Other (Specify)":
            a["q11a"] = "Tent"

        a["q12"] = pick_weighted(
            ["Owner occupied", "Rented", "Family house", "Employer provided", "Other (Specify)"],
            [10, 45, 40, 3, 2],
        )
        if a["q12"] == "Other (Specify)":
            a["q12a"] = "Squatting"

        a["q13"] = random.randint(2, 7)
        a["q14"] = "Fishing"
        if a["q14"] == "Other (Specify)":
            a["q14a"] = "Trading other things"

        a["q15"] = pick_yes(0.55)
        # Always generate q16 regardless of q15 answer
        a["q16"] = pick_weighted(
            ["Trading", "Farming", "Transport business", "Processing", "Casual labour", "Other (Specify)"],
            [40, 5, 8, 35, 38, 3],
        )
        if a["q16"] == "Other (Specify)":
            a["q16a"] = "Teaching"

        a["q17"] = fishing_experience_for_age(age)

        a["q18"] = pick_weighted(
            ["Canoe owner", "Crew member", "Both owner and crew member"],
            [15, 40, 45],
        )

        a["q19"] = gear_ownership_for_status(a["q18"])

        a["q20"] = pick_weighted(
            ["Ordinary member", "Opinion leader", "Chief fisherman", "Assembly representative", "Other (Specify)"],
            [55, 40, 3, 1, 1],
        )
        if a["q20"] == "Other (Specify)":
            a["q20a"] = "Elder"

        a["q21"] = pick_yes(0.82)
        # Always generate q22, q23 regardless of q21 answer
        a["q22"] = pick_weighted(
            ["Fisher association", "Fish processors association", "Cooperative society",
             "Savings group", "Religious association", "Other (Specify)"],
            [50, 8, 45, 10, 5, 2],
        )
        if a["q22"] == "Other (Specify)":
            a["q22a"] = "Youth group"
        
        a["q23"] = random.randint(1, min(15, max(2, age - 18)))

        # --- Section B ---
        challenges = pick_multiple_weighted(
            ["fuel cost too high", "fish stock declining every day", "damage to our fishing gear", "pollution in the sea", "no cold storage here", "lack of credit and loans"],
            [40, 12, 35, 30, 2, 15],
            min_count=1,
            max_count=2,
        )
        a["q24"] = " and ".join(challenges).capitalize() + "."

        a["q25"] = pick_yes(0.90)
        # Always generate q26, q27 regardless of q25 answer
        a["q26"] = random.randint(300, 1200)
        a["q27"] = pick_weighted(
            ["Very low", "Low", "Moderate", "High", "Very high"],
            [5, 20, 25, 30, 20],
        )

        a["q28"] = pick_yes(0.78)
        # Always generate q29 regardless of q28 answer
        a["q29"] = pick_weighted(["Very often", "Often", "Occasionally", "Rarely"], [15, 45, 35, 5])

        a["q30"] = pick_yes(0.85)
        # Always generate q31 regardless of q30 answer
        a["q31"] = pick_weighted(["Low", "Moderate", "High", "Very high"], [10, 40, 35, 15])

        a["q32"] = pick_yes(0.60)
        # Always generate q33 regardless of q32 answer
        a["q33"] = pick_weighted(
            ["Light fishing", "Pair trawling", "Dynamite fishing", "Use of chemicals", "Other (Specify)"],
            [40, 35, 5, 18, 2],
        )
        if a["q33"] == "Other (Specify)":
            a["q33a"] = "Illegal nets"

        a["q34"] = pick_yes(0.70)
        # Always generate q35, q36 regardless of q34 answer
        a["q35"] = pick_weighted(
            ["Trawlers", "Pollution", "Wear and tear", "Storms", "Other (Specify)"],
            [20, 35, 38, 5, 2],
        )
        if a["q35"] == "Other (Specify)":
            a["q35a"] = "Accident"
        a["q36"] = random.randint(200, 600)

        a["q37"] = pick_yes(0.80)
        # Always generate q38 regardless of q37 answer
        a["q38"] = pick_weighted(["Low", "Moderate", "High", "Very high"], [10, 40, 35, 15])

        a["q39"] = pick_yes(0.12)
        a["q40"] = pick_yes(0.65)
        
        a["q41"] = pick_yes(0.70)
        # Always generate q42 regardless of q41 answer
        a["q42"] = pick_weighted(["Very often", "Often", "Occasionally", "Rarely"], [10, 45, 40, 5])

        a["q43"] = pick_yes(0.85)
        # Always generate q44 regardless of q43 answer
        a["q44"] = pick_yes(0.80)

        a["q45"] = pick_weighted(
            ["Very low", "Low", "Moderate", "High", "Very high"],
            [2, 8, 30, 40, 20],
        )
        a["q46"] = pick_yes(0.55)

        a["q47"] = pick_weighted(
            ["Fuel cost", "Fish stock decline", "Gear damage", "Pollution", "Inadequate storage facilities", "Credit constraints"],
            [35, 20, 15, 15, 5, 10],
        )

        # Q48 fixed ranking
        a["q48"] = {
            "Fuel cost": 1,
            "Gear damage": 2,
            "Pollution": 3,
            "Credit constraints": 4,
            "Fish stock decline": 5,
            "Inadequate storage facilities": 6,
        }

        # --- Section C ---
        income_effects = pick_multiple_weighted(
            ["my catch is reduced", "cost of operation is too high", "we get lower prices for fish", "our income is irregular", "we lose many fishing days"],
            [30, 35, 20, 25, 20],
            min_count=1,
            max_count=2,
        )
        a["q49"] = " and ".join(income_effects).capitalize() + "."

        a["q50"] = random.randint(100, 400)
        a["q51"] = random.randint(40, 90)
        a["q52"] = int(income_for_age(age))

        a["q53"] = pick_weighted(
            ["Very unstable", "Unstable", "Moderately stable", "Stable", "Very stable"],
            [15, 30, 30, 20, 5],
        )
        a["q54"] = pick_weighted(["Always", "Often", "Sometimes", "Rarely"], [5, 30, 55, 10])
        a["q55"] = pick_yes(0.82)
        a["q56"] = pick_yes(0.80)
        # Always generate q57, q58 regardless of q56 answer
        a["q57"] = pick_weighted(["Peak season", "Lean season", "Same for all seasons"], [70, 10, 20])
        a["q58"] = pick_weighted(["Peak season", "Lean season"], [15, 85])

        a["q59"] = pick_yes(0.15)
        a["q60"] = pick_yes(0.15)
        a["q61"] = pick_yes(0.44)
        a["q62"] = pick_yes(0.77)
        a["q63"] = pick_yes(0.90)
        a["q64"] = pick_yes(0.75)
        a["q65"] = pick_weighted(
            ["Very weak", "Weak", "Moderate", "Strong", "Very strong"],
            [10, 25, 35, 22, 8],
        )
        a["q66"] = pick_weighted(
            ["Very poor", "Poor", "Average", "Good", "Very good"],
            [20, 30, 30, 15, 5],
        )

        # --- Section D ---
        measures = pick_multiple_weighted(
            ["provide cheap credit and loans", "build cold storage facilities", "regular premix fuel supply", "help us with cheap fishing equipment", "improve harbour infrastructure", "give us training programmes"],
            [25, 20, 35, 22, 28, 15],
            min_count=1,
            max_count=2,
        )
        a["q67"] = " and ".join(measures).capitalize() + "."

        a["q68"] = pick_yes(0.57)
        a["q69"] = pick_yes(0.20)
        a["q70"] = pick_yes(0.36)
        
        # Always generate q71 regardless of q70 answer
        a["q71"] = pick_weighted(
            ["Fuel subsidy", "Training", "Fishing equipment support", "Credit support", "Other (Specify)"],
            [40, 15, 28, 15, 2],
        )
        if a["q71"] == "Other (Specify)":
            a["q71a"] = "Free nets"

        a["q72"] = pick_weighted(
            ["Credit facilities", "Cold storage facilities", "Premix fuel supply", "Fishing equipment", "Harbour infrastructure improvement", "Training programmes"],
            [25, 20, 30, 12, 10, 3],
        )

        a["q73"] = pick_yes(0.71)
        a["q74"] = pick_yes(0.85)
        a["q75"] = pick_yes(0.28)
        a["q76"] = "Yes"
        a["q77"] = pick_yes(0.85)
        
        yes_pct = 0.65 + (age - 25) * 0.02
        a["q78"] = pick_yes(min(0.95, yes_pct))

        q72_map = {
            "Credit facilities": "We need credit and loan for canoe. Govment shud help us.",
            "Cold storage facilities": "Cold store no dey here. We need cold store so fish no spoil.",
            "Premix fuel supply": "Premix fuel price too high and shortage dey. Help us with fuel.",
            "Fishing equipment": "Fishing gear and net too cost. We need help with equipment.",
            "Harbour infrastructure improvement": "Harbour need repair. Boats cant land proper.",
            "Training programmes": "Training from govment will help us small.",
        }
        rec = q72_map.get(a["q72"], "Govment should reduce fuel price and give premix on time")
        a["q79"] = degrade_english(rec)

        a["_meta"] = {
            "respondent_index": respondent_index + 1,
            "age": age,
            "name": a["q1"],
        }
        return a
