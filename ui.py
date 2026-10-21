# =============================================================================
# Elementos visuais: tema escuro, cards de KPI e estilo dos graficos.
# =============================================================================
import base64
import pathlib

import streamlit as st

_LOGO_PATH = pathlib.Path(__file__).parent / "logo" / "logo_roboteasy.png"


def logo_base64() -> str:
    """Retorna a logo em base64 (para embeds HTML). Vazio se nao encontrar."""
    try:
        return base64.b64encode(_LOGO_PATH.read_bytes()).decode()
    except Exception:
        return ""


def logo_img_tag(height: int = 48, style: str = "") -> str:
    """Tag <img> com a logo embutida em base64."""
    b64 = logo_base64()
    if not b64:
        return ""
    return (f'<img src="data:image/png;base64,{b64}" '
            f'height="{height}" style="object-fit:contain;{style}">')

# Paleta
PRIMARY = "#00D9A6"
GREEN = "#22C55E"
AMBER = "#FBBF24"
RED = "#F43F5E"
BLUE = "#3B82F6"
PURPLE = "#A855F7"
TEAL = "#14B8A6"
SLATE = "#64748B"
PINK = "#EC4899"

SEQ = [PRIMARY, BLUE, AMBER, PURPLE, TEAL, RED, PINK, SLATE]
STATUS_COLORS = {"Pago": GREEN, "Pendente": AMBER, "Vencido": RED, "Em aberto": AMBER}

_CSS = """
<style>
.block-container {padding-top: 2.2rem; padding-bottom: 2.5rem; max-width: 1400px;}
section[data-testid="stSidebar"] {background: #0B0E14;}
.kpi-grid {display:grid;grid-template-columns:repeat(auto-fit, minmax(165px, 1fr));
           gap:14px;margin-bottom:14px;}
.kpi {background:#161B26;border:1px solid #262D3D;border-radius:14px;
      padding:16px 18px;display:flex;flex-direction:column;gap:6px;height:100%;}
.kpi .lbl {color:#8A93A6;font-size:.72rem;font-weight:600;
           text-transform:uppercase;letter-spacing:.05em;}
.kpi .val {font-size:1.65rem;font-weight:700;line-height:1.1;}
.kpi .sub {color:#6B7280;font-size:.76rem;}
.kpi .accent {height:4px;border-radius:4px;margin-top:6px;}
h1,h2,h3 {letter-spacing:-.01em;}
hr {margin:1rem 0;border-color:#1E2433;}
.lblrow {display:flex;align-items:center;gap:5px;}
.tip {position:relative;display:inline-flex;align-items:center;cursor:help;}
.tip .ic {width:15px;height:15px;border-radius:50%;background:#2A3550;color:#AEB8C8;
          font-size:11px;line-height:15px;text-align:center;font-weight:700;
          font-style:italic;font-family:Georgia,serif;}
.tip .ic:hover {background:#3A4866;color:#EAF0F7;}
.tip .box {visibility:hidden;opacity:0;position:absolute;z-index:1000;bottom:160%;left:-6px;
           width:250px;background:#0F1420;border:1px solid #3A4866;color:#D9E0EA;
           padding:10px 12px;border-radius:10px;font-size:12px;font-weight:400;line-height:1.55;
           text-transform:none;letter-spacing:.2px;box-shadow:0 10px 30px rgba(0,0,0,.6);
           transition:opacity .15s ease;pointer-events:none;}
.tip:hover .box {visibility:visible;opacity:1;}
.tip .box b {color:#EAF0F7;}
.login-head {text-align:center;margin:2px 0 18px;}
.login-logo {display:flex;justify-content:center;align-items:center;
             margin-bottom:14px;padding:10px 0;}
.login-title {font-size:1.3rem;font-weight:700;margin-top:2px;}
.login-sub {color:#8A93A6;font-size:.84rem;margin-top:4px;}
div[data-testid="stForm"] {background:#161B26;border:1px solid #2D3748;
                           border-radius:16px;padding:28px 28px 22px;margin-top:7vh;
                           box-shadow:0 16px 48px rgba(0,0,0,.55);}

/* labels dos campos de login */
div[data-testid="stForm"] label p {
    color:#C7CEDB !important;
    font-size:.82rem !important;
    font-weight:600 !important;
    letter-spacing:.04em;
    text-transform:uppercase;
    margin-bottom:4px !important;
}
/* container externo do input */
div[data-testid="stForm"] div[data-testid="stTextInput"] > div,
div[data-testid="stForm"] div[data-testid="stTextInput"] > div > div {
    background:#0D1117 !important;
    border:2px solid #4A5E82 !important;
    border-radius:8px !important;
}
/* foco: borda verde + brilho */
div[data-testid="stForm"] div[data-testid="stTextInput"] > div:focus-within,
div[data-testid="stForm"] div[data-testid="stTextInput"] > div > div:focus-within {
    border-color:#00D9A6 !important;
    box-shadow:0 0 0 3px rgba(0,217,166,.2) !important;
}
/* garante que nenhum filho apague a borda */
div[data-testid="stForm"] div[data-testid="stTextInput"] * {
    border:none !important;
    background:transparent !important;
    outline:none !important;
    box-shadow:none !important;
}
div[data-testid="stForm"] div[data-testid="stTextInput"] > div,
div[data-testid="stForm"] div[data-testid="stTextInput"] > div > div {
    border:2px solid #4A5E82 !important;
    background:#0D1117 !important;
    border-radius:8px !important;
}
div[data-testid="stForm"] div[data-testid="stTextInput"] > div:focus-within,
div[data-testid="stForm"] div[data-testid="stTextInput"] > div > div:focus-within {
    border-color:#00D9A6 !important;
    box-shadow:0 0 0 3px rgba(0,217,166,.2) !important;
}
/* texto digitado e cursor */
div[data-testid="stForm"] div[data-testid="stTextInput"] input {
    color:#EAF0F7 !important;
    font-size:1rem !important;
    caret-color:#00D9A6 !important;
    background:transparent !important;
}
div[data-testid="stForm"] div[data-testid="stTextInput"] input::placeholder {
    color:#5A6880 !important;
}
/* espaçamento entre os campos */
div[data-testid="stForm"] div[data-testid="stTextInput"] {
    margin-bottom:14px;
}
</style>
"""


def inject_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def _tip(text):
    """HTML de um icone de ajuda (i) com tooltip no hover."""
    if not text:
        return ""
    safe = text.replace('"', "&quot;")
    return f'<span class="tip"><span class="ic">i</span><span class="box">{safe}</span></span>'


def kpi_row(cards):
    """cards = lista de dicts {label, value, color?, sub?, help?}.

    Renderiza todos os cards num grid CSS com espacamento uniforme (mesmo gap
    horizontal e vertical), em um unico bloco HTML.
    """
    partes = ["<div class='kpi-grid'>"]
    for c in cards:
        color = c.get("color", PRIMARY)
        sub = f'<div class="sub">{c["sub"]}</div>' if c.get("sub") else ""
        lbl = (f'<div class="lblrow"><span class="lbl">{c["label"]}</span>'
               f'{_tip(c.get("help"))}</div>')
        partes.append(
            f'<div class="kpi">{lbl}'
            f'<div class="val" style="color:{color}">{c["value"]}</div>'
            f'{sub}<div class="accent" style="background:{color}"></div></div>'
        )
    partes.append("</div>")
    st.markdown("".join(partes), unsafe_allow_html=True)


def style_fig(fig, height=330, legend=True):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=30, b=10, l=6, r=6),
        height=height,
        font=dict(color="#C7CEDB", size=12),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=-0.22, x=0, title=None),
        colorway=SEQ,
        # numeros no padrao BR: milhar "." e decimal ","
        separators=",.",
        hovermode="closest",
        hoverlabel=dict(
            bgcolor="#0F1420",
            bordercolor="#334155",
            font=dict(color="#EAF0F7", size=13, family="Segoe UI, Inter, sans-serif"),
            align="left",
            namelength=-1,
        ),
    )
    fig.update_xaxes(gridcolor="#20283A", zeroline=False, title=None)
    fig.update_yaxes(gridcolor="#20283A", zeroline=False, title=None, hoverformat=",.2f")
    return fig
