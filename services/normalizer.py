import re
import unicodedata
import pandas as pd

def normalize_text(text):
    if not isinstance(text, str):
        return ""
    # Normalize unicode
    text = unicodedata.normalize('NFKC', str(text))
    text = text.lower()
    # Giữ lại chữ, số và khoảng trắng
    text = re.sub(r'[^\w\s]', ' ', text)
    # Xóa khoảng trắng thừa
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_first10(normalized_text):
    return normalized_text.replace(" ", "")[:10]

def extract_amount(val):
    if pd.isna(val) or val == '':
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
        
    text_val = str(val).strip()
    
    # Kế toán/Excel thường dùng dấu '-' hoặc '_' để biểu diễn số 0
    if text_val in ['-', '_']:
        return 0.0
        
    # Chỉ giữ lại số và dấu phân cách
    text_val = re.sub(r'[^\d,\.-]', '', text_val)
    
    # Nếu sau khi lọc chỉ còn lại rỗng, dấu trừ hoặc dấu chấm thì trả về 0
    if not text_val or text_val in ['-', '.', '-.']:
        return 0.0
        
    # Đưa về chuẩn (loại bỏ dấu phân cách hàng nghìn)
    if ',' in text_val and '.' in text_val:
        if text_val.rfind(',') > text_val.rfind('.'):
            text_val = text_val.replace('.', '').replace(',', '.')
        else:
            text_val = text_val.replace(',', '')
            
    try:
        return float(text_val)
    except ValueError:
        return 0.0