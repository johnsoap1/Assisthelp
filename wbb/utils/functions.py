# wbb/utils/functions.py
import re

def extract_text_and_keyb(ikb_func, text):
    """Extract inline keyboard buttons from text"""
    keyboard = []
    
    # Pattern: [Button Text, url/callback_data]
    pattern = r'\[([^\[\]]+)\s*,\s*([^\[\]]+)\]'
    
    matches = re.finditer(pattern, text)
    
    for match in matches:
        button_text = match.group(1).strip()
        button_data = match.group(2).strip()
        
        button = {}
        button['text'] = button_text
        
        if button_data.startswith('http'):
            button['url'] = button_data
        else:
            button['callback_data'] = button_data
        
        keyboard.append([button])
        text = text.replace(match.group(0), '')
    
    if keyboard:
        return text.strip(), ikb_func(keyboard)
    return text.strip(), None
