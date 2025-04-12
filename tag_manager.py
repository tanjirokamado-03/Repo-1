# tag_manager.py

from typing import Set, List, Dict, Optional
import json
import os

# Enhanced tag categories for college student emails
TAG_CATEGORIES = {
    "priority": ["urgent", "important", "normal", "low"],
    "academic": ["academic", "deadline", "research", "lecture"],
    "activities": ["sports", "event", "club", "cultural"],
    "administrative": ["admin", "announcement", "registration", "fees"]
}

# Tag color configuration for visual identification
TAG_COLORS = {
    # Priority tags
    "urgent": "#e74c3c",     # Red
    "important": "#e67e22",  # Orange
    "normal": "#3498db",     # Blue
    "low": "#95a5a6",        # Gray
    
    # Academic tags
    "academic": "#9b59b6",   # Purple
    "deadline": "#c0392b",   # Dark Red
    "research": "#8e44ad",   # Dark Purple
    "lecture": "#2980b9",    # Dark Blue
    
    # Activities tags
    "sports": "#2ecc71",     # Green
    "event": "#e67e22",      # Orange
    "club": "#3498db",       # Blue
    "cultural": "#d35400",   # Dark Orange
    
    # Administrative tags
    "admin": "#7f8c8d",      # Gray
    "announcement": "#34495e", # Dark Gray
    "registration": "#1abc9c", # Turquoise
    "fees": "#f1c40f",       # Yellow
    
    # Default for other tags
    "general": "#34495e"     # Dark Gray
}

class TagManager:
    def __init__(self, tags_file="tags.json"):
        self.tags_file = tags_file
        self.user_tags: Set[str] = set()
        self.tag_colors: Dict[str, str] = dict(TAG_COLORS)  # Start with default colors
        self.load_tags()
        
        # Standard tags that are always available
        self.standard_tags: Set[str] = set()
        for category in TAG_CATEGORIES.values():
            self.standard_tags.update(category)
    
    def load_tags(self):
        if os.path.exists(self.tags_file):
            try:
                with open(self.tags_file, 'r') as f:
                    data = json.load(f)
                    self.user_tags = set(data.get("user_tags", []))
                    
                    # Update colors from saved file, but keep defaults
                    saved_colors = data.get("tag_colors", {})
                    for tag, color in saved_colors.items():
                        self.tag_colors[tag] = color
            except Exception as e:
                print(f"Error loading tags: {e}")
    
    def save_tags(self):
        with open(self.tags_file, 'w') as f:
            json.dump({
                "user_tags": list(self.user_tags),
                "tag_colors": self.tag_colors
            }, f)
    
    def get_all_tags(self) -> List[str]:
        """Get all available tags (standard + user-defined)"""
        return sorted(self.standard_tags.union(self.user_tags))
    
    def add_tag(self, tag: str) -> bool:
        """Add a new user-defined tag"""
        tag = tag.lower().strip()
        if tag and tag not in self.standard_tags:
            self.user_tags.add(tag)
            
            # Assign a default color if none exists
            if tag not in self.tag_colors:
                self.tag_colors[tag] = "#3498db"  # Default blue
                
            self.save_tags()
            return True
        return False
    
    def remove_tag(self, tag: str) -> bool:
        """Remove a user-defined tag"""
        tag = tag.lower().strip()
        if tag in self.user_tags:
            self.user_tags.remove(tag)
            if tag in self.tag_colors:
                del self.tag_colors[tag]
            self.save_tags()
            return True
        return False
    
    def set_tag_color(self, tag: str, color: str) -> bool:
        """Set color for a tag"""
        tag = tag.lower().strip()
        if tag in self.get_all_tags():
            self.tag_colors[tag] = color
            self.save_tags()
            return True
        return False
    
    def get_tag_color(self, tag: str) -> Optional[str]:
        """Get color for a tag"""
        return self.tag_colors.get(tag.lower().strip())
    
    def get_tags_by_category(self) -> Dict[str, List[str]]:
        """Get tags organized by categories"""
        result = {category: list(tags) for category, tags in TAG_CATEGORIES.items()}
        result["custom"] = list(self.user_tags)
        return result
    
    def get_all_tag_details(self) -> List[Dict[str, str]]:
        """Get detailed information about all tags"""
        result = []
        for tag in self.get_all_tags():
            category = "custom"
            for cat_name, cat_tags in TAG_CATEGORIES.items():
                if tag in cat_tags:
                    category = cat_name
                    break
                    
            result.append({
                "name": tag,
                "color": self.get_tag_color(tag) or "#888888",
                "category": category
            })
        
        return result

# Initialize singleton
tag_manager = TagManager()

# Export functions for backward compatibility
def get_tags():
    return tag_manager.get_all_tags()

def add_tag(new_tag):
    return tag_manager.add_tag(new_tag)

def get_tag_color(tag):
    return tag_manager.get_tag_color(tag)
