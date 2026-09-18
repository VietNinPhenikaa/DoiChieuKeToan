import pandas as pd
from services.normalizer import clean_string, parse_date, parse_amount

def identify_header_and_columns(df):
    # Bộ từ khóa cốt lõi để xác định dòng tiêu đề của bảng
    keywords_count = {
        'date': ['ngày', 'date', 'thời gian'],
        'desc': ['diễn giải', 'nội dung', 'mô tả', 'transaction description'],
        'debit': ['nợ', 'debit', 'phát sinh nợ'],
        'credit': ['có', 'credit', 'phát sinh có']
    }
    
    best_row_idx = 0
    max_score = 0
    
    # 1. Trượt qua 35 dòng đầu tiên, ghép 2 dòng liên tiếp để tìm chính xác dòng tiêu đề thật
    for i in range(min(35, len(df))):
        row_str = ' '.join([str(x).lower() for x in df.iloc[i].values if pd.notna(x)])
        next_row_str = ' '.join([str(x).lower() for x in df.iloc[i+1].values if pd.notna(x)]) if i+1 < len(df) else ''
        combined_str = row_str + ' ' + next_row_str
        
        # Chấm điểm xem dòng này giống dòng tiêu đề bao nhiêu phần trăm
        score = sum(any(kw in combined_str for kw in kws) for kws in keywords_count.values())
        if score > max_score:
            max_score = score
            best_row_idx = i
            
    # 2. Lấy 2 dòng tiêu đề ghép lại thành tên cột hoàn chỉnh
    row1 = df.iloc[best_row_idx].fillna('')
    row2 = df.iloc[best_row_idx+1].fillna('') if best_row_idx+1 < len(df) else pd.Series(['']*len(df.columns))
    col_names = [(str(row1.iloc[i]) + ' ' + str(row2.iloc[i])).strip().lower() for i in range(len(df.columns))]
    
    mapping = {'date': None, 'desc': None, 'debit': None, 'credit': None, 'ref': None}
    
    # Từ khóa chi tiết để nhận diện từng cột
    kw_map = {
        'date': ['ngày', 'date', 'thời gian'],
        'desc': ['diễn giải', 'nội dung', 'mô tả', 'chi tiết', 'transaction description'],
        'debit': ['phát sinh nợ', 'nợ', 'debit', 'ghi nợ'],
        'credit': ['phát sinh có', 'có', 'credit', 'ghi có'],
        'ref': ['số chứng từ', 'số giao dịch', 'mã giao dịch', 'số ct', 'transaction number', 'chứng từ', 'số']
    }
    
    # 3. Gắn cột tương ứng (Bỏ qua các cột chứa từ khóa gây nhiễu như 'số dư', 'tổng')
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
    # Đọc file thô không lấy header mặc định
    df = pd.read_excel(filepath, header=None) 
    
    # Kích hoạt quét thông minh
    header_idx, mapping = identify_header_and_columns(df)
    
    if not all([mapping['date'], mapping['desc'], mapping['debit'], mapping['credit']]):
        raise ValueError(f"Không thể tự động nhận diện các cột. Vui lòng kiểm tra lại định dạng file.")
        
    records = []
    # Bỏ qua tất cả các dòng rác ở trên và các dòng chứa header (Bắt đầu lấy data thật)
    start_row = header_idx + 2
    
    for idx in range(start_row, len(df)):
        row = df.iloc[idx]
        row_num = idx + 1 # Giữ số dòng gốc Excel để báo lỗi
        
        # Nếu cột ngày trống => Bỏ qua (thường là dòng tổng kết cuối trang)
        date_val = parse_date(row[mapping['date']])
        if date_val is None: continue 
        
        desc_val = clean_string(row[mapping['desc']])
        debit_val = parse_amount(row[mapping['debit']])
        credit_val = parse_amount(row[mapping['credit']])
        ref_val = str(row[mapping['ref']]) if mapping['ref'] and not pd.isna(row[mapping['ref']]) else ""
        
        # Nếu cả Nợ và Có đều bằng 0 => Bỏ qua
        if debit_val == 0 and credit_val == 0: continue
        
        amount = max(debit_val, credit_val)
        
        # Phân loại IN/OUT theo đúng nguyên tắc kế toán
        if is_bank:
            tx_type = 'IN' if credit_val > 0 else 'OUT'
        else:
            tx_type = 'IN' if debit_val > 0 else 'OUT'
            
        records.append({
            'row': row_num,
            'date': date_val,
            'desc': desc_val,
            'debit': debit_val,
            'credit': credit_val,
            'ref': ref_val,
            'amount': amount,
            'tx_type': tx_type,
            'matched': False,
            'raw_row': row.to_dict()
        })
    return records