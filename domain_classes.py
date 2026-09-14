# domain_classes.py
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# ==========================================
# 1. 프론트엔드 전송 데이터 DTO (ScoreCardDTO)
# ==========================================
class SubjectScore(BaseModel):
    subject: Optional[str] = ""
    detail: Optional[str] = ""
    std: Optional[float] = 0.0
    pct: Optional[float] = 0.0
    grd: Optional[int] = 9

class GradeOnlySubject(BaseModel):
    grd: Optional[int] = 9

class ScoreCardDTO(BaseModel):
    mockYear: str
    mockHaknyeon: str
    mockMonth: str
    jeongsiYear: str
    targetUniv: str
    
    kor: SubjectScore
    math: SubjectScore
    eng: GradeOnlySubject
    hist: GradeOnlySubject
    inq1: SubjectScore
    inq2: SubjectScore
    frn: Optional[GradeOnlySubject] = GradeOnlySubject(grd=9)
    # [핵심] /validate에서 쿼리한 4개 테이블 전체 데이터 저장소
    all_db_cache: Optional[Dict[str, Any]] = None

    
# ==========================================
# 2. 내부 점수 산출 및 상태 관리 클래스 (CalcScore)
# ==========================================
class CalcScore:
    def __init__(self):
        # ----------------------------------
        # A. 시험 및 대학 메타 정보
        # ----------------------------------
        self.jeongsi_year: str = ""      # 예: "2026학년도 정시"
        self.mock_year: str = ""         # 예: "2025"
        self.mock_haknyeon: str = ""     # 예: "고3"
        self.mock_month: str = ""        # 예: "6월"
        
        self.univ_name: str = ""         # 대학명
        self.major_name: str = ""        # 학과명/모집단위
        self.max_score: float = 1000.0   # 대학 환산 만점

        # ----------------------------------------------------
        # [신규 추가] 정시(수능) 전국 성적 통계 (dict)
        # ----------------------------------------------------
        self.sat_std_max: dict = {}        # 정시 과목별 전국 최고 표준점수 (예: {'국어': 150})
        self.sat_grd_std_max: dict = {}    # 정시 과목/등급별 최고 표준점수 (예: {('국어', 1): 150})
        self.sat_grd_std_min: dict = {}    # 정시 과목/등급별 최저 표준점수 (예: {('국어', 1): 134})

        # ----------------------------------------------------
        # [신규 추가] 모의고사 전국 성적 통계 (dict)
        # ----------------------------------------------------
        self.mock_std_max: dict = {}       # 모의고사 과목별 전국 최고 표준점수
        self.mock_grd_std_max: dict = {}   # 모의고사 과목/등급별 최고 표준점수
        self.mock_grd_std_min: dict = {}   # 모의고사 과목/등급별 최저 표준점수

        # ----------------------------------------------------
        # [신규 추가] 대학/학과별 기준 최고 점수
        # ----------------------------------------------------
        self.univ_trans_max: dict = {}     # 대학별 탐구 변환표준점수 최고점 (예: {'탐1': 70.0})
        self.univ_score_max: dict = {}     # 대학 자체 반영 과목별 만점점수
        self.subj_std_max: dict = {}       # 계산 중 사용하는 과목별 표준점수 최고점
        self.converted_scores: dict = {}   # 대학별 탐구 변환표준점수 표

        # ----------------------------------
        # B. 학생 원본 성적 정보
        # ----------------------------------
        self.kor_detail: str = ""
        self.kor_std: float = 0.0
        self.kor_pct: float = 0.0
        self.kor_grd: int = 9

        self.math_detail: str = ""
        self.math_std: float = 0.0
        self.math_pct: float = 0.0
        self.math_grd: int = 9

        self.eng_grd: int = 9
        self.hist_grd: int = 9

        self.inq1_detail: str = ""
        self.inq1_std: float = 0.0
        self.inq1_pct: float = 0.0
        self.inq1_grd: int = 9

        self.inq2_detail: str = ""
        self.inq2_std: float = 0.0
        self.inq2_pct: float = 0.0
        self.inq2_grd: int = 9

        self.frn_grd: int = 9

        # ----------------------------------
        # C. 대학별 환산 결과 점수
        # ----------------------------------
        self.kor_raw: float = 0.0
        self.kor_converted: float = 0.0
        self.kor_type: str = ""

        self.math_raw: float = 0.0
        self.math_converted: float = 0.0
        self.math_type: str = ""

        self.eng_raw: int = 9
        self.eng_converted: float = 0.0

        self.hist_raw: int = 9
        self.hist_converted: float = 0.0
        self.hist_converted2: float = 0.0

        self.inq1_raw: float = 0.0
        self.inq1_converted: float = 0.0
        self.inq1_type: str = ""

        self.inq2_raw: float = 0.0
        self.inq2_converted: float = 0.0
        self.inq2_type: str = ""

        self.frn_raw: int = 9
        self.frn_converted: float = 0.0

        # ----------------------------------
        # D. 가산점 저장 변수
        # ----------------------------------
        self.bonus_case2: float = 0.0
        self.bonus_case3: float = 0.0
        self.bonus_case4: float = 0.0
        self.bonus_case7: float = 0.0
        self.bonus_case8: float = 0.0
        self.bonus_case9: float = 0.0
        self.bonus_case10: float = 0.0

        self.final_score: float = 0.0

    def reset(self, score_card: ScoreCardDTO, dept_info: dict = None) -> None:
        """학과 순회 시 현재 학과 관련 계산 상태 재초기화"""
        # 1. 시험 메타정보
        self.jeongsi_year = score_card.jeongsiYear or ""
        self.mock_year = score_card.mockYear or ""
        self.mock_haknyeon = score_card.mockHaknyeon or ""
        self.mock_month = score_card.mockMonth or ""

        # 2. 학생 원본 성적 추출
        self.kor_detail = score_card.kor.detail or ""
        self.kor_std = float(score_card.kor.std or 0.0)
        self.kor_pct = float(score_card.kor.pct or 0.0)
        self.kor_grd = score_card.kor.grd if score_card.kor.grd is not None else 9

        self.math_detail = score_card.math.detail or ""
        self.math_std = float(score_card.math.std or 0.0)
        self.math_pct = float(score_card.math.pct or 0.0)
        self.math_grd = score_card.math.grd if score_card.math.grd is not None else 9

        self.eng_grd = score_card.eng.grd if score_card.eng.grd is not None else 9
        self.hist_grd = score_card.hist.grd if score_card.hist.grd is not None else 9

        self.inq1_detail = score_card.inq1.detail or ""
        self.inq1_std = float(score_card.inq1.std or 0.0)
        self.inq1_pct = float(score_card.inq1.pct or 0.0)
        self.inq1_grd = score_card.inq1.grd if score_card.inq1.grd is not None else 9

        self.inq2_detail = score_card.inq2.detail or ""
        self.inq2_std = float(score_card.inq2.std or 0.0)
        self.inq2_pct = float(score_card.inq2.pct or 0.0)
        self.inq2_grd = score_card.inq2.grd if score_card.inq2.grd is not None else 9

        if hasattr(score_card, "frn") and score_card.frn and score_card.frn.grd is not None:
            self.frn_grd = score_card.frn.grd
        else:
            self.frn_grd = None

        # 3. 대학/학과 메타정보 주입
        if dept_info:
            self.univ_name = dept_info.get("대학교명") or dept_info.get("대학명") or ""
            self.major_name = dept_info.get("학과명") or dept_info.get("모집단위") or ""
            try:
                self.max_score = float(dept_info.get("만점") or 1000.0)
            except (ValueError, TypeError):
                self.max_score = 1000.0
        else:
            self.univ_name = ""
            self.major_name = ""
            self.max_score = 1000.0

        # 4. 대학별 환산 결과 점수 및 가산점 변수 리셋
        self.kor_raw, self.kor_converted, self.kor_type = 0.0, 0.0, ""
        self.math_raw, self.math_converted, self.math_type = 0.0, 0.0, ""
        self.eng_raw, self.eng_converted = self.eng_grd, 0.0
        self.hist_raw, self.hist_converted, self.hist_converted2 = self.hist_grd, 0.0, 0.0
        self.inq1_raw, self.inq1_converted, self.inq1_type = 0.0, 0.0, ""
        self.inq2_raw, self.inq2_converted, self.inq2_type = 0.0, 0.0, ""
        self.frn_raw = self.frn_grd if self.frn_grd is not None else 0
        self.frn_converted = 0.0

        self.bonus_case2 = 0.0
        self.bonus_case3 = 0.0
        self.bonus_case4 = 0.0
        self.bonus_case7 = 0.0
        self.bonus_case8 = 0.0
        self.bonus_case9 = 0.0
        self.bonus_case10 = 0.0
        self.final_score = 0.0

        # 대학/학과별 기준 최고점 초기화 (sat_*, mock_* 전국 통계는 유지)
        self.univ_trans_max.clear()
        self.univ_score_max.clear()
        self.subj_std_max.clear()

    def __repr__(self) -> str:
        border = "+" + "-"*88 + "+"
        mock_info = f"|  [모의고사] {self.mock_year}년 {self.mock_haknyeon} {self.mock_month}"
        dept_info = f"|  [대학/학과] {self.univ_name} {self.major_name} ({self.jeongsi_year})"
        
        mock_padded = mock_info.ljust(88) + "|"
        dept_padded = dept_info.ljust(88) + "|"
        
        table = (
            f"\n{border}\n"
            f"{mock_padded}\n"
            f"{dept_padded}\n"
            f"{border}\n"
            f"| 영역     | 상세 과목명         | 반영Type     | 원점수(표점/등급) | 환산점수(Converted) |\n"
            f"+----------+---------------------+--------------+-------------------+--------------------+\n"
            f"| 국어     | {self.kor_detail:<19} | {self.kor_type:<12} | {self.kor_raw:>17.1f} | {self.kor_converted:>18.2f} |\n"
            f"| 수학     | {self.math_detail:<19} | {self.math_type:<12} | {self.math_raw:>17.1f} | {self.math_converted:>18.2f} |\n"
            f"| 탐구1    | {self.inq1_detail:<19} | {self.inq1_type:<12} | {self.inq1_raw:>17.1f} | {self.inq1_converted:>18.2f} |\n"
            f"| 탐구2    | {self.inq2_detail:<19} | {self.inq2_type:<12} | {self.inq2_raw:>17.1f} | {self.inq2_converted:>18.2f} |\n"
            f"| 영어     | -                      | 등급환산              | {self.eng_raw:>15}등급 | {self.eng_converted:>18.2f} |\n"
            f"| 한국사   | -                      | 등급환산              | {self.hist_raw:>15}등급 | {self.hist_converted:>18.2f} |\n"
            f"| 제2외국어| -                      | 등급환산              | {self.frn_raw:>15}등급 | {self.frn_converted:>18.2f} |\n"
            f"{border}\n"
            f"| ★ 최종 환산점수 : {self.final_score:>67.2f} |\n"
            f"{border}"
        )
        return table


# ==========================================
# 3. 등급별 백분위 범위 상수 (1~9등급)
# ==========================================
GradeRange = {
    1: {"percentile_min": 96.0, "percentile_max": 100.0},
    2: {"percentile_min": 89.0, "percentile_max": 95.0},
    3: {"percentile_min": 77.0, "percentile_max": 88.0},
    4: {"percentile_min": 60.0, "percentile_max": 76.0},
    5: {"percentile_min": 40.0, "percentile_max": 59.0},
    6: {"percentile_min": 23.0, "percentile_max": 39.0},
    7: {"percentile_min": 11.0, "percentile_max": 22.0},
    8: {"percentile_min": 4.0,  "percentile_max": 10.0},
    9: {"percentile_min": 0.0,  "percentile_max": 3.0},
}