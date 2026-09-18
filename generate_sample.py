import pandas as pd
from datetime import datetime

# SỔ PHỤ NGÂN HÀNG (Chuẩn)
bank_data = [
    # CÓ (In) -> File kế toán phải là NỢ
    {"Ngày GD": "15/09/2026", "Diễn giải": "CONG TY ABC THANH TOAN", "Nợ": 0, "Có": 5000000, "Mã GD": "FT001"}, # Đúng
    {"Ngày GD": "15/09/2026", "Diễn giải": "CONG TY XYZ THANH TOAN", "Nợ": 0, "Có": 5000000, "Mã GD": "FT002"}, # Sẽ bị nhập thiếu
    {"Ngày GD": "15/09/2026", "Diễn giải": "NGUYEN VAN A CHUYEN TIEN", "Nợ": 0, "Có": 10000000, "Mã GD": "FT003"}, # Đúng
    # NỢ (Out) -> File kế toán phải là CÓ
    {"Ngày GD": "15/09/2026", "Diễn giải": "PHI DICH VU NGAN HANG", "Nợ": 2000000, "Có": 0, "Mã GD": "FT004"}, # Đúng
    {"Ngày GD": "16/09/2026", "Diễn giải": "THANH TOAN TIEN DIEN", "Nợ": 1500000, "Có": 0, "Mã GD": "FT005"}, # Lệch ngày
    {"Ngày GD": "17/09/2026", "Diễn giải": "TRA LUONG THANG 9", "Nợ": 20000000, "Có": 0, "Mã GD": "FT006"}, # Sai tiền
    {"Ngày GD": "18/09/2026", "Diễn giải": "THU TIEN BAN HANG", "Nợ": 0, "Có": 8000000, "Mã GD": "FT007"}, # Nhầm Nợ/Có
    {"Ngày GD": "19/09/2026", "Diễn giải": "PHI SMS", "Nợ": 11000, "Có": 0, "Mã GD": "FT008"}, # Bị trùng bên kế toán
]

# FILE KẾ TOÁN
acc_data = [
    {"Ngày": "15/09/2026", "Nội dung": "Công ty ABC thanh toán HĐ", "Nợ": 5000000, "Có": 0}, # Đúng (Khớp FT001)
    # Cố tình thiếu XYZ 5tr (FT002)
    {"Ngày": "15/09/2026", "Nội dung": "Ông A chuyển khoản", "Nợ": 10000000, "Có": 0}, # Đúng (Khớp FT003)
    {"Ngày": "15/09/2026", "Nội dung": "Phí dịch vụ NH", "Nợ": 0, "Có": 2000000}, # Đúng (Khớp FT004)
    {"Ngày": "17/09/2026", "Nội dung": "Thanh toán tiền điện", "Nợ": 0, "Có": 1500000}, # Lệch ngày so với FT005 (16/09)
    {"Ngày": "17/09/2026", "Nội dung": "Trả lương tháng 9 NV", "Nợ": 0, "Có": 19500000}, # Sai tiền so với FT006 (20tr)
    {"Ngày": "18/09/2026", "Nội dung": "Thu tiền bán hàng", "Nợ": 0, "Có": 8000000}, # Nhầm Nợ/Có (Sổ phụ là Có, lẽ ra KT phải là Nợ, nhưng lại ghi Có)
    {"Ngày": "19/09/2026", "Nội dung": "Phí SMS Banking", "Nợ": 0, "Có": 11000}, # Giao dịch chuẩn cho FT008
    {"Ngày": "19/09/2026", "Nội dung": "Phí SMS Banking (Kế toán lỡ tay nhập 2 lần)", "Nợ": 0, "Có": 11000}, # Nhập trùng
    {"Ngày": "20/09/2026", "Nội dung": "Tiền sếp cho thêm không có trong NH", "Nợ": 500000, "Có": 0} # Nhập dư
]

pd.DataFrame(bank_data).to_excel("Mau_SoPhu.xlsx", index=False)
pd.DataFrame(acc_data).to_excel("Mau_KeToan.xlsx", index=False)
print("Đã tạo xong 2 file: Mau_SoPhu.xlsx và Mau_KeToan.xlsx")