# ============================================================
# 5단계. 인구구조가 가장 비슷한 지역 Top 5 찾기
# ------------------------------------------------------------
# '인구구조'란 나이별 인구 비율(모양)을 말해요.
# 총인구 크기가 달라도, 나이별 비율(그래프 모양)이 비슷하면
# "인구구조가 비슷하다"고 볼 수 있어요.
# ============================================================
st.divider()
st.header("4️⃣ 나와 인구구조가 가장 비슷한 지역 Top 5")
st.write(
    "동네 하나를 고르면, 전국에서 **나이별 인구 비율(모양)**이 "
    "가장 비슷한 지역 5곳을 찾아드려요. "
    "(단순히 인구 '규모'가 비슷한 게 아니라, 나이대별 비중이 비슷한 지역이에요!)"
)

# 시도 + 시군구 + 동 + 코드를 합쳐서 지역마다 겹치지 않는 이름표를 만들어요.
df_최신["지역명"] = (
    df_최신["시도"].fillna("")
    + " "
    + df_최신["시군구"].fillna("")
    + " "
    + df_최신["동"].fillna("")
).str.strip()
df_최신["지역표시명"] = df_최신["지역명"] + " (" + df_최신["코드"].astype(str) + ")"

지역_검색어 = st.text_input("🔍 비교 기준이 될 지역을 검색해보세요 (예: 강남, 해운대, 종로)", "")

if 지역_검색어.strip():
    후보_목록 = df_최신[df_최신["지역명"].str.contains(지역_검색어.strip(), na=False)]
else:
    후보_목록 = df_최신

if len(후보_목록) == 0:
    st.warning("검색 결과가 없어요. 다른 키워드로 검색해보세요.")
    st.stop()

기준_지역_표시명 = st.selectbox(
    "위 검색 결과 중, 기준이 될 동네를 하나 선택하세요",
    options=후보_목록["지역표시명"].tolist(),
)

# '계_0세', '계_1세', ... '계_100세 이상' 열을 모아서
# 각 지역의 나이별 인구 벡터를 만들고, 총인구로 나눠서 '비율(구조)'로 바꿔줘요.
계열_목록 = [col for col in df_최신.columns if col.startswith("계_")]

나이별_인구 = df_최신[계열_목록].to_numpy(dtype=float)
지역별_총합 = 나이별_인구.sum(axis=1, keepdims=True)
지역별_총합[지역별_총합 == 0] = 1

나이별_비율 = 나이별_인구 / 지역별_총합

# 유클리드 거리가 가까울수록(작을수록) 인구구조 모양이 비슷하다는 뜻이에요.
기준_행_번호 = df_최신.index[df_최신["지역표시명"] == 기준_지역_표시명][0]
기준_위치 = df_최신.index.get_loc(기준_행_번호)
기준_비율벡터 = 나이별_비율[기준_위치]

거리_배열 = ((나이별_비율 - 기준_비율벡터) ** 2).sum(axis=1) ** 0.5
df_최신["구조거리"] = 거리_배열

top5 = (
    df_최신[df_최신["지역표시명"] != 기준_지역_표시명]
    .sort_values("구조거리")
    .head(5)
)

st.subheader(f"'{기준_지역_표시명}'과(와) 인구구조가 가장 비슷한 지역 Top 5")
st.dataframe(
    top5[["지역명", "총인구", "구조거리"]]
    .rename(columns={"구조거리": "구조 차이(작을수록 비슷)"})
    .reset_index(drop=True),
    use_container_width=True,
)

연령_라벨_목록 = [col.replace("계_", "") for col in 계열_목록]
fig_구조비교 = go.Figure()

fig_구조비교.add_trace(
    go.Scatter(
        x=연령_라벨_목록, y=기준_비율벡터, mode="lines",
        name=f"⭐ {기준_지역_표시명} (기준)", line=dict(width=4, color="#E45756"),
    )
)
for _, row in top5.iterrows():
    행_위치 = df_최신.index.get_loc(row.name)
    fig_구조비교.add_trace(
        go.Scatter(
            x=연령_라벨_목록, y=나이별_비율[행_위치], mode="lines",
            name=row["지역표시명"], line=dict(width=1.8, dash="dot"), opacity=0.85,
        )
    )

fig_구조비교.update_layout(
    height=550, hovermode="x unified",
    xaxis_title="나이", yaxis_title="비율 (해당 나이 인구 ÷ 총인구)",
    yaxis_tickformat=".1%", legend_title="지역",
    title="기준 지역 vs 인구구조가 비슷한 Top 5 지역",
)
fig_구조비교.update_xaxes(tickangle=-45)
st.plotly_chart(fig_구조비교, use_container_width=True)
