import unittest
from packages.shared_utils.taxonomy import map_to_agency_category, get_adobe_category_code

class TestCategoryMapper(unittest.TestCase):
    def test_map_avatar_to_people(self):
        # AI returns garbage, but keywords have 'avatar' and 'face'
        cat_shutter = map_to_agency_category("Graphic Resources", "shutterstock", title="Cute avatar icon", keywords=["avatar", "face", "cute"])
        cat_adobe = map_to_agency_category("Graphic Resources", "adobe stock", title="Cute avatar icon", keywords=["avatar", "face", "cute"])
        
        self.assertEqual(cat_shutter, "People")
        self.assertEqual(cat_adobe, "People")
        
        # Test exact Adobe Stock ID
        code = get_adobe_category_code("Graphic Resources", title="Cute avatar icon", keywords=["avatar", "face", "cute"])
        self.assertEqual(code, 13) # People is 13

    def test_map_business_workflow_to_business(self):
        # Title has business context
        cat_shutter = map_to_agency_category("Technology", "shutterstock", title="Business strategy workflow", keywords=["workflow", "strategy", "office"])
        cat_adobe = map_to_agency_category("Technology", "adobe stock", title="Business strategy workflow", keywords=["workflow", "strategy", "office"])
        
        self.assertEqual(cat_shutter, "Business/Finance")
        self.assertEqual(cat_adobe, "Business")
        
        # Test Adobe Stock ID
        code = get_adobe_category_code("Technology", title="Business strategy workflow", keywords=["workflow", "strategy", "office"])
        self.assertEqual(code, 3) # Business is 3

    def test_map_tech_to_technology(self):
        cat_shutter = map_to_agency_category("Abstract", "shutterstock", title="Software development", keywords=["coding", "developer", "computer"])
        self.assertEqual(cat_shutter, "Technology")

    def test_map_medical_to_science_or_healthcare(self):
        cat_shutter = map_to_agency_category("Lifestyle", "shutterstock", title="Nurse at clinic", keywords=["nurse", "medical", "hospital"])
        cat_adobe = map_to_agency_category("Lifestyle", "adobe stock", title="Nurse at clinic", keywords=["nurse", "medical", "hospital"])
        
        self.assertEqual(cat_shutter, "Healthcare/Medical")
        self.assertEqual(cat_adobe, "Science")
        
        code = get_adobe_category_code("Lifestyle", title="Nurse at clinic", keywords=["nurse", "medical", "hospital"])
        self.assertEqual(code, 16) # Science is 16

    def test_fallback_robustness(self):
        # Totally unknown category, empty title, empty keywords
        cat_shutter = map_to_agency_category("GloopGlop", "shutterstock", title="", keywords=[])
        self.assertEqual(cat_shutter, "The Arts") # Defaults to The Arts for vector fallback in csv exporter normally, but here it's just raw category so it falls through to effective_cat capitalization. Wait, let's see.
        
        # Actually our map_to_agency_category falls through to effective_cat.title() for unknown platforms, but for shutterstock it returns "The Arts" if no match
        cat_unknown = map_to_agency_category("GloopGlop", "freepik", title="", keywords=[])
        self.assertEqual(cat_unknown, "Gloopglop") # Title-cased effective_cat
        
        cat_empty = map_to_agency_category("", "freepik", title="", keywords=[])
        self.assertEqual(cat_empty, "Graphic Resources")

        code = get_adobe_category_code("GloopGlop")
        self.assertEqual(code, 8) # Fallbacks to Graphic Resources (8)

if __name__ == '__main__':
    unittest.main()
