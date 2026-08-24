import streamlit as st
import pandas as pd
import re
import plotly.graph_objects as go

st.set_page_config(page_title="연령별 인구현황 대시보드", layout="wide")

st.title("📊 행정안전부 연령별 인구현황 대시보드")
st.caption("행정안전부 주민등록 연령별 인구현황(월간) 데이터를 분석합니다.")

# ------------------------------------------------------------------
# 1. 데이터 파일 경로 (코드와 같은 폴더에 있다고 가정)
# ------------------------------------------------------------------
DATA_FILE = "202607_202607_연령별인구현황_월간.csv"


# ------------------------------------------------------------------
# 2. 데이터 로드 및 전처리
# ------------------------------------------------------------------
@st.cache_data
def load_data(path):
    # 행정안전부 인구통계 CSV는 보통 cp949(euc-kr) 인코딩
    try:
        df = pd.read_csv(path, encoding="cp949", low_memory=False)
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="utf-8", low_memory=False)

    # 숫자 컬럼의 콤마 제거 후 숫자형 변환
    numeric_cols = df.columns[1:]
    df[numeric_cols] = df[numeric_cols].apply(
        lambda s: pd.to_numeric(s.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")
    )

    # 행정구역 컬럼에서 지역명과 코드 분리
    df["지역명"] = df["행정구역"].str.extract(r"^(.*?)\s*\(\d+\)")[0].str.strip()
    df["지역코드"] = df["행정구역"].str.extract(r"\((\d+)\)")[0]

    return df


try:
    df = load_data(DATA_FILE)
except FileNotFoundError:
    st.error(
        f"'{DATA_FILE}' 파일을 찾을 수 없습니다. "
        f"이 앱 코드(app.py)와 같은 폴더에 데이터 CSV 파일을 넣어주세요."
    )
    st.stop()

# 컬럼명에서 기준연월, 성별, 연령 정보 파싱 (예: 2026년07월_계_0세)
pattern = re.compile(r"(\d{4})년(\d{2})월_(계|남|여)_(.+)")

age_cols = {}  # {성별: {연령라벨: 컬럼명}}
base_period = None
for col in df.columns:
    m = pattern.match(col)
    if not m:
        continue
    year, month, gender, label = m.groups()
    base_period = f"{year}년 {month}월"
    if label in ("총인구수", "연령구간인구수"):
        continue
    age_cols.setdefault(gender, {})[label] = col


def age_sort_key(label):
    if "이상" in label:
        return 1000
    return int(re.sub(r"[^0-9]", "", label))


age_labels_sorted = sorted(age_cols["계"].keys(), key=age_sort_key)

total_col = {}
for g in ["계", "남", "여"]:
    candidates = [c for c in df.columns if c.endswith(f"{g}_총인구수")]
    total_col[g] = candidates[0] if candidates else None

st.success(f"데이터 로드 완료 · 기준연월: **{base_period}** · 행정구역 수: **{len(df):,}개**")

# ------------------------------------------------------------------
# 3. 사이드바 - 지역 선택 (검색 입력 + 드롭다운 선택 동시 지원)
# ------------------------------------------------------------------
st.sidebar.header("🔎 지역 선택")

region_list = sorted(df["지역명"].dropna().unique().tolist())

search_text = st.sidebar.text_input(
    "지역명 검색 (예: 강남, 해운대, 종로)", ""
)
filtered_options = (
    [r for r in region_list if search_text.strip() in r] if search_text.strip() else region_list
)

if search_text.strip() and not filtered_options:
    st.sidebar.warning("검색 결과가 없습니다. 다른 키워드로 검색해보세요.")

selected_regions = st.sidebar.multiselect(
    "행정구역 선택 (검색 후 목록에서 클릭하거나, 직접 타이핑 후 선택)",
    options=filtered_options,
    default=[],
    help="검색창에 입력하면 목록이 좁혀집니다. 여러 지역을 선택해 비교할 수 있습니다.",
)

gender_option = st.sidebar.radio("성별", options=["계", "남", "여"], horizontal=True)

group_5yr = st.sidebar.checkbox("5세 단위로 묶어서 보기 (그래프를 더 보기 쉽게)", value=False)

if not selected_regions:
    st.info("왼쪽 사이드바에서 지역을 검색하고 선택해주세요.")
    st.stop()

# ------------------------------------------------------------------
# 4. 요약 지표 (첫 번째 선택 지역 기준)
# ------------------------------------------------------------------
main_region = selected_regions[0]
main_row = df[df["지역명"] == main_region].iloc[0]

col1, col2, col3 = st.columns(3)
col1.metric(f"{main_region} 총인구수 (계)", f"{main_row[total_col['계']]:,.0f}명")
col2.metric(f"{main_region} 남성 인구수", f"{main_row[total_col['남']]:,.0f}명")
col3.metric(f"{main_region} 여성 인구수", f"{main_row[total_col['여']]:,.0f}명")

st.divider()

# ------------------------------------------------------------------
# 5. 연령별 인구 구조 - 꺾은선 그래프 (선택 지역 비교, Plotly)
# ------------------------------------------------------------------
st.subheader(f"연령별 인구 구조 ({gender_option})")

def build_age_series(row, gender):
    """연령 라벨별 인구수 시리즈 반환 (필요 시 5세 단위로 묶음)"""
    values = {label: row[age_cols[gender][label]] for label in age_labels_sorted}
    if not group_5yr:
        return list(values.keys()), list(values.values())

    grouped_labels, grouped_values = [], []
    bucket_sum, bucket_start = 0, 0
    for label in age_labels_sorted:
        v = values[label]
        if "이상" in label:
            grouped_labels.append("100세 이상")
            grouped_values.append(v)
            continue
        age = int(re.sub(r"[^0-9]", "", label))
        bucket_sum += v
        if age % 5 == 4:
            grouped_labels.append(f"{bucket_start}-{age}세")
            grouped_values.append(bucket_sum)
            bucket_sum, bucket_start = 0, age + 1
    return grouped_labels, grouped_values


fig = go.Figure()
for region in selected_regions:
    row = df[df["지역명"] == region]
    if row.empty:
        continue
    row = row.iloc[0]
    x_labels, y_values = build_age_series(row, gender_option)
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=y_values,
            mode="lines+markers",
            name=region,
            line=dict(width=2.5),
            marker=dict(size=4),
        )
    )

fig.update_layout(
    height=550,
    hovermode="x unified",
    xaxis_title="연령",
    yaxis_title="인구수(명)",
    legend_title="지역",
    margin=dict(l=10, r=10, t=30, b=10),
)
fig.update_xaxes(tickangle=-45)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# ------------------------------------------------------------------
# 6. 인구 피라미드 (첫 번째 선택 지역 기준, 남/여 비교, Plotly)
# ------------------------------------------------------------------
st.subheader(f"인구 피라미드 - {main_region}")

male_vals = [-main_row[age_cols["남"][label]] for label in age_labels_sorted]
female_vals = [main_row[age_cols["여"][label]] for label in age_labels_sorted]

fig_pyramid = go.Figure()
fig_pyramid.add_trace(
    go.Bar(y=age_labels_sorted, x=male_vals, name="남", orientation="h", marker_color="#4C78A8")
)
fig_pyramid.add_trace(
    go.Bar(y=age_labels_sorted, x=female_vals, name="여", orientation="h", marker_color="#F58518")
)
fig_pyramid.update_layout(
    barmode="relative",
    height=700,
    xaxis_title="인구수",
    yaxis_title="연령",
    yaxis=dict(categoryorder="array", categoryarray=age_labels_sorted[::-1]),
    margin=dict(l=10, r=10, t=30, b=10),
)
st.plotly_chart(fig_pyramid, use_container_width=True)

st.divider()

# ------------------------------------------------------------------
# 7. 원본 데이터 테이블
# ------------------------------------------------------------------
with st.expander("📋 선택 지역 원본 데이터 보기"):
    show_cols = ["지역명", total_col["계"], total_col["남"], total_col["여"]]
    st.dataframe(
        df[df["지역명"].isin(selected_regions)][show_cols].rename(
            columns={
                total_col["계"]: "총인구수(계)",
                total_col["남"]: "총인구수(남)",
                total_col["여"]: "총인구수(여)",
            }
        ),
        use_container_width=True,
    )

st.caption("데이터 출처: 행정안전부 주민등록 연령별 인구현황(월간)")
