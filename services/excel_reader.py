import pandas as pd
from services.normalizer import clean_string, parse_date, parse_amount

def identify_header_and_columns(df):
    keywords_count = {
        'date': ['ngày', 'date', 'thời gian'],
        'desc': ['diễn giải', 'nội dung', 'mô tả', 'transaction description'],
        'debit': ['nợ', 'debit', 'phát sinh nợ'],
        'credit': ['có', 'credit', 'phát sinh có']
    }
    
    best_row_idx = 0
    max_score = 0
    
    for i in range(min(35, len(df))):
        row_str = ' '.join([str(x).lower() for x in df.iloc[i].values if pd.notna(x)])
        next_row_str = ' '.join([str(x).lower() for x in df.iloc[i+1].values if pd.notna(x)]) if i+1 < len(df) else ''
        combined_str = row_str + ' ' + next_row_str
        
        score = sum(any(kw in combined_str for kw in kws) for kws in keywords_count.values())
        if score > max_score:
            max_score = score
            best_row_idx = i
            
    row1 = df.iloc[best_row_idx].fillna('')
    row2 = df.iloc[best_row_idx+1].fillna('') if best_row_idx+1 < len(df) else pd.Series(['']*len(df.columns))
    col_names = [(str(row1.iloc[i]) + ' ' + str(row2.iloc[i])).strip().lower() for i in range(len(df.columns))]
    
    mapping = {'date': None, 'desc': None, 'debit': None, 'credit': None, 'ref': None}
    kw_map = {
        'date': ['ngày', 'date', 'thời gian'],
        'desc': ['diễn giải', 'nội dung', 'mô tả', 'chi tiết', 'transaction description'],
        'debit': ['phát sinh nợ', 'nợ', 'debit', 'ghi nợ'],
        'credit': ['phát sinh có', 'có', 'credit', 'ghi có'],
        'ref': ['số chứng từ', 'số giao dịch', 'mã giao dịch', 'số ct', 'transaction number', 'chứng từ', 'số']
    }
    
    for key, kws in kw_map.items():
        for kw in kws:
            for i, col_name in enumerate(col_names):
                if any(bad in col_name for bad in ['số dư', 'dư đầu', 'dư cuối', 'tổng']): 
                    continue
                if kw in col_name and mapping[key] is None:
                    mapping[key] = df.columns[i]
                    break
            if mapping[key] is not None: 
                break
    return best_row_idx, mapping

def read_and_normalize(filepath, is_bank=True):
    df = pd.read_excel(filepath, header=None) 
    header_idx, mapping = identify_header_and_columns(df)
    
    if not all([mapping['date'], mapping['desc'], mapping['debit'], mapping['credit']]):
        raise ValueError(f"Không thể tự động nhận diện các cột. Vui lòng kiểm tra lại định dạng file.")
        
    records = []
    start_row = header_idx + 2
    
    for idx in range(start_row, len(df)):
        row = df.iloc[idx]
        row_num = idx + 1 
        
        date_val = parse_date(row[mapping['date']])
        if date_val is None: continue 
        
        # BẢO TỒN NGUYÊN TRẠNG NỘI DUNG GỐC ĐỂ XUẤT EXCEL TÌM KIẾM
        raw_desc = str(row[mapping['desc']]) if pd.notna(row[mapping['desc']]) else ""
        # LÀM SẠCH ĐỂ AI SO SÁNH (Ẩn bên trong)
        desc_val = clean_string(raw_desc)
        
        debit_val = parse_amount(row[mapping['debit']])
        credit_val = parse_amount(row[mapping['credit']])
        ref_val = str(row[mapping['ref']]) if mapping['ref'] and not pd.isna(row[mapping['ref']]) else ""
        
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
            'raw_desc': raw_desc, # LƯU LẠI NỘI DUNG GỐC
            'debit': debit_val,
            'credit': credit_val,
            'ref': ref_val,
            'amount': amount,
            'tx_type': tx_type,
            'matched': False,
            'raw_row': row.to_dict()
        })
    return records