import traceback
from typing import Dict, Any, List, Tuple
from domain_classes import CalcScore, ScoreCardDTO

UNIV_GROUPS = {
    "SKY": ["서울대학교", "고려대학교", "연세대학교"],
    "서성한": ["서강대학교", "성균관대학교", "한양대학교"],
    "중경외시이": ["중앙대학교", "경희대학교", "한국외국어대학교", "서울시립대학교", "이화여자대학교"],
    "건동홍아숙": ["건국대학교", "동국대학교", "홍익대학교", "아주대학교", "숙명여자대학교"],
    "국숭세단인": ["국민대학교", "숭실대학교", "세종대학교", "단국대학교_죽전", "인천대학교"],
    "광명상가": ["광운대학교", "명지대학교", "상명대학교", "가천대학교"],
    "지역거점국립대": ["충남대학교", "충북대학교", "전남대학교", "전북대학교", "강원대학교_춘천", "부산대학교", "경북대학교", "경상국립대학교"],
    "경기인천권": ["가천대학교", "가톨릭대학교", "경기대학교", "단국대학교_죽전", "아주대학교", "을지대학교", "인천대학교", "인하대학교", "한국외국어대학교_글로벌캠퍼스", "한양대학교_에리카"],
    "강원권": ["강원대학교_춘천", "연세대학교_미래"],
    "충청권": ["건국대학교_글로컬", "고려대학교_세종", "단국대학교_천안", "상명대학교_천안", "충남대학교", "충북대학교", "한국교원대학교", "한남대학교", "홍익대학교_세종"],
    "경상권": ["경북대학교", "경상국립대학교", "동국대학교_경주", "국립부경대학교", "부산대학교"],
    "전라권": ["국립목포해양대학교", "전남대학교", "전북대학교"]
}

def load_univ_data_from_cache(score_card: ScoreCardDTO) -> list:
    """캐시된 입결성적 목록에서 대상 대학 학과 필터링 (DB 호출 0건)"""
    cache = score_card.all_db_cache or {}
    raw_depts = cache.get("dept_scores", [])
    
    target_univ = score_card.targetUniv
    jeongsi_year = score_card.jeongsiYear

    filtered = []
    for dept in raw_depts:
        if dept.get("학년도") != jeongsi_year:
            continue
            
        univ_name = dept.get("대학교명")
        if target_univ in UNIV_GROUPS:
            if univ_name in UNIV_GROUPS[target_univ]:
                filtered.append(dept)
        elif target_univ == "모든대학":
            filtered.append(dept)
        elif univ_name == target_univ:
            filtered.append(dept)

    return filtered


def bind_exam_statistics(score_card: ScoreCardDTO, target_scores: CalcScore) -> None:
    """/validate에서 받아온 캐시 데이터를 CalcScore 메모리에 바인딩 (DB 호출 0건)"""
    cache = score_card.all_db_cache or {}
    
    # 1. 모의고사 표점 바인딩
    for row in cache.get("mock_scores", []):
        subj, grd = row.get("과목"), row.get("등급")
        if subj and grd is not None:
            grade = int(grd)
            max_score = float(row.get("표준점수_최고", 0.0))
            target_scores.mock_grd_std_max[(subj, grade)] = max_score
            target_scores.mock_grd_std_min[(subj, int(grd))] = float(row.get("표준점수_최저", 0.0))
            if grade == 1:
                target_scores.mock_std_max[subj] = max_score

    # 2. 수능 표점 바인딩
    for row in cache.get("sat_scores", []):
        subj, grd = row.get("과목"), row.get("등급")
        if subj and grd is not None:
            grade = int(grd)
            max_score = float(row.get("표준점수_최고", 0.0))
            target_scores.sat_grd_std_max[(subj, grade)] = max_score
            target_scores.sat_grd_std_min[(subj, int(grd))] = float(row.get("표준점수_최저", 0.0))
            if grade == 1:
                target_scores.sat_std_max[subj] = max_score

    # 3. 변환표준점수 바인딩
    if not hasattr(target_scores, "converted_scores"):
        target_scores.converted_scores = {}

    for row in cache.get("trans_scores", []):
        univ_key = row.get("대학교명")
        if univ_key:
            target_scores.converted_scores[univ_key] = {
                col: float(val) for col, val in row.items() 
                if col.isdigit() and val is not None
            }


def prepare_department_score(
    target_scores: CalcScore,
    dept_info: dict
) -> dict:
    """학과 1개에 대한 점수 환산 메인 함수 (DB 매개변수 완전 제거)"""
    process_type = dept_info.get("백분위/표준점수/변환표준점수/등급") or "표준점수"

    process_kor_math(target_scores=target_scores, process_type=process_type)
    process_inquiry(target_scores=target_scores, process_type=process_type, dept_info=dept_info)
    process_eng(target_scores=target_scores, dept_info=dept_info)
    process_hist(target_scores=target_scores, dept_info=dept_info)

    if target_scores.univ_name == "서울대학교" and getattr(target_scores, "frn_grd", None) is not None:
        process_frn(target_scores=target_scores, dept_info=dept_info)
    else:
        target_scores.frn_raw = getattr(target_scores, "frn_grd", None) or 0
        target_scores.frn_converted = 0.0
    
    return dept_info


def process_kor_math(target_scores: CalcScore, process_type: str) -> None:
    target_scores.subj_std_max["kor"] = target_scores.sat_grd_std_max.get(("국어", 1), 100.0)
    target_scores.subj_std_max["math"] = target_scores.sat_grd_std_max.get(("수학", 1), 100.0)

    subjects = [
        ("kor", "국어", target_scores.kor_std, target_scores.kor_pct, target_scores.kor_grd),
        ("math", "수학", target_scores.math_std, target_scores.math_pct, target_scores.math_grd),
    ]

    results = {}

    for key_name, subj_name, std_val, pct_val, grade_val in subjects:
        std_v = float(std_val or 0.0)
        pct_v = float(pct_val or 0.0)
        grd_v = int(grade_val or 9)
        
        if process_type in ["표준점수", "변환표준점수"]:
            raw_val = std_v
            max_m = target_scores.mock_grd_std_max.get((subj_name, grd_v))
            min_m = target_scores.mock_grd_std_min.get((subj_name, grd_v))
            max_c = target_scores.sat_grd_std_max.get((subj_name, grd_v))
            min_c = target_scores.sat_grd_std_min.get((subj_name, grd_v))

            if max_m is not None and min_m is not None and max_c is not None and min_c is not None:
                pos = 0.0 if max_m == min_m else (std_v - min_m) / (max_m - min_m)
                pos = max(0.0, min(1.0, pos))
                converted_val = float(round(min_c + pos * (max_c - min_c)))
            else:
                converted_val = raw_val
                
            results[key_name] = (raw_val, converted_val)

        elif process_type == "백분위":
            results[key_name] = (pct_v, pct_v)
        elif process_type == "등급":
            results[key_name] = (float(grd_v), float(grd_v))
        else:
            results[key_name] = (std_v, std_v)

    target_scores.kor_raw, target_scores.kor_converted = results["kor"]
    target_scores.kor_type = process_type
    target_scores.math_raw, target_scores.math_converted = results["math"]
    target_scores.math_type = process_type


def inquiry_lookup_name(jeongsi_year: str, univ_name: str, dept_info: dict, subject_name: str) -> str:
    trans_type = dept_info.get("변환점수적용구분") or ""
    major_name = dept_info.get("학과명") or dept_info.get("모집단위") or ""
    is_science = subject_name.endswith("Ⅰ") or subject_name.endswith("Ⅱ")
    inq_type_str = "과탐" if is_science else "사탐"
    lookup_name = univ_name

    if jeongsi_year == "2024학년도 정시":
        if trans_type:
            if univ_name in ["광운대학교", "한양대학교"]:
                lookup_name = f"{univ_name}-A" if (univ_name == "광운대학교" and trans_type == "B" and not is_science) else f"{univ_name}-{trans_type}"
            elif univ_name in ["동국대학교", "성균관대학교"]:
                lookup_name = f"{univ_name}-{trans_type}-{inq_type_str}" if (trans_type == "C" or univ_name == "성균관대학교") else f"{univ_name}-{trans_type}"
            else:
                lookup_name = f"{univ_name}-{trans_type}"
        else:
            if univ_name in ["경북대학교", "고려대학교", "서울시립대학교", "세종대학교", "아주대학교", "연세대학교_미래", "전북대학교", "고려대학교_세종", "이화여자대학교"]:
                lookup_name = f"{univ_name}-{inq_type_str}"

    elif jeongsi_year == "2025학년도 정시":
        if univ_name in ["고려대학교", "고려대학교_세종", "서울시립대학교", "성균관대학교", "아주대학교", "전북대학교", "경북대학교"]:
            lookup_name = f"{univ_name}-{inq_type_str}"
        elif univ_name == "가톨릭대학교":
            lookup_name = f"{univ_name}-약의" if major_name in ["의예과", "약학과"] else (f"{univ_name}-간호" if major_name == "간호학과" else univ_name)

    elif jeongsi_year == "2026학년도 정시":
        if univ_name in ["서강대학교", "성균관대학교", "중앙대학교"]:
            if trans_type:
                lookup_name = f"{univ_name}-{trans_type}"
        elif univ_name in ["서울시립대학교", "이화여자대학교", "전북대학교"]:
            lookup_name = f"{univ_name}-{inq_type_str}"

    return lookup_name


def process_inquiry(target_scores: CalcScore, process_type: str, dept_info: dict) -> None:
    subjects = [
        ("inq1", target_scores.inq1_detail, target_scores.inq1_std, target_scores.inq1_pct, target_scores.inq1_grd),
        ("inq2", target_scores.inq2_detail, target_scores.inq2_std, target_scores.inq2_pct, target_scores.inq2_grd)
    ]

    results = {}
    jeongsi_year = target_scores.jeongsi_year
    univ_name = dept_info.get("대학교명") or ""

    if jeongsi_year in ["2024학년도 정시", "2025학년도 정시", "2026학년도 정시"] and univ_name == "단국대학교_천안":
        process_type = "백분위"

    for key_name, raw_subj_name, std_val, pct_val, grade_val in subjects:
        std_v = float(std_val or 0.0)
        pct_v = float(pct_val or 0.0)
        grd_v = int(grade_val or 9)
        
        if not raw_subj_name or grade_val is None:
            results[key_name] = (0.0, 0.0)
            continue

        subj_name = raw_subj_name.strip()
        subj_name_altered = subj_name

        if jeongsi_year in ["2024학년도 정시", "2025학년도 정시", "2026학년도 정시", "2027학년도 정시"]:
            if subj_name == "사회탐구":
                subj_name_altered = "사회·문화"
            elif subj_name == "과학탐구":
                subj_name_altered = "지구과학Ⅰ"

        if process_type == "표준점수":
            raw_val = std_v
            target_scores.subj_std_max[key_name] = target_scores.sat_grd_std_max.get((subj_name_altered, 1), 70.0)

            max_m = target_scores.mock_grd_std_max.get((subj_name, grd_v))
            min_m = target_scores.mock_grd_std_min.get((subj_name, grd_v))
            max_c = target_scores.sat_grd_std_max.get((subj_name_altered, grd_v))
            min_c = target_scores.sat_grd_std_min.get((subj_name_altered, grd_v))

            if max_m is not None and min_m is not None and max_c is not None and min_c is not None:
                pos = 0.0 if max_m == min_m else (std_val - min_m) / (max_m - min_m)
                pos = max(0.0, min(1.0, pos))
                converted_val = float(round(min_c + pos * (max_c - min_c)))
            else:
                converted_val = raw_val

            results[key_name] = (raw_val, converted_val)

        elif process_type == "변환표준점수":
            raw_val = std_v
            if raw_val <= 0:
                results[key_name] = (raw_val, raw_val)
                continue

            pct_col = str(int(round(pct_v)))
            lookup_univ_name = inquiry_lookup_name(jeongsi_year, univ_name, dept_info, subj_name_altered)
            trans_dict = getattr(target_scores, "converted_scores", {}).get(lookup_univ_name, {})

            target_scores.subj_std_max[key_name] = trans_dict.get("100", 70.0)
            converted_val = trans_dict.get(pct_col, raw_val)

            results[key_name] = (raw_val, converted_val)

        elif process_type == "백분위":
            results[key_name] = (pct_v, pct_v)
        elif process_type == "등급":
            results[key_name] = (float(grd_v), float(grd_v))
        else:
            results[key_name] = (std_v, std_v)

    target_scores.inq1_raw, target_scores.inq1_converted = results.get("inq1", (0.0, 0.0))
    target_scores.inq1_type = process_type
    target_scores.inq2_raw, target_scores.inq2_converted = results.get("inq2", (0.0, 0.0))
    target_scores.inq2_type = process_type


def process_eng(target_scores: CalcScore, dept_info: dict) -> None:
    eng_max_val = dept_info.get("영1")
    if eng_max_val is not None and str(eng_max_val).strip() != "":
        try:
            target_scores.subj_std_max["eng"] = float(eng_max_val)
        except ValueError:
            target_scores.subj_std_max["eng"] = 1.0
    else:
        target_scores.subj_std_max["eng"] = 1.0

    eng_grade = target_scores.eng_grd if target_scores.eng_grd is not None else 9
    if not (1 <= eng_grade <= 9):
        eng_grade = 9

    target_scores.eng_raw = eng_grade
    col_name = f"영{eng_grade}"
    converted_val = dept_info.get(col_name)

    if converted_val is not None and str(converted_val).strip() != "":
        try:
            target_scores.eng_converted = float(converted_val)
        except ValueError:
            target_scores.eng_converted = 0.0
    else:
        target_scores.eng_converted = 0.0


def process_hist(target_scores: CalcScore, dept_info: dict) -> None:
    hist_grade = target_scores.hist_grd if target_scores.hist_grd is not None else 9
    if not (1 <= hist_grade <= 9):
        hist_grade = 9

    target_scores.hist_raw = hist_grade
    col_name = f"한{hist_grade}"
    raw_val = dept_info.get(col_name)

    if raw_val is not None and str(raw_val).strip() != "":
        val_str = str(raw_val).strip()
        if "(" in val_str and ")" in val_str:
            try:
                main_str, sub_str = val_str.split("(")
                target_scores.hist_converted = float(main_str.strip())
                target_scores.hist_converted2 = float(sub_str.replace(")", "").strip())
            except ValueError:
                target_scores.hist_converted = 0.0
                target_scores.hist_converted2 = 0.0
        else:
            try:
                val = float(val_str)
                target_scores.hist_converted = val
                target_scores.hist_converted2 = val
            except ValueError:
                target_scores.hist_converted = 0.0
                target_scores.hist_converted2 = 0.0
    else:
        target_scores.hist_converted = 0.0
        target_scores.hist_converted2 = 0.0


def process_frn(target_scores: CalcScore, dept_info: dict) -> None:
    frn_grade = target_scores.frn_grd
    if frn_grade is None or not (1 <= frn_grade <= 9):
        target_scores.frn_raw = frn_grade or 0
        target_scores.frn_converted = 0.0
        return

    target_scores.frn_raw = frn_grade
    col_name = f"제2한{frn_grade}"
    raw_val = dept_info.get(col_name)

    if raw_val is not None and str(raw_val).strip() != "":
        try:
            target_scores.frn_converted = float(raw_val)
        except ValueError:
            target_scores.frn_converted = 0.0
    else:
        target_scores.frn_converted = 0.0