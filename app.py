# =============================================================================
# Dashboard Financeiro - Google Sheets + Streamlit (tema escuro).
#
#  - Resumo executivo + paineis sob medida por aba.
#  - Detecta o cabecalho de cada aba, entende R$ (inclusive negativos entre
#    parenteses) e datas dd/mm/aaaa.
#  - Aba "Editar": grava SOMENTE as celulas alteradas (preserva formulas).
#
# Modulos: sheets_utils.py (dados) · ui.py (visual) · views.py (paineis).
# =============================================================================
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

import auth
import sheets_utils as su
import ui
import views

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SERVICE_EMAIL = "gestora@sistemafinanceiro-478923.iam.gserviceaccount.com"

TAB_CP = "Contas a Pagar"
TAB_CR = "CR em aberto"
TAB_FOLHA = "Folha"
TAB_EXTRATO = "Extrato mes"
TAB_RECEBIDOS = "Recebidos"

st.set_page_config(page_title="Dashboard Financeiro", page_icon="📊", layout="wide")
ui.inject_css()

# ----------------------------- Login (protege o app) -------------------------
if not auth.require_login():
    st.stop()


# -----------------------------------------------------------------------------
# Conexao
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_client():
    info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_resource(show_spinner=False)
def get_spreadsheet():
    return get_client().open_by_key(st.secrets["sheet_id"])


@st.cache_data(ttl=30, show_spinner="Carregando dados...")
def load_values(worksheet_name: str):
    return get_spreadsheet().worksheet(worksheet_name).get_all_values()


def get_frames(worksheet_name: str) -> su.Frames:
    values = load_values(worksheet_name)
    hr = su.detect_header_row(values)
    raw, first = su.build_df(values, hr)
    _, nums0 = su.numeric_df(raw)
    raw = su.drop_summary_rows(raw, nums0)  # remove linhas de "Total"/residuo
    num, nums = su.numeric_df(raw)
    dates = su.date_columns(raw)
    return su.Frames(raw, num, nums, dates, first, hr)


# -----------------------------------------------------------------------------
# Conexao + barra lateral
# -----------------------------------------------------------------------------
try:
    spreadsheet = get_spreadsheet()
    names = [ws.title for ws in spreadsheet.worksheets()]
except Exception as e:
    st.error(
        "**Nao consegui acessar a planilha.** Compartilhe a planilha (como "
        f"**Editor**) com:\n\n`{SERVICE_EMAIL}`\n\ne confira o `sheet_id` em "
        "`.streamlit/secrets.toml`."
    )
    st.caption(f"Detalhe tecnico: {e}")
    st.stop()

VIEWS = {
    "📈 Resumo Executivo": "resumo",
    "💸 Contas a Pagar": "cp",
    "📥 Contas a Receber": "cr",
    "💰 Recebidos": "recebidos",
    "👥 Folha": "folha",
    "🏦 Extrato": "extrato",
    "✏️ Editar dados": "editar",
}

with st.sidebar:
    st.markdown("## 📊 Financeiro")
    st.caption(f"Conectado a **{spreadsheet.title}**")
    escolha = st.radio("Visao", list(VIEWS.keys()), label_visibility="collapsed")

    st.divider()
    auto = st.toggle("Atualizar automaticamente", value=False)
    intervalo = st.slider("Intervalo (s)", 10, 300, 30, disabled=not auto)
    if st.button("🔄 Atualizar agora", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.caption(f"👤 Logado como **{auth.current_user()}**")
    if st.button("🚪 Sair", width="stretch"):
        auth.logout()
        st.rerun()
    st.caption(f"Conta de servico:\n\n{SERVICE_EMAIL}")

if auto and st_autorefresh is not None:
    st_autorefresh(interval=intervalo * 1000, key="auto_refresh")
    st.cache_data.clear()

view = VIEWS[escolha]
st.title("📊 Dashboard Financeiro")


def frames_or_warn(tab):
    if tab not in names:
        st.warning(f"A aba **{tab}** nao foi encontrada na planilha.")
        return None
    return get_frames(tab)


def frames_opt(tab):
    """Carrega uma aba opcional; retorna None se nao existir (sem avisar)."""
    return get_frames(tab) if tab in names else None


# -----------------------------------------------------------------------------
# Edicao (fica aqui porque grava na planilha)
# -----------------------------------------------------------------------------
def render_editar():
    st.subheader("✏️ Editar dados")
    aba = st.selectbox("Aba", names)
    fr = get_frames(aba)
    if fr.raw.empty:
        st.info("Esta aba esta vazia (ou so tem cabecalho).")
        return
    st.info(
        "Edite as celulas e clique em **Salvar**. O app grava na planilha "
        "**apenas o que voce mudou** (as formulas das demais celulas sao "
        "preservadas). Linhas novas vao para o fim."
    )
    edited = st.data_editor(fr.raw, width="stretch", num_rows="dynamic",
                            hide_index=True, key=f"editor_{aba}_{fr.header_row}")
    if st.button("💾 Salvar na planilha", type="primary"):
        try:
            updates, n_cel, n_novas, n_rem = su.build_cell_updates(
                fr.raw, edited, fr.first_row)
            if updates:
                get_spreadsheet().worksheet(aba).batch_update(
                    updates, value_input_option="USER_ENTERED")
                st.cache_data.clear()
                msg = f"Salvo! {n_cel} celula(s) alterada(s)"
                if n_novas:
                    msg += f", {n_novas} linha(s) nova(s)"
                st.success(msg + ".")
            else:
                st.info("Nenhuma alteracao para salvar.")
            if n_rem:
                st.warning(
                    f"Voce removeu {n_rem} linha(s) na tela; por seguranca o app nao "
                    "apaga linhas. Apague direto no Google Sheets se precisar."
                )
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")


# -----------------------------------------------------------------------------
# Dispatch
# -----------------------------------------------------------------------------
if view == "resumo":
    views.render_resumo(frames_or_warn(TAB_CP), frames_or_warn(TAB_CR),
                        frames_or_warn(TAB_FOLHA), frames_or_warn(TAB_EXTRATO),
                        rb=frames_opt(TAB_RECEBIDOS))
elif view == "cp":
    fr = frames_or_warn(TAB_CP)
    if fr:
        views.render_contas_pagar(fr)
elif view == "cr":
    fr = frames_or_warn(TAB_CR)
    if fr:
        views.render_contas_receber(fr, rb=frames_opt(TAB_RECEBIDOS))
elif view == "recebidos":
    fr = frames_or_warn(TAB_RECEBIDOS)
    if fr:
        views.render_recebidos(fr)
elif view == "folha":
    fr = frames_or_warn(TAB_FOLHA)
    if fr:
        views.render_folha(fr)
elif view == "extrato":
    fr = frames_or_warn(TAB_EXTRATO)
    if fr:
        views.render_extrato(fr)
elif view == "editar":
    render_editar()
