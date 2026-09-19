import pandas as pd
from services.normalizer import clean_string, parse_date, parse_amount

def try_map_columns(col_names):
    mapping = {'date': None, 'desc': None, 'debit': None, 'credit': None, 'ref': None}
    kw_map = {
        'date': ['ngày', 'date', 'thời gian', 'time'],
        'desc': ['diễn giải', 'nội dung', 'mô tả', 'chi tiết', 'description', 'transaction description'],
        'debit': ['ghi nợ', 'phát sinh nợ', 'nợ', 'debit', 'ps nợ'],
        'credit': ['ghi có', 'phát sinh có', 'có', 'credit', 'ps có'],
        'ref': ['số tham chiếu', 'mã giao dịch', 'số giao dịch', 'số chứng từ', 'chứng từ', 'số ct', 'transaction number', 'ref', 'số']
    }
    
    for key, kws in kw_map.items():
        for kw in kws:
            for i, col_name in enumerate(col_names):
                if any(bad in col_name for bad in ['số dư', 'dư đầu', 'dư cuối', 'tổng']): 
                    continue
                if kw in col_name and mapping[key] is None:
                    mapping[key] = i
                    break
            if mapping[key] is not None: 
                break
    
    score = 0
    if mapping['date'] is not None: score += 10
    if mapping['desc'] is not None: score += 10
    if mapping['debit'] is not None: score += 10
    if mapping['credit'] is not None: score += 10
    if mapping['ref'] is not None: score += 5
    return score, mapping

def identify_header_and_columns(df):
    best_score = -1
    best_mapping = None
    best_row_idx = 0 
    
    for i in range(min(35, len(df))):
        # 1. Thử quét dòng đơn lẻ
        row1 = df.iloc[i].fillna('')
        col_names_single = [str(x).strip().lower() for x in row1.values]
        score_single, map_single = try_map_columns(col_names_single)
        if score_single > best_score:
            best_score = score_single
            best_mapping = map_single
            best_row_idx = i
            
        # 2. Thử quét ghép dòng
        if i + 1 < len(df):
            row2 = df.iloc[i+1].fillna('')
            col_names_comb = [(str(row1.iloc[j]) + ' ' + str(row2.iloc[j])).strip().lower() for j in range(len(df.columns))]
            score_comb, map_comb = try_map_columns(col_names_comb)
            
            if score_comb > best_score:
                best_score = score_comb
                best_mapping = map_comb
                best_row_idx = i + 1 
                
    final_mapping = {k: df.columns[v] if v is not None else None for k, v in best_mapping.items()}
    return best_row_idx, final_mapping

def read_excel_robust(filepath):
    try:
        return pd.read_excel(filepath, header=None, engine='xlrd')
    except: pass
        
    try:
        return pd.read_excel(filepath, header=None, engine='openpyxl')
    except: pass
        
    try:
        dfs = pd.read_html(filepath)
        if dfs: return dfs[0]
    except: pass
        
    try:
        return pd.read_excel(filepath, header=None)
    except Exception as e:
        raise ValueError("File hỏng định dạng. Vui lòng mở bằng Excel rồi Save As (.xlsx) để thử lại.")

def read_and_normalize(filepath, is_bank=True):
    df = read_excel_robust(filepath)
    header_idx, mapping = identify_header_and_columns(df)
    
    # ĐÃ SỬA LỖI PYTHON INDEX 0 Ở ĐÂY:
    if None in (mapping['date'], mapping['desc'], mapping['debit'], mapping['credit']):
        raise ValueError(f"Không thể nhận diện các cột cơ bản. Các cột tìm thấy: {mapping}")
        
    records = []
    start_row = header_idx + 1
    
    for idx in range(start_row, len(df)):
        row = df.iloc[idx]
        row_num = idx + 1 
        
        date_val = parse_date(row[mapping['date']])
        if date_val is None: continue 
        
        raw_desc = str(row[mapping['desc']]) if pd.notna(row[mapping['desc']]) else ""
        desc_val = clean_string(raw_desc)
        
        debit_val = parse_amount(row[mapping['debit']])
        credit_val = parse_amount(row[mapping['credit']])
        
        # ĐÃ SỬA LỖI PYTHON INDEX 0 Ở ĐÂY:
        ref_val = str(row[mapping['ref']]) if mapping['ref'] is not None and pd.notna(row[mapping['ref']]) else ""
        
        if debit_val == 0 and credit_val == 0: continue
        
        amount = max(debit_val, credit_val)
        if is_bank:
            tx_type = 'IN' if credit_val > 0 else 'OUT'
        else:
            tx_type = 'IN' if debit_val > 0 else 'OUT'
            
        records.append({
            'row': row_num,
            'date': date_val,
            'desc': desc_val,
            'raw_desc': raw_desc,
            'debit': debit_val,
            'credit': credit_val,
            'ref': ref_val,
            'amount': amount,
            'tx_type': tx_type,
            'matched': False,
            'raw_row': row.to_dict()
        })
    return records