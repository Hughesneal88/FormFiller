import random
import json

# Ghanaian Ga and Fante Male Names
GA_NAMES = ["Nii", "Adama", "Korkwei", "Laryea", "Kpakpo", "Tetteh", "Mensah", "Anang", "Armah", "Sowah", "Adjei", "Tawiah", "Okaidja", "Oblitey", "Bortey", "Kwei"]
FANTE_NAMES = ["Kwesi", "Kojo", "Kwabena", "Kobina", "Yaw", "Kofi", "Kwame", "Kwamena", "Kweku", "Ato", "Ebo", "Kakra", "Panyin", "Fiifi", "Joojo"]
LAST_NAMES = ["Lartey", "Addo", "Osei", "Mensah", "Appiah", "Quaye", "Ansah", "Blankson", "Ackon", "Essel", "Quarshie", "Lamptey", "Abbey", "Amartey", "Vanderpuije", "Bruce", "Mills", "Ankrah", "Atta", "Baffoe", "Cudjoe", "Eshun", "Koomson", "Arthur", "Yankey"]

# Location options for Q9
LOCATIONS = ["Jamestown", "Chorkor", "Korle Gonno", "Ussher Town", "Sempe", "Gbese", "Salaga", "Alata", "Lartebiokorshie", "Mamprobi"]

# Q16 options
OCCUPATIONS = ["trading", "casual work", "processing", "farming", "transport", "other"]

# Q22 options
ASSOCIATIONS = ["fisher association", "cooperative society", "microfinance group", "none"]

# Text answers for Q49 (English of illiterate fishermen)
Q49_ANSWERS = [
    "premix petrol cost is too high, catching no fish",
    "gears are expensive and trawler spoil them",
    "no money for fuel, price increase too much",
    "premix fuel not there so we wait too long, no work",
    "trawlers spoil our net, we loss plenty money",
    "no storage for fish, so fish spoil and we sell cheap",
    "bad weather stop us from going to sea, no cash",
    "too much congestion at harbor, waste time",
    "government make too much rules, limit our days",
    "lack of credit, bank no give money to buy gear",
    "market prices are too low, people no buy fish",
    "theft of gear, engine stolen, we loss everything",
    "big trawlers take all the fish, we get nothing",
    "fuel shortage delay us, no premix at station",
    "net repair cost too high, no profit again"
]

# Text answers for Q67 (English of illiterate fishermen)
Q67_ANSWERS = [
    "govment must reduce fuel price and premix",
    "need help with money and soft loans",
    "give us premix fuel regularly, stop hoarding",
    "stop pollution in sea and plastic waste",
    "teach us how to fish with modern tools",
    "make net and gear cost small, subsidize them",
    "we need financial aid from government",
    "build better storage and cold store for us",
    "stop big industrial trawlers from fishing near coast",
    "improve harbor and landing site facilities",
    "give us credit without high interest",
    "provide security against engine theft",
    "reduce premix fuel price, it is too expensive",
    "government should support our local unions",
    "clean the sea, too much rubbish spoil nets"
]

def generate_phone_number():
    # Ghanaian phone number prefixes
    # MTN (024, 054, 055, 059, 053), Telecel (020, 050), AirtelTigo (026, 056, 027, 057)
    prefixes = ["024", "054", "055", "059", "020", "050", "026", "056", "027", "057"]
    prefix = random.choice(prefixes)
    digits = "".join([str(random.randint(0, 9)) for _ in range(7)])
    return f"{prefix}{digits}"

def generate_record():
    # 3. All Male
    gender = "Male"
    
    # 4. Mid 20s to late 40s
    age = random.randint(25, 49)
    
    # 1. Random Ghanaian names preferably Ga and Fante
    first_name = random.choice(GA_NAMES + FANTE_NAMES)
    last_name = random.choice(LAST_NAMES)
    name = f"{first_name} {last_name}"
    
    # 2. Random Ghanaian phone numbers
    phone = generate_phone_number()
    
    # 17. From 6 to 30 but should correlate with their age
    # E.g. starting around age 16-19
    min_exp = 6
    max_exp = min(30, age - 16)
    experience = random.randint(min_exp, max_exp)
    
    # 52. 3000-7000 should correlate with age
    # Younger ages earn less on average, older earn more
    base_income = 3000 + int((age - 25) * 160)
    income = base_income + random.randint(-400, 400)
    income = max(3000, min(7000, income))
    
    # 18. Mostly both or crew members
    q18_val = random.choices(["both", "crew member", "boat owner"], weights=[45, 45, 10])[0]
    
    # 19. Random but must correlate with previous answer
    if q18_val == "crew member":
        q19_val = random.choices(["deck hand", "net handling", "sorting fish"], weights=[40, 40, 20])[0]
    elif q18_val == "boat owner":
        q19_val = random.choices(["managing boat", "buying fuel", "selling catch"], weights=[40, 40, 20])[0]
    else: # both
        q19_val = random.choices(["deck hand", "managing boat", "net handling", "selling catch"], weights=[25, 25, 25, 25])[0]

    # 49. Open text response with low English proficiency
    q49_val = random.choice(Q49_ANSWERS)
    
    # 67. Open text response with low English proficiency
    q67_val = random.choice(Q67_ANSWERS)
    
    # 79. Answer should match their response to q67
    q79_val = q67_val

    # 78. mostly yes for older ages
    if age >= 38:
        q78_val = random.choices(["Yes", "No"], weights=[85, 15])[0]
    else:
        q78_val = random.choices(["Yes", "No"], weights=[35, 65])[0]

    # Generate survey answers dict matching all rules
    record = {
        "q1_name": name,
        "q2_phone": phone,
        "q3_gender": gender,
        "q4_age": age,
        
        # 5. Random
        "q5_ans": random.choice(["Option 1", "Option 2", "Option 3", "Option 4"]),
        
        # 6. Mostly Random but dominated by the first 3 options
        "q6_ans": random.choices(["Option 1", "Option 2", "Option 3", "Option 4", "Option 5"], weights=[25, 25, 25, 12.5, 12.5])[0],
        
        # 7. Frequency of option selection should following this ranking 3,1,4,2
        "q7_ans": random.choices(["Option 1", "Option 2", "Option 3", "Option 4"], weights=[30, 10, 45, 15])[0],
        
        # 8. Options 1,2 about 80% should be one 1
        "q8_ans": random.choices(["Option 1", "Option 2"], weights=[80, 20])[0],
        
        # 9. Jamestown and surrounding towns. Fishing areas near jamestown
        "q9_location": random.choice(LOCATIONS),
        
        # 10. Options 1,2 mostly 1
        "q10_ans": random.choices(["Option 1", "Option 2"], weights=[90, 10])[0],
        
        # 11. Frequency of option selection should following this ranking 1,3,4,2
        "q11_ans": random.choices(["Option 1", "Option 2", "Option 3", "Option 4"], weights=[45, 10, 30, 15])[0],
        
        # 12. Mostly Options 2 and 3
        "q12_ans": random.choices(["Option 1", "Option 2", "Option 3", "Option 4"], weights=[10, 40, 40, 10])[0],
        
        # 13. Anywhere from 2 to 7
        "q13_num": random.randint(2, 7),
        
        # 14. Option 1
        "q14_ans": "Option 1",
        
        # 15. Random
        "q15_ans": random.choice(["Option 1", "Option 2", "Option 3", "Option 4"]),
        
        # 16. mostly trading, casual work and processing
        "q16_occupation": random.choices(OCCUPATIONS, weights=[35, 35, 20, 4, 3, 3])[0],
        
        # 17. From 6 to 30 but should corelate with their age
        "q17_experience": experience,
        
        # 18. Mostly both or crew members
        "q18_role": q18_val,
        
        # 19. Random but must corelate previous answer
        "q19_activity": q19_val,
        
        # 20. Options 1 or 2
        "q20_ans": random.choices(["Option 1", "Option 2"], weights=[50, 50])[0],
        
        # 21. Mostly yes
        "q21_ans": random.choices(["Yes", "No"], weights=[80, 20])[0],
        
        # 22. mostly fisher association and cooperative society
        "q22_group": random.choices(ASSOCIATIONS, weights=[45, 45, 5, 5])[0],
        
        # 23. should relate to years of experience and age
        # Say, options represent financial stability or access level: Low, Medium, High
        # Higher experience/age yields higher financial rating
        "q23_status": random.choices(
            ["Low", "Medium", "High"], 
            weights=[60, 30, 10] if experience < 15 else ([10, 60, 30] if experience < 25 else [5, 40, 55])
        )[0],
        
        # 24. pick out of the option in q47 but mostly fuel, gear damage and pollution. The least however should be inadequate storage facilities
        # Option 1: Fuel, Option 2: Gear damage, Option 3: Pollution, Option 4: Storage, Option 5: Other
        "q24_issue": random.choices(["fuel", "gear damage", "pollution", "inadequate storage facilities", "other"], weights=[35, 35, 20, 2, 8])[0],
        
        # 25. 90% should say yes
        "q25_ans": random.choices(["Yes", "No"], weights=[90, 10])[0],
        
        # 26. 300 -1200
        "q26_cost": random.randint(300, 1200),
        
        # 27. between low - very high
        "q27_intensity": random.choices(["Low", "Medium", "High", "Very High"], weights=[15, 35, 35, 15])[0],
        
        # 28. 70% should say yes
        "q28_ans": random.choices(["Yes", "No"], weights=[70, 30])[0],
        
        # 29. often and occasionally
        "q29_freq": random.choices(["often", "occasionally", "rarely"], weights=[50, 45, 5])[0],
        
        # 30. 55% should say yes
        "q30_ans": random.choices(["Yes", "No"], weights=[55, 45])[0],
        
        # 31. moderate and high
        "q31_level": random.choices(["moderate", "high", "low"], weights=[48, 48, 4])[0],
        
        # 32. 60% should say no
        "q32_ans": random.choices(["Yes", "No"], weights=[40, 60])[0],
        
        # 33. mostly Light fishing Pair trawling and Use of chemicals
        "q33_practice": random.choices(["Light fishing", "Pair trawling", "Use of chemicals", "Other"], weights=[30, 30, 30, 10])[0],
        
        # 34. all yes
        "q34_ans": "Yes",
        
        # 35. mostly pollution, wear and tear and occasionaly trawler
        "q35_cause": random.choices(["pollution", "wear and tear", "industrial trawler", "other"], weights=[40, 40, 15, 5])[0],
        
        # 36. 200-600 cedis
        "q36_amount": random.randint(200, 600),
        
        # 37. 65% should say yes
        "q37_ans": random.choices(["Yes", "No"], weights=[65, 35])[0],
        
        # 38. moderate and high
        "q38_impact": random.choices(["moderate", "high", "low"], weights=[48, 48, 4])[0],
        
        # 39. 90% should say yes
        "q39_ans": random.choices(["Yes", "No"], weights=[90, 10])[0],
        
        # 40. 85% should say no
        "q40_ans": random.choices(["Yes", "No"], weights=[15, 85])[0],
        
        # 41. 67% should say yes
        "q41_ans": random.choices(["Yes", "No"], weights=[67, 33])[0],
        
        # 42. responses should range from often - rarely
        "q42_freq": random.choices(["often", "sometimes", "rarely"], weights=[33, 44, 23])[0],
        
        # 43. 55% should say yes
        "q43_ans": random.choices(["Yes", "No"], weights=[55, 45])[0],
        
        # 44. 60% should say yes
        "q44_ans": random.choices(["Yes", "No"], weights=[60, 40])[0],
        
        # 45. responses should range from moderate to high
        "q45_range": random.choices(["moderate", "high", "low"], weights=[50, 45, 5])[0],
        
        # 46. 75% should say yes
        "q46_ans": random.choices(["Yes", "No"], weights=[75, 25])[0],
        
        # 47. random but the least should be options 5 and 2
        "q47_ans": random.choices(["Option 1", "Option 2", "Option 3", "Option 4", "Option 5"], weights=[28, 8, 28, 28, 8])[0],
        
        # 48. frequency ranking should match: fuel (1), Gear (2), pollution (3), credit constraints (4), fish stock decline (5), inadequate storage fac. (6)
        "q48_priority": random.choices(
            ["fuel", "Gear", "pollution", "credit constraints", "fish stock decline", "inadequate storage fac."],
            weights=[35, 25, 17, 12, 8, 3]
        )[0],
        
        "q49_challenges": q49_val,
        
        # 50. 125-350
        "q50_catch": random.randint(125, 350),
        
        # 51. 45-80
        "q51_price": random.randint(45, 80),
        
        "q52_income": income,
        
        # 53. responses should range from very unstable to stable
        "q53_stability": random.choices(["very unstable", "unstable", "stable"], weights=[30, 50, 20])[0],
        
        # 54. responses should range from should say often and sometimes
        "q54_freq": random.choices(["often", "sometimes", "rarely"], weights=[45, 45, 10])[0],
        
        # 55. mostly yes 75% should say yes
        "q55_ans": random.choices(["Yes", "No"], weights=[75, 25])[0],
        
        # 56. yes 80% should say yes
        "q56_ans": random.choices(["Yes", "No"], weights=[80, 20])[0],
        
        # 57. mostly peak 60%
        "q57_season": random.choices(["peak", "lean", "normal"], weights=[60, 30, 10])[0],
        
        # 58. mostly lean 60%
        "q58_season": random.choices(["lean", "peak", "normal"], weights=[60, 30, 10])[0],
        
        # 59. mostly no 90%
        "q59_ans": random.choices(["Yes", "No"], weights=[10, 90])[0],
        
        # 60. mostly no 85%
        "q60_ans": random.choices(["Yes", "No"], weights=[15, 85])[0],
        
        # 61. mostly no 56%
        "q61_ans": random.choices(["Yes", "No"], weights=[44, 56])[0],
        
        # 62. mostly yes 77%
        "q62_ans": random.choices(["Yes", "No"], weights=[77, 23])[0],
        
        # 63. mostly yes 90%
        "q63_ans": random.choices(["Yes", "No"], weights=[90, 10])[0],
        
        # 64. random
        "q64_ans": random.choice(["Option 1", "Option 2", "Option 3", "Option 4"]),
        
        # 65. weak to strong
        "q65_strength": random.choices(["weak", "moderate", "strong"], weights=[30, 45, 25])[0],
        
        # 66. very good to poor
        "q66_rating": random.choices(["very good", "good", "fair", "poor"], weights=[15, 40, 35, 10])[0],
        
        "q67_recommendations": q67_val,
        
        # 68. yes 57%
        "q68_ans": random.choices(["Yes", "No"], weights=[57, 43])[0],
        
        # 69. mostly no 64%
        "q69_ans": random.choices(["Yes", "No"], weights=[36, 64])[0],
        
        # 70. mostly no 51%
        "q70_ans": random.choices(["Yes", "No"], weights=[49, 51])[0],
        
        # 71. options 1,4,3 2 should be weighted in that order
        "q71_ans": random.choices(["Option 1", "Option 4", "Option 3", "Option 2"], weights=[40, 30, 20, 10])[0],
        
        # 72. options 3,1,4,5,6,2 should be weighted in that order
        "q72_ans": random.choices(["Option 3", "Option 1", "Option 4", "Option 5", "Option 6", "Option 2"], weights=[35, 25, 18, 12, 7, 3])[0],
        
        # 73. mostly yes 71%
        "q73_ans": random.choices(["Yes", "No"], weights=[71, 29])[0],
        
        # 74. yes 85%
        "q74_ans": random.choices(["Yes", "No"], weights=[85, 15])[0],
        
        # 75. no 72%
        "q75_ans": random.choices(["Yes", "No"], weights=[28, 72])[0],
        
        # 76. all yes
        "q76_ans": "Yes",
        
        # 77. mostly yes 85%
        "q77_ans": random.choices(["Yes", "No"], weights=[85, 15])[0],
        
        "q78_ans": q78_val,
        "q79_ans": q79_val
    }
    return record

def generate_dataset(count=95):
    records = []
    for i in range(count):
        rec = generate_record()
        rec["id"] = i + 1
        rec["status"] = "Ready" # Ready, Pending, Submitted, Failed
        records.append(rec)
    return records

if __name__ == "__main__":
    # Test generation and print statistical summary of the rules to verify
    dataset = generate_dataset(1000)
    print(f"Generated {len(dataset)} records for verification.")
    
    # Check age range
    ages = [r["q4_age"] for r in dataset]
    print(f"Age range: {min(ages)} - {max(ages)}")
    
    # Check gender
    genders = [r["q3_gender"] for r in dataset]
    print(f"Genders: Male={genders.count('Male')} Female={genders.count('Female')}")
    
    # Check Rule 8 (Options 1,2 about 80% should be 1)
    q8 = [r["q8_ans"] for r in dataset]
    print(f"Q8 distribution: Option 1={q8.count('Option 1')/10}%, Option 2={q8.count('Option 2')/10}%")
    
    # Check Q25 (90% should say yes)
    q25 = [r["q25_ans"] for r in dataset]
    print(f"Q25 distribution: Yes={q25.count('Yes')/10}%, No={q25.count('No')/10}%")
    
    # Check correlation for Q78 (mostly yes for older ages)
    under_38_yes = sum(1 for r in dataset if r["q4_age"] < 38 and r["q78_ans"] == "Yes")
    under_38_total = sum(1 for r in dataset if r["q4_age"] < 38)
    over_38_yes = sum(1 for r in dataset if r["q4_age"] >= 38 and r["q78_ans"] == "Yes")
    over_38_total = sum(1 for r in dataset if r["q4_age"] >= 38)
    print(f"Q78 Correlation: Under 38 Yes={under_38_yes/under_38_total*100:.1f}%, Over 38 Yes={over_38_yes/over_38_total*100:.1f}%")
