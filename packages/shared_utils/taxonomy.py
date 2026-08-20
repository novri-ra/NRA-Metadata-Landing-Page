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
    return ADOBE_CATEGORY_MAP.get(category_name, 8)

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
