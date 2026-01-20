import json
import os

class TextFormatter:
    """Format explanatory text for categories and parameters"""
    
    def __init__(self):
        self.categories_config = self._load_categories_config()
    
    def _load_categories_config(self):
        """Load categories configuration"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'categories.json')
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_category_explanation(self, category_name):
        """Get explanation text for a category"""
        for cat in self.categories_config['categories']:
            if cat['name'] == category_name:
                return cat.get('explanation', '')
        return f"This category includes various laboratory parameters related to {category_name.lower()}."
    
    def format_parameter_group_explanation(self, parameters):
        """Format explanation for a group of related parameters"""
        explanations = []
        for param in parameters:
            if param.get('explanation'):
                explanations.append({
                    'name': param['english_name'],
                    'text': param['explanation']
                })
        return explanations
