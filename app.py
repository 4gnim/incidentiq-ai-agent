
import os
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

API_BASE_URL = os.getenv(
    "INCIDENTIQ_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")


st.set_page_config(
    page_title="IncidentIQ | AI Incident Response",
    page_icon="🚨",
    layout="wide",
)


def api_get(path: str):
    response = requests.get(
        f"{API_BASE_URL}{path}",
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict):
    response = requests.post(
        f"{API_BASE_URL}{path}",
        json=payload,
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def clear_investigation():
    st.session_state.pop("investigation", None)
    st.session_state.pop("decision_result", None)


def show_api_error(error):
    if isinstance(error, requests.HTTPError):
        response = error.response
        st.error(
            f"API mengembalikan HTTP {response.status_code}: "
            f"{response.text}"
        )
    else:
        st.error(f"Tidak dapat menghubungi API: {error}")


st.title("🚨 IncidentIQ")
st.caption(
    "AI-assisted incident investigation with human approval "
    "and simulated remediation."
)

# --------------------------------------------------
# 1. Periksa koneksi backend
# --------------------------------------------------

with st.sidebar:
    st.header("System Status")

    try:
        health = api_get("/health")
        st.success(f"API online: {health['service']}")
    except requests.RequestException as error:
        st.error("API tidak dapat dihubungi.")
        st.caption(
            "Jalankan backend dengan: "
            "uvicorn incidentiq.api:app --reload"
        )
        st.stop()

    st.divider()
    st.caption(f"Backend: {API_BASE_URL}")
    st.caption("Mode remediasi: simulasi saja")



# --------------------------------------------------
# 2. Ambil daftar insiden dan seluruh layanan
# --------------------------------------------------

try:
    incident_response = api_get("/incidents")
    incidents = incident_response["incidents"]

    service_response = api_get("/services")
    services = service_response["services"]
    service_summary = service_response["summary"]

except (requests.RequestException, KeyError) as error:
    show_api_error(error)
    st.stop()

if not incidents:
    st.info("Belum ada insiden di database.")
    st.stop()

if not services:
    st.warning("Belum ada layanan di database.")
    st.stop()

incident_by_id = {
    incident["incident_id"]: incident
    for incident in incidents
}


# --------------------------------------------------
# 3. Ringkasan insiden
# --------------------------------------------------

total_incidents = len(incidents)

sev1_count = sum(
    incident["severity"] == "SEV1"
    for incident in incidents
)

active_count = sum(
    incident["incident_status"] in ("open", "investigating")
    for incident in incidents
)

st.subheader("Incident Overview")

metric1, metric2, metric3 = st.columns(3)

metric1.metric("Total Insiden", total_incidents)
metric2.metric("Insiden SEV1", sev1_count)
metric3.metric("Insiden Aktif", active_count)


# --------------------------------------------------
# 4. Ringkasan kesehatan semua layanan
# --------------------------------------------------

st.divider()
st.subheader("Service Health")

service_col1, service_col2, service_col3, service_col4 = (
    st.columns(4)
)

service_col1.metric(
    "Total Layanan",
    service_summary["total"],
)

service_col2.metric(
    "Healthy",
    service_summary["healthy"],
)

service_col3.metric(
    "Degraded",
    service_summary["degraded"],
)

service_col4.metric(
    "Down",
    service_summary["down"],
)


# --------------------------------------------------
# 5. Tabel seluruh layanan
# --------------------------------------------------

with st.expander("Lihat seluruh layanan", expanded=True):
    st.dataframe(
        services,
        use_container_width=True,
        hide_index=True,
    )

st.caption(
    "Metrik Service Health dihitung dari seluruh tabel services, "
    "bukan hanya layanan yang memiliki insiden."
)

st.divider()



# --------------------------------------------------
# 4. Pilih insiden
# --------------------------------------------------

st.subheader("Investigasi Insiden")

incident_ids = list(incident_by_id.keys())

selected_id = st.selectbox(
    "Pilih insiden untuk dianalisis",
    options=incident_ids,
    format_func=lambda incident_id: (
        f"{incident_id} | "
        f"{incident_by_id[incident_id]['severity']} | "
        f"{incident_by_id[incident_id]['title']}"
    ),
)

selected = incident_by_id[selected_id]

col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(f"### {selected['title']}")
    st.write(selected["description"])

with col2:
    st.metric("Severity", selected["severity"])
    st.write(f"**Service:** {selected['service_name']}")
    st.write(f"**Incident status:** {selected['incident_status']}")
    st.write(f"**Service status:** {selected['service_status']}")

    st.write(
        f"**Latency:** {selected['latency_ms']} ms"
    )
    st.write(
        f"**Error rate:** {selected['error_rate_pct']}%"
    )


# Bersihkan hasil lama ketika pengguna memilih insiden lain.
current_investigation = st.session_state.get("investigation")

if (
    current_investigation
    and current_investigation.get("incident_id") != selected_id
):
    clear_investigation()


if st.button(
    "🔍 Investigate with AI",
    type="primary",
    use_container_width=True,
):
    try:
        with st.spinner(
            "Mengumpulkan bukti dan menganalisis insiden..."
        ):
            result = api_post(
                "/incidents/investigate",
                {"incident_id": selected_id},
            )

        st.session_state["investigation"] = result
        st.session_state.pop("decision_result", None)
        st.rerun()

    except requests.RequestException as error:
        show_api_error(error)


# --------------------------------------------------
# 5. Hasil investigasi
# --------------------------------------------------

investigation = st.session_state.get("investigation")

if (
    investigation
    and investigation.get("incident_id") == selected_id
):
    st.divider()
    st.subheader("AI Investigation Report")

    if investigation.get("status") == "awaiting_approval":
        st.warning(
            "Investigasi selesai. Menunggu keputusan manusia. "
            "Belum ada tindakan remediasi yang dijalankan."
        )

    st.markdown(investigation.get("analysis", ""))

    st.subheader("Proposed Remediation")
    proposed_action = investigation.get("proposed_action", {})

    st.write(
        f"**Action:** `{proposed_action.get('action', 'unknown')}`"
    )
    st.write(proposed_action.get("description", ""))

    st.info(
        "Tindakan ini merupakan simulasi. "
        "Tidak ada layanan nyata yang diubah."
    )

    
    # --------------------------------------------------
    # Evidence collected by the investigation workflow
    # --------------------------------------------------

    evidence = investigation.get("evidence", {})

    st.divider()
    st.subheader("Investigation Evidence")

    service_evidence = evidence.get("service")

    with st.expander("Current service metrics", expanded=True):
        if service_evidence:
            st.json(service_evidence)
        else:
            st.info("Tidak ada data layanan yang tersedia.")

    timeline = evidence.get("timeline", [])

    with st.expander(
        f"Incident timeline ({len(timeline)} log entries)",
        expanded=False,
    ):
        if timeline:
            st.dataframe(
                timeline,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Tidak ada log untuk insiden ini.")

    deployments = evidence.get("deployments", [])

    with st.expander(
        f"Deployment history ({len(deployments)} records)",
        expanded=False,
    ):
        if deployments:
            st.dataframe(
                deployments,
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Tidak ada riwayat deployment.")

    runbooks = evidence.get("runbooks", [])

    with st.expander(
        f"Retrieved runbooks ({len(runbooks)} documents)",
        expanded=False,
    ):
        if runbooks:
            for index, runbook in enumerate(runbooks, start=1):
                source = runbook.get("source", "unknown")
                distance = runbook.get("distance")

                st.markdown(f"**{index}. {source}**")

                if distance is not None:
                    st.caption(
                        f"Retrieval distance: {distance:.4f}"
                    )

                st.markdown(
                    runbook.get("content", "_No content returned._")
                )

                if index < len(runbooks):
                    st.divider()
        else:
            st.info("Tidak ada runbook yang ditemukan.")

    decision_result = st.session_state.get("decision_result")

    if decision_result:
        status = decision_result.get("status")

        if status == "simulated":
            st.success(
                "Simulasi remediasi selesai. "
                "Ini bukan bukti bahwa layanan nyata telah pulih."
            )
        elif status == "rejected":
            st.warning(
                "Remediasi ditolak. Tidak ada tindakan yang dijalankan."
            )
        else:
            st.info(f"Status workflow: {status}")

        st.subheader("Simulation Result")
        st.json(decision_result.get("execution_result"))

        st.subheader("Verification")
        st.json(decision_result.get("verification"))

        st.caption(
            "Real service modified: "
            f"{decision_result.get('real_service_modified', False)}"
        )

    elif investigation.get("status") == "awaiting_approval":
        st.subheader("Human Approval")

        st.write(
            "Tinjau analisis dan rekomendasi sebelum memilih tindakan."
        )

        approval_reason = st.text_input(
            "Catatan keputusan",
            value="Reviewed in IncidentIQ dashboard",
            max_chars=500,
        )

        approve_col, reject_col = st.columns(2)

        with approve_col:
            approve_clicked = st.button(
                "✅ Approve simulation",
                type="primary",
                use_container_width=True,
            )

        with reject_col:
            reject_clicked = st.button(
                "❌ Reject",
                use_container_width=True,
            )

        if approve_clicked or reject_clicked:
            approved = approve_clicked

            try:
                with st.spinner("Memproses keputusan..."):
                    result = api_post(
                        f"/incidents/{investigation['thread_id']}/approval",
                        {
                            "approved": approved,
                            "reason": approval_reason,
                        },
                    )

                st.session_state["decision_result"] = result
                st.rerun()

            except requests.RequestException as error:
                show_api_error(error)


st.divider()
st.caption(
    "IncidentIQ — portfolio project. "
    "Synthetic incident data; remediation is simulated only."
)