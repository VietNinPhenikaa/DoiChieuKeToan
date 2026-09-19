import itertools
from rapidfuzz import fuzz

def compare_strings(s1, s2):
    if not s1 and not s2: return 100
    if not s1 or not s2: return 0
    return fuzz.token_sort_ratio(str(s1).lower(), str(s2).lower())

def create_virtual_acc(records):
    combo_rows = ", ".join([str(a['row']) for a in records])
    unique_raw_descs = list(dict.fromkeys([a['raw_desc'] for a in records]))
    
    return {
        'row': combo_rows,
        'date': records[0]['date'],
        'ref': ', '.join(set([a['ref'] for a in records if a['ref']])),
        'desc': records[0]['desc'],
        'raw_desc': "\n".join(unique_raw_descs),
        'debit': sum([a['debit'] for a in records]),
        'credit': sum([a['credit'] for a in records]),
        'amount': sum([a['amount'] for a in records]),
        'tx_type': records[0]['tx_type']
    }

def match_transactions(bank_records, acc_records):
    results = []

    # ==========================================
    # TẦNG 1: KHỚP 1-1 (Sai số ngày <= 3, Cùng tiền)
    # ==========================================
    for b in bank_records:
        if b['matched']: continue
        candidates = []
        for a in acc_records:
            if not a['matched'] and b['tx_type'] == a['tx_type'] and b['amount'] == a['amount']:
                day_diff = abs((b['date'] - a['date']).days)
                if day_diff <= 3:
                    score = compare_strings(b['desc'], a['desc'])
                    candidates.append((score, a, day_diff))
        
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_acc, day_diff = candidates[0]
            if best_score >= 50 or len(candidates) == 1:
                b['matched'] = True
                best_acc['matched'] = True
                msg = 'Khớp 1-1 chính xác' if day_diff == 0 else f'Khớp 1-1 (Lệch {day_diff} ngày)'
                results.append(create_result_row('ĐÚNG', b, best_acc, best_score, msg))

    # ==========================================
    # TẦNG 2: GỘP 1-N XUYÊN NGÀY (Lệch <= 3 ngày) - SIÊU TỐC ĐỘ
    # ==========================================
    for b in bank_records:
        if b['matched']: continue
        
        # 1. Tìm ứng viên: Cùng chiều, Lệch <= 3 ngày, Nội dung có nét tương đồng
        candidates_raw = []
        for a in acc_records:
            if not a['matched'] and b['tx_type'] == a['tx_type']:
                day_diff = abs((b['date'] - a['date']).days)
                if day_diff <= 3:
                    score = compare_strings(b['desc'], a['desc'])
                    if score > 55 or (a['ref'] and b['ref'] and a['ref'] == b['ref']):
                        candidates_raw.append((score, a))
                        
        if not candidates_raw: continue
        
        # 2. BỘ LỌC CHỐNG SẬP: Chỉ lấy Top 10 dòng giống nhất để tính tổ hợp
        candidates_raw.sort(key=lambda x: x[0], reverse=True)
        top_candidates = [x[1] for x in candidates_raw[:10]]
        
        # 3. BỘ LỌC CHỐNG CHẠY THỪA: Nếu tổng 10 dòng này < tiền Sổ phụ -> Bỏ qua ngay
        if sum(a['amount'] for a in top_candidates) < b['amount']:
            continue
            
        # 4. Tính chập 2 -> 5 (Dù duyệt qua nhiều ngày vẫn chỉ mất mili-giây)
        valid_combos = []
        for r in range(2, min(6, len(top_candidates) + 1)):
            for combo in itertools.combinations(top_candidates, r):
                if sum(a['amount'] for a in combo) == b['amount']:
                    avg_score = sum(compare_strings(b['desc'], a['desc']) for a in combo) / r
                    valid_combos.append((avg_score, combo))
                    
        if valid_combos:
            valid_combos.sort(key=lambda x: x[0], reverse=True)
            best_score, matched_combo = valid_combos[0]
            
            b['matched'] = True
            for a in matched_combo: a['matched'] = True
            v_acc = create_virtual_acc(matched_combo)
            
            # Ghi chú ĐÚNG và liệt kê rõ những dòng đã ghép
            combo_rows_str = ", ".join([str(a['row']) for a in matched_combo])
            results.append(create_result_row('ĐÚNG', b, v_acc, best_score, f'Gộp {len(matched_combo)} dòng (Dòng kế toán: {combo_rows_str}) => Tổng tiền khớp 100%'))

    # ==========================================
    # TẦNG 3: NHẦM NỢ/CÓ (Lệch <= 3 ngày)
    # ==========================================
    for b in bank_records:
        if b['matched']: continue
        for a in acc_records:
            if not a['matched'] and b['amount'] == a['amount'] and b['tx_type'] != a['tx_type']:
                day_diff = abs((b['date'] - a['date']).days)
                if day_diff <= 3:
                    score = compare_strings(b['desc'], a['desc'])
                    if score >= 60:
                        b['matched'] = True
                        a['matched'] = True
                        results.append(create_result_row('NHẦM NỢ/CÓ', b, a, score, 'Lỗi hạch toán ngược chiều Nợ/Có'))
                        break

    # ==========================================
    # TẦNG 4: SAI SỐ TIỀN (Gộp nhiều dòng bị thiếu/thừa tiền)
    # ==========================================
    for b in bank_records:
        if b['matched']: continue
        
        candidates_raw = []
        for a in acc_records:
            if not a['matched'] and b['tx_type'] == a['tx_type']:
                day_diff = abs((b['date'] - a['date']).days)
                if day_diff <= 3:
                    score = compare_strings(b['desc'], a['desc'])
                    if score >= 75 or (a['ref'] and b['ref'] and a['ref'] == b['ref']):
                        candidates_raw.append(a)
                        
        if candidates_raw:
            b['matched'] = True
            for a in candidates_raw: a['matched'] = True
                
            if len(candidates_raw) == 1:
                a = candidates_raw[0]
                diff = abs(b['amount'] - a['amount'])
                msg = f"Nhập thiếu {diff:,.0f}" if b['amount'] > a['amount'] else f"Nhập thừa {diff:,.0f}"
                results.append(create_result_row('SAI SỐ TIỀN', b, a, compare_strings(b['desc'], a['desc']), msg))
            else:
                v_acc = create_virtual_acc(candidates_raw)
                diff = abs(b['amount'] - v_acc['amount'])
                avg_score = sum(compare_strings(b['desc'], a['desc']) for a in candidates_raw) / len(candidates_raw)
                
                combo_rows_str = ", ".join([str(a['row']) for a in candidates_raw])
                msg = f"Nhập thiếu {diff:,.0f}" if b['amount'] > v_acc['amount'] else f"Nhập thừa {diff:,.0f}"
                msg = f"Gộp {len(candidates_raw)} dòng (Dòng {combo_rows_str}) nhưng vẫn {msg.lower()}"
                
                results.append(create_result_row('SAI SỐ TIỀN', b, v_acc, avg_score, msg))

    # ==========================================
    # TẦNG 5: NHẬP DƯ, NHẬP THIẾU
    # ==========================================
    for b in bank_records:
        if not b['matched']:
            results.append(create_result_row('NHẬP THIẾU', b, None, 0, 'Chưa hạch toán'))
    for a in acc_records:
        if not a['matched']:
            results.append(create_result_row('NHẬP DƯ', None, a, 0, 'Nhập khống / Sai số quá xa'))

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
        'b_desc': bank['raw_desc'] if bank else '',
        'a_desc': acc['raw_desc'] if acc else '',
        'b_debit': bank['debit'] if bank else 0,
        'b_credit': bank['credit'] if bank else 0,
        'a_debit': acc['debit'] if acc else 0,
        'a_credit': acc['credit'] if acc else 0,
        'diff': abs((bank['amount'] if bank else 0) - (acc['amount'] if acc else 0)),
        'score': round(score, 1),
        'note': note
    }