# Standard taxonomy lists for microstock platforms

ADOBE_STOCK_CATEGORIES = [
    "Animals", "Buildings and Architecture", "Business", "Drinks", "The Environment",
    "States of Mind", "Food", "Graphic Resources", "Hobbies and Leisure", "Industry",
    "Landscapes", "Lifestyle", "People", "Plants and Flowers", "Culture and Religion",
    "Science", "Social Issues", "Sports", "Technology", "Transport", "Travel"
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
    "Travel": 21
}

def get_adobe_category_code(category_name: str) -> int:
    if not category_name:
        return 8
    res = ADOBE_CATEGORY_MAP.get(category_name)
    if res is not None:
        return res
    cat_lower = category_name.lower()
    if "animal" in cat_lower: return 1
    if "building" in cat_lower or "architecture" in cat_lower: return 2
    if "business" in cat_lower: return 3
    if "environment" in cat_lower or "nature" in cat_lower: return 5
    if "mind" in cat_lower or "emotion" in cat_lower: return 6
    if "food" in cat_lower: return 7
    if "hobby" in cat_lower or "leisure" in cat_lower: return 9
    if "industr" in cat_lower: return 10
    if "landscape" in cat_lower: return 11
    if "lifestyle" in cat_lower: return 12
    if "people" in cat_lower: return 13
    if "plant" in cat_lower or "flower" in cat_lower: return 14
    if "cultur" in cat_lower or "religion" in cat_lower: return 15
    if "scienc" in cat_lower: return 16
    if "social" in cat_lower: return 17
    if "sport" in cat_lower: return 18
    if "tech" in cat_lower: return 19
    if "transport" in cat_lower: return 20
    if "travel" in cat_lower: return 21
    return 8

SHUTTERSTOCK_CATEGORIES = [
    "Abstract", "Animals/Wildlife", "Backgrounds/Textures", "Beauty/Fashion",
    "Buildings/Landmarks", "Business/Finance", "Celebrities", "Education",
    "Food and Drink", "Healthcare/Medical", "Holidays", "Illustrations/Clip-Art",
    "Industrial", "Interiors", "Miscellaneous", "Nature", "Objects",
    "Parks/Outdoor", "People", "Religion", "Science", "Signs/Symbols",
    "Sports/Recreation", "Technology", "The Arts", "Transportation", "Vintage"
]

def get_adobe_stock_categories():
    return ADOBE_STOCK_CATEGORIES

def get_shutterstock_categories():
    return SHUTTERSTOCK_CATEGORIES
