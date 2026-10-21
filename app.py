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

import pandas as pd

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
TAB_RECEBIDOS = "Recebidos"
TAB_SEGMENTO = "Segmento"
EXTRATO_EMPRESAS = ["Roboteasy", "Agapys"]  # cada empresa tem sua aba de extrato

_logo_path = "logo/logo_roboteasy.png"
st.set_page_config(
    page_title="Roboteasy Financeiro",
    page_icon=_logo_path,
    layout="wide",
)
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
    "🎯 Resumo Executivo": "resumo",
    "🔴 Contas a Pagar": "cp",
    "⚡ Contas a Receber": "cr",
    "✅ Recebidos": "recebidos",
    "🏷️ Segmento": "segmento",
    "🤖 Folha": "folha",
    "🔍 Extrato": "extrato",
    "🔄 Importar Extrato": "importar",
    "⚙️ Editar dados": "editar",
}

with st.sidebar:
    st.image(_logo_path, width=180)
    st.caption(f"Conectado a **{spreadsheet.title}**")
    escolha = st.radio("Visao", list(VIEWS.keys()), label_visibility="collapsed")

    st.divider()
    auto = st.toggle("Atualizar automaticamente", value=False)
    intervalo = st.slider("Intervalo (s)", 10, 300, 30, disabled=not auto)
    if st.button("⚡ Atualizar agora", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.caption(f"👤 Logado como **{auth.current_user()}**")
    if st.button("🔐 Sair", width="stretch"):
        auth.logout()
        st.rerun()
    st.caption(f"Conta de servico:\n\n{SERVICE_EMAIL}")

if auto and st_autorefresh is not None:
    st_autorefresh(interval=intervalo * 1000, key="auto_refresh")
    st.cache_data.clear()

view = VIEWS[escolha]


def frames_or_warn(tab):
    if tab not in names:
        st.warning(f"A aba **{tab}** nao foi encontrada na planilha.")
        return None
    return get_frames(tab)


def frames_opt(tab):
    """Carrega uma aba opcional; retorna None se nao existir (sem avisar)."""
    return get_frames(tab) if tab in names else None


def _extrato_tab(empresa):
    """Nome da aba de extrato de cada empresa (com fallback para 'Extrato mes')."""
    pref = f"Extrato {empresa}"
    if pref in names:
        return pref
    if empresa == "Roboteasy" and "Extrato mes" in names:
        return "Extrato mes"
    return pref


def load_extratos():
    """Dict {empresa: Frames ou None} com os extratos existentes."""
    out = {}
    for emp in EXTRATO_EMPRESAS:
        tab = _extrato_tab(emp)
        fr = get_frames(tab) if tab in names else None
        out[emp] = fr if (fr is not None and not fr.raw.empty) else None
    return out


# -----------------------------------------------------------------------------
# Edicao (fica aqui porque grava na planilha)
# -----------------------------------------------------------------------------
def render_editar():
    st.subheader("⚙️ Editar dados")
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
# Importar extrato (.xls do banco -> aba da empresa)
# -----------------------------------------------------------------------------
def render_importar():
    st.subheader("🔄 Importar Extrato")
    st.caption("Envie o arquivo **.xls** do extrato (Sicredi) e o app preenche a aba da "
               "empresa automaticamente.")
    empresa = st.selectbox("Empresa", EXTRATO_EMPRESAS, key="imp_empresa")
    file = st.file_uploader("Arquivo do extrato (.xls)", type=["xls", "xlsx"],
                            key="imp_file")
    if not file:
        return
    try:
        linhas = su.parse_extrato_sicredi(file, filename=file.name)
    except Exception as e:
        st.error(f"Não consegui ler o arquivo: {e}")
        return
    if len(linhas) <= 9:
        st.warning("O arquivo não tem lançamentos reconhecidos. Confira se é o extrato certo.")
        return

    tab = _extrato_tab(empresa)
    existe = tab in names
    n_lanc = sum(1 for r in linhas if r[0] and r[0][:2].isdigit())
    st.success(f"✅ Arquivo lido: **{n_lanc} lançamentos**. Prévia do que será gravado:")
    prev = pd.DataFrame(linhas[8:], columns=linhas[8] if len(linhas) > 8 else None)
    st.dataframe(prev.iloc[1:], width="stretch", hide_index=True, height=320)
    st.caption(f"Destino: aba **{tab}** " +
               ("(o conteúdo atual será substituído)." if existe else "(aba nova será criada)."))

    if st.button("💾 Gravar na planilha", type="primary"):
        try:
            if existe:
                ws = get_spreadsheet().worksheet(tab)
                ws.clear()
            else:
                ws = get_spreadsheet().add_worksheet(
                    title=tab, rows=max(100, len(linhas) + 10), cols=8)
            ws.update(values=linhas, range_name="A1", value_input_option="RAW")
            st.cache_data.clear()
            st.success(f"Extrato da **{empresa}** gravado na aba '{tab}'! "
                       "Veja em 🔍 Extrato.")
            st.balloons()
        except Exception as e:
            st.error(f"Erro ao gravar: {e}")


# -----------------------------------------------------------------------------
# Dispatch
# -----------------------------------------------------------------------------
if view == "resumo":
    views.render_resumo(frames_or_warn(TAB_CP), frames_or_warn(TAB_CR),
                        frames_or_warn(TAB_FOLHA), load_extratos(),
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
elif view == "segmento":
    fr = frames_or_warn(TAB_SEGMENTO)
    if fr:
        views.render_segmento(fr)
elif view == "extrato":
    views.render_extrato(load_extratos())
elif view == "importar":
    render_importar()
elif view == "editar":
    render_editar()
