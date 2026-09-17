# Standard taxonomy lists for microstock platforms

ADOBE_STOCK_CATEGORIES = [
    "Animals",
    "Buildings and Architecture",
    "Business",
    "Drinks",
    "The Environment",
    "States of Mind",
    "Food",
    "Graphic Resources",
    "Hobbies and Leisure",
    "Industry",
    "Landscapes",
    "Lifestyle",
    "People",
    "Plants and Flowers",
    "Culture and Religion",
    "Science",
    "Social Issues",
    "Sports",
    "Technology",
    "Transport",
    "Travel",
]

ADOBE_CATEGORY_MAP = {
    "Animals": 1,
    "Buildings and Architecture": 2,
    "Business": 3,
    "Drinks": 4,
    "The Environment": 5,
    "States of Mind": 6,
    "Food": 7,
    "Graphic Resources": 8,
    "Hobbies and Leisure": 9,
    "Industry": 10,
    "Landscapes": 11,
    "Lifestyle": 12,
    "People": 13,
    "Plants and Flowers": 14,
    "Culture and Religion": 15,
    "Science": 16,
    "Social Issues": 17,
    "Sports": 18,
    "Technology": 19,
    "Transport": 20,
    "Travel": 21,
}

SHUTTERSTOCK_CATEGORIES = [
    "Abstract",
    "Animals/Wildlife",
    "Backgrounds/Textures",
    "Beauty/Fashion",
    "Buildings/Landmarks",
    "Business/Finance",
    "Celebrities",
    "Education",
    "Food and Drink",
    "Healthcare/Medical",
    "Holidays",
    "Illustrations/Clip-Art",
    "Industrial",
    "Interiors",
    "Miscellaneous",
    "Nature",
    "Objects",
    "Parks/Outdoor",
    "People",
    "Religion",
    "Science",
    "Signs/Symbols",
    "Sports/Recreation",
    "Technology",
    "The Arts",
    "Transportation",
    "Vintage",
]


def map_to_agency_category(raw_category: str, target_platform: str, title: str = "", keywords: list | None = None) -> str:
    """Map AI raw category or fallback based on title/keywords to exact platform category name."""
    if keywords is None:
        keywords = []
    
    # 1. Normalisasi string
    raw_cat = (raw_category or "").strip().lower()
    text_context = (raw_cat + " " + title.lower() + " " + " ".join(k.lower() for k in keywords)).strip()
    
    # 2. Heuristik berdasarkan sinonim / keywords
    inferred_cat = ""
    
    if any(k in text_context for k in ["avatar", "face", "character", "people", "person", "human", "woman", "man", "girl", "boy"]):
        inferred_cat = "people"
    elif any(k in text_context for k in ["business", "office", "strategy", "marketing", "financ"]):
        inferred_cat = "business"
    elif any(k in text_context for k in ["tech", "coding", "software", "computer", "program", "developer", "data"]):
        inferred_cat = "technology"
    elif any(k in text_context for k in ["nurse", "medical", "clinic", "health", "doctor", "hospital", "medicine"]):
        inferred_cat = "science"  # Adobe uses Science or Social Issues; Shutter uses Healthcare/Medical
    elif any(k in text_context for k in ["animal", "wildlife", "pet", "dog", "cat", "bird"]):
        inferred_cat = "animals"
    elif any(k in text_context for k in ["food", "drink", "meal", "restaurant"]):
        inferred_cat = "food"
    elif any(k in text_context for k in ["building", "architecture", "city", "house"]):
        inferred_cat = "buildings"
    elif any(k in text_context for k in ["nature", "environment", "tree", "forest", "landscape", "mountain"]):
        inferred_cat = "nature"
    
    # Jika tidak ada yang cocok, fallback ke raw category atau graphic resources
    effective_cat = inferred_cat if inferred_cat else raw_cat

    # 3. Deterministic Mapping per Platform
    target = target_platform.strip().lower()
    
    if target == "adobe stock":
        if "people" in effective_cat:
            return "People"
        if "business" in effective_cat:
            return "Business"
        if "technology" in effective_cat:
            return "Technology"
        if "science" in effective_cat:
            return "Science"
        if "social" in effective_cat:
            return "Social Issues"
        if "animal" in effective_cat:
            return "Animals"
        if "building" in effective_cat or "architecture" in effective_cat:
            return "Buildings and Architecture"
        if "nature" in effective_cat or "environment" in effective_cat:
            return "The Environment"
        if "food" in effective_cat or "drink" in effective_cat:
            return "Food"
        if "landscape" in effective_cat:
            return "Landscapes"
        if "industry" in effective_cat or "industrial" in effective_cat:
            return "Industry"
        if "mind" in effective_cat or "emotion" in effective_cat:
            return "States of Mind"
        if "lifestyle" in effective_cat:
            return "Lifestyle"
        if "plant" in effective_cat or "flower" in effective_cat:
            return "Plants and Flowers"
        if "cultur" in effective_cat or "religion" in effective_cat:
            return "Culture and Religion"
        if "sport" in effective_cat or "fitness" in effective_cat:
            return "Sports"
        if "transport" in effective_cat or "vehicle" in effective_cat:
            return "Transport"
        if "travel" in effective_cat:
            return "Travel"
        return "Graphic Resources"

    if target == "shutterstock":
        if "people" in effective_cat:
            return "People"
        if "business" in effective_cat:
            return "Business/Finance"
        if "technology" in effective_cat:
            return "Technology"
        if "science" in effective_cat or "medical" in effective_cat or "health" in effective_cat:
            if "medical" in text_context or "health" in text_context or "nurse" in text_context or "clinic" in text_context:
                return "Healthcare/Medical"
            return "Science"
        if "animal" in effective_cat:
            return "Animals/Wildlife"
        if "building" in effective_cat or "architecture" in effective_cat:
            return "Buildings/Landmarks"
        if "nature" in effective_cat or "environment" in effective_cat or "landscape" in effective_cat:
            return "Nature"
        if "food" in effective_cat or "drink" in effective_cat:
            return "Food and Drink"
        if "industry" in effective_cat or "industrial" in effective_cat:
            return "Industrial"
        if "sport" in effective_cat or "fitness" in effective_cat:
            return "Sports/Recreation"
        if "transport" in effective_cat or "vehicle" in effective_cat:
            return "Transportation"
        if "travel" in effective_cat:
            return "Parks/Outdoor"
        if "art" in effective_cat or "graphic" in effective_cat or "illustration" in effective_cat:
            return "The Arts"
        if "background" in effective_cat or "texture" in effective_cat:
            return "Backgrounds/Textures"
        if "object" in effective_cat:
            return "Objects"
        if "holiday" in effective_cat:
            return "Holidays"
        if "sign" in effective_cat or "symbol" in effective_cat:
            return "Signs/Symbols"
        if "education" in effective_cat:
            return "Education"
        return "The Arts"

    # Default fallback for Vecteezy / Freepik or unknown
    # Typically they just accept tags or string. We just capitalize the determined category.
    return effective_cat.title() if effective_cat else "Graphic Resources"


def get_adobe_category_code(category_name: str, title: str = "", keywords: list | None = None) -> int:
    # Use mapping to ensure strict Adobe Stock name is passed, then return its code
    mapped_name = map_to_agency_category(category_name, "adobe stock", title=title, keywords=keywords)
    return ADOBE_CATEGORY_MAP.get(mapped_name, 8)


def get_adobe_stock_categories():
    return ADOBE_STOCK_CATEGORIES


def get_shutterstock_categories():
    return SHUTTERSTOCK_CATEGORIES



