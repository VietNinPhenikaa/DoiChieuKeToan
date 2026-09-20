from collections import defaultdict
from itertools import combinations
from rapidfuzz import fuzz

def build_indices(df, prefix):
    # Index bằng lượng tiền và hướng dòng tiền
    idx_amt = defaultdict(list)
    idx_first10 = defaultdict(list)
    
    for _, row in df.iterrows():
        r_dict = row.to_dict()
        r_dict['_type'] = prefix
        
        amt_dir_key = (r_dict['amount'], r_dict['direction'])
        idx_amt[amt_dir_key].append(r_dict)
        
        f10_dir_key = (r_dict['first10'], r_dict['direction'])
        idx_first10[f10_dir_key].append(r_dict)
        
    return idx_amt, idx_first10

def find_subset_combinations(items, target_sum, max_len=4):
    valid_combos = []
    for r in range(1, min(max_len + 1, len(items) + 1)):
        for combo in combinations(items, r):
            if abs(sum(x['amount'] for x in combo) - target_sum) < 1.0:
                valid_combos.append(list(combo))
    return valid_combos

def check_group_match(bank_group, acc_group):
    # Trọng số match dựa trên First10 hoặc mô tả
    b_text = " ".join([x['norm_desc'] for x in bank_group])
    a_text = " ".join([x['norm_desc'] for x in acc_group])
    
    b_first10s = set([x['first10'] for x in bank_group])
    a_first10s = set([x['first10'] for x in acc_group])
    
    if b_first10s & a_first10s: 
        return True # Khớp tín hiệu mạnh
        
    if fuzz.token_set_ratio(b_text, a_text) > 70:
        return True
        
    return False

def match_transactions(df_bank, df_acc):
    matched_groups = []
    
    # 1. Chuyển thành list dict và theo dõi matched
    banks = df_bank.to_dict('records')
    accs = df_acc.to_dict('records')
    
    matched_bank_ids = set()
    matched_acc_ids = set()
    
    def add_match(b_items, a_items, match_type):
        for b in b_items: matched_bank_ids.add(b['id'])
        for a in a_items: matched_acc_ids.add(a['id'])
        matched_groups.append({
            'bank': b_items,
            'acc': a_items,
            'type': match_type
        })

    # === BƯỚC 1: EXACT MATCH 1-1 (Nhanh nhất) ===
    # Gom nhóm theo Amount + Direction + First10
    idx_acc_exact = defaultdict(list)
    for a in accs:
        idx_acc_exact[(a['amount'], a['direction'], a['first10'])].append(a)
        
    for b in banks:
        key = (b['amount'], b['direction'], b['first10'])
        candidates = [a for a in idx_acc_exact[key] if a['id'] not in matched_acc_ids]
        if candidates:
            c = candidates[0]
            add_match([b], [c], "Khớp 1-1")

    # === BƯỚC 2: FUZZY 1-1 (Dựa trên Số tiền + Hướng, xét token) ===
    idx_acc_amt = defaultdict(list)
    for a in accs:
        if a['id'] not in matched_acc_ids:
            idx_acc_amt[(a['amount'], a['direction'])].append(a)
            
    for b in banks:
        if b['id'] in matched_bank_ids: continue
        key = (b['amount'], b['direction'])
        candidates = [a for a in idx_acc_amt[key] if a['id'] not in matched_acc_ids]
        
        best_candidate = None
        best_score = 0
        for c in candidates:
            score = fuzz.token_set_ratio(b['norm_desc'], c['norm_desc'])
            if score > 75 and score > best_score:
                best_score = score
                best_candidate = c
                
        if best_candidate:
            add_match([b], [best_candidate], "Khớp 1-1 (Tương đồng diễn giải)")

    # === BƯỚC 3: GROUP MATCHING N-M (Giới hạn tối đa 4 dòng) ===
    # Nhóm các dòng chưa match theo First10 và Direction
    idx_b_first10 = defaultdict(list)
    idx_a_first10 = defaultdict(list)
    
    for b in banks:
        if b['id'] not in matched_bank_ids:
            idx_b_first10[(b['first10'], b['direction'])].append(b)
    for a in accs:
        if a['id'] not in matched_acc_ids:
            idx_a_first10[(a['first10'], a['direction'])].append(a)
            
    for key, b_list in idx_b_first10.items():
        a_list = idx_a_first10.get(key, [])
        if not a_list: continue
        
        # Thử vét cạn tổ hợp nhỏ trong nhóm có chung First10
        for i in range(1, min(5, len(b_list) + 1)):
            for b_combo in combinations([x for x in b_list if x['id'] not in matched_bank_ids], i):
                target_sum = sum(x['amount'] for x in b_combo)
                a_avail = [x for x in a_list if x['id'] not in matched_acc_ids]
                a_combos = find_subset_combinations(a_avail, target_sum, max_len=4)
                
                if a_combos:
                    best_a_combo = a_combos[0]
                    add_match(b_combo, best_a_combo, f"Khớp {len(b_combo)}-{len(best_a_combo)}")

    # Trả về kết quả
    unmatched_bank = [b for b in banks if b['id'] not in matched_bank_ids]
    unmatched_acc = [a for a in accs if a['id'] not in matched_acc_ids]
    
    return matched_groups, unmatched_bank, unmatched_acc