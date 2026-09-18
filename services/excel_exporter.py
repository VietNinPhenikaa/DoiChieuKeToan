import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

# Cấu hình màu sắc trạng thái
COLORS = {
    'ĐÚNG': 'C6EFCE', 'NHẬP THIẾU': 'FFC7CE', 'NHẬP DƯ': 'FFEB9C',
    'SAI SỐ TIỀN': 'FF9999', 'NHẦM NỢ/CÓ': 'FFCC99', 
    'LỆCH NGÀY': 'B4C6E7', 'NHẬP TRÙNG': 'E2EFDA'
}

def export_results(results, bank_total, acc_total, output_path):
    wb = Workbook()
    
    df_results = pd.DataFrame(results)
    
    # --- Sheet 1: TỔNG HỢP ---
    ws_summary = wb.active
    ws_summary.title = "TONG_HOP"
    
    summary_data = [
        ["CHỈ TIÊU", "SỐ LƯỢNG", "GIÁ TRỊ TIỀN"],
        ["Tổng GD Sổ phụ", bank_total, ""],
        ["Tổng GD File nhập", acc_total, ""],
        ["GD ĐÚNG", len(df_results[df_results['status'] == 'ĐÚNG']), ""],
        ["GD NHẬP THIẾU", len(df_results[df_results['status'] == 'NHẬP THIẾU']), df_results[df_results['status'] == 'NHẬP THIẾU']['b_credit'].sum() + df_results[df_results['status'] == 'NHẬP THIẾU']['b_debit'].sum()],
        ["GD NHẬP DƯ", len(df_results[df_results['status'] == 'NHẬP DƯ']), df_results[df_results['status'] == 'NHẬP DƯ']['a_credit'].sum() + df_results[df_results['status'] == 'NHẬP DƯ']['a_debit'].sum()],
        ["GD SAI SỐ TIỀN", len(df_results[df_results['status'] == 'SAI SỐ TIỀN']), ""],
        ["GD NHẦM NỢ/CÓ", len(df_results[df_results['status'] == 'NHẦM NỢ/CÓ']), ""],
        ["GD NHẬP TRÙNG", len(df_results[df_results['status'] == 'NHẬP TRÙNG']), ""],
        ["GD LỆCH NGÀY", len(df_results[df_results['status'] == 'LỆCH NGÀY']), ""]
    ]
    
    for row in summary_data:
        ws_summary.append(row)
        
    ws_summary.column_dimensions['A'].width = 25
    ws_summary.column_dimensions['B'].width = 15
    ws_summary.column_dimensions['C'].width = 25
    for cell in ws_summary["1:1"]: cell.font = Font(bold=True)
    
    # --- Function hỗ trợ ghi Sheet ---
    def write_sheet(ws, df_subset):
        headers = ["STT", "Trạng thái", "Dòng SP", "Dòng KT", "Ngày SP", "Ngày KT", 
                   "Mã SP", "Mã KT", "Nội dung Sổ phụ", "Nội dung File KT", 
                   "NỢ (SP)", "CÓ (SP)", "NỢ (KT)", "CÓ (KT)", "Chênh lệch", "Độ giống (%)", "Nhận xét"]
        ws.append(headers)
        
        for idx, row in enumerate(df_subset.itertuples(index=False), 1):
            ws.append((idx, *row))
            
        # Formatting
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        
        # Format Width & Number
        for col in range(1, 18):
            ws.column_dimensions[ws.cell(1, col).column_letter].width = 15
        ws.column_dimensions['I'].width = 40
        ws.column_dimensions['J'].width = 40
        ws.column_dimensions['Q'].width = 30
        
        for row_idx in range(2, ws.max_row + 1):
            status = ws.cell(row=row_idx, column=2).value
            if status in COLORS:
                for col_idx in range(1, 18):
                    ws.cell(row=row_idx, column=col_idx).fill = PatternFill(start_color=COLORS[status], end_color=COLORS[status], fill_type="solid")
            
            # Format tiền (Cột 11 đến 15)
            for col_idx in range(11, 16):
                ws.cell(row=row_idx, column=col_idx).number_format = '#,##0'
                
        for cell in ws["1:1"]: cell.font = Font(bold=True)

    # --- Sheet 2: SAI_LECH ---
    ws_diff = wb.create_sheet("SAI_LECH")
    df_diff = df_results[df_results['status'] != 'ĐÚNG']
    write_sheet(ws_diff, df_diff)

    # --- Sheet 3: DOI_CHIEU_DUNG ---
    ws_correct = wb.create_sheet("DOI_CHIEU_DUNG")
    df_correct = df_results[df_results['status'] == 'ĐÚNG']
    write_sheet(ws_correct, df_correct)

    wb.save(output_path)
    return summary_data