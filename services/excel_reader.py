import pandas as pd
import os
import traceback
from .normalizer import normalize_text, get_first10, extract_amount

def read_smart_excel(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.xls':
        with open(file_path, 'rb') as f:
            header_bytes = f.read(1024).lower()
            if b'<html' in header_bytes or b'<table' in header_bytes or b'<!doctype' in header_bytes or b'xml' in header_bytes:
                try:
                    dfs = pd.read_html(file_path)
                    return dfs[0] if dfs else pd.DataFrame()
                except Exception as e:
                    raise Exception(f"Lỗi đọc file giả HTML: {str(e)}")
                    
    engines = {
        '.xlsx': 'openpyxl',
        '.xlsm': 'openpyxl',
        '.xlsb': 'pyxlsb',
        '.xls': 'xlrd',
        '.ods': 'odf',
    }
    
    if ext == '.csv':
        return pd.read_csv(file_path)
        
    engine = engines.get(ext, None)
    return pd.read_excel(file_path, engine=engine, header=None)

def extract_data_with_mapping(df, col_mapping, file_type):
    if df.empty:
        raise ValueError(f"File [{file_type}] không có dữ liệu.")
        
    df_cleaned = df.dropna(how='all').reset_index(drop=True)
    
    if df_cleaned.empty:
        raise ValueError(f"File [{file_type}] chỉ toàn các dòng rỗng.")

    best_mapping = {}
    max_header_row = -1

    # Quét DỌC từng cột để tìm tên cột (Hỗ trợ cấu trúc Header 2-3 dòng của file Kế toán)
    for std_col, possible_names in col_mapping.items():
        norm_possible = [normalize_text(n) for n in possible_names]
        found = False
        
        for col_idx in range(df_cleaned.shape[1]):
            if col_idx in best_mapping.values():
                continue # Cột này đã map vào trường khác, bỏ qua
                
            # Quét 20 dòng đầu của cột này
            for row_idx in range(min(20, df_cleaned.shape[0])):
                val = df_cleaned.iloc[row_idx, col_idx]
                if pd.isna(val) or str(val).strip() == '':
                    continue
                    
                norm_val = normalize_text(str(val))
                
                # Ưu tiên match chính xác trước, nếu không thì match chứa (in)
                if any(pn == norm_val for pn in norm_possible if pn) or any(pn in norm_val for pn in norm_possible if pn):
                    best_mapping[std_col] = col_idx
                    max_header_row = max(max_header_row, row_idx) # Đẩy dòng bắt đầu dữ liệu xuống dưới cùng
                    found = True
                    break 
                    
            if found:
                break 

    if 'date' not in best_mapping or 'description' not in best_mapping:
        debug_info = df_cleaned.head(10).to_string()
        raise ValueError(f"Không xác định được cột ở file [{file_type}].\nMapping tìm được: {best_mapping}\n\nDữ liệu 10 dòng đầu:\n{debug_info}")

    # Dữ liệu thật sự bắt đầu ngay dưới dòng header thấp nhất được tìm thấy
    data_rows = df_cleaned.iloc[max_header_row + 1:].copy()
    result_df = pd.DataFrame()
    
    for std_col in col_mapping.keys():
        if std_col in best_mapping:
            result_df[std_col] = data_rows.iloc[:, best_mapping[std_col]]
        else:
            if std_col in ['debit', 'credit']:
                result_df[std_col] = 0.0
            else:
                result_df[std_col] = ""

    result_df['debit'] = result_df['debit'].apply(extract_amount)
    result_df['credit'] = result_df['credit'].apply(extract_amount)
    result_df['amount'] = result_df.apply(lambda x: x['credit'] if x['credit'] > 0 else x['debit'], axis=1)
    
    result_df['norm_desc'] = result_df['description'].apply(normalize_text)
    result_df['first10'] = result_df['norm_desc'].apply(get_first10)
    
    # Hàm loại bỏ các dòng siêu dữ liệu kế toán (Dư đầu, Dư cuối, Tổng cộng)
    def is_valid_transaction(desc):
        if pd.isna(desc): return False
        d = str(desc).lower().strip()
        if not d: return False
        if 'dư đầu' in d or 'dư cuối' in d or 'tổng cộng' in d or 'cộng phát sinh' in d:
            return False
        return True

    # Lọc dữ liệu hợp lệ
    result_df = result_df[
        (result_df['amount'] > 0) & 
        (result_df['description'].apply(is_valid_transaction))
    ].copy()
    
    result_df['id'] = range(1, len(result_df) + 1)
    
    return result_df

def read_bank_file(file_path):
    df = read_smart_excel(file_path)
    col_mapping = {
        'date': ['ngày giao dịch', 'ngày hạch toán', 'ngày', 'transaction date', 'accounting date'],
        'description': ['mô tả giao dịch', 'mô tả', 'nội dung', 'diễn giải', 'transaction description', 'details'],
        'debit': ['số tiền ghi nợ', 'phát sinh nợ', 'nợ', 'debit'],
        'credit': ['số tiền ghi có', 'phát sinh có', 'có', 'credit']
    }
    standard_df = extract_data_with_mapping(df, col_mapping, "NGÂN HÀNG")
    standard_df['direction'] = standard_df.apply(lambda x: 1 if x['credit'] > 0 else -1, axis=1)
    return standard_df

def read_accounting_file(file_path):
    df = read_smart_excel(file_path)
    col_mapping = {
        'date': ['ngày chứng từ', 'ngày hạch toán', 'ngày', 'date'],
        'description': ['diễn giải', 'nội dung', 'mô tả', 'description'],
        'debit': ['phát sinh nợ', 'nợ', 'debit'],
        'credit': ['phát sinh có', 'có', 'credit']
    }
    standard_df = extract_data_with_mapping(df, col_mapping, "KẾ TOÁN")
    standard_df['direction'] = standard_df.apply(lambda x: 1 if x['debit'] > 0 else -1, axis=1)
    return standard_df