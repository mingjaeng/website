import pandas as pd
import os
import json

# 경로 설정
csv_folder = r"C:\Users\yt\Desktop\asdasd-main\capstone_app\static\data_all\재무제표"
json_base_folder = r"C:\Users\yt\Desktop\asdasd-main\capstone_app\static\data_all\재무제표_json"

year_targets = ['2024', '2023', '2022']

for root, _, files in os.walk(csv_folder):
    for file in files:
        if file.endswith(".csv"):
            csv_path = os.path.join(root, file)

            try:
                df = pd.read_csv(csv_path, encoding='utf-8')
            except UnicodeDecodeError:
                df = pd.read_csv(csv_path, encoding='cp949')

            df.columns = [str(col) for col in df.columns]
            year_cols = [col for col in df.columns if any(y in col for y in year_targets)]
            df = df.replace({pd.NA: '--', float('nan'): '--', None: '--'}).fillna('--')

            result = {}
            for _, row in df.iterrows():
                try:
                    label = str(row[1]).strip()
                    result[label] = {
                        year: str(row[col]).strip()
                        for year in year_targets
                        for col in year_cols
                        if year in col
                    }
                except:
                    continue

            # ✅ 기업명 추출 (파일명 앞부분 사용: 예 "고려제강_재무상태표.csv" → "고려제강")
            company_name = file.split("_")[0]

            # ✅ 기업명 폴더 경로 생성
            company_folder = os.path.join(json_base_folder, company_name)
            os.makedirs(company_folder, exist_ok=True)

            # ✅ JSON 저장
            json_filename = os.path.splitext(file)[0] + ".json"
            json_path = os.path.join(company_folder, json_filename)

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"✅ {company_name} → {json_filename} 저장 완료")
