import itertools
from rapidfuzz import fuzz
from collections import defaultdict

def compare_strings(s1, s2):
    if not s1 and not s2: return 100
    if not s1 or not s2: return 0
    return fuzz.token_sort_ratio(str(s1).lower(), str(s2).lower())

def create_virtual_acc(records):
    combo_rows = ", ".join([str(a['row']) for a in records])
    unique_raw_descs = list(dict.fromkeys([a['raw_desc'] for a in records]))
    combo_desc_raw = "\n".join(unique_raw_descs)
    
    return {
        'row': combo_rows,
        'date': records[0]['date'],
        'ref': ', '.join(set([a['ref'] for a in records if a['ref']])),
        'desc': records[0]['desc'],
        'raw_desc': combo_desc_raw,
        'debit': sum([a['debit'] for a in records]),
        'credit': sum([a['credit'] for a in records]),
        'amount': sum([a['amount'] for a in records]),
        'tx_type': records[0]['tx_type']
    }

def match_transactions(bank_records, acc_records):
    results = []
    
    # ĐÁNH CHỈ MỤC TỐC ĐỘ CAO (Giảm thời gian chạy từ 40s xuống 0.1s)
    acc_by_date_type = defaultdict(list)
    acc_by_amount_type = defaultdict(list)
    acc_by_date_rev = defaultdict(list)
    
    for a in acc_records:
        acc_by_date_type[(a['date'], a['tx_type'])].append(a)
        acc_by_amount_type[(a['amount'], a['tx_type'])].append(a)
        rev_type = 'OUT' if a['tx_type'] == 'IN' else 'IN'
        acc_by_date_rev[(a['date'], rev_type)].append(a)

    # ==========================================================
    # TẦNG 1: KHỚP 1-1 (Tra cứu ngăn kéo Date & Type)
    # ==========================================================
    for b in bank_records:
        if b['matched']: continue
        
        # CHỈ lấy những giao dịch kế toán Cùng ngày, Cùng chiều để xét (Cực nhanh)
        candidates_raw = [a for a in acc_by_date_type[(b['date'], b['tx_type'])] if not a['matched'] and a['amount'] == b['amount']]
        if not candidates_raw: continue
        
        candidates = [(compare_strings(b['desc'], a['desc']), a) for a in candidates_raw]
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_acc = candidates[0]
        
        if best_score > 50 or len(candidates) == 1:
            b['matched'] = True
            best_acc['matched'] = True
            results.append(create_result_row('ĐÚNG', b, best_acc, best_score, 'Kế toán nhập chuẩn 100%'))

    # ==========================================================
    # TẦNG 2: GHÉP GỘP ĐÚNG TIỀN (Tra cứu ngăn kéo Date & Type)
    # ==========================================================
    for b in bank_records:
        if b['matched']: continue
        
        candidates_raw = [a for a in acc_by_date_type[(b['date'], b['tx_type'])] if not a['matched']]
        if not candidates_raw: continue
        
        related_accs = []
        for a in candidates_raw:
            score = compare_strings(b['desc'], a['desc'])
            if score > 60 or (a['ref'] and b['ref'] and a['ref'] == b['ref']):
                related_accs.append((score, a))
                
        if not related_accs: continue
        
        related_accs.sort(key=lambda x: x[0], reverse=True)
        top_candidates = [x[1] for x in related_accs[:8]] # Chỉ lấy Top 8 để giới hạn phép tính
        
        if sum(item['amount'] for item in top_candidates) < b['amount']:
            continue
            
        valid_combos = []
        for r in range(2, min(5, len(top_candidates) + 1)):
            for combo in itertools.combinations(top_candidates, r):
                if sum(item['amount'] for item in combo) == b['amount']:
                    avg_score = sum(compare_strings(b['desc'], item['desc']) for item in combo) / r
                    valid_combos.append((avg_score, combo))
                    
        if valid_combos:
            valid_combos.sort(key=lambda x: x[0], reverse=True)
            best_score, matched_combo = valid_combos[0]
            b['matched'] = True
            for a in matched_combo: a['matched'] = True
            virtual_acc = create_virtual_acc(matched_combo)
            combo_rows_str = ", ".join([str(a['row']) for a in matched_combo])
            results.append(create_result_row('ĐÚNG', b, virtual_acc, best_score, f'GỘP {len(matched_combo)} DÒNG KẾ TOÁN (Dòng {combo_rows_str}) => TỔNG TIỀN KHỚP 100%'))

    # ==========================================================
    # TẦNG 3: NHẦM NỢ/CÓ (Tra cứu ngăn kéo Ngược chiều)
    # ==========================================================
    for b in bank_records:
        if b['matched']: continue
        
        candidates_raw = [a for a in acc_by_date_rev[(b['date'], b['tx_type'])] if not a['matched'] and a['amount'] == b['amount']]
        for a in candidates_raw:
            score = compare_strings(b['desc'], a['desc'])
            if score > 75: 
                b['matched'] = True
                a['matched'] = True
                results.append(create_result_row('NHẦM NỢ/CÓ', b, a, score, 'LỖI KẾ TOÁN: Hạch toán ngược chiều Nợ/Có'))
                break

    # ==========================================================
    # TẦNG 4: LỆCH NGÀY (Tra cứu ngăn kéo Số tiền - Đỉnh cao Tối ưu)
    # ==========================================================
    for b in bank_records:
        if b['matched']: continue
        
        # Chỉ quét các dòng kế toán có BẰNG CHÍNH XÁC SỐ TIỀN ĐÓ (Cực nhanh)
        candidates_raw = [a for a in acc_by_amount_type[(b['amount'], b['tx_type'])] if not a['matched']]
        
        candidates = []
        for a in candidates_raw:
            day_diff = abs((b['date'] - a['date']).days)
            if 1 <= day_diff <= 3:
                score = compare_strings(b['desc'], a['desc'])
                candidates.append((score, a, day_diff))
                
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_acc, day_diff = candidates[0]
            if best_score > 60:
                b['matched'] = True
                best_acc['matched'] = True
                results.append(create_result_row('LỆCH NGÀY', b, best_acc, best_score, f'LỖI KẾ TOÁN: Sai ngày (lệch {day_diff} ngày)'))

    # ==========================================================
    # TẦNG 5: SAI SỐ TIỀN & GỘP LỆCH TIỀN
    # ==========================================================
    for b in bank_records:
        if b['matched']: continue
        
        candidates_raw = [a for a in acc_by_date_type[(b['date'], b['tx_type'])] if not a['matched']]
        if not candidates_raw: continue
        
        candidates_records = []
        scored_cands = []
        for a in candidates_raw:
            score = compare_strings(b['desc'], a['desc'])
            if score >= 80 or (a['ref'] and b['ref'] and a['ref'] == b['ref']):
                candidates_records.append(a)
                scored_cands.append(score)
                
        if candidates_records:
            total_acc_amount = sum(a['amount'] for a in candidates_records)
            b['matched'] = True
            for a in candidates_records: a['matched'] = True
                
            if len(candidates_records) == 1:
                a = candidates_records[0]
                diff = abs(b['amount'] - a['amount'])
                status_msg = f"LỖI KẾ TOÁN: Nhập THIẾU {diff:,.0f} VNĐ" if b['amount'] > a['amount'] else f"LỖI KẾ TOÁN: Nhập THỪA {diff:,.0f} VNĐ"
                results.append(create_result_row('SAI SỐ TIỀN', b, a, scored_cands[0], status_msg))
            else:
                virtual_acc = create_virtual_acc(candidates_records)
                diff = abs(b['amount'] - total_acc_amount)
                avg_score = sum(scored_cands) / len(candidates_records)
                combo_rows_str = ", ".join([str(a['row']) for a in candidates_records])
                if b['amount'] > total_acc_amount:
                    msg = f"LỖI KẾ TOÁN: Gộp {len(candidates_records)} dòng kế toán (Dòng {combo_rows_str}) nhưng vẫn THIẾU {diff:,.0f} VNĐ"
                else:
                    msg = f"LỖI KẾ TOÁN: Gộp {len(candidates_records)} dòng kế toán (Dòng {combo_rows_str}) nhưng bị THỪA {diff:,.0f} VNĐ"
                
                results.append(create_result_row('SAI SỐ TIỀN', b, virtual_acc, avg_score, msg))

    # ==========================================================
    # TẦNG 6: NHẬP THIẾU, DƯ, TRÙNG
    # ==========================================================
    matched_acc_amounts_dates = [(a['date'], a['amount']) for a in acc_records if a['matched']]
    
    for b in bank_records:
        if not b['matched']:
            results.append(create_result_row('NHẬP THIẾU', b, None, 0, 'LỖI KẾ TOÁN: Chưa hạch toán giao dịch này'))
            
    for a in acc_records:
        if not a['matched']:
            if (a['date'], a['amount']) in matched_acc_amounts_dates:
                results.append(create_result_row('NHẬP TRÙNG', None, a, 0, 'LỖI KẾ TOÁN: Nhập trùng lặp'))
            else:
                results.append(create_result_row('NHẬP DƯ', None, a, 0, 'LỖI KẾ TOÁN: Nhập khống hoặc sai tiền quá xa'))
                
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