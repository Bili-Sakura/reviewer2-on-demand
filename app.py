import os
import json
from typing import List

import streamlit as st
from dotenv import load_dotenv

from pipelines import PaperReviewPipeline, PaperReviewConfig
from pipelines.config import MinerUConfig, LLMConfig


def create_pipeline(
    mineru_key: str,
    dashscope_key: str,
    output_dir: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    output_format: str,
) -> PaperReviewPipeline:
    mineru_cfg = MinerUConfig(api_key=mineru_key, output_dir=output_dir)
    llm_cfg = LLMConfig(
        api_key=dashscope_key,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    cfg = PaperReviewConfig(mineru=mineru_cfg, llm=llm_cfg, output_format=output_format)
    return PaperReviewPipeline(cfg)


def run_pipeline(pipeline: PaperReviewPipeline, inputs: List[str], conference: str):
    if len(inputs) == 1:
        return pipeline(inputs[0], conference=conference)
    return pipeline(inputs, conference=conference)


load_dotenv()

st.set_page_config(page_title="Reviewer2 On-Demand", page_icon="📝", layout="wide")

st.title("Reviewer2 On-Demand 📝")
st.caption("Quickly parse papers with MinerU and get a single 1–10 review score")

with st.sidebar:
    st.header("Configuration")
    mineru_key = st.text_input(
        "MINERU_API_KEY", value=os.getenv("MINERU_API_KEY", ""), type="password"
    )
    dashscope_key = st.text_input(
        "DASHSCOPE_API_KEY", value=os.getenv("DASHSCOPE_API_KEY", ""), type="password"
    )
    output_dir = st.text_input("Output directory", value="./output/parsed_papers")
    conference = st.selectbox(
        "Conference", ["auto", "neurips", "icml", "iclr", "aaai"], index=0
    )
    output_format = st.selectbox("Output format", ["json", "markdown", "txt"], index=0)

    st.divider()
    st.subheader("LLM Settings")
    model_name = st.text_input("Model", value="qwen-plus")
    temperature = st.slider(
        "Temperature", min_value=0.0, max_value=1.0, value=0.1, step=0.05
    )
    max_tokens = st.number_input(
        "Max tokens", min_value=256, max_value=8000, value=4000, step=128
    )

st.subheader("Inputs")

tab1, tab2 = st.tabs(["From URL/Path", "Upload PDF File(s)"])

with tab1:
    urls = st.text_area(
        "Enter one or more URLs or local PDF paths (one per line)",
        placeholder="https://arxiv.org/pdf/2103.12345.pdf\n./papers/local.pdf",
        height=120,
    )

with tab2:
    uploaded_files = st.file_uploader(
        "Upload PDF files", type=["pdf"], accept_multiple_files=True
    )

inputs: List[str] = []

if uploaded_files:
    os.makedirs("./uploads", exist_ok=True)
    for file in uploaded_files:
        save_path = os.path.join("./uploads", file.name)
        with open(save_path, "wb") as f:
            f.write(file.getbuffer())
        inputs.append(save_path)

if urls.strip():
    inputs.extend([line.strip() for line in urls.splitlines() if line.strip()])

col_run, col_clear = st.columns([1, 1])

with col_run:
    run_clicked = st.button(
        "Run Review", type="primary", use_container_width=True, disabled=not inputs
    )
with col_clear:
    clear_clicked = st.button("Clear", use_container_width=True)

if clear_clicked:
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

if run_clicked:
    # Fallback to environment variables (including .env) if fields are left blank
    effective_mineru_key = mineru_key or os.getenv("MINERU_API_KEY", "")
    effective_dashscope_key = dashscope_key or os.getenv("DASHSCOPE_API_KEY", "")

    if not effective_mineru_key:
        st.error("Please provide MINERU_API_KEY in the sidebar or .env")
    elif not effective_dashscope_key:
        st.error("Please provide DASHSCOPE_API_KEY in the sidebar or .env")
    else:
        with st.spinner("Initializing pipeline..."):
            try:
                pipeline = create_pipeline(
                    mineru_key=effective_mineru_key,
                    dashscope_key=effective_dashscope_key,
                    output_dir=output_dir,
                    model_name=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    output_format=output_format,
                )
            except Exception as e:
                st.exception(e)
                st.stop()

        with st.spinner("Running review..."):
            try:
                result = run_pipeline(pipeline, inputs, conference)
            except Exception as e:
                st.exception(e)
                st.stop()

        st.success("Completed")

        def render_result(res: dict):
            st.write(f"Input: {res.get('input')}")
            st.write(f"Conference: {res.get('conference')}")
            review = res.get("review", {})
            parsed = review.get("parsed_review", {})
            cols = st.columns(1)
            cols[0].metric("Score", f"{parsed.get('score', 'N/A')}/10")

            with st.expander("Model Output", expanded=False):
                st.write(review.get("full_response") or review.get("raw_response"))

            with st.expander("Parsed Content (preview)"):
                pc = res.get("parsed_content", {})
                st.caption(
                    f"File: {pc.get('output_file')} | Length: {pc.get('file_size')} chars"
                )
                st.code((pc.get("content") or "")[:2000])

            with st.expander("Raw JSON"):
                st.code(json.dumps(res, indent=2, ensure_ascii=False))

        if isinstance(result, list):
            for idx, item in enumerate(result, start=1):
                st.divider()
                st.subheader(f"Result {idx}")
                if "error" in item:
                    st.error(item["error"])
                else:
                    render_result(item)
        else:
            render_result(result)
