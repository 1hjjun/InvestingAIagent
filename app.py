from __future__ import annotations

import streamlit as st

from investment_assistant import PROJECT_ROOT, answer_question
from src.memory_store import load_daily_journals, load_memory
from src.portfolio_analytics import calculate_portfolio_analytics
from src.profile_store import load_portfolio, load_profile, save_portfolio, save_profile


st.set_page_config(page_title="개인 투자 PDF AI 비서", layout="wide")

st.title("개인 투자 PDF AI 비서")

st.markdown(
    """
    <style>
    div[data-testid="stHorizontalBlock"] div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 8px;
    }
    .journal-card-meta {
        color: #6b7280;
        font-size: 0.82rem;
        margin-bottom: 0.25rem;
    }
    .journal-card-title {
        font-size: 0.95rem;
        font-weight: 700;
        line-height: 1.35;
        min-height: 2.6rem;
    }
    .journal-card-subtitle {
        color: #4b5563;
        font-size: 0.82rem;
        line-height: 1.35;
        min-height: 2.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_journal_index" not in st.session_state:
    st.session_state.selected_journal_index = 0


def render_reference_chunks(chunks: list[dict]) -> None:
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk["metadata"]
        chunk_type = metadata.get("chunk_type", "topic_summary")
        page_label = metadata.get("pages") if chunk_type == "topic_summary" else metadata.get("page")
        source_path = str(metadata.get("source_path") or "")
        image_path = PROJECT_ROOT / source_path if source_path else None
        st.markdown(f"**{index}. {chunk_type} / page {page_label} / `{source_path}`**")
        st.caption(f"section: {metadata.get('section', '')} / topic: {metadata.get('topic', '')}")
        st.write(chunk["text"])
        if chunk_type != "topic_summary" and image_path and image_path.is_file():
            st.image(str(image_path), caption=source_path, width="stretch")
        st.divider()


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def safe_index(options: list[str], value: str, default: str) -> int:
    if value in options:
        return options.index(value)
    return options.index(default)


def format_krw(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{int(value):,}원"


def render_portfolio_dashboard() -> None:
    portfolio = load_portfolio()
    analytics = calculate_portfolio_analytics(portfolio)
    theme_allocation = analytics.get("theme_allocation", [])

    with st.expander("포트폴리오 대시보드", expanded=True):
        col1, col2 = st.columns(2)
        col1.metric("전체 시드", format_krw(analytics.get("total_seed_krw")))
        col2.metric("시드의 10%", format_krw(analytics.get("ten_percent_seed_krw")))
        col3, col4 = st.columns(2)
        col3.metric("현금", format_krw(analytics.get("cash_krw")))
        col4.metric("현금 비중", f"{analytics.get('cash_ratio_pct', 0):.2f}%")

        if theme_allocation:
            st.vega_lite_chart(
                theme_allocation,
                {
                    "mark": {"type": "arc", "innerRadius": 35},
                    "encoding": {
                        "theta": {"field": "value_krw", "type": "quantitative"},
                        "color": {
                            "field": "theme_label",
                            "type": "nominal",
                            "legend": {"orient": "bottom", "columns": 1},
                        },
                        "tooltip": [
                            {"field": "theme_label", "type": "nominal", "title": "테마"},
                            {"field": "value_krw", "type": "quantitative", "title": "금액", "format": ","},
                            {"field": "allocation_pct", "type": "quantitative", "title": "비중(%)"},
                        ],
                    },
                    "view": {"stroke": None},
                },
                use_container_width=True,
            )
            st.dataframe(
                [
                    {
                        "테마": item["theme_label"],
                        "금액": format_krw(item["value_krw"]),
                        "비중": f"{item['allocation_pct']:.2f}%",
                    }
                    for item in theme_allocation
                ],
                use_container_width=True,
                hide_index=True,
            )


def render_conversation_journals() -> None:
    journals = load_daily_journals()
    if not journals:
        with st.expander("대화 노트", expanded=False):
            st.caption("아직 저장된 대화 노트가 없습니다. 질문과 답변이 한 번 오가면 날짜별 글이 자동으로 만들어집니다.")
        return

    st.subheader("대화 노트")
    st.caption("날짜별 대화를 블로그 글처럼 모아둔 공간입니다. 카드를 선택하면 아래에 글이 펼쳐집니다.")
    selected_index = min(st.session_state.selected_journal_index, len(journals) - 1)
    visible_journals = journals[:6]
    columns = st.columns(min(3, len(visible_journals)))
    for index, journal in enumerate(visible_journals):
        with columns[index % len(columns)]:
            with st.container(border=True):
                st.markdown(
                    "\n".join(
                        [
                            f"<div class='journal-card-meta'>{journal.get('date', '')} · {journal.get('conversation_count', 0)}개 대화</div>",
                            f"<div class='journal-card-title'>{journal.get('title', '투자 대화 노트')}</div>",
                            f"<div class='journal-card-subtitle'>{journal.get('subtitle', '')}</div>",
                        ]
                    ),
                    unsafe_allow_html=True,
                )
                if st.button("읽기", key=f"journal_{journal.get('date', index)}", use_container_width=True):
                    st.session_state.selected_journal_index = index
                    selected_index = index

    selected = journals[selected_index]
    with st.container(border=True):
        st.caption(f"{selected.get('date', '')} · 마지막 업데이트 {selected.get('updated_at', '')}")
        st.markdown(selected.get("article", ""))


def render_profile_editor() -> None:
    profile = load_profile()
    with st.expander("투자 프로필 편집", expanded=False):
        with st.form("profile_form"):
            investment_style_options = ["long_term", "mid_term", "short_term", "mixed"]
            risk_tolerance_options = ["conservative", "moderate", "aggressive"]
            investment_style = st.selectbox(
                "투자 성향",
                investment_style_options,
                index=safe_index(investment_style_options, profile.get("investment_style", "long_term"), "long_term"),
            )
            risk_tolerance = st.selectbox(
                "위험 선호도",
                risk_tolerance_options,
                index=safe_index(risk_tolerance_options, profile.get("risk_tolerance", "moderate"), "moderate"),
            )
            preferred_assets = st.text_input("관심 자산", ", ".join(profile.get("preferred_assets", [])))
            interests = st.text_input("관심 섹터/주제", ", ".join(profile.get("interests", [])))
            base_currency = st.text_input("기준 통화", profile.get("base_currency", "KRW"))
            notes = st.text_area("메모", profile.get("notes", ""), height=100)
            submitted = st.form_submit_button("프로필 저장")
            if submitted:
                save_profile(
                    {
                        "investment_style": investment_style,
                        "risk_tolerance": risk_tolerance,
                        "preferred_assets": split_csv(preferred_assets),
                        "interests": split_csv(interests),
                        "base_currency": base_currency.strip() or "KRW",
                        "notes": notes.strip(),
                    }
                )
                st.success("프로필을 저장했습니다.")


def render_portfolio_editor() -> None:
    portfolio = load_portfolio()
    current_cash_ratio = portfolio.get("cash_ratio")
    if current_cash_ratio is None:
        current_cash_ratio = 0
    current_cash_krw = portfolio.get("cash_krw")
    if current_cash_krw is None:
        current_cash_krw = 0

    with st.expander("포트폴리오 편집", expanded=False):
        cash_ratio = st.number_input(
            "현금 비중(%)",
            min_value=0.0,
            max_value=100.0,
            value=float(current_cash_ratio),
            step=1.0,
        )
        cash_krw = st.number_input(
            "현금 금액(KRW)",
            min_value=0,
            value=int(current_cash_krw),
            step=100000,
        )
        positions = portfolio.get("positions", [])
        edited_positions = st.data_editor(
            positions,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "ticker": st.column_config.TextColumn("ticker"),
                "asset_type": st.column_config.TextColumn("asset type"),
                "target_role": st.column_config.TextColumn("target role"),
                "weight": st.column_config.NumberColumn("weight", min_value=0.0, max_value=100.0),
                "notes": st.column_config.TextColumn("notes"),
            },
            key="portfolio_editor",
        )
        if st.button("포트폴리오 저장"):
            updated_portfolio = dict(portfolio)
            updated_portfolio["cash_ratio"] = cash_ratio
            updated_portfolio["cash_krw"] = cash_krw
            updated_portfolio["positions"] = edited_positions
            updated_portfolio["analytics"] = calculate_portfolio_analytics(updated_portfolio)
            save_portfolio(updated_portfolio)
            st.success("포트폴리오를 저장했습니다.")


with st.sidebar:
    top_k = st.slider("검색할 주제 수", min_value=1, max_value=5, value=3)
    answer_style = st.radio(
        "답변 스타일",
        ["해석/코칭 모드", "자료 엄격 모드", "아이디어 확장 모드"],
        index=0,
        help="창의성과 근거 엄격함의 균형을 고릅니다.",
    )
    use_vision = st.checkbox(
        "답변할 때 관련 원본 이미지 재확인",
        value=False,
        help="검색된 페이지 중 차트/표/캡처가 있는 원본 이미지만 Vision 모델로 다시 확인합니다. API 비용이 추가됩니다.",
    )
    pdf_only = st.checkbox("PDF 근거만 사용", value=False)
    include_portfolio = st.checkbox("포트폴리오 관점 포함", value=True)
    conservative_view = st.checkbox("보수적 관점으로 답변", value=False)
    max_images = st.slider("재확인할 이미지 수", min_value=1, max_value=5, value=2, disabled=not use_vision)
    render_portfolio_dashboard()
    render_profile_editor()
    render_portfolio_editor()
    with st.expander("대화 메모리", expanded=False):
        memory = load_memory()
        st.caption(memory.get("updated_at", ""))
        st.write(memory.get("summary", ""))
    if st.button("대화 초기화"):
        st.session_state.messages = []
        st.rerun()

render_conversation_journals()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and message.get("image_review"):
            with st.expander("원본 이미지 재확인 결과", expanded=False):
                st.markdown(message["image_review"])
        if message["role"] == "assistant" and message.get("chunks"):
            with st.expander("참고 자료", expanded=False):
                render_reference_chunks(message["chunks"])

prompt = st.chat_input("질문을 입력하세요")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    conversation_history = [
        {"role": message["role"], "content": message["content"]}
        for message in st.session_state.messages
        if message["role"] in {"user", "assistant"}
    ]

    with st.chat_message("assistant"):
        with st.spinner("자료를 검색하고 답변을 생성하는 중입니다..."):
            try:
                result = answer_question(
                    prompt,
                    top_k=top_k,
                    use_vision=use_vision,
                    max_images=max_images,
                    conversation_history=conversation_history[:-1],
                    answer_style=answer_style,
                    pdf_only=pdf_only,
                    include_portfolio=include_portfolio,
                    conservative_view=conservative_view,
                )
            except Exception as exc:
                st.error(f"오류가 발생했습니다: {exc}")
                st.stop()

        st.markdown(result["answer"])
        if result["image_review"]:
            with st.expander("원본 이미지 재확인 결과", expanded=False):
                st.markdown(result["image_review"])
        with st.expander("참고 자료", expanded=False):
            render_reference_chunks(result["chunks"])

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "chunks": result["chunks"],
            "image_review": result["image_review"],
        }
    )
