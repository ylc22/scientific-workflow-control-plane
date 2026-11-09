import os
import requests
import streamlit as st

API = os.getenv("CONTROL_PLANE_API", "http://127.0.0.1:8000")

st.set_page_config(page_title="Scientific Workflow Control Plane", layout="wide")
st.title("Scientific Workflow Control Plane")
st.caption("Operator view for synthetic scientific jobs")

left, right = st.columns([1, 2])

with left:
    st.subheader("Submit job")
    workflow = st.selectbox("Workflow", ["rna-seq-qc", "protein-batch-score", "variant-annotation"])
    sample_id = st.text_input("Sample ID", "SAMPLE_001")
    fail_step = st.selectbox("Failure injection", ["none", "ingest", "validate", "analyze", "publish"])
    if st.button("Submit", type="primary"):
        payload = {
            "workflow": workflow,
            "sample_id": sample_id,
            "parameters": {},
            "fail_step": None if fail_step == "none" else fail_step,
        }
        r = requests.post(f"{API}/jobs", json=payload, timeout=10)
        r.raise_for_status()
        st.success(f"Submitted {r.json()['id']}")

with right:
    st.subheader("Recent jobs")
    try:
        jobs = requests.get(f"{API}/jobs", timeout=10).json()
        if jobs:
            st.dataframe(
                [
                    {
                        "id": j["id"],
                        "workflow": j["workflow"],
                        "sample": j["sample_id"],
                        "status": j["status"],
                        "attempt": j["attempt"],
                    }
                    for j in jobs
                ],
                use_container_width=True,
                hide_index=True,
            )
            cancellable = [j for j in jobs if j["status"] in {"queued", "running"}]
            if cancellable:
                selected = st.selectbox(
                    "Cancel a job",
                    [j["id"] for j in cancellable],
                    format_func=lambda job_id: next(
                        f"{j['workflow']} · {j['sample_id']} · {job_id[:8]}"
                        for j in cancellable
                        if j["id"] == job_id
                    ),
                )
                if st.button("Cancel selected job"):
                    r = requests.post(f"{API}/jobs/{selected}/cancel", timeout=10)
                    if r.status_code == 200:
                        st.success(f"Cancelled {selected}")
                        st.rerun()
                    else:
                        st.error(r.json().get("detail", "Cancellation failed"))
        else:
            st.info("No jobs yet")
    except Exception as exc:
        st.warning(f"API unavailable: {exc}")

st.subheader("Operational metrics")
try:
    st.json(requests.get(f"{API}/metrics", timeout=10).json())
except Exception as exc:
    st.warning(f"Metrics unavailable: {exc}")
