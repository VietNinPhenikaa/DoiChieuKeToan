import itertools
from rapidfuzz import fuzz

def compare_strings(s1, s2):
    if not s1 and not s2: return 100
    if not s1 or not s2: return 0
    # So sánh độ tương đồng của 2 chuỗi văn bản (Bỏ qua hoa thường, thứ tự từ)
    return fuzz.token_sort_ratio(str(s1).lower(), str(s2).lower())

def match_transactions(bank_records, acc_records):
    results = []
    
    # =================================================================
    # TẦNG 1: GHÉP CHÍNH XÁC 1-1 (Cùng ngày, cùng tiền, cùng chiều)
    # =================================================================
    for b in bank_records:
        if b['matched']: continue
        candidates = []
        for a in acc_records:
            if not a['matched'] and b['date'] == a['date'] and b['amount'] == a['amount'] and b['tx_type'] == a['tx_type']:
                score = compare_strings(b['desc'], a['desc'])
                candidates.append((score, a))
        
        if candidates:
            # Ưu tiên ứng viên có nội dung giống nhất
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_acc = candidates[0]
            # Nếu điểm tương đồng > 50 hoặc là ứng viên duy nhất trong ngày
            if best_score > 50 or len(candidates) == 1:
                b['matched'] = True
                best_acc['matched'] = True
                results.append(create_result_row('ĐÚNG', b, best_acc, best_score, 'Khớp 1-1 chính xác'))
                
    # =================================================================
    # TẦNG 2 (NÂNG CẤP): GHÉP GỘP 1-N (1 dòng Sổ phụ = Nhiều dòng KT)
    # Tự động quét tổ hợp, chấm điểm diễn giải để chống ghép bậy
    # =================================================================
    for b in bank_records:
        if b['matched']: continue
        
        # Chỉ lấy các dòng KT chưa ghép, cùng ngày, cùng chiều Nợ/Có
        candidates = [a for a in acc_records if not a['matched'] and a['date'] == b['date'] and a['tx_type'] == b['tx_type']]
        if not candidates: continue
        
        valid_combos = []
        # Thử ghép từ 2 đến tối đa 5 dòng KT lại với nhau
        for r in range(2, min(6, len(candidates) + 1)):
            for combo in itertools.combinations(candidates, r):
                if sum(item['amount'] for item in combo) == b['amount']:
                    # Tính điểm trung bình diễn giải của các dòng con so với Sổ phụ
                    avg_score = sum(compare_strings(b['desc'], item['desc']) for item in combo) / r
                    valid_combos.append((avg_score, combo))
                    
        if valid_combos:
            # Sắp xếp các tổ hợp khớp tiền, CHỌN TỔ HỢP CÓ NỘI DUNG GIỐNG SỔ PHỤ NHẤT
            valid_combos.sort(key=lambda x: x[0], reverse=True)
            best_score, matched_combo = valid_combos[0]
            
            b['matched'] = True
            for a in matched_combo: 
                a['matched'] = True
            
            # Gộp thông tin các dòng kế toán lại để xuất ra Excel cho rõ ràng
            combo_rows = ", ".join([str(a['row']) for a in matched_combo])
            combo_desc = " + ".join([f"[{a['amount']:,.0f}] {a['desc']}" for a in matched_combo])
            
            virtual_acc = {
                'row': combo_rows, # Xuất ra ví dụ: Dòng 12, 13, 14
                'date': matched_combo[0]['date'],
                'ref': ', '.join([a['ref'] for a in matched_combo if a['ref']]),
                'desc': combo_desc, # Xuất ra ví dụ: [5tr] Mua hàng + [5tr] Đặt cọc
                'debit': sum([a['debit'] for a in matched_combo]),
                'credit': sum([a['credit'] for a in matched_combo]),
                'amount': sum([a['amount'] for a in matched_combo]),
                'tx_type': matched_combo[0]['tx_type']
            }
            
            results.append(create_result_row('ĐÚNG', b, virtual_acc, best_score, f'GHÉP GỘP CỰC CHUẨN: 1 dòng Sổ phụ = {len(matched_combo)} dòng Kế toán (Dòng gốc: {combo_rows})'))

    # =================================================================
    # TẦNG 3: NHẦM NỢ/CÓ (Sai chiều)
    # =================================================================
    for b in bank_records:
        if b['matched']: continue
        for a in acc_records:
            if not a['matched'] and b['date'] == a['date'] and b['amount'] == a['amount'] and b['tx_type'] != a['tx_type']:
                score = compare_strings(b['desc'], a['desc'])
                if score > 70: 
                    b['matched'] = True
                    a['matched'] = True
                    results.append(create_result_row('NHẦM NỢ/CÓ', b, a, score, 'Số tiền và nội dung giống nhưng ghi sai chiều NỢ/CÓ'))
                    break

    # =================================================================
    # TẦNG 4: LỆCH NGÀY (Lệch tối đa 3 ngày, Cùng tiền, Cùng chiều)
    # =================================================================
    for b in bank_records:
        if b['matched']: continue
        candidates = []
        for a in acc_records:
            if not a['matched'] and b['amount'] == a['amount'] and b['tx_type'] == a['tx_type']:
                day_diff = abs((b['date'] - a['date']).days)
                if 1 <= day_diff <= 3:
                    score = compare_strings(b['desc'], a['desc'])
                    candidates.append((score, a, day_diff))
                    
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_acc, day_diff = candidates[0]
            # Chỉ nhận lệch ngày nếu nội dung giống trên 60%
            if best_score > 60:
                b['matched'] = True
                best_acc['matched'] = True
                results.append(create_result_row('LỆCH NGÀY', b, best_acc, best_score, f'Nghi ngờ chung giao dịch nhưng lệch {day_diff} ngày'))

    # =================================================================
    # TẦNG 5: SAI LỆCH SỐ TIỀN (Do gõ nhầm phí, sai số lẻ)
    # =================================================================
    for b in bank_records:
        if b['matched']: continue
        for a in acc_records:
            if not a['matched'] and b['date'] == a['date'] and b['tx_type'] == a['tx_type']:
                score = compare_strings(b['desc'], a['desc'])
                # Nội dung phải CỰC KỲ GIỐNG (trên 85%) mới dám kết luận là sai tiền
                if score > 85: 
                    b['matched'] = True
                    a['matched'] = True
                    diff = abs(b['amount'] - a['amount'])
                    results.append(create_result_row('SAI SỐ TIỀN', b, a, score, f'Nội dung rất giống nhưng lệch {diff:,.0f} VNĐ'))
                    break

    # =================================================================
    # TẦNG 6: PHÂN LOẠI DƯ, THIẾU, TRÙNG LẶP
    # =================================================================
    matched_acc_amounts_dates = [(a['date'], a['amount']) for a in acc_records if a['matched']]
    
    for b in bank_records:
        if not b['matched']:
            results.append(create_result_row('NHẬP THIẾU', b, None, 0, 'Sổ phụ có nhưng file kế toán không có (Hoặc lệch ngày/sai tiền quá xa)'))
            
    for a in acc_records:
        if not a['matched']:
            # Kiểm tra xem giao dịch này đã được ghi nhận ĐÚNG trước đó chưa (phòng kế toán copy paste nhầm)
            if (a['date'], a['amount']) in matched_acc_amounts_dates:
                results.append(create_result_row('NHẬP TRÙNG', None, a, 0, 'Giao dịch này nghi ngờ bị kế toán nhập thừa/trùng nhiều lần'))
            else:
                results.append(create_result_row('NHẬP DƯ', None, a, 0, 'Kế toán tự chế thêm giao dịch mà Sổ phụ không có'))
                
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