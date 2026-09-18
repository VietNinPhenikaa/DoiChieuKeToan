from rapidfuzz import fuzz
from datetime import timedelta

def compare_strings(s1, s2):
    return fuzz.token_sort_ratio(s1, s2)

def match_transactions(bank_records, acc_records):
    results = []
    
    # TẦNG 1 & 2: Ghép chính xác và Ghép mờ (Cùng ngày, Cùng số tiền, Cùng chiều)
    for b in bank_records:
        if b['matched']: continue
        
        candidates = []
        for a in acc_records:
            if not a['matched'] and b['date'] == a['date'] and b['amount'] == a['amount'] and b['tx_type'] == a['tx_type']:
                score = compare_strings(b['desc'], a['desc'])
                candidates.append((score, a))
                
        if candidates:
            # Sắp xếp ứng viên theo điểm nội dung giảm dần
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_acc = candidates[0]
            
            if best_score > 60: # Chấp nhận tương đồng trên 60%
                b['matched'] = True
                best_acc['matched'] = True
                status = 'ĐÚNG'
                results.append(create_result_row(status, b, best_acc, best_score))
                continue
                
    # TẦNG 3: Nhầm NỢ/CÓ (Cùng ngày, Cùng số tiền, NGƯỢC chiều)
    for b in bank_records:
        if b['matched']: continue
        for a in acc_records:
            if not a['matched'] and b['date'] == a['date'] and b['amount'] == a['amount'] and b['tx_type'] != a['tx_type']:
                score = compare_strings(b['desc'], a['desc'])
                if score > 75: # Yêu cầu điểm cao hơn vì sai chiều
                    b['matched'] = True
                    a['matched'] = True
                    results.append(create_result_row('NHẦM NỢ/CÓ', b, a, score, 'Số tiền và nội dung giống nhưng ghi sai chiều NỢ/CÓ'))
                    break

    # TẦNG 4: Lệch ngày (Lệch tối đa 2 ngày, Cùng tiền, Cùng chiều)
    for b in bank_records:
        if b['matched']: continue
        for a in acc_records:
            if not a['matched'] and b['amount'] == a['amount'] and b['tx_type'] == a['tx_type']:
                day_diff = abs((b['date'] - a['date']).days)
                if 1 <= day_diff <= 2:
                    score = compare_strings(b['desc'], a['desc'])
                    if score > 75:
                        b['matched'] = True
                        a['matched'] = True
                        results.append(create_result_row('LỆCH NGÀY', b, a, score, f'Lệch {day_diff} ngày'))
                        break

    # TẦNG 5: Sai số tiền (Cùng ngày, Cùng chiều, Nội dung rất giống, Khác tiền)
    for b in bank_records:
        if b['matched']: continue
        for a in acc_records:
            if not a['matched'] and b['date'] == a['date'] and b['tx_type'] == a['tx_type']:
                score = compare_strings(b['desc'], a['desc'])
                if score > 85: # Nội dung gần như giống hệt
                    b['matched'] = True
                    a['matched'] = True
                    diff = abs(b['amount'] - a['amount'])
                    results.append(create_result_row('SAI SỐ TIỀN', b, a, score, f'Chênh lệch {diff:,.0f}'))
                    break

    # XỬ LÝ PHẦN CÒN LẠI (Thiếu, Dư, Trùng)
    matched_acc_amounts_dates = [(a['date'], a['amount']) for a in acc_records if a['matched']]
    
    for b in bank_records:
        if not b['matched']:
            results.append(create_result_row('NHẬP THIẾU', b, None, 0, 'Sổ phụ có nhưng file kế toán không có'))
            
    for a in acc_records:
        if not a['matched']:
            # Kiểm tra xem giao dịch dư này có phải là do nhập trùng 2 lần trong file kế toán không
            if (a['date'], a['amount']) in matched_acc_amounts_dates:
                results.append(create_result_row('NHẬP TRÙNG', None, a, 0, 'Giao dịch này bị nhập nhiều lần trong file kế toán'))
            else:
                results.append(create_result_row('NHẬP DƯ', None, a, 0, 'File kế toán có nhưng sổ phụ ngân hàng không có'))
                
    return results

def create_result_row(status, bank, acc, score=0, note=""):
    return {
        'status': status,
        'b_row': bank['row'] if bank else '',
        'a_row': acc['row'] if acc else '',
        'b_date': bank['date'].strftime('%d/%m/%Y') if bank else '',
        'a_date': acc['date'].strftime('%d/%m/%Y') if acc else '',
        'b_ref': bank['ref'] if bank else '',
        'a_ref': acc['ref'] if acc else '',
        'b_desc': bank['desc'] if bank else '',
        'a_desc': acc['desc'] if acc else '',
        'b_debit': bank['debit'] if bank else 0,
        'b_credit': bank['credit'] if bank else 0,
        'a_debit': acc['debit'] if acc else 0,
        'a_credit': acc['credit'] if acc else 0,
        'diff': abs((bank['amount'] if bank else 0) - (acc['amount'] if acc else 0)),
        'score': round(score, 1),
        'note': note
    }