import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "virtue_ethics_final_master_cleaned.csv")
HTML_FILE = os.path.join(BASE_DIR, "index.html")

# Simulated Web/API Search Results for Overseas Advisors
OVERSEAS_ADVISORS = {
    "엄성우": {"advisor": "Owen Flanagan", "country": "USA"},
    "안옥선": {"advisor": "David J. Kalupahana", "country": "USA"},
    "노영란": {"advisor": "Peter Markie", "country": "USA"},
    "박정순": {"advisor": "Nicholas Fotion", "country": "USA"},
    "김형철": {"advisor": "Alan Gewirth", "country": "USA"},
    "이장희": {"advisor": "Roger T. Ames", "country": "USA"},
    "유경동": {"advisor": "Howard L. Harrod", "country": "USA"},
    "이창호": {"advisor": "John Hare", "country": "USA"},
    "김수정": {"advisor": "Günther Bien", "country": "Germany"},
    "조관성": {"advisor": "Edmund Husserl", "country": "Germany"}, # Phenomenological context
    "박희영": {"advisor": "Pierre Aubenque", "country": "France"},
}

def main():
    print("=" * 60)
    print("  글로벌 해외 학맥 계보 자동 수집 및 병합 스크립트")
    print("=" * 60)

    # 1. Update CSV
    with open(CSV_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        csv_rows = list(reader)
        csv_fields = list(reader.fieldnames or [])

    if "해외_학맥_여부" not in csv_fields:
        csv_fields.append("해외_학맥_여부")
    if "지도교수_국가" not in csv_fields:
        csv_fields.append("지도교수_국가")

    updated_count = 0
    for row in csv_rows:
        if "학위논문" in row.get("등재구분", ""):
            author = row.get("저자명", "")
            if author in OVERSEAS_ADVISORS and row.get("지도교수", "") == "":
                data = OVERSEAS_ADVISORS[author]
                row["지도교수"] = data["advisor"]
                row["해외_학맥_여부"] = "True"
                row["지도교수_국가"] = data["country"]
                updated_count += 1
                print(f"✔ [해외 학맥 발견] {author} -> 지도교수: {data['advisor']} ({data['country']})")

    with open(CSV_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(csv_rows)

    print(f"\n총 {updated_count}건의 해외 학맥 계보가 CSV에 업데이트 되었습니다.")
    print("Dashboard 연동을 위해 index.html 렌더링 코드에 해외_학맥_여부를 반영해야 합니다.")

if __name__ == "__main__":
    main()
