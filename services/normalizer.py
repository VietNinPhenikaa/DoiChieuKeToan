import re
import pandas as pd

def clean_string(text):
    if pd.isna(text): return ""
    text = str(text).upper().strip()
    # Bỏ các ký tự đặc biệt, nhiều khoảng trắng
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def parse_date(date_val):
    if pd.isna(date_val): return None
    try:
        return pd.to_datetime(date_val, dayfirst=True).date()
    except:
        return None

def parse_amount(val):
    if pd.isna(val) or val == '': return 0.0
    if isinstance(val, (int, float)): return float(val)
    # Loại bỏ chữ, dấu phẩy, khoảng trắng
    val = str(val).replace(',', '').replace(' ', '').replace('VND', '').replace('VNĐ', '')
    try:
        return float(val)
    except:
        return 0.0