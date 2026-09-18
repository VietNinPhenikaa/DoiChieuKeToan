import itertools
from rapidfuzz import fuzz

def compare_strings(s1, s2):
    return fuzz.token_sort_ratio(s1, s2)

def match_transactions(bank_records, acc_records):
    results = []
    
    # TẦNG 1: Ghép chính xác 1-1 (Cùng ngày, cùng số tiền, cùng chiều)
    for b in bank_records:
        if b['matched']: continue
        
        candidates = []
        for a in acc_records:
            if not a['matched'] and b['date'] == a['date'] and b['amount'] == a['amount'] and b['tx_type'] == a['tx_type']:
                score = compare_strings(b['desc'], a['desc'])
                candidates.append((score, a))
                
        if candidates:
            # Nếu trong ngày chỉ có DUY NHẤT 1 giao dịch cùng số tiền -> Ghép luôn không cần xét điểm chữ
            if len(candidates) == 1:
                best_score, best_acc = candidates[0]
                b['matched'] = True
                best_acc['matched'] = True
                results.append(create_result_row('ĐÚNG', b, best_acc, best_score))
            else:
                # Nếu có nhiều giao dịch trùng tiền -> Lấy cái có nội dung giống nhất
                candidates.sort(key=lambda x: x[0], reverse=True)
                best_score, best_acc = candidates[0]
                if best_score > 60: 
                    b['matched'] = True
                    best_acc['matched'] = True
                    results.append(create_result_row('ĐÚNG', b, best_acc, best_score))
                    
    # =====================================================================
    # TẦNG 2 (MỚI): GHÉP GỘP (1 dòng Sổ phụ = Nhiều dòng Kế toán cộng lại)
    # =====================================================================
    for b in bank_records:
        if b['matched']: continue
        
        # Lọc ra các dòng Kế toán chưa ghép, cùng ngày, cùng chiều Nợ/Có
        candidates = [a for a in acc_records if not a['matched'] and a['date'] == b['date'] and a['tx_type'] == b['tx_type']]
        if not candidates: continue
        
        matched_combo = None
        # Thử tổ hợp ghép từ 2 đến tối đa 5 dòng Kế toán lại với nhau
        for r in range(2, min(6, len(candidates) + 1)):
            for combo in itertools.combinations(candidates, r):
                if sum(item['amount'] for item in combo) == b['amount']:
                    matched_combo = combo
                    break # Khớp phát là dừng ngay
            if matched_combo: break
            
        if matched_combo:
            b['matched'] = True
            for a in matched_combo: 
                a['matched'] = True
            
            # Gộp thông tin các dòng kế toán lại để xuất ra Excel cho đẹp
            combo_rows = ", ".join([str(a['row']) for a in matched_combo])
            combo_desc = " + ".join([f"[{a['amount']:,.0f}] {a['desc']}" for a in matched_combo])
            
            # Tạo một bản ghi Kế toán "ảo" (là tổng hợp của các dòng)
            virtual_acc = {
                'row': combo_rows, # Sẽ hiển thị dạng "Dòng 12, 13, 15"
                'date': matched_combo[0]['date'],
                'ref': ', '.join([a['ref'] for a in matched_combo if a['ref']]),
                'desc': combo_desc, # Sẽ hiển thị "[5tr] Mua hàng + [5tr] Đặt cọc"
                'debit': sum([a['debit'] for a in matched_combo]),
                'credit': sum([a['credit'] for a in matched_combo]),
                'amount': sum([a['amount'] for a in matched_combo]),
                'tx_type': matched_combo[0]['tx_type']
            }
            
            # Đánh dấu trạng thái là ĐÚNG, nhưng ghi chú rõ là do Ghép gộp
            results.append(create_result_row('ĐÚNG', b, virtual_acc, 100, f'GHÉP GỘP: 1 dòng Sổ phụ khớp tổng {len(matched_combo)} dòng Kế toán'))

    # TẦNG 3: Nhầm NỢ/CÓ (Cùng ngày, Cùng số tiền, NGƯỢC chiều)
    for b in bank_records:
        if b['matched']: continue
        for a in acc_records:
            if not a['matched'] and b['date'] == a['date'] and b['amount'] == a['amount'] and b['tx_type'] != a['tx_type']:
                score = compare_strings(b['desc'], a['desc'])
                if score > 75: 
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
                if score > 85: 
                    b['matched'] = True
                    a['matched'] = True
                    diff = abs(b['amount'] - a['amount'])
                    results.append(create_result_row('SAI SỐ TIỀN', b, a, score, f'Chênh lệch {diff:,.0f}'))
                    break

    # TẦNG 6: Nhập dư, thiếu, trùng
    matched_acc_amounts_dates = [(a['date'], a['amount']) for a in acc_records if a['matched']]
    
    for b in bank_records:
        if not b['matched']:
            results.append(create_result_row('NHẬP THIẾU', b, None, 0, 'Sổ phụ có nhưng file kế toán không có'))
            
    for a in acc_records:
        if not a['matched']:
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