# =============================================================================
# Paineis (visoes) do dashboard. Cada funcao recebe Frames ja tratados.
# =============================================================================
import re

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import sheets_utils as su
import ui


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
_CHART = {"i": 0}


def _plot(fig, width="stretch", **_):
    """st.plotly_chart com chave unica (evita colisao de IDs em abas)."""
    _CHART["i"] += 1
    st.plotly_chart(fig, width=width, key=f"ch_{_CHART['i']}")


def _h(title, help=None):
    """Titulo de grafico/secao com icone de ajuda (?) no hover."""
    st.markdown(f"**{title}**", help=help)


def _group(fr, dim, val, top=None, asc=False):
    """Agrupa por uma categoria e soma um valor numerico."""
    d = fr.num.copy()
    d[dim] = d[dim].astype(str).str.strip()
    d = d[d[dim] != ""]
    g = d.groupby(dim, dropna=False)[val].sum().reset_index().sort_values(val, ascending=asc)
    return g.head(top) if top else g


def _empty(df):
    if df is None or len(df) == 0:
        st.caption("Sem dados no filtro atual.")
        return True
    return False


def _mt(fig, date=False, keepname=False, prefix="R$ "):
    """Hover unificado com data DD/MM/AAAA e valor em R$."""
    lx = "%{x|%d/%m/%Y}" if date else "%{x}"
    tail = "" if keepname else "<extra></extra>"
    fig.update_traces(hovertemplate=f"<b>{lx}</b><br>{prefix}%{{y:,.2f}}{tail}")
    return fig


# Raio dos cantos das barras (suporte Plotly 5.19+/7.x)
_CORNER = 6


def _bar(df, x, y, color=None, cmap=None, horizontal=False, height=330, legend=False,
         marker=None, money=True):
    if _empty(df):
        return
    if horizontal:
        fig = px.bar(df, x=y, y=x, orientation="h", color=color,
                     color_discrete_map=cmap, text_auto=".2s")
    else:
        fig = px.bar(df, x=x, y=y, color=color, color_discrete_map=cmap, text_auto=".2s")

    # cantos arredondados + sem borda + opacidade suave
    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        marker_line_width=0,
        opacity=0.92,
        marker_cornerradius=_CORNER,
        textfont=dict(size=11, color="#C7CEDB"),
    )
    if marker and color is None:
        fig.update_traces(marker_color=marker)

    if color is None:
        pref = "R$ " if money else ""
        dec = ":,.2f" if money else ":,.0f"
        if horizontal:
            fig.update_traces(
                hovertemplate=f"<b>%{{y}}</b><br>{pref}%{{x{dec}}}<extra></extra>")
        else:
            fig.update_traces(
                hovertemplate=f"<b>%{{x}}</b><br>{pref}%{{y{dec}}}<extra></extra>")

    _plot(ui.style_fig(fig, height, legend=legend or color is not None), width="stretch")


def _ranking_bar(grouped, dim, val, key, title, top=None, height=None, marker=None, help=None):
    """Ranking horizontal com controle de ordem."""
    st.markdown(f"**{title}**", help=help)
    if grouped is None or len(grouped) == 0:
        st.caption("Sem dados no filtro atual.")
        return
    n = min(top, len(grouped)) if top else len(grouped)
    ordem = st.radio("Ordem", ["Maior → menor", "Menor → maior"],
                     horizontal=True, key=f"{key}_ord")
    sel = grouped.sort_values(val, ascending=False).head(n)
    g = sel.sort_values(val, ascending=(ordem == "Maior → menor"))
    _bar(g, dim, val, horizontal=True, height=height or max(300, n * 26), marker=marker)


def _donut(df, names, values, cmap=None, height=330):
    if _empty(df):
        return
    fig = px.pie(df, names=names, values=values, hole=0.62, color=names,
                 color_discrete_map=cmap)
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        textfont=dict(size=12),
        marker=dict(line=dict(color="rgba(0,0,0,0)", width=0)),
        pull=[0.03] * len(df),  # leve separacao entre fatias
        hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent}<extra></extra>",
    )
    _plot(ui.style_fig(fig, height), width="stretch")


def _need(fr, *names):
    """Retorna os nomes reais das colunas pedidas (None se nao achar)."""
    return [su.find_col(fr.raw.columns, n) for n in names]


def _table(fr):
    with st.expander("📋 Ver tabela completa"):
        st.dataframe(fr.raw, width="stretch", hide_index=True)
        st.caption(f"{len(fr.raw)} linhas · {len(fr.raw.columns)} colunas · "
                   f"cabecalho na linha {fr.header_row + 1}")


def _builder(fr):
    with st.expander("🔧 Montar meu proprio grafico"):
        if not fr.nums:
            st.caption("Nenhuma coluna numerica nesta aba.")
            return
        dims = [c for c in fr.raw.columns if c not in fr.nums] or list(fr.raw.columns)
        c1, c2, c3 = st.columns(3)
        dim = c1.selectbox("Agrupar por", dims, key=f"b_dim_{id(fr)}")
        val = c2.selectbox("Valor", fr.nums, key=f"b_val_{id(fr)}")
        tp = c3.selectbox("Tipo", ["Barras", "Linha", "Pizza"], key=f"b_tp_{id(fr)}")
        g = _group(fr, dim, val).head(30)
        if tp == "Barras":
            _bar(g, dim, val)
        elif tp == "Linha":
            fig = px.line(g.sort_values(dim), x=dim, y=val, markers=True)
            fig.update_traces(line=dict(width=3, shape="spline", smoothing=1.2),
                              marker=dict(size=8, line=dict(width=2, color="#0E1117")))
            _plot(ui.style_fig(fig), width="stretch")
        else:
            _donut(g.head(12), dim, val)


# -----------------------------------------------------------------------------
# RESUMO EXECUTIVO (helpers)
# -----------------------------------------------------------------------------
def _empresa_col(fr):
    return su.find_col(fr.raw.columns, "EMPRESA", "Empresa",
                       "Minha Empresa (Nome Fantasia)", "Nome Fantasia")


def _filter_empresa(fr, empresa):
    if fr is None or empresa == "Todas":
        return fr
    col = _empresa_col(fr)
    if not col:
        return fr
    mask = fr.raw[col].astype(str).str.strip().str.upper() == empresa.upper()
    return su.Frames(fr.raw[mask].reset_index(drop=True),
                     fr.num[mask].reset_index(drop=True),
                     fr.nums, fr.dates, fr.first_row, fr.header_row)


def _filter_periodo(fr, date_names, d1, d2):
    if fr is None or d1 is None:
        return fr
    col = su.find_col(fr.raw.columns, *date_names)
    if not col:
        return fr
    dts = su.parse_dates(fr.raw[col])
    mask = ((dts.dt.date >= d1) & (dts.dt.date <= d2)).fillna(False)
    return su.Frames(fr.raw[mask].reset_index(drop=True),
                     fr.num[mask].reset_index(drop=True),
                     fr.nums, fr.dates, fr.first_row, fr.header_row)


def _sum(fr, *cands):
    if fr is None:
        return 0.0
    col = su.find_col(fr.num.columns, *cands)
    return float(fr.num[col].sum()) if col else 0.0


def _range_datas(pairs):
    mins, maxs = [], []
    for fr, dnames in pairs:
        if fr is None:
            continue
        col = su.find_col(fr.raw.columns, *dnames)
        if not col:
            continue
        dts = su.parse_dates(fr.raw[col]).dropna()
        if not dts.empty:
            mins.append(dts.min().date())
            maxs.append(dts.max().date())
    return (min(mins), max(maxs)) if mins else (None, None)


def _empresas_disponiveis(frames):
    vals = set()
    for fr in frames:
        if fr is None:
            continue
        col = _empresa_col(fr)
        if col:
            s = fr.raw[col].astype(str).str.strip().str.title()
            vals |= set(s[s != ""].unique())
    return ["Todas"] + sorted(vals)


def _by_empresa_sum(fr, emp_cands, val_cands):
    if fr is None:
        return {}
    ec = su.find_col(fr.raw.columns, *emp_cands)
    vc = su.find_col(fr.num.columns, *val_cands)
    if not ec or not vc:
        return {}
    d = fr.num.copy()
    d["_e"] = fr.raw[ec].astype(str).str.strip().str.title()
    d = d[d["_e"] != ""]
    return d.groupby("_e")[vc].sum().to_dict()


def _month_group(fr, date_names, val_names):
    if fr is None:
        return pd.DataFrame(columns=["m", "valor"])
    dcol = su.find_col(fr.raw.columns, *date_names)
    vcol = su.find_col(fr.num.columns, *val_names)
    if not dcol or not vcol:
        return pd.DataFrame(columns=["m", "valor"])
    m = su.parse_dates(fr.raw[dcol]).dt.to_period("M").astype(str)
    g = fr.num.assign(m=m)
    g = g[g["m"] != "NaT"].groupby("m")[vcol].sum().reset_index()
    g.columns = ["m", "valor"]
    return g


def _gauge(value, ref=1.0):
    vmax = max(1.5, min(3.0, value * 1.3)) if value and value > 0 else 1.5
    cor = ui.GREEN if value >= 1.2 else (ui.AMBER if value >= 0.8 else ui.RED)
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=value,
        delta={"reference": ref, "valueformat": ".2f",
               "increasing": {"color": ui.GREEN}, "decreasing": {"color": ui.RED}},
        number={"valueformat": ".2f", "font": {"size": 36, "color": cor}},
        gauge={
            "axis": {"range": [0, vmax], "tickwidth": 1, "tickcolor": "#4A5568",
                     "dtick": 0.5},
            "bar": {"color": cor, "thickness": 0.3},
            "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
            "steps": [
                {"range": [0, 0.8], "color": "rgba(244,63,94,0.18)"},
                {"range": [0.8, 1.2], "color": "rgba(251,191,36,0.18)"},
                {"range": [1.2, vmax], "color": "rgba(34,197,94,0.18)"},
            ],
            "threshold": {
                "line": {"color": "rgba(255,255,255,0.6)", "width": 2},
                "thickness": 0.82, "value": ref,
            },
        },
    ))
    fig.update_layout(margin=dict(t=20, b=0, l=20, r=20))
    _plot(ui.style_fig(fig, 240, legend=False), width="stretch")


def _waterfall(caixa, receber, pagar):
    final = caixa + receber - pagar
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "total"],
        x=["Caixa", "+ A Receber", "− A Pagar", "Projetado"],
        y=[caixa, receber, -pagar, 0],
        text=[su.format_brl(v) for v in [caixa, receber, -pagar, final]],
        textposition="outside",
        textfont=dict(size=11, color="#C7CEDB"),
        connector={"line": {"color": "rgba(100,116,139,0.4)", "width": 1.5,
                            "dash": "dot"}},
        increasing={"marker": {"color": ui.GREEN, "line": {"width": 0}}},
        decreasing={"marker": {"color": ui.RED, "line": {"width": 0}}},
        totals={"marker": {"color": ui.PRIMARY if final >= 0 else ui.RED,
                           "line": {"width": 0}}},
        opacity=0.9,
    ))
    _plot(ui.style_fig(fig, 300, legend=False), width="stretch")


def _aging_bar(fr, venc_col, val_col, hoje, height=320):
    dias = (su.parse_dates(fr.raw[venc_col]) - hoje).dt.days

    def bucket(d):
        if pd.isna(d):
            return "Sem data"
        if d < 0:
            return "Vencido"
        if d <= 30:
            return "0–30 dias"
        if d <= 60:
            return "31–60 dias"
        return "60+ dias"

    order = ["Vencido", "0–30 dias", "31–60 dias", "60+ dias", "Sem data"]
    cmap = {"Vencido": ui.RED, "0–30 dias": ui.AMBER, "31–60 dias": ui.BLUE,
            "60+ dias": ui.GREEN, "Sem data": ui.SLATE}
    g = fr.num.assign(_b=dias.map(bucket)).groupby("_b")[val_col].sum().reset_index()
    if _empty(g):
        return
    g["_o"] = g["_b"].map({k: i for i, k in enumerate(order)})
    g = g.sort_values("_o")
    fig = px.bar(g, x="_b", y=val_col, color="_b", color_discrete_map=cmap, text_auto=".2s")
    fig.update_traces(textposition="outside", cliponaxis=False)
    _mt(fig)
    _plot(ui.style_fig(fig, height, legend=False), width="stretch")


def _receita_despesa_empresa(cr, cp, fo=None):
    rec = _by_empresa_sum(cr, ["Minha Empresa (Nome Fantasia)", "Nome Fantasia"], ["A Receber"])
    # Despesa = VALOR do Contas a Pagar (que JA inclui a folha). Nao soma a aba Folha
    # de novo para evitar dupla contagem.
    dcp = _by_empresa_sum(cp, ["EMPRESA"], ["VALOR", "Valor"])
    empresas = sorted(set(rec) | set(dcp))
    if not empresas:
        st.caption("Sem dados.")
        return
    rows = []
    for e in empresas:
        rows.append({"Empresa": e, "Tipo": "Receita", "Valor": rec.get(e, 0)})
        rows.append({"Empresa": e, "Tipo": "Despesa", "Valor": dcp.get(e, 0)})
    g = pd.DataFrame(rows)
    fig = px.bar(g, x="Empresa", y="Valor", color="Tipo", barmode="group",
                 color_discrete_map={"Receita": ui.GREEN, "Despesa": ui.RED}, text_auto=".2s")
    fig.update_traces(textposition="outside", cliponaxis=False)
    _mt(fig, keepname=True)
    _plot(ui.style_fig(fig, 320, legend=True), width="stretch")


def _saldo_evolucao(ex):
    data = su.find_col(ex.raw.columns, "Data")
    saldo = su.find_col(ex.num.columns, "Saldo (R$)", "Saldo")
    if not data or not saldo:
        return
    d = ex.num.assign(_d=su.parse_dates(ex.raw[data])).dropna(subset=["_d"])
    if d.empty:
        return
    _h("Evolucao do saldo bancario no mes",
       "Saldo da conta ao fim de cada dia (último 'Saldo' de cada data no Extrato). "
       "A linha pontilhada é o zero: abaixo dela, a conta está no cheque especial.")
    g = d.groupby("_d")[saldo].last().reset_index().sort_values("_d")
    cor = ui.GREEN if g[saldo].iloc[-1] >= 0 else ui.RED
    fig = px.area(g, x="_d", y=saldo, markers=True)
    fig.update_traces(
        line=dict(color=cor, width=3, shape="spline", smoothing=1.1),
        fillcolor=f"rgba({','.join(str(int(cor.lstrip('#')[i:i+2],16)) for i in (0,2,4))},0.12)",
        marker=dict(size=7, color=cor, line=dict(width=2, color="#0E1117")),
    )
    _mt(fig, date=True)
    fig.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.2)", line_width=1)
    _plot(ui.style_fig(fig, 300, legend=False), width="stretch")


def _alertas(caixa, a_pagar, a_receber, venc_n, venc_val, liquidez, crf, cpf):
    criticos, avisos, infos = [], [], []
    if caixa < 0:
        criticos.append(f"**Saldo bancario negativo:** {su.format_brl(caixa)} — "
                        "a conta esta usando limite/cheque especial.")
    if venc_n > 0:
        criticos.append(f"**{venc_n} conta(s) vencida(s)** somando {su.format_brl(venc_val)}.")
    if liquidez and liquidez < 1:
        avisos.append(f"**Liquidez imediata em {liquidez:.2f}** (abaixo de 1,00): "
                      "caixa + a receber nao cobrem o total a pagar.")
    if a_pagar > a_receber:
        avisos.append(f"**A pagar supera a receber** em "
                      f"{su.format_brl(a_pagar - a_receber)} no periodo.")
    if crf is not None:
        cli = su.find_col(crf.raw.columns, "Razão Social", "Razao Social", "Cliente")
        ar = su.find_col(crf.num.columns, "A Receber")
        if cli and ar and len(crf.num) and crf.num[ar].notna().any():
            i = crf.num[ar].idxmax()
            infos.append(f"Maior recebivel: **{crf.raw.loc[i, cli]}** — "
                         f"{su.format_brl(crf.num.loc[i, ar])}.")
    if cpf is not None:
        forn = su.find_col(cpf.raw.columns, "FORNECEDOR", "Fornecedor")
        sal = su.find_col(cpf.num.columns, "Saldo")
        if forn and sal and len(cpf.num) and cpf.num[sal].notna().any():
            i = cpf.num[sal].idxmax()
            infos.append(f"Maior conta a pagar: **{cpf.raw.loc[i, forn]}** — "
                         f"{su.format_brl(cpf.num.loc[i, sal])}.")
    for t in criticos:
        st.error("🔴 " + t)
    for t in avisos:
        st.warning("⚠️ " + t)
    for t in infos:
        st.info("ℹ️ " + t)
    if not criticos and not avisos:
        st.success("✅ Sem alertas criticos no periodo.")


# -----------------------------------------------------------------------------
# RESUMO EXECUTIVO
# -----------------------------------------------------------------------------
def render_resumo(cp, cr, fo, extratos, rb=None):
    st.subheader("🎯 Resumo Executivo")
    hoje = pd.Timestamp.today().normalize()
    st.caption(f"Posicao consolidada · {hoje.strftime('%d/%m/%Y')}")

    # ---------- Filtros ----------
    empresas = _empresas_disponiveis([cp, cr, fo])
    dmin, dmax = _range_datas([(cp, ["DIA", "Vencimento"]), (cr, ["Vencimento"]),
                               (rb, ["Vencimento"])])
    fc1, fc2 = st.columns([1.3, 2])
    with fc1:
        empresa = st.radio("Empresa", empresas, horizontal=True, key="flt_empresa")
    with fc2:
        if dmin and dmax and dmin < dmax:
            periodo = st.date_input("Periodo (por vencimento)", (dmin, dmax),
                                    min_value=dmin, max_value=dmax,
                                    format="DD/MM/YYYY", key="flt_periodo")
            d1, d2 = periodo if isinstance(periodo, (list, tuple)) and len(periodo) == 2 \
                else (dmin, dmax)
        else:
            d1, d2 = dmin, dmax

    cpf = _filter_periodo(_filter_empresa(cp, empresa), ["DIA", "Vencimento"], d1, d2)
    crf = _filter_periodo(_filter_empresa(cr, empresa), ["Vencimento"], d1, d2)
    fof = _filter_empresa(fo, empresa)

    # ---------- Numeros ----------
    def _caixa_de(frame):
        if frame is None:
            return 0.0
        cc = su.find_col(frame.num.columns, "Saldo (R$)", "Saldo")
        if not cc:
            return 0.0
        s = frame.num[cc].dropna()
        return float(s.iloc[-1]) if not s.empty else 0.0

    extratos = extratos or {}
    if empresa == "Todas":
        caixa = sum(_caixa_de(f) for f in extratos.values())
    else:
        caixa = _caixa_de(extratos.get(empresa))
    a_receber = _sum(crf, "A Receber")
    if rb is not None:  # "Recebido" vem da aba dedicada "Recebidos"
        rbf = _filter_periodo(_filter_empresa(rb, empresa), ["Vencimento"], d1, d2)
        recebido = _sum(rbf, "Recebido")
    else:
        recebido = _sum(crf, "Recebido")
    a_pagar = _sum(cpf, "Saldo")
    total_pagar = _sum(cpf, "VALOR", "Valor")  # total do mes (ja inclui a folha)
    pago = _sum(cpf, "Valor pago")
    folha = _sum(fof, "PROJEÇÃO", "Projeção", "PROJECAO")  # custo mensal real
    if not folha:
        folha = _sum(fof, "VALOR", "Valor")
    resultado = a_receber - a_pagar
    projetado = caixa + a_receber - a_pagar
    liquidez = (caixa + a_receber) / a_pagar if a_pagar else 0.0
    pct_receb = recebido / (recebido + a_receber) * 100 if (recebido + a_receber) else 0
    pct_pago = pago / (pago + a_pagar) * 100 if (pago + a_pagar) else 0

    stt = su.find_col(cpf.raw.columns, "Status") if cpf is not None else None
    venc_val, venc_n = 0.0, 0
    if stt:
        vmask = cpf.raw[stt].astype(str).str.strip().str.lower() == "vencido"
        sal_c = su.find_col(cpf.num.columns, "Saldo")
        venc_val = float(cpf.num.loc[vmask, sal_c].sum()) if sal_c else 0.0
        venc_n = int(vmask.sum())

    # ---------- KPIs ----------
    ui.kpi_row([
        {"label": "Saldo em Caixa", "value": su.format_brl(caixa),
         "color": ui.GREEN if caixa >= 0 else ui.RED,
         "sub": "conta corrente" + (" (grupo)" if empresa == "Todas" else f" ({empresa})"),
         "help": "Dinheiro disponível hoje. É o último saldo do extrato de cada empresa. "
                 "Com empresa = Todas, soma as duas contas; filtrando por empresa, mostra "
                 "só a dela."},
        {"label": "A Receber", "value": su.format_brl(a_receber), "color": ui.GREEN,
         "help": "Quanto os clientes ainda devem. Soma da coluna 'A Receber' dos títulos "
                 "em aberto (aba CR em aberto), respeitando os filtros acima."},
        {"label": "A Pagar (em aberto)", "value": su.format_brl(a_pagar), "color": ui.RED,
         "help": "Quanto você ainda deve. Soma da coluna 'Saldo' (= VALOR − Valor pago) das "
                 "Contas a Pagar ainda em aberto."},
        {"label": "Folha", "value": su.format_brl(folha), "color": ui.BLUE,
         "help": "Custo mensal com consultores (soma da coluna PROJEÇÃO da aba Folha). "
                 "Obs.: este valor já está DENTRO do Contas a Pagar (linha 'Folha'), "
                 "então não deve ser somado a 'A Pagar' nem a 'Obrigações do mês'."},
        {"label": "Resultado (Rec − Pag)", "value": su.format_brl(resultado),
         "color": ui.GREEN if resultado >= 0 else ui.RED,
         "help": "A Receber − A Pagar. Positivo = há mais a receber do que a pagar no período."},
    ])
    ui.kpi_row([
        {"label": "Obrigações do mês", "value": su.format_brl(total_pagar),
         "color": ui.PINK, "sub": "total a pagar (já inclui folha)",
         "help": "Total de compromissos do mês = soma de VALOR do Contas a Pagar (contas "
                 "pagas + a pagar). JÁ INCLUI a folha (há uma linha 'Folha' no Contas a "
                 "Pagar), impostos e fornecedores — por isso NÃO se soma a folha de novo. "
                 "É o mesmo 'Total a Pagar' da tela Contas a Pagar."},
        {"label": "Saldo Projetado", "value": su.format_brl(projetado),
         "color": ui.GREEN if projetado >= 0 else ui.RED,
         "sub": "caixa + receber − pagar",
         "help": "Estimativa do caixa após receber os títulos em aberto e pagar as contas "
                 "em aberto. Conta: Saldo em Caixa + A Receber − A Pagar. A Folha aparece "
                 "como indicador à parte (e já está refletida nas contas a pagar/extrato)."},
        {"label": "Recebido", "value": su.format_brl(recebido),
         "color": ui.TEAL, "sub": f"{pct_receb:.0f}% do faturado",
         "help": "Quanto já entrou de clientes. Soma da coluna 'Recebido' da aba Recebidos. "
                 "O % = Recebido ÷ (Recebido + A Receber)."},
        {"label": "Pago", "value": su.format_brl(pago),
         "color": ui.TEAL, "sub": f"{pct_pago:.0f}% do total",
         "help": "Quanto já foi pago a fornecedores. Soma de 'Valor pago' das Contas a Pagar. "
                 "O % = Pago ÷ (Pago + A Pagar em aberto)."},
        {"label": f"Contas Vencidas ({venc_n})", "value": su.format_brl(venc_val),
         "color": ui.RED, "sub": "contas a pagar em atraso",
         "help": "Contas a pagar já vencidas e não quitadas. Soma do 'Saldo' das contas com "
                 "Status = Vencido. O número entre parênteses é a quantidade."},
    ])

    st.divider()

    # ---------- Saude: liquidez + projecao ----------
    g1, g2 = st.columns([1, 1.8])
    with g1:
        _h("Liquidez imediata",
           "Mede se o dinheiro disponível cobre o que você deve. Conta: "
           "(Saldo em Caixa + A Receber) ÷ A Pagar. Acima de 1,00 = cobre; "
           "abaixo de 1,00 = não cobre.")
        _gauge(liquidez)
        st.caption("(Caixa + A Receber) ÷ A Pagar · acima de 1,00 cobre o que deve.")
    with g2:
        _h("Projecao de caixa",
           "Mostra, passo a passo, como o caixa fica após movimentar o que está em aberto: "
           "Saldo atual → soma A Receber → subtrai A Pagar → Saldo projetado.")
        _waterfall(caixa, a_receber, a_pagar)

    # ---------- Linha do tempo ----------
    _h("Recebimentos × Pagamentos por mes (vencimento)",
       "Compara, por mês de vencimento, o que entra (A Receber, verde) e o que sai "
       "(A Pagar em aberto, vermelho). Ajuda a antecipar meses apertados de caixa.")
    rec = _month_group(crf, ["Vencimento"], ["A Receber"]).rename(columns={"valor": "A Receber"})
    pag = _month_group(cpf, ["DIA", "Vencimento"], ["Saldo"]).rename(columns={"valor": "A Pagar"})
    tl = pd.merge(rec, pag, on="m", how="outer").fillna(0).sort_values("m")
    if not tl.empty:
        tlm = tl.melt("m", var_name="Tipo", value_name="Valor")
        fig = px.bar(tlm, x="m", y="Valor", color="Tipo", barmode="group",
                     color_discrete_map={"A Receber": ui.GREEN, "A Pagar": ui.RED},
                     text_auto=".2s")
        fig.update_traces(textposition="outside", cliponaxis=False)
        _mt(fig, keepname=True)
        _plot(ui.style_fig(fig, 320, legend=True), width="stretch")
    else:
        st.caption("Sem dados no filtro atual.")

    # ---------- Status & aging ----------
    c1, c2 = st.columns(2)
    with c1:
        val = su.find_col(cpf.num.columns, "VALOR", "Valor") if cpf is not None else None
        if stt and val:
            _h("Contas a Pagar por status",
               "Divide o total das contas a pagar (coluna VALOR) pelo Status: "
               "Pago, Pendente (a vencer) e Vencido. Cada fatia é a soma de VALOR daquele status.")
            _donut(_group(cpf, stt, val), stt, val, cmap=ui.STATUS_COLORS)
    with c2:
        venc = su.find_col(crf.raw.columns, "Vencimento") if crf is not None else None
        ar = su.find_col(crf.num.columns, "A Receber") if crf is not None else None
        if venc and ar:
            _h("A Receber por prazo (aging)",
               "Agrupa o 'A Receber' pela distância até o vencimento (hoje − Vencimento): "
               "já vencido, ou a vencer em 0–30, 31–60 e 60+ dias. Mostra quando o dinheiro entra.")
            _aging_bar(crf, venc, ar, hoje)

    # ---------- Rankings ----------
    c3, c4 = st.columns(2)
    with c3:
        cli = su.find_col(crf.raw.columns, "Razão Social", "Razao Social", "Cliente") if crf is not None else None
        ar = su.find_col(crf.num.columns, "A Receber") if crf is not None else None
        if cli and ar:
            _ranking_bar(_group(crf, cli, ar), cli, ar, "res_cli",
                         "Top 5 clientes a receber", top=5, height=300,
                         help="Os 5 clientes com maior valor a receber. Soma de 'A Receber' "
                              "por cliente (Razão Social), mostrando os 5 maiores.")
    with c4:
        forn = su.find_col(cpf.raw.columns, "FORNECEDOR", "Fornecedor") if cpf is not None else None
        sal = su.find_col(cpf.num.columns, "Saldo") if cpf is not None else None
        if forn and sal:
            _ranking_bar(_group(cpf, forn, sal), forn, sal, "res_forn",
                         "Top 5 fornecedores a pagar", top=5, height=300,
                         help="Os 5 fornecedores com maior valor em aberto. Soma do 'Saldo' "
                              "(em aberto) por fornecedor, mostrando os 5 maiores.")

    # ---------- Folha & empresas ----------
    c5, c6 = st.columns(2)
    with c5:
        setor = su.find_col(fof.raw.columns, "SETOR", "Setor") if fof is not None else None
        fval = (su.find_col(fof.num.columns, "PROJEÇÃO", "Projeção", "PROJECAO")
                or su.find_col(fof.num.columns, "VALOR", "Valor")) if fof is not None else None
        if setor and fval:
            _h("Folha por setor",
               "Custo mensal da folha dividido por setor. Soma da coluna PROJEÇÃO "
               "(custo de cada consultor) agrupada pelo SETOR.")
            _bar(_group(fof, setor, fval, asc=True), setor, fval, horizontal=True, height=320)
    with c6:
        _h("Receita × Despesa por empresa",
           "Por empresa: Receita = soma de 'A Receber' (clientes). Despesa = soma de VALOR "
           "do Contas a Pagar (que já inclui a folha). Compara quem gera e quem consome caixa.")
        _receita_despesa_empresa(cr, cp, fo)

    # ---------- Evolucao do saldo ----------
    ev = (extratos.get(empresa) if empresa != "Todas"
          else next((f for f in extratos.values() if f is not None), None))
    if ev is not None:
        _saldo_evolucao(ev)

    # ---------- Alertas ----------
    st.divider()
    st.markdown("### 🚨 Alertas e destaques")
    _alertas(caixa, a_pagar, a_receber, venc_n, venc_val, liquidez, crf, cpf)


# -----------------------------------------------------------------------------
# CONTAS A PAGAR (helpers + view)
# -----------------------------------------------------------------------------
def _styled_table(disp, money_cols=(), status_col=None, sign_cols=(), height=None):
    """Tabela com valores em R$, Status colorido e/ou valores coloridos por sinal."""
    money = [c for c in money_cols if c and c in disp.columns]
    sty = disp.style.format(
        {c: su.format_brl for c in money},
        na_rep="—",
    )
    if status_col and status_col in disp.columns:
        cores = {"Pago": ui.GREEN, "Pendente": ui.AMBER, "Vencido": ui.RED,
                 "Faturado": ui.TEAL, "Faturar": ui.AMBER}

        def _c(v):
            cor = cores.get(str(v).strip())
            return f"color:{cor};font-weight:600" if cor else ""

        sty = sty.map(_c, subset=[status_col])
    for sc in sign_cols:
        if sc and sc in disp.columns:
            def _sign(v):
                try:
                    x = float(v)
                except (TypeError, ValueError):
                    return ""
                return f"color:{ui.GREEN if x >= 0 else ui.RED};font-weight:600"

            sty = sty.map(_sign, subset=[sc])
    kwargs = {"width": "stretch", "hide_index": True}
    if height is not None:
        kwargs["height"] = height
    st.dataframe(sty, **kwargs)


def _pareto(d, dim, val, top=20):
    p = d.groupby(dim)[val].sum().reset_index()
    p = p[p[val] > 0].sort_values(val, ascending=False).head(top)
    if p.empty:
        st.caption("Sem dados.")
        return
    p["cum"] = p[val].cumsum() / p[val].sum() * 100
    fig = go.Figure()
    fig.add_bar(x=p[dim], y=p[val], name="Valor", marker_color=ui.BLUE,
                marker_line_width=0, opacity=0.88,
                marker_cornerradius=_CORNER,
                hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>")
    fig.add_scatter(x=p[dim], y=p["cum"], name="% acumulado", yaxis="y2",
                    mode="lines+markers",
                    line=dict(color=ui.AMBER, width=3, shape="spline", smoothing=1.1),
                    marker=dict(size=7, color=ui.AMBER,
                                line=dict(width=2, color="#0E1117")),
                    hovertemplate="<b>%{x}</b><br>Acumulado: %{y:.1f}%<extra></extra>")
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", range=[0, 105],
                                  ticksuffix="%", showgrid=False))
    _plot(ui.style_fig(fig, 380, legend=True), width="stretch")


def render_contas_pagar(fr):
    st.subheader("🔴 Contas a Pagar — Gestão")
    hoje = pd.Timestamp.today().normalize()

    semana = su.find_col(fr.raw.columns, "Semana")
    dia = su.find_col(fr.raw.columns, "DIA", "Vencimento", "Data")
    empresa = su.find_col(fr.raw.columns, "EMPRESA", "Empresa")
    forn = su.find_col(fr.raw.columns, "FORNECEDOR", "Fornecedor")
    desc = su.find_col(fr.raw.columns, "DESCRIÇÃO", "Descrição", "Descricao")
    equipe = su.find_col(fr.raw.columns, "Equipe", "Centro de custo")
    valor = su.find_col(fr.num.columns, "VALOR", "Valor")
    pago = su.find_col(fr.num.columns, "Valor pago", "Pago")
    saldo = su.find_col(fr.num.columns, "Saldo")
    status = su.find_col(fr.raw.columns, "Status")

    if not saldo or not valor:
        st.warning("Não encontrei as colunas VALOR/Saldo nesta aba.")
        _table(fr)
        return

    # ---------- Filtros ----------
    def opts(col):
        if not col:
            return []
        s = fr.raw[col].astype(str).str.strip()
        return sorted(s[s != ""].unique())

    st.markdown("##### 🔎 Filtros")
    f1, f2, f3 = st.columns([1, 1.1, 1.5])
    sel_emp = f1.multiselect("Empresa", opts(empresa), default=opts(empresa), key="cp_emp")
    sel_st = f2.multiselect("Status", opts(status), default=opts(status), key="cp_st")
    busca = f3.text_input("Buscar fornecedor / descrição", key="cp_busca")

    dmin = dmax = None
    if dia:
        dts = su.parse_dates(fr.raw[dia]).dropna()
        if not dts.empty:
            dmin, dmax = dts.min().date(), dts.max().date()
    if dmin and dmax and dmin < dmax:
        d1, d2 = st.slider("Período (vencimento)", dmin, dmax, (dmin, dmax),
                           format="DD/MM/YYYY", key="cp_per")
    else:
        d1, d2 = dmin, dmax

    # ---------- Aplica filtros ----------
    d = fr.num.copy()
    if empresa:
        d = d[d[empresa].astype(str).str.strip().isin(sel_emp)]
    if status:
        d = d[d[status].astype(str).str.strip().isin(sel_st)]
    if busca:
        campos = [c for c in [forn, desc] if c]
        m = pd.Series(False, index=d.index)
        for c in campos:
            m |= d[c].astype(str).str.contains(busca, case=False, na=False)
        d = d[m]
    if dia and d1:
        vv = su.parse_dates(d[dia])
        d = d[((vv.dt.date >= d1) & (vv.dt.date <= d2)).fillna(False)]
    if d.empty:
        st.warning("Nenhuma conta corresponde aos filtros.")
        return

    venc_dt = su.parse_dates(d[dia]) if dia else pd.Series(pd.NaT, index=d.index)
    d = d.assign(_venc=venc_dt, _atraso=(hoje - venc_dt).dt.days)
    s = d[status].astype(str).str.strip() if status else pd.Series("", index=d.index)
    is_venc = s.str.lower() == "vencido"
    is_pend = s.str.lower() == "pendente"

    total = d[valor].sum()
    pago_t = d[pago].sum() if pago else 0
    aberto = d[saldo].sum()
    venc_val = d.loc[is_venc, saldo].sum()
    venc_n = int(is_venc.sum())
    pend_val = d.loc[is_pend, saldo].sum()
    prox7 = d[(d["_venc"] >= hoje) & (d["_venc"] <= hoje + pd.Timedelta(days=7)) & (d[saldo] > 0)]
    vence7 = prox7[saldo].sum()
    pct_pago = pago_t / total * 100 if total else 0
    n_forn = d[forn].astype(str).str.strip().replace("", pd.NA).nunique() if forn else 0
    ticket = total / len(d) if len(d) else 0

    ui.kpi_row([
        {"label": "Total a Pagar", "value": su.format_brl(total), "color": ui.BLUE,
         "sub": f"{len(d)} contas",
         "help": "Valor total das contas no filtro. Soma da coluna VALOR (valor cheio de "
                 "cada conta, pago ou não)."},
        {"label": "Pago", "value": su.format_brl(pago_t), "color": ui.GREEN,
         "sub": f"{pct_pago:.0f}% do total",
         "help": "Quanto já foi pago. Soma da coluna 'Valor pago'. O % = Pago ÷ Total a Pagar."},
        {"label": "Em aberto", "value": su.format_brl(aberto), "color": ui.AMBER,
         "help": "Quanto ainda falta pagar. Soma da coluna 'Saldo' (= VALOR − Valor pago)."},
        {"label": f"Vencido ({venc_n})", "value": su.format_brl(venc_val), "color": ui.RED,
         "sub": "em atraso",
         "help": "Contas já vencidas e em aberto. Soma do 'Saldo' das contas com Status = "
                 "Vencido. O número é a quantidade de contas."},
    ])
    ui.kpi_row([
        {"label": "A vencer", "value": su.format_brl(pend_val), "color": ui.TEAL,
         "sub": "pendentes",
         "help": "Contas ainda no prazo. Soma do 'Saldo' das contas com Status = Pendente."},
        {"label": "Vence em 7 dias", "value": su.format_brl(vence7), "color": ui.AMBER,
         "sub": f"{len(prox7)} contas",
         "help": "Contas em aberto que vencem de hoje até 7 dias à frente. Soma do 'Saldo' "
                 "das contas com vencimento (DIA) nesse intervalo."},
        {"label": "Ticket médio", "value": su.format_brl(ticket), "color": ui.SLATE,
         "help": "Valor médio por conta. Conta: Total a Pagar ÷ número de contas."},
        {"label": "Fornecedores", "value": str(n_forn), "color": ui.PURPLE,
         "help": "Quantidade de fornecedores diferentes no filtro (valores únicos da "
                 "coluna FORNECEDOR)."},
    ])
    st.divider()

    t1, t2, t3, t4 = st.tabs(
        ["🖥️ Visão Geral", "🔗 Fornecedores", "📡 Vencimentos", "🗂️ Detalhado"])

    # ===== Visão Geral =====
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            if status:
                _h("Em aberto por status",
                   "Divide o valor em aberto (coluna 'Saldo') pelo Status: Pendente (a vencer) "
                   "e Vencido. Cada fatia é a soma do Saldo daquele status.")
                _donut(_dgroup(d, status, saldo), status, saldo, cmap=ui.STATUS_COLORS)
        with c2:
            _h("Aging de vencidos (dias em atraso)",
               "Só as contas vencidas, agrupadas por quanto tempo estão em atraso "
               "(hoje − vencimento): 1–15, 16–30, 31–60 e 60+ dias. Barra = soma do Saldo.")
            vr = d[is_venc]
            if vr.empty:
                st.caption("Nenhuma conta vencida no filtro. 🎉")
            else:
                def bk(a):
                    if pd.isna(a):
                        return "Sem data"
                    if a <= 15:
                        return "1–15 dias"
                    if a <= 30:
                        return "16–30 dias"
                    if a <= 60:
                        return "31–60 dias"
                    return "60+ dias"

                ordem = ["1–15 dias", "16–30 dias", "31–60 dias", "60+ dias", "Sem data"]
                cmap = {"1–15 dias": ui.AMBER, "16–30 dias": "#FB7185",
                        "31–60 dias": ui.RED, "60+ dias": "#B91C1C", "Sem data": ui.SLATE}
                g = vr.assign(_b=vr["_atraso"].map(bk)).groupby("_b")[saldo].sum().reset_index()
                g["_o"] = g["_b"].map({k: i for i, k in enumerate(ordem)})
                g = g.sort_values("_o")
                fig = px.bar(g, x="_b", y=saldo, color="_b", color_discrete_map=cmap,
                             text_auto=".2s")
                fig.update_traces(textposition="outside", cliponaxis=False)
                _mt(fig)
                _plot(ui.style_fig(fig, 330, legend=False), width="stretch")

        if semana:
            _h("Desembolso em aberto por semana do mês",
               "Quanto ainda falta pagar em cada semana do mês. Soma do 'Saldo' (em aberto) "
               "agrupado pela coluna Semana, empilhado por status.")
            dd = d[d[saldo] > 0].copy()
            dd[semana] = dd[semana].astype(str).str.strip()
            by = [semana, status] if status else [semana]
            g = dd.groupby(by)[saldo].sum().reset_index()
            g["_k"] = g[semana].str.extract(r"(\d+)").astype(float)
            g = g.sort_values("_k")
            fig = px.bar(g, x=semana, y=saldo, color=(status if status else None),
                         barmode="stack", color_discrete_map=ui.STATUS_COLORS, text_auto=".2s")
            _mt(fig, keepname=bool(status))
            _plot(ui.style_fig(fig, 320, legend=bool(status)), width="stretch")

        if empresa and status:
            _h("Em aberto por empresa e status",
               "Valor em aberto ('Saldo') por empresa (Roboteasy/Agapys), empilhado por "
               "status (Pendente/Vencido). Mostra onde está concentrada a dívida.")
            dd = d.copy()
            dd[empresa] = dd[empresa].astype(str).str.strip()
            dd[status] = dd[status].astype(str).str.strip()
            g = dd.groupby([empresa, status])[saldo].sum().reset_index()
            fig = px.bar(g, x=empresa, y=saldo, color=status, barmode="stack",
                         color_discrete_map=ui.STATUS_COLORS, text_auto=".2s")
            _mt(fig, keepname=True)
            _plot(ui.style_fig(fig, 320, legend=True), width="stretch")

    # ===== Fornecedores =====
    with t2:
        if forn:
            _ranking_bar(_dgroup(d, forn, saldo), forn, saldo, "cp_forn",
                         "Fornecedores por valor em aberto", top=15, height=460,
                         help="Soma do 'Saldo' (em aberto) por fornecedor, do maior para o "
                              "menor. Mostra de quem você mais deve.")
            _h("Concentração (Pareto) — maiores fornecedores",
               "Barras = valor em aberto por fornecedor (maior→menor). A linha é o % "
               "acumulado: mostra quantos fornecedores concentram a maior parte da dívida "
               "(regra 80/20).")
            _pareto(d, forn, saldo)
        if equipe:
            eq = d.copy()
            eq[equipe] = eq[equipe].astype(str).str.strip()
            eq = eq[eq[equipe] != ""]
            if not eq.empty:
                _h("Por equipe / centro de custo (quando preenchido)",
                   "Valor em aberto ('Saldo') somado por Equipe/centro de custo. Só considera "
                   "as contas que têm esse campo preenchido.")
                _bar(_dgroup(eq, equipe, saldo, asc=True), equipe, saldo,
                     horizontal=True, height=300)

    # ===== Vencimentos =====
    with t3:
        if dia:
            _h("Linha do tempo de vencimentos (em aberto)",
               "Valor a pagar ('Saldo') em cada data de vencimento (coluna DIA). A linha "
               "pontilhada marca o dia de hoje: à esquerda já venceu, à direita vai vencer.")
            dd = d[d[saldo] > 0].dropna(subset=["_venc"])
            if dd.empty:
                st.caption("Sem contas em aberto no filtro.")
            else:
                by = ["_venc", status] if status else ["_venc"]
                g = dd.groupby(by)[saldo].sum().reset_index()
                fig = px.bar(g, x="_venc", y=saldo, color=(status if status else None),
                             color_discrete_map=ui.STATUS_COLORS)
                _mt(fig, date=True, keepname=bool(status))
                fig.add_vline(x=hoje, line_dash="dot", line_color="#E6EAF1")
                _plot(ui.style_fig(fig, 320, legend=bool(status)), width="stretch")

        cc1, cc2 = st.columns(2)
        with cc1:
            _h("🔴 Vencidas (maior atraso primeiro)",
               "Lista das contas com Status = Vencido, da mais atrasada para a menos. "
               "'Atraso (dias)' = hoje − vencimento (DIA).")
            vr = d[is_venc].sort_values("_atraso", ascending=False)
            if vr.empty:
                st.caption("Nenhuma conta vencida. 🎉")
            else:
                disp = vr.assign(**{"Atraso (dias)": vr["_atraso"].astype("Int64")})
                cols = [c for c in [dia, forn, desc, "Atraso (dias)", saldo] if c]
                _styled_table(disp[cols], money_cols=[saldo])
        with cc2:
            _h("🟡 Próximos vencimentos (a vencer)",
               "Contas ainda em aberto que vão vencer, da mais próxima para a mais distante. "
               "'Faltam (dias)' = vencimento (DIA) − hoje.")
            pr = d[(d["_venc"] >= hoje) & (d[saldo] > 0)].sort_values("_venc")
            if pr.empty:
                st.caption("Sem contas a vencer no filtro.")
            else:
                disp = pr.assign(**{"Faltam (dias)": (-pr["_atraso"]).astype("Int64")})
                cols = [c for c in [dia, forn, desc, "Faltam (dias)", saldo] if c]
                _styled_table(disp[cols], money_cols=[saldo])

    # ===== Detalhado =====
    with t4:
        _h("Todas as contas (conforme filtros)",
           "A tabela completa das contas a pagar que passam pelos filtros. Valores em R$ e "
           "Status colorido. Use o botão abaixo para baixar em CSV/Excel.")
        dd = d.sort_values("_venc" if dia else saldo)
        cols = [c for c in [semana, dia, empresa, forn, desc, equipe,
                            valor, pago, saldo, status] if c]
        _styled_table(dd[cols], money_cols=[valor, pago, saldo], status_col=status)
        st.download_button("⬇️ Baixar CSV", dd[cols].to_csv(index=False).encode("utf-8-sig"),
                           "contas_a_pagar.csv", "text/csv", key="cp_csv")
        st.caption(f"{len(dd)} contas no filtro.")


# -----------------------------------------------------------------------------
# CONTAS A RECEBER (CR em aberto)
# -----------------------------------------------------------------------------
def render_contas_receber(fr, rb=None):
    st.subheader("⚡ Contas a Receber — Gestão")
    hoje = pd.Timestamp.today().normalize()

    cli = su.find_col(fr.raw.columns, "Razão Social", "Razao Social", "Cliente")
    venc = su.find_col(fr.raw.columns, "Vencimento")
    prev = su.find_col(fr.raw.columns, "Previsão", "Previsao")
    origem = su.find_col(fr.raw.columns, "Origem")
    doc = su.find_col(fr.raw.columns, "Documento", "Número", "Numero")
    areceber = su.find_col(fr.num.columns, "A Receber")
    bruto = su.find_col(fr.num.columns, "Valor da Conta")
    liquido = su.find_col(fr.num.columns, "Valor Líquido", "Valor Liquido", "Líquido", "Liquido")

    if not areceber:
        st.warning("Não encontrei a coluna 'A Receber' nesta aba.")
        _table(fr)
        return

    AGING = ["Vencido", "Vence ≤ 7d", "8–15 dias", "16–30 dias", "30+ dias", "Sem data"]
    ACMAP = {"Vencido": ui.RED, "Vence ≤ 7d": ui.AMBER, "8–15 dias": ui.BLUE,
             "16–30 dias": ui.TEAL, "30+ dias": ui.GREEN, "Sem data": ui.SLATE}

    def bucket(a):
        if pd.isna(a):
            return "Sem data"
        if a > 0:
            return "Vencido"
        if a >= -7:
            return "Vence ≤ 7d"
        if a >= -15:
            return "8–15 dias"
        if a >= -30:
            return "16–30 dias"
        return "30+ dias"

    # ---------- Filtros ----------
    def opts(col):
        if not col:
            return []
        s = fr.raw[col].astype(str).str.strip()
        return sorted(s[s != ""].unique())

    st.markdown("##### 🔎 Filtros")
    f1, f2, f3 = st.columns([1.2, 1, 1.3])
    sel_org = f1.multiselect("Origem", opts(origem), default=opts(origem), key="cr_org")
    sel_sit = f2.multiselect("Situação", ["Vencido", "A vencer"],
                             default=["Vencido", "A vencer"], key="cr_sit")
    busca = f3.text_input("Buscar cliente", key="cr_busca")

    dmin = dmax = None
    if venc:
        dts = su.parse_dates(fr.raw[venc]).dropna()
        if not dts.empty:
            dmin, dmax = dts.min().date(), dts.max().date()
    if dmin and dmax and dmin < dmax:
        d1, d2 = st.slider("Período (vencimento)", dmin, dmax, (dmin, dmax),
                           format="DD/MM/YYYY", key="cr_per")
    else:
        d1, d2 = dmin, dmax

    # ---------- Aplica filtros ----------
    d = fr.num.copy()
    if origem:
        d = d[d[origem].astype(str).str.strip().isin(sel_org)]
    if busca and cli:
        d = d[d[cli].astype(str).str.contains(busca, case=False, na=False)]
    if venc and d1:
        vv = su.parse_dates(d[venc])
        d = d[((vv.dt.date >= d1) & (vv.dt.date <= d2)).fillna(False)]
    if d.empty:
        st.warning("Nenhum título corresponde aos filtros.")
        return

    venc_dt = su.parse_dates(d[venc]) if venc else pd.Series(pd.NaT, index=d.index)
    d = d.assign(_venc=venc_dt, _atraso=(hoje - venc_dt).dt.days)
    d["_sit"] = d["_atraso"].apply(lambda a: "Vencido" if (pd.notna(a) and a > 0) else "A vencer")
    d["_aging"] = d["_atraso"].map(bucket)
    d = d[d["_sit"].isin(sel_sit)]
    if d.empty:
        st.warning("Nenhum título corresponde aos filtros.")
        return

    # ---------- Métricas ----------
    ar_total = d[areceber].sum()
    is_venc = d["_atraso"] > 0
    venc_val = d.loc[is_venc, areceber].sum()
    venc_n = int(is_venc.sum())
    avencer_val = d.loc[~is_venc, areceber].sum()
    prox7 = d[(d["_venc"] >= hoje) & (d["_venc"] <= hoje + pd.Timedelta(days=7)) & (d[areceber] > 0)]
    vence7 = prox7[areceber].sum()
    bruto_t = d[bruto].sum() if bruto else 0
    if rb is not None:
        rcol = su.find_col(rb.num.columns, "Recebido")
        rec = float(rb.num[rcol].sum()) if rcol else 0
    else:
        rcol = su.find_col(fr.num.columns, "Recebido")
        rec = float(d[rcol].sum()) if rcol else 0
    n_cli = d[cli].astype(str).str.strip().replace("", pd.NA).nunique() if cli else 0
    ticket = ar_total / len(d) if len(d) else 0

    ui.kpi_row([
        {"label": "A Receber", "value": su.format_brl(ar_total), "color": ui.GREEN,
         "sub": f"{len(d)} títulos",
         "help": "Total que os clientes ainda devem. Soma da coluna 'A Receber' dos títulos "
                 "em aberto, no filtro atual."},
        {"label": f"Vencido ({venc_n})", "value": su.format_brl(venc_val), "color": ui.RED,
         "sub": "em atraso",
         "help": "Títulos cujo vencimento já passou e ainda não foram recebidos. Soma do "
                 "'A Receber' dos títulos com vencimento < hoje. O número é a quantidade."},
        {"label": "A vencer", "value": su.format_brl(avencer_val), "color": ui.TEAL,
         "help": "Títulos ainda dentro do prazo. Soma do 'A Receber' dos títulos com "
                 "vencimento maior ou igual a hoje."},
        {"label": "Vence em 7 dias", "value": su.format_brl(vence7), "color": ui.AMBER,
         "sub": f"{len(prox7)} títulos",
         "help": "O que deve entrar de hoje até 7 dias à frente. Soma do 'A Receber' dos "
                 "títulos com vencimento nesse intervalo."},
    ])
    ui.kpi_row([
        {"label": "Recebido (mês)", "value": su.format_brl(rec), "color": ui.TEAL,
         "sub": "aba Recebidos",
         "help": "Quanto já entrou de clientes no mês. Soma da coluna 'Recebido' da aba "
                 "Recebidos (recebimentos efetivos)."},
        {"label": "Bruto faturado", "value": su.format_brl(bruto_t), "color": ui.BLUE,
         "help": "Valor cheio dos títulos, antes de impostos retidos. Soma da coluna "
                 "'Valor da Conta'."},
        {"label": "Ticket médio", "value": su.format_brl(ticket), "color": ui.SLATE,
         "help": "Valor médio por título a receber. Conta: A Receber ÷ número de títulos."},
        {"label": "Clientes", "value": str(n_cli), "color": ui.PURPLE,
         "help": "Quantidade de clientes diferentes no filtro (valores únicos de Razão Social)."},
    ])
    st.divider()

    t1, t2, t3, t4 = st.tabs(
        ["🖥️ Visão Geral", "🎯 Clientes", "⚡ Aging & Cobrança", "🗂️ Detalhado"])

    # ===== Visão Geral =====
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            _h("Situação (vencido × a vencer)",
               "Divide o 'A Receber' em dois: já Vencido (vermelho) e a vencer (verde). "
               "Cada fatia é a soma do A Receber de cada situação.")
            _donut(_dgroup(d, "_sit", areceber), "_sit", areceber,
                   cmap={"Vencido": ui.RED, "A vencer": ui.GREEN})
        with c2:
            _h("Aging de recebíveis",
               "Agrupa o 'A Receber' pelo prazo até o vencimento: já Vencido, ou a vencer em "
               "≤7, 8–15, 16–30 e 30+ dias. Mostra a saúde da carteira de recebíveis.")
            g = d.groupby("_aging")[areceber].sum().reset_index()
            g["_o"] = g["_aging"].map({k: i for i, k in enumerate(AGING)})
            g = g.sort_values("_o")
            fig = px.bar(g, x="_aging", y=areceber, color="_aging",
                         color_discrete_map=ACMAP, text_auto=".2s")
            fig.update_traces(textposition="outside", cliponaxis=False)
            _mt(fig)
            _plot(ui.style_fig(fig, 330, legend=False), width="stretch")

        if prev:
            _h("Previsão de recebimento (entrada de caixa prevista)",
               "Quanto deve entrar em cada data, usando a coluna 'Previsão' (data prevista de "
               "recebimento). Soma do 'A Receber' por data prevista.")
            dd = d.assign(_p=su.parse_dates(d[prev])).dropna(subset=["_p"])
            if not dd.empty:
                g = dd.groupby("_p")[areceber].sum().reset_index().sort_values("_p")
                fig = px.bar(g, x="_p", y=areceber, text_auto=".2s")
                fig.update_traces(marker_color=ui.GREEN, textposition="outside", cliponaxis=False)
                _mt(fig, date=True)
                fig.add_vline(x=hoje, line_dash="dot", line_color="#E6EAF1")
                _plot(ui.style_fig(fig, 320, legend=False), width="stretch")

    # ===== Clientes =====
    with t2:
        if cli:
            _ranking_bar(_dgroup(d, cli, areceber), cli, areceber, "cr_cli",
                         "A receber por cliente", top=15, height=460, marker=ui.GREEN,
                         help="Soma do 'A Receber' por cliente (Razão Social), do maior para "
                              "o menor. Mostra quem mais deve.")
            _h("Concentração (Pareto) — maiores clientes",
               "Barras = a receber por cliente (maior→menor). A linha é o % acumulado: "
               "mostra se poucos clientes concentram a maior parte da carteira (80/20).")
            _pareto(d, cli, areceber)

    # ===== Aging & Cobrança =====
    with t3:
        _h("A receber por dia de vencimento",
           "Valor a receber ('A Receber') em cada data de vencimento, colorido por situação "
           "(vencido/a vencer). A linha pontilhada é o dia de hoje.")
        dd = d.dropna(subset=["_venc"])
        if not dd.empty:
            g = dd.groupby(["_venc", "_sit"])[areceber].sum().reset_index()
            fig = px.bar(g, x="_venc", y=areceber, color="_sit",
                         color_discrete_map={"Vencido": ui.RED, "A vencer": ui.GREEN})
            _mt(fig, date=True, keepname=True)
            fig.add_vline(x=hoje, line_dash="dot", line_color="#E6EAF1")
            _plot(ui.style_fig(fig, 320, legend=True), width="stretch")

        cc1, cc2 = st.columns(2)
        with cc1:
            _h("🔴 Vencidos (maior atraso primeiro)",
               "Títulos já vencidos, do mais atrasado para o menos. 'Atraso (dias)' = "
               "hoje − vencimento. Útil para priorizar a cobrança.")
            vr = d[is_venc].sort_values("_atraso", ascending=False)
            if vr.empty:
                st.caption("Nenhum título vencido no filtro. 🎉")
            else:
                disp = vr.assign(**{"Atraso (dias)": vr["_atraso"].astype("Int64")})
                cols = [c for c in [venc, cli, "Atraso (dias)", areceber] if c]
                _styled_table(disp[cols], money_cols=[areceber])
        with cc2:
            _h("🟡 Próximos vencimentos",
               "Títulos a vencer, do mais próximo para o mais distante. 'Faltam (dias)' = "
               "vencimento − hoje.")
            pr = d[(d["_venc"] >= hoje) & (d[areceber] > 0)].sort_values("_venc")
            if pr.empty:
                st.caption("Sem títulos a vencer no filtro.")
            else:
                disp = pr.assign(**{"Faltam (dias)": (-pr["_atraso"]).astype("Int64")})
                cols = [c for c in [venc, cli, "Faltam (dias)", areceber] if c]
                _styled_table(disp[cols], money_cols=[areceber])

    # ===== Detalhado =====
    with t4:
        _h("Todos os títulos (conforme filtros)",
           "Tabela completa dos títulos a receber no filtro, com vencimento, previsão, "
           "valor bruto, líquido e a receber. Baixe em CSV/Excel no botão abaixo.")
        dd = d.sort_values("_venc" if venc else areceber)
        cols = [c for c in [venc, prev, cli, origem, bruto, liquido, areceber] if c]
        _styled_table(dd[cols], money_cols=[bruto, liquido, areceber])
        st.download_button("⬇️ Baixar CSV", dd[cols].to_csv(index=False).encode("utf-8-sig"),
                           "contas_a_receber.csv", "text/csv", key="cr_csv")
        st.caption(f"{len(dd)} títulos no filtro.")


# -----------------------------------------------------------------------------
# FOLHA (helpers)
# -----------------------------------------------------------------------------
_PT_MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
             "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def _dgroup(d, dim, val, top=None, asc=False, agg="sum"):
    x = d.copy()
    x[dim] = x[dim].astype(str).str.strip()
    x = x[x[dim] != ""]
    s = x.groupby(dim)[val]
    g = (s.mean() if agg == "mean" else s.sum()).reset_index().sort_values(val, ascending=asc)
    return g.head(top) if top else g


def _dcount(d, dim, asc=False):
    x = d.copy()
    x[dim] = x[dim].astype(str).str.strip()
    x = x[x[dim] != ""]
    g = x[dim].value_counts().reset_index()
    g.columns = [dim, "Qtde"]
    return g.sort_values("Qtde", ascending=asc)


def _parse_reajuste(series):
    """Converte 'ago./26', 'set./23' em 'YYYY-MM' (ou None)."""
    out = []
    for v in series.astype(str):
        m = re.match(r"\s*([a-zç]{3})\.?\s*[/\-]?\s*(\d{2,4})", v.strip().lower())
        if m and m.group(1) in _PT_MESES:
            y = int(m.group(2))
            y = y + 2000 if y < 100 else y
            out.append(f"{y:04d}-{_PT_MESES[m.group(1)]:02d}")
        else:
            out.append(None)
    return pd.Series(out, index=series.index)


# -----------------------------------------------------------------------------
# FOLHA
# -----------------------------------------------------------------------------
def render_folha(fr):
    st.subheader("🤖 Folha / Consultores — Análise Detalhada")
    hoje = pd.Timestamp.today().normalize()

    consult = su.find_col(fr.raw.columns, "Consultores", "Consultor", "Nome")
    valor = su.find_col(fr.num.columns, "VALOR", "Valor")
    tipo = su.find_col(fr.raw.columns, "TIPO", "Tipo")
    modelo = su.find_col(fr.raw.columns, "MODELO", "Modelo")
    empresa = su.find_col(fr.raw.columns, "EMPRESA", "Empresa")
    setor = su.find_col(fr.raw.columns, "SETOR", "Setor")
    dtini = su.find_col(fr.raw.columns, "DT.INÍCIO", "DT.INICIO", "Admissão", "Admissao")
    reaj = su.find_col(fr.raw.columns, "REAJUSTE", "Reajuste")
    horas = su.find_col(fr.num.columns, "TOT.HRS", "TOT.HORAS", "Horas")
    vlrhr = su.find_col(fr.num.columns, "VLR/HR", "VLR/HORA")
    proj = su.find_col(fr.num.columns, "PROJEÇÃO", "Projeção", "PROJECAO")
    projf = su.find_col(fr.num.columns, "PROJEÇÃO com Fundo", "Projeção com Fundo")

    # ---------- Filtros ----------
    def opts(col):
        if not col:
            return []
        s = fr.raw[col].astype(str).str.strip()
        return sorted(s[s != ""].unique())

    st.markdown("##### 🔎 Filtros")
    f1, f2, f3, f4 = st.columns(4)
    sel_emp = f1.multiselect("Empresa", opts(empresa), default=opts(empresa), key="fo_emp")
    sel_set = f2.multiselect("Setor", opts(setor), default=opts(setor), key="fo_set")
    sel_tipo = f3.multiselect("Tipo", opts(tipo), default=opts(tipo), key="fo_tipo")
    sel_mod = f4.multiselect("Modelo", opts(modelo), default=opts(modelo), key="fo_mod")
    g1, g2 = st.columns([2, 1])
    metrica = g1.radio("Métrica de custo",
                       ["Projeção (custo mensal)", "Projeção com Fundo", "Valor base"],
                       horizontal=True, key="fo_metrica")
    busca = g2.text_input("Buscar consultor", key="fo_busca")

    if "Fundo" in metrica and projf:
        custo_col = projf
    elif "Projeção" in metrica and proj:
        custo_col = proj
    else:
        custo_col = valor or proj or projf
    if custo_col is None:
        st.warning("Nao encontrei colunas de custo (PROJEÇÃO/VALOR) nesta aba.")
        return

    # ---------- Aplica filtros ----------
    d = fr.num.copy()
    for col, sel in [(empresa, sel_emp), (setor, sel_set), (tipo, sel_tipo), (modelo, sel_mod)]:
        if col:
            d = d[d[col].astype(str).str.strip().isin(sel)]
    if busca and consult:
        d = d[d[consult].astype(str).str.contains(busca, case=False, na=False)]
    if d.empty:
        st.warning("Nenhum consultor corresponde aos filtros.")
        return

    # ---------- KPIs ----------
    custo_total = float(d[custo_col].sum())
    custo_fundo = float(d[projf].sum()) if projf else custo_total
    base_proj = float(d[proj].sum()) if proj else 0.0
    provisao = (custo_fundo - base_proj) if (proj and projf) else 0.0
    headcount = len(d)
    custo_medio = custo_total / headcount if headcount else 0
    vlrhr_medio = float(d[vlrhr].mean()) if vlrhr else 0
    horas_total = float(d[horas].sum()) if horas else 0
    n_setores = d[setor].astype(str).str.strip().replace("", pd.NA).nunique() if setor else 0

    ui.kpi_row([
        {"label": "Custo Mensal", "value": su.format_brl(custo_total), "color": ui.BLUE,
         "sub": metrica,
         "help": "Custo total da folha no mês. Soma da métrica escolhida acima (PROJEÇÃO = "
                 "valor/hora × horas, ou salário fixo) de todos os consultores do filtro."},
        {"label": "Com Fundo", "value": su.format_brl(custo_fundo), "color": ui.PURPLE,
         "sub": f"provisao {su.format_brl(provisao)}",
         "help": "Custo já incluindo a provisão (fundo). Soma da coluna 'PROJEÇÃO com Fundo'. "
                 "A provisão = Com Fundo − Projeção."},
        {"label": "Consultores", "value": str(headcount), "color": ui.TEAL,
         "sub": f"{n_setores} setores",
         "help": "Quantidade de consultores no filtro (linhas). Abaixo, o nº de setores "
                 "diferentes."},
        {"label": "Custo Medio", "value": su.format_brl(custo_medio), "color": ui.AMBER,
         "sub": "por consultor",
         "help": "Custo médio por pessoa. Conta: Custo Mensal ÷ número de consultores."},
    ])
    ui.kpi_row([
        {"label": "VLR/HR Medio", "value": su.format_brl(vlrhr_medio), "color": ui.TEAL,
         "help": "Média do valor/hora dos consultores. Média aritmética da coluna VLR/HR "
                 "no filtro."},
        {"label": "Total Horas/mes", "value": f"{horas_total:,.0f}".replace(",", "."),
         "color": ui.SLATE,
         "help": "Soma das horas mensais previstas de todos os consultores (coluna TOT.HRS)."},
        {"label": "Maior custo", "value": su.format_brl(d[custo_col].max()), "color": ui.RED,
         "sub": "consultor mais caro",
         "help": "O maior custo individual no filtro (maior valor da métrica escolhida)."},
        {"label": "Menor custo", "value": su.format_brl(d[custo_col].min()), "color": ui.GREEN,
         "sub": "consultor mais barato",
         "help": "O menor custo individual no filtro (menor valor da métrica escolhida)."},
    ])
    st.divider()

    t1, t2, t3, t4, t5 = st.tabs(
        ["🖥️ Composição", "🏗️ Setores", "⚡ Horas & R$/h", "🤖 Consultores", "🔄 Reajustes"])

    # ===== Composição =====
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            if setor:
                _h("Custo por setor",
                   "Custo da folha (métrica escolhida) somado por SETOR. Mostra onde está "
                   "concentrado o custo de pessoal.")
                _bar(_dgroup(d, setor, custo_col, asc=True), setor, custo_col,
                     horizontal=True, height=360)
        with c2:
            if tipo:
                _h("Custo por tipo (HORA × FIXO)",
                   "Custo somado por TIPO de contratação: por hora (HORA) ou fixo mensal "
                   "(FIXO). Cada fatia é a soma do custo daquele tipo.")
                _donut(_dgroup(d, tipo, custo_col), tipo, custo_col)
        c3, c4 = st.columns(2)
        with c3:
            if modelo:
                _h("Custo por modelo de contratação",
                   "Custo somado por MODELO (Koopere, CLT, PJ). Mostra como o custo se "
                   "distribui entre os formatos de contratação.")
                _donut(_dgroup(d, modelo, custo_col), modelo, custo_col)
        with c4:
            if empresa:
                _h("Custo por empresa",
                   "Custo da folha somado por EMPRESA (Roboteasy/Agapys).")
                _bar(_dgroup(d, empresa, custo_col), empresa, custo_col, height=360)

    # ===== Setores =====
    with t2:
        if setor:
            c1, c2 = st.columns(2)
            with c1:
                _h("Custo por setor",
                   "Custo da folha somado por SETOR (total de cada área).")
                _bar(_dgroup(d, setor, custo_col, asc=True), setor, custo_col,
                     horizontal=True, height=360)
            with c2:
                _h("Headcount por setor",
                   "Número de consultores em cada setor (contagem de pessoas, não é R$).")
                _bar(_dcount(d, setor, asc=True), setor, "Qtde", horizontal=True,
                     height=360, money=False)
            _h("Custo médio por consultor, por setor",
               "Custo médio de cada pessoa dentro do setor. Conta: custo total do setor ÷ "
               "nº de consultores do setor (média).")
            _bar(_dgroup(d, setor, custo_col, agg="mean"), setor, custo_col, height=320)
            _h("Mapa de custos: setor → consultor",
               "Retângulos proporcionais ao custo: cada setor se divide nos seus consultores. "
               "Quanto maior o bloco, maior o custo daquela pessoa/setor.")
            td = d.copy()
            td[setor] = td[setor].astype(str).str.strip().replace("", "(sem setor)")
            td = td[td[custo_col].fillna(0) > 0]
            path = [px.Constant("Folha"), setor] + ([consult] if consult else [])
            fig = px.treemap(td, path=path, values=custo_col, color=custo_col,
                             color_continuous_scale=["#0F2A2A", "#00D9A6"],
                             hover_data={custo_col: ":,.2f"})
            fig.update_traces(
                textinfo="label+value",
                textfont=dict(size=13),
                marker=dict(cornerradius=6, line=dict(width=2, color="#0E1117")),
                hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<extra></extra>",
            )
            fig.update_layout(margin=dict(t=10, b=0, l=0, r=0))
            _plot(ui.style_fig(fig, 460, legend=False), width="stretch")
        else:
            st.caption("Coluna de setor não encontrada.")

    # ===== Horas & R$/h =====
    with t3:
        c1, c2 = st.columns(2)
        with c1:
            if setor and vlrhr:
                _h("VLR/HR médio por setor",
                   "Valor/hora médio de cada setor. Média da coluna VLR/HR dos consultores "
                   "daquele setor.")
                _bar(_dgroup(d, setor, vlrhr, agg="mean", asc=True), setor, vlrhr,
                     horizontal=True, height=340)
        with c2:
            if vlrhr:
                _h("Distribuição de VLR/HR",
                   "Quantos consultores há em cada faixa de valor/hora. As barras contam "
                   "pessoas por faixa de VLR/HR.")
                fig = px.histogram(d.dropna(subset=[vlrhr]), x=vlrhr, nbins=20)
                fig.update_traces(
                    marker_color=ui.TEAL,
                    marker_line_width=0,
                    opacity=0.88,
                    marker_cornerradius=4,
                    hovertemplate="R$/h: %{x:,.2f}<br>Qtde: %{y:,.0f}<extra></extra>",
                )
                _plot(ui.style_fig(fig, 340, legend=False), width="stretch")
        if horas and vlrhr:
            _h("Relação horas × valor/hora (tamanho = custo mensal)",
               "Cada bolha é um consultor: eixo X = horas/mês, eixo Y = valor/hora, tamanho "
               "da bolha = custo mensal. Ajuda a achar quem é caro por hora ou por volume.")
            sc = d.dropna(subset=[horas, vlrhr, custo_col]).copy()
            sc["Consultor"] = sc[consult].astype(str) if consult else ""
            fig = px.scatter(sc, x=horas, y=vlrhr, size=custo_col,
                             color=(tipo if tipo else None), hover_name="Consultor",
                             size_max=46, color_discrete_sequence=ui.SEQ)
            fig.update_traces(
                marker=dict(opacity=0.82, line=dict(width=1.5, color="rgba(0,0,0,0.4)")),
                hovertemplate="<b>%{hovertext}</b><br>Horas: %{x:,.0f}<br>"
                              "R$/h: R$ %{y:,.2f}<br>Custo: R$ %{marker.size:,.2f}<extra></extra>",
            )
            _plot(ui.style_fig(fig, 420, legend=bool(tipo)), width="stretch")

    # ===== Consultores =====
    with t4:
        rtop1, rtop2 = st.columns([2, 1])
        if headcount <= 6:
            n = headcount
            rtop1.caption(f"{headcount} consultores no filtro.")
        else:
            n = rtop1.slider("Quantos no ranking? (padrao: todos)", 5, headcount,
                             headcount, key="fo_topn")
        ordem = rtop2.radio("Ordem", ["Maior → menor", "Menor → maior"], key="fo_ordem")
        if consult:
            sel = _dgroup(d, consult, custo_col).head(n)  # sempre os n de maior custo
            g = sel.sort_values(custo_col, ascending=(ordem == "Maior → menor"))
            titulo = ("Todos os consultores" if n >= headcount
                      else f"Top {n} consultores") + " por custo"
            _h(f"{titulo} · {ordem.lower()}",
               "Custo mensal (métrica escolhida) de cada consultor. Use o controle de "
               "quantidade e a ordem para focar nos mais caros ou mais baratos.")
            _bar(g, consult, custo_col, horizontal=True, height=max(320, n * 24))
        if dtini:
            anos = (hoje - su.parse_dates(d[dtini])).dt.days / 365.25
            dd = d.assign(_anos=anos)

            def faixa(a):
                if pd.isna(a):
                    return "Sem data"
                if a < 1:
                    return "< 1 ano"
                if a < 3:
                    return "1–3 anos"
                if a < 5:
                    return "3–5 anos"
                return "5+ anos"

            ordem = ["< 1 ano", "1–3 anos", "3–5 anos", "5+ anos", "Sem data"]
            cc1, cc2 = st.columns(2)
            with cc1:
                _h("Tempo de casa (headcount)",
                   "Quantos consultores há por faixa de antiguidade. Tempo de casa = hoje − "
                   "DT.INÍCIO, agrupado em <1, 1–3, 3–5 e 5+ anos.")
                g = dd.assign(_f=dd["_anos"].map(faixa))["_f"].value_counts().reset_index()
                g.columns = ["Faixa", "Qtde"]
                g["_o"] = g["Faixa"].map({k: i for i, k in enumerate(ordem)})
                g = g.sort_values("_o")
                fig = px.bar(g, x="Faixa", y="Qtde", text_auto=True)
                fig.update_traces(marker_color=ui.BLUE,
                                  hovertemplate="<b>%{x}</b><br>%{y:,.0f} consultor(es)<extra></extra>")
                _plot(ui.style_fig(fig, 320, legend=False), width="stretch")
            with cc2:
                _h("Custo × tempo de casa",
                   "Cada ponto é um consultor: eixo X = anos de casa, eixo Y = custo mensal. "
                   "Ajuda a ver se os mais antigos custam mais.")
                sc = dd.dropna(subset=["_anos"])
                fig = px.scatter(sc, x="_anos", y=custo_col,
                                 color=(setor if setor else None),
                                 hover_name=(consult if consult else None),
                                 color_discrete_sequence=ui.SEQ,
                                 labels={"_anos": "Anos de casa"})
                fig.update_traces(
                    marker=dict(size=11, opacity=0.85,
                                line=dict(width=1.5, color="rgba(0,0,0,0.4)")),
                    hovertemplate="<b>%{hovertext}</b><br>Anos: %{x:.1f}<br>"
                                  "Custo: R$ %{y:,.2f}<extra></extra>",
                )
                _plot(ui.style_fig(fig, 320, legend=False), width="stretch")
        _h("Tabela detalhada",
           "Lista completa dos consultores no filtro, ordenada do maior custo para o menor, "
           "com tipo, modelo, setor, horas, valor/hora e projeções.")
        show = [c for c in [consult, empresa, setor, tipo, modelo, dtini, reaj,
                            horas, vlrhr, valor, proj, projf] if c]
        colcfg = {}
        for c in [valor, vlrhr, proj, projf]:
            if c:
                colcfg[c] = st.column_config.NumberColumn(format="R$ %.2f")
        if horas:
            colcfg[horas] = st.column_config.NumberColumn(format="%.0f")
        st.dataframe(d[show].sort_values(custo_col, ascending=False), width="stretch",
                     hide_index=True, column_config=colcfg)
        st.caption(f"{headcount} consultores no filtro.")

    # ===== Reajustes =====
    with t5:
        if reaj:
            per = _parse_reajuste(d[reaj])
            dd = d.assign(_per=per)
            com = dd[dd["_per"].notna()]
            sem = len(dd) - len(com)
            st.caption(f"{len(com)} consultores com reajuste definido · {sem} sem data.")
            atual = hoje.strftime("%Y-%m")
            if not com.empty:
                c1, c2 = st.columns([1.4, 1])
                with c1:
                    _h("Reajustes por mês",
                       "Quantos consultores têm reajuste marcado em cada mês (coluna "
                       "REAJUSTE). Amarelo = ainda vai acontecer; cinza = já passou.")
                    g = com["_per"].value_counts().reset_index()
                    g.columns = ["Mes", "Qtde"]
                    g = g.sort_values("Mes")
                    g["Quando"] = g["Mes"].apply(
                        lambda m: "Futuro/atual" if m >= atual else "Passado")
                    fig = px.bar(g, x="Mes", y="Qtde", color="Quando", text_auto=True,
                                 color_discrete_map={"Futuro/atual": ui.AMBER,
                                                     "Passado": ui.SLATE})
                    fig.update_traces(hovertemplate="<b>%{x}</b><br>%{y:,.0f} reajuste(s)")
                    _plot(ui.style_fig(fig, 340, legend=True), width="stretch")
                with c2:
                    _h("Próximos reajustes",
                       "Lista de consultores com reajuste marcado de hoje em diante "
                       "(mês ≥ mês atual), ordenada pela data.")
                    prox = com[com["_per"] >= atual].sort_values("_per")
                    cols = [c for c in [consult, setor, reaj] if c]
                    if not prox.empty:
                        st.dataframe(prox[cols], width="stretch", hide_index=True)
                    else:
                        st.caption("Nenhum reajuste futuro no filtro.")
        else:
            st.caption("Coluna de reajuste não encontrada.")


# -----------------------------------------------------------------------------
# EXTRATO (helpers + view)
# -----------------------------------------------------------------------------
def _ex_categoria(texto):
    s = str(texto).upper()
    if "PIX" in s and ("RECEB" in s or "CRED" in s):
        return "Recebimento PIX"
    if "PIX" in s:
        return "Pagamento PIX"
    if "TED" in s:
        return "TED/DOC"
    if "BOLETO" in s or "LIQUIDACAO" in s or s.startswith("COB"):
        return "Boleto"
    if "IOF" in s:
        return "IOF"
    if "JUROS" in s or "ENC0" in s or "ESPECIAL" in s or "ENCARGO" in s:
        return "Juros/Encargos"
    if "MANUTENCAO" in s or "CESTA" in s or "TARIFA" in s or "FATURA" in s:
        return "Tarifas/Fatura"
    if "APLICAC" in s or "CAPTACAO" in s or "RESGATE" in s or "LIBERACAO" in s or "CAPITAL" in s:
        return "Aplicação/Capital"
    return "Outros"


_EX_CUSTO = {"IOF", "Juros/Encargos", "Tarifas/Fatura"}


def render_extrato(extratos):
    st.subheader("🔍 Extrato Bancário — Fluxo de Caixa")

    # extratos: dict {empresa: Frames ou None}
    disponiveis = [e for e, f in (extratos or {}).items() if f is not None and not f.raw.empty]
    if not disponiveis:
        st.info("Ainda não há extrato importado. Use **🔄 Importar Extrato** para enviar "
                "o arquivo .xls do banco.")
        return
    if len(disponiveis) > 1:
        empresa = st.radio("Empresa", disponiveis, horizontal=True, key="ex_empresa")
    else:
        empresa = disponiveis[0]
        st.caption(f"Empresa: **{empresa}**")
    fr = extratos[empresa]

    data = su.find_col(fr.raw.columns, "Data")
    desc = su.find_col(fr.raw.columns, "Descrição", "Descricao", "Historico")
    doc = su.find_col(fr.raw.columns, "Documento")
    valor = su.find_col(fr.num.columns, "Valor (R$)", "Valor")
    saldo = su.find_col(fr.num.columns, "Saldo (R$)", "Saldo")

    if not valor:
        st.warning("Não encontrei a coluna de valores nesta aba.")
        _table(fr)
        return

    # saldo inicial/final usam a coluna Saldo inteira (inclui "Saldo Anterior")
    saldo_ini = saldo_fim = 0
    if saldo:
        ss = fr.num[saldo].dropna()
        if not ss.empty:
            saldo_ini, saldo_fim = float(ss.iloc[0]), float(ss.iloc[-1])

    # base de lançamentos (exclui linhas sem valor, ex. "Saldo Anterior")
    base = fr.num.copy()
    base["_cat"] = (base[desc].astype(str) + " " + (base[doc].astype(str) if doc else "")) \
        .map(_ex_categoria) if desc else "Outros"
    base["_tipo"] = base[valor].apply(lambda x: "Entrada" if (pd.notna(x) and x > 0) else "Saída")
    base = base[base[valor].notna() & (base[valor] != 0)]

    # ---------- Filtros ----------
    def opts(col):
        if not col:
            return []
        s = fr.raw[col].astype(str).str.strip()
        return sorted(s[s != ""].unique())

    st.markdown("##### 🔎 Filtros")
    f1, f2, f3 = st.columns([1, 1.3, 1.3])
    sel_tipo = f1.multiselect("Tipo", ["Entrada", "Saída"], default=["Entrada", "Saída"],
                              key="ex_tipo")
    cats = sorted(base["_cat"].unique())
    sel_cat = f2.multiselect("Categoria", cats, default=cats, key="ex_cat")
    busca = f3.text_input("Buscar descrição", key="ex_busca")

    dmin = dmax = None
    if data:
        dts = su.parse_dates(fr.raw[data]).dropna()
        if not dts.empty:
            dmin, dmax = dts.min().date(), dts.max().date()
    if dmin and dmax and dmin < dmax:
        d1, d2 = st.slider("Período", dmin, dmax, (dmin, dmax), format="DD/MM/YYYY",
                           key="ex_per")
    else:
        d1, d2 = dmin, dmax

    # ---------- Aplica filtros ----------
    d = base[base["_tipo"].isin(sel_tipo) & base["_cat"].isin(sel_cat)]
    if busca and desc:
        d = d[d[desc].astype(str).str.contains(busca, case=False, na=False)]
    if data and d1:
        vv = su.parse_dates(d[data])
        d = d[((vv.dt.date >= d1) & (vv.dt.date <= d2)).fillna(False)]
    if d.empty:
        st.warning("Nenhum lançamento corresponde aos filtros.")
        return

    d = d.assign(_d=su.parse_dates(d[data]) if data else pd.NaT)

    # ---------- Métricas ----------
    v = d[valor]
    entradas = v[v > 0].sum()
    saidas = -v[v < 0].sum()
    liquido = v.sum()
    custo_banc = -d[d["_cat"].isin(_EX_CUSTO)][valor].clip(upper=0).sum()
    n_lanc = len(d)
    maior_ent = v.max() if (v > 0).any() else 0
    maior_sai = -v.min() if (v < 0).any() else 0
    dias_neg = 0
    if saldo and "_d" in d:
        fech = d.dropna(subset=["_d"]).groupby("_d")[saldo].last()
        dias_neg = int((fech < 0).sum())

    ui.kpi_row([
        {"label": "Saldo inicial", "value": su.format_brl(saldo_ini),
         "color": ui.GREEN if saldo_ini >= 0 else ui.RED,
         "help": "Saldo da conta no começo do período. É o primeiro 'Saldo' do extrato "
                 "(linha 'Saldo Anterior')."},
        {"label": "Entradas", "value": su.format_brl(entradas), "color": ui.GREEN,
         "help": "Tudo que entrou. Soma dos lançamentos com valor positivo, no filtro atual."},
        {"label": "Saídas", "value": su.format_brl(saidas), "color": ui.RED,
         "help": "Tudo que saiu. Soma (em módulo) dos lançamentos com valor negativo."},
        {"label": "Saldo final", "value": su.format_brl(saldo_fim),
         "color": ui.GREEN if saldo_fim >= 0 else ui.RED,
         "help": "Saldo da conta no fim do período (último 'Saldo' do extrato). "
                 "Confere: Saldo inicial + Entradas − Saídas."},
    ])
    ui.kpi_row([
        {"label": "Resultado do período", "value": su.format_brl(liquido),
         "color": ui.GREEN if liquido >= 0 else ui.RED,
         "help": "Entradas − Saídas do período. Positivo = entrou mais do que saiu."},
        {"label": "Custo bancário", "value": su.format_brl(custo_banc), "color": ui.RED,
         "sub": "tarifas + IOF + juros",
         "help": "Quanto o banco custou. Soma das saídas das categorias Tarifas/Fatura, "
                 "IOF e Juros/Encargos (inclui juros do cheque especial)."},
        {"label": "Lançamentos", "value": str(n_lanc), "color": ui.TEAL,
         "help": "Quantidade de movimentações no extrato, no filtro atual."},
        {"label": "Dias no negativo", "value": str(dias_neg), "color": ui.AMBER,
         "sub": "saldo < 0",
         "help": "Em quantos dias a conta fechou com saldo abaixo de zero (uso de cheque "
                 "especial/limite)."},
    ])
    st.divider()

    t1, t2, t3, t4 = st.tabs(
        ["📡 Fluxo de Caixa", "🏷️ Categorias", "🚀 Maiores", "🗂️ Detalhado"])

    # ===== Fluxo de Caixa =====
    with t1:
        dd = d.dropna(subset=["_d"])
        if saldo and not dd.empty:
            _h("Evolução do saldo (fechamento diário)",
               "Saldo da conta ao fim de cada dia (último 'Saldo' de cada data). A linha "
               "pontilhada é o zero: abaixo dela, a conta está no cheque especial.")
            g = dd.groupby("_d")[saldo].last().reset_index().sort_values("_d")
            cor = ui.GREEN if g[saldo].iloc[-1] >= 0 else ui.RED
            fig = px.area(g, x="_d", y=saldo, markers=True)
            fill_col = "rgba(0,217,166,0.12)" if cor == ui.GREEN else "rgba(244,63,94,0.12)"
            fig.update_traces(
                line=dict(color=cor, width=3, shape="spline", smoothing=1.1),
                fillcolor=fill_col,
                marker=dict(size=7, color=cor, line=dict(width=2, color="#0E1117")),
            )
            _mt(fig, date=True)
            fig.add_hline(y=0, line_dash="dot", line_color="rgba(255,255,255,0.2)", line_width=1)
            _plot(ui.style_fig(fig, 320, legend=False), width="stretch")

        if not dd.empty:
            _h("Entradas × Saídas por dia",
               "Por dia: quanto entrou (verde) e quanto saiu (vermelho). Soma das entradas e "
               "das saídas de cada data. Ajuda a ver os dias de maior movimento.")
            x2 = dd.assign(Entradas=dd[valor].clip(lower=0), Saídas=-dd[valor].clip(upper=0))
            g = x2.groupby("_d")[["Entradas", "Saídas"]].sum().reset_index().sort_values("_d")
            gm = g.melt("_d", var_name="Tipo", value_name="Valor")
            fig = px.bar(gm, x="_d", y="Valor", color="Tipo", barmode="group",
                         color_discrete_map={"Entradas": ui.GREEN, "Saídas": ui.RED})
            _mt(fig, date=True, keepname=True)
            _plot(ui.style_fig(fig, 320, legend=True), width="stretch")

            _h("Fluxo líquido por dia (entradas − saídas)",
               "Resultado de cada dia: soma de todos os valores do dia (entradas menos "
               "saídas). Verde = dia positivo (entrou mais), vermelho = dia negativo.")
            gn = dd.groupby("_d")[valor].sum().reset_index().sort_values("_d")
            gn["_cor"] = gn[valor].apply(lambda x: "Positivo" if x >= 0 else "Negativo")
            fig = px.bar(gn, x="_d", y=valor, color="_cor",
                         color_discrete_map={"Positivo": ui.GREEN, "Negativo": ui.RED})
            _mt(fig, date=True, keepname=True)
            _plot(ui.style_fig(fig, 300, legend=False), width="stretch")

    # ===== Categorias =====
    with t2:
        c1, c2 = st.columns(2)
        with c1:
            _h("Saídas por categoria",
               "Para onde o dinheiro foi. Soma do valor das saídas (negativas) por categoria "
               "do lançamento (PIX, TED, Boleto, IOF, Juros, Tarifas...).")
            sd = d[d[valor] < 0].assign(_v=-d[valor])
            _donut(_dgroup(sd, "_cat", "_v"), "_cat", "_v")
        with c2:
            _h("Entradas por categoria",
               "De onde o dinheiro veio. Soma do valor das entradas (positivas) por categoria "
               "(Recebimento PIX, TED, Boleto...).")
            en = d[d[valor] > 0]
            _donut(_dgroup(en, "_cat", valor), "_cat", valor)

        _h("Custos bancários (tarifas, IOF, juros)",
           "Quanto o banco cobrou no período. Soma das saídas das categorias Tarifas/Fatura, "
           "IOF e Juros/Encargos. Quanto menor, melhor.")
        cb = d[d["_cat"].isin(_EX_CUSTO) & (d[valor] < 0)].assign(_v=-d[valor])
        if cb.empty:
            st.caption("Sem custos bancários no filtro. 🎉")
        else:
            _bar(_dgroup(cb, "_cat", "_v", asc=True), "_cat", "_v",
                 horizontal=True, height=260, marker=ui.RED)

    # ===== Maiores =====
    with t3:
        if desc:
            en = d[d[valor] > 0].assign(_desc=d[desc].astype(str).str.slice(0, 40))
            grp_e = en.groupby("_desc")[valor].sum().reset_index()
            _ranking_bar(grp_e, "_desc", valor, "ex_ent",
                         "Maiores entradas", top=10, height=380, marker=ui.GREEN,
                         help="As 10 maiores entradas, somadas por descrição do lançamento.")

            sd = d[d[valor] < 0].assign(_desc=d[desc].astype(str).str.slice(0, 40),
                                        _v=-d[valor])
            grp_s = sd.groupby("_desc")["_v"].sum().reset_index()
            _ranking_bar(grp_s, "_desc", "_v", "ex_sai",
                         "Maiores saídas", top=10, height=380, marker=ui.RED,
                         help="As 10 maiores saídas (em valor absoluto), somadas por descrição.")

    # ===== Detalhado =====
    with t4:
        _h("Todos os lançamentos (conforme filtros)",
           "Extrato completo no filtro. Valor em verde (entrada) ou vermelho (saída), mais a "
           "categoria e o saldo após cada lançamento. Baixe em CSV/Excel abaixo.")
        dd = d.sort_values("_d") if data else d
        cols = [c for c in [data, desc, doc, "_cat", valor, saldo] if c]
        disp = dd[cols].rename(columns={"_cat": "Categoria"})
        _styled_table(disp, money_cols=[valor, saldo], sign_cols=[valor])
        st.download_button("⬇️ Baixar CSV", disp.to_csv(index=False).encode("utf-8-sig"),
                           "extrato.csv", "text/csv", key="ex_csv")
        st.caption(f"{len(dd)} lançamentos no filtro.")


# -----------------------------------------------------------------------------
# RECEBIDOS
# -----------------------------------------------------------------------------
def render_recebidos(fr):
    st.subheader("✅ Recebidos — Recebimentos")

    cliente = su.find_col(fr.raw.columns, "Cliente") or \
        su.find_col(fr.raw.columns, "Razão Social", "Razao Social")
    categoria = su.find_col(fr.raw.columns, "Categoria")
    conta = su.find_col(fr.raw.columns, "Conta Corrente")
    datac = su.find_col(fr.raw.columns, "Data de Crédito ou Débito (No Extrato)",
                        "Data de Crédito", "Data de Credito", "Data")
    nf = su.find_col(fr.raw.columns, "Nota Fiscal")
    recebido = su.find_col(fr.num.columns, "Recebido")
    bruto = su.find_col(fr.num.columns, "Valor da Conta", "Valor")
    juros = su.find_col(fr.num.columns, "Juros")
    multa = su.find_col(fr.num.columns, "Multa")
    desc_col = su.find_col(fr.num.columns, "Desconto")
    imp_cols = {n: su.find_col(fr.num.columns, f"Valor {n}")
                for n in ["PIS", "COFINS", "CSLL", "IR", "ISS", "INSS"]}
    imp_cols = {n: c for n, c in imp_cols.items() if c}

    if not recebido:
        st.warning("Não encontrei a coluna 'Recebido' nesta aba.")
        _table(fr)
        return

    # ---------- Filtros ----------
    def opts(col):
        if not col:
            return []
        s = fr.raw[col].astype(str).str.strip()
        return sorted(s[s != ""].unique())

    def cat_short(v):
        return str(v).split(" - ")[-1].strip()

    st.markdown("##### 🔎 Filtros")
    f1, f2, f3 = st.columns([1.2, 1, 1.2])
    sel_cat = f1.multiselect("Categoria", opts(categoria), default=opts(categoria), key="rc_cat")
    sel_cc = f2.multiselect("Conta corrente", opts(conta), default=opts(conta), key="rc_cc")
    busca = f3.text_input("Buscar cliente", key="rc_busca")

    dmin = dmax = None
    if datac:
        dts = su.parse_dates(fr.raw[datac]).dropna()
        if not dts.empty:
            dmin, dmax = dts.min().date(), dts.max().date()
    if dmin and dmax and dmin < dmax:
        d1, d2 = st.slider("Período (data de crédito)", dmin, dmax, (dmin, dmax),
                           format="DD/MM/YYYY", key="rc_per")
    else:
        d1, d2 = dmin, dmax

    # ---------- Aplica filtros ----------
    d = fr.num.copy()
    if categoria:
        d = d[d[categoria].astype(str).str.strip().isin(sel_cat)]
    if conta:
        d = d[d[conta].astype(str).str.strip().isin(sel_cc)]
    if busca and cliente:
        d = d[d[cliente].astype(str).str.contains(busca, case=False, na=False)]
    if datac and d1:
        vv = su.parse_dates(d[datac])
        d = d[((vv.dt.date >= d1) & (vv.dt.date <= d2)).fillna(False)]
    if d.empty:
        st.warning("Nenhum recebimento corresponde aos filtros.")
        return

    # ---------- Métricas ----------
    tot_rec = d[recebido].sum()
    tot_bruto = d[bruto].sum() if bruto else 0
    imp_total = float(sum(d[c].sum() for c in imp_cols.values())) if imp_cols else 0
    juros_t = d[juros].sum() if juros else 0
    multa_t = d[multa].sum() if multa else 0
    desc_t = d[desc_col].sum() if desc_col else 0
    n_rec = len(d)
    n_cli = d[cliente].astype(str).str.strip().replace("", pd.NA).nunique() if cliente else 0
    ticket = tot_rec / n_rec if n_rec else 0

    ui.kpi_row([
        {"label": "Recebido (líquido)", "value": su.format_brl(tot_rec), "color": ui.GREEN,
         "help": "Quanto de fato caiu na conta. Soma da coluna 'Recebido' (já descontados "
                 "impostos retidos), no filtro atual."},
        {"label": "Valor bruto", "value": su.format_brl(tot_bruto), "color": ui.BLUE,
         "sub": "antes de retenções",
         "help": "Valor cheio dos recebimentos, antes das retenções. Soma da coluna "
                 "'Valor da Conta'."},
        {"label": "Impostos retidos", "value": su.format_brl(imp_total), "color": ui.RED,
         "sub": "PIS/COFINS/CSLL/IR",
         "help": "Impostos que o cliente reteve na fonte. Soma das colunas Valor PIS + "
                 "COFINS + CSLL + IR + ISS + INSS."},
        {"label": "Recebimentos", "value": str(n_rec), "color": ui.TEAL,
         "sub": f"{n_cli} clientes",
         "help": "Quantidade de recebimentos (linhas) no filtro. Abaixo, o nº de clientes "
                 "diferentes."},
    ])
    ui.kpi_row([
        {"label": "Ticket médio", "value": su.format_brl(ticket), "color": ui.SLATE,
         "help": "Valor médio por recebimento. Conta: Recebido líquido ÷ nº de recebimentos."},
        {"label": "Juros + Multa", "value": su.format_brl(juros_t + multa_t), "color": ui.AMBER,
         "sub": "recebidos a mais",
         "help": "Valores extras recebidos por atraso do cliente. Soma das colunas Juros + "
                 "Multa."},
        {"label": "Descontos", "value": su.format_brl(desc_t), "color": ui.SLATE,
         "sub": "concedidos",
         "help": "Descontos dados aos clientes. Soma da coluna 'Desconto'."},
        {"label": "% líquido/bruto",
         "value": f"{(tot_rec / tot_bruto * 100):.1f}%" if tot_bruto else "—",
         "color": ui.PURPLE,
         "help": "Quanto sobra do bruto após retenções. Conta: Recebido líquido ÷ Valor "
                 "bruto × 100."},
    ])
    st.divider()

    t1, t2, t3, t4 = st.tabs(
        ["🖥️ Visão Geral", "🎯 Clientes", "🧮 Impostos & Deduções", "🗂️ Detalhado"])

    # ===== Visão Geral =====
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            if categoria:
                _h("Recebido por categoria",
                   "Recebido líquido somado por categoria da receita (ex.: Licença de Uso, "
                   "Serviços/Consultoria). Cada fatia é a soma de 'Recebido' da categoria.")
                dd = d.assign(_cat=d[categoria].map(cat_short))
                _donut(_dgroup(dd, "_cat", recebido), "_cat", recebido)
        with c2:
            if conta:
                _h("Recebido por conta corrente",
                   "Em qual banco o dinheiro entrou. Soma de 'Recebido' por Conta Corrente "
                   "(Omie.CASH, Sicredi, Banco do Brasil).")
                _donut(_dgroup(d, conta, recebido), conta, recebido)
        if datac:
            _h("Recebimentos por dia (data de crédito)",
               "Quanto entrou em cada dia. Soma de 'Recebido' pela 'Data de Crédito' (dia em "
               "que o valor caiu na conta).")
            dd = d.assign(_d=su.parse_dates(d[datac])).dropna(subset=["_d"])
            g = dd.groupby("_d")[recebido].sum().reset_index().sort_values("_d")
            fig = px.bar(g, x="_d", y=recebido, text_auto=".2s")
            fig.update_traces(marker_color=ui.GREEN, textposition="outside", cliponaxis=False)
            _mt(fig, date=True)
            _plot(ui.style_fig(fig, 320, legend=False), width="stretch")

    # ===== Clientes =====
    with t2:
        if cliente:
            _ranking_bar(_dgroup(d, cliente, recebido), cliente, recebido, "rc_cli",
                         "Recebido por cliente", top=15, height=460, marker=ui.GREEN,
                         help="Recebido líquido somado por cliente, do maior para o menor. "
                              "Mostra quem mais pagou no período.")
            _h("Concentração (Pareto) — maiores clientes",
               "Barras = recebido por cliente (maior→menor). A linha é o % acumulado: "
               "mostra se poucos clientes concentram a maior parte do que foi recebido.")
            _pareto(d, cliente, recebido)

    # ===== Impostos & Deduções =====
    with t3:
        _h("De bruto a líquido",
           "Passo a passo do valor cheio até o que caiu na conta: Bruto − Impostos retidos − "
           "Descontos + Juros + Multa = Recebido líquido.")
        fig = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "relative", "total"],
            x=["Bruto", "− Impostos", "− Descontos", "+ Juros", "+ Multa", "Recebido"],
            y=[tot_bruto, -imp_total, -desc_t, juros_t, multa_t, 0],
            text=[su.format_brl(v) for v in
                  [tot_bruto, -imp_total, -desc_t, juros_t, multa_t, tot_rec]],
            textposition="outside",
            textfont=dict(size=11, color="#C7CEDB"),
            connector={"line": {"color": "rgba(100,116,139,0.4)", "width": 1.5,
                                "dash": "dot"}},
            increasing={"marker": {"color": ui.GREEN, "line": {"width": 0}}},
            decreasing={"marker": {"color": ui.RED, "line": {"width": 0}}},
            totals={"marker": {"color": ui.PRIMARY, "line": {"width": 0}}},
            opacity=0.9,
        ))
        _plot(ui.style_fig(fig, 340, legend=False), width="stretch")

        if imp_cols:
            _h("Impostos retidos por tipo",
               "Quanto foi retido de cada imposto. Soma de cada coluna: Valor PIS, COFINS, "
               "CSLL, IR, ISS, INSS.")
            g = pd.DataFrame({"Imposto": list(imp_cols.keys()),
                              "Valor": [float(d[c].sum()) for c in imp_cols.values()]})
            g = g[g["Valor"] > 0].sort_values("Valor", ascending=False)
            _bar(g, "Imposto", "Valor", marker=ui.RED)

    # ===== Detalhado =====
    with t4:
        _h("Todos os recebimentos (conforme filtros)",
           "Tabela completa dos recebimentos no filtro, com data, cliente, categoria, conta, "
           "bruto, impostos e líquido. Baixe em CSV/Excel no botão abaixo.")
        disp = d.copy()
        if imp_cols:
            disp["Impostos"] = sum(disp[c] for c in imp_cols.values())
        if datac:
            disp = disp.assign(_s=su.parse_dates(disp[datac])).sort_values("_s").drop(columns="_s")
        show = [c for c in [datac, cliente, categoria, conta, nf, bruto,
                            ("Impostos" if imp_cols else None), recebido] if c]
        _styled_table(disp[show], money_cols=[bruto, "Impostos", recebido])
        st.download_button("⬇️ Baixar CSV", disp[show].to_csv(index=False).encode("utf-8-sig"),
                           "recebidos.csv", "text/csv", key="rc_csv")
        st.caption(f"{len(disp)} recebimentos no filtro.")


# -----------------------------------------------------------------------------
# SEGMENTO — Carteira de Projetos / Contratos
# -----------------------------------------------------------------------------
def _seg_normaliza(serie: pd.Series) -> pd.Series:
    """Normaliza segmentos: RPA/Saas -> RPA/SaaS, Cloud -> CLOUD etc."""
    m = {"rpa/saas": "RPA/SaaS", "rpa/saas ": "RPA/SaaS",
         "cloud": "CLOUD", "e-push/saas": "E-Push/SaaS"}
    return serie.astype(str).str.strip().map(lambda x: m.get(x.lower(), x))


def render_segmento(fr):
    st.subheader("🏷️ Segmento — Carteira de Projetos")
    hoje = pd.Timestamp.today().normalize()

    status  = su.find_col(fr.raw.columns, "Status")
    projeto = su.find_col(fr.raw.columns, "PROJETO", "Projeto")
    fat_por = su.find_col(fr.raw.columns, "Faturar por")
    seg     = su.find_col(fr.raw.columns, "Segmento")
    cli     = su.find_col(fr.raw.columns, "Cliente")
    parcela = su.find_col(fr.raw.columns, "Parcela")
    desc    = su.find_col(fr.raw.columns, "DESCRIÇÃO DO PROJETO", "Descrição do Projeto")
    venc    = su.find_col(fr.raw.columns, "Vencimento")
    prev_fat= su.find_col(fr.raw.columns, "Dt.Prevista Fatura", "Previsão Fatura")
    emissao = su.find_col(fr.raw.columns, "Data Emissão")
    nf_col  = su.find_col(fr.raw.columns, "NF")
    val_tot = su.find_col(fr.num.columns, "Valor total", "Valor Total")
    val_par = su.find_col(fr.num.columns, "Valor")

    if not val_par:
        st.warning("Não encontrei a coluna 'Valor' nesta aba.")
        _table(fr)
        return

    # normaliza segmentos
    d = fr.num.copy()
    if seg:
        d[seg] = _seg_normaliza(d[seg])

    def opts(col):
        if not col:
            return []
        s = d[col].astype(str).str.strip()
        return sorted(s[s.replace("nan", "").str.strip() != ""].unique())

    # ---------- Filtros ----------
    st.markdown("##### 🔎 Filtros")
    f1, f2, f3, f4 = st.columns([1, 1, 1.5, 1.5])
    sel_status = f1.multiselect("Status", opts(status), default=opts(status), key="sg_st")
    sel_emp    = f2.multiselect("Faturar por", opts(fat_por), default=opts(fat_por), key="sg_emp")
    sel_seg    = f3.multiselect("Segmento", opts(seg), default=opts(seg), key="sg_seg")
    busca      = f4.text_input("Buscar cliente / projeto", key="sg_busca")

    dmin = dmax = None
    if venc:
        dts = su.parse_dates(d[venc]).dropna()
        if not dts.empty:
            dmin, dmax = dts.min().date(), dts.max().date()
    if dmin and dmax and dmin < dmax:
        d1, d2 = st.slider("Período (vencimento)", dmin, dmax, (dmin, dmax),
                           format="DD/MM/YYYY", key="sg_per")
    else:
        d1, d2 = dmin, dmax

    # aplica filtros
    if status:
        d = d[d[status].astype(str).str.strip().isin(sel_status)]
    if fat_por:
        d = d[d[fat_por].astype(str).str.strip().isin(sel_emp)]
    if seg:
        d = d[d[seg].astype(str).str.strip().isin(sel_seg)]
    if busca:
        campos = [c for c in [cli, projeto] if c]
        m2 = pd.Series(False, index=d.index)
        for c in campos:
            m2 |= d[c].astype(str).str.contains(busca, case=False, na=False)
        d = d[m2]
    if venc and d1:
        vv = su.parse_dates(d[venc])
        d = d[((vv.dt.date >= d1) & (vv.dt.date <= d2)).fillna(False)]

    if d.empty:
        st.warning("Nenhum registro corresponde aos filtros.")
        return

    # ---------- Métricas ----------
    total_mes   = d[val_par].sum()
    total_cart  = d[val_tot].sum() if val_tot else 0
    n_fat       = int((d[status].astype(str).str.strip() == "Faturado").sum()) if status else 0
    n_a_fat     = int((d[status].astype(str).str.strip() == "Faturar").sum()) if status else 0
    val_fat     = d.loc[d[status].astype(str).str.strip() == "Faturado", val_par].sum() if status else 0
    val_a_fat   = d.loc[d[status].astype(str).str.strip() == "Faturar",  val_par].sum() if status else 0
    n_cli       = d[cli].astype(str).str.strip().replace("", pd.NA).nunique() if cli else 0
    ticket      = total_mes / len(d) if len(d) else 0
    # vencendo em 7 dias
    prox7 = pd.Series(dtype=float)
    if venc:
        vd = su.parse_dates(d[venc])
        prox7 = d[(vd >= hoje) & (vd <= hoje + pd.Timedelta(days=7))][val_par]
    n_seg = d[seg].astype(str).str.strip().replace("", pd.NA).nunique() if seg else 0

    ui.kpi_row([
        {"label": "Valor do Mês", "value": su.format_brl(total_mes), "color": ui.GREEN,
         "sub": f"{len(d)} parcelas",
         "help": "Soma do campo 'Valor' (parcela mensal) de todos os registros no filtro."},
        {"label": f"Faturado ({n_fat})", "value": su.format_brl(val_fat), "color": ui.TEAL,
         "help": "Parcelas com Status = Faturado. Já foram emitidas NF."},
        {"label": f"A Faturar ({n_a_fat})", "value": su.format_brl(val_a_fat), "color": ui.AMBER,
         "help": "Parcelas com Status = Faturar. NF ainda não emitida."},
        {"label": "Vence em 7 dias", "value": su.format_brl(prox7.sum()),
         "color": ui.RED if prox7.sum() > 0 else ui.SLATE,
         "sub": f"{len(prox7)} parcelas",
         "help": "Parcelas cujo vencimento cai nos próximos 7 dias."},
    ])
    ui.kpi_row([
        {"label": "Carteira Total", "value": su.format_brl(total_cart), "color": ui.BLUE,
         "sub": "soma Valor total dos contratos",
         "help": "Soma do campo 'Valor total' — representa o valor cheio de cada contrato, "
                 "não apenas a parcela do mês."},
        {"label": "Clientes", "value": str(n_cli), "color": ui.PURPLE,
         "help": "Quantidade de clientes únicos no filtro."},
        {"label": "Segmentos", "value": str(n_seg), "color": ui.PINK,
         "help": "Quantidade de segmentos diferentes no filtro."},
        {"label": "Ticket médio", "value": su.format_brl(ticket), "color": ui.SLATE,
         "help": "Valor médio por parcela. Conta: Valor do Mês ÷ nº de parcelas."},
    ])
    st.divider()

    t1, t2, t3, t4 = st.tabs(
        ["🖥️ Visão Geral", "🏷️ Segmentos", "🎯 Clientes", "🗂️ Detalhado"])

    # ===== Visão Geral =====
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            if status:
                _h("Status dos contratos",
                   "Divide o valor total das parcelas por Status: Faturado (NF emitida) "
                   "e Faturar (ainda pendente).")
                _donut(_dgroup(d, status, val_par), status, val_par,
                       cmap={"Faturado": ui.TEAL, "Faturar": ui.AMBER})
        with c2:
            if fat_por:
                _h("Por empresa (Faturar por)",
                   "Valor das parcelas por empresa que fatura (Roboteasy ou Agapys).")
                _donut(_dgroup(d, fat_por, val_par), fat_por, val_par)

        if venc:
            _h("Vencimentos por data",
               "Valor das parcelas agrupado pelo dia de vencimento. Mostra a "
               "concentração de recebimentos no mês.")
            dd = d.assign(_vd=su.parse_dates(d[venc])).dropna(subset=["_vd"])
            if not dd.empty:
                g = dd.assign(_s=d[status].astype(str).str.strip() if status else "")
                g = g.groupby(["_vd", "_s"])[val_par].sum().reset_index() if status \
                    else dd.groupby("_vd")[val_par].sum().reset_index()
                cmap_s = {"Faturado": ui.TEAL, "Faturar": ui.AMBER}
                if status:
                    fig = px.bar(g, x="_vd", y=val_par, color="_s",
                                 color_discrete_map=cmap_s, text_auto=".2s")
                else:
                    fig = px.bar(g, x="_vd", y=val_par, text_auto=".2s")
                    fig.update_traces(marker_color=ui.GREEN)
                fig.update_traces(marker_line_width=0, marker_cornerradius=_CORNER,
                                  textposition="outside", cliponaxis=False)
                _mt(fig, date=True, keepname=bool(status))
                fig.add_vline(x=hoje, line_dash="dot",
                              line_color="rgba(255,255,255,0.25)", line_width=1)
                _plot(ui.style_fig(fig, 320, legend=bool(status)), width="stretch")

        if prev_fat:
            _h("Cronograma de faturamento (data prevista de emissão NF)",
               "Agrupa as parcelas 'A Faturar' pela data prevista de emissão da NF. "
               "Mostra o que precisa ser faturado em cada dia.")
            dd2 = d[d[status].astype(str).str.strip() == "Faturar"] if status else d
            dd2 = dd2.assign(_pf=su.parse_dates(dd2[prev_fat])).dropna(subset=["_pf"])
            if not dd2.empty:
                g2 = dd2.groupby("_pf")[val_par].sum().reset_index().sort_values("_pf")
                fig2 = px.bar(g2, x="_pf", y=val_par, text_auto=".2s")
                fig2.update_traces(marker_color=ui.AMBER, marker_line_width=0,
                                   marker_cornerradius=_CORNER,
                                   textposition="outside", cliponaxis=False)
                _mt(fig2, date=True)
                fig2.add_vline(x=hoje, line_dash="dot",
                               line_color="rgba(255,255,255,0.25)", line_width=1)
                _plot(ui.style_fig(fig2, 300, legend=False), width="stretch")

    # ===== Segmentos =====
    with t2:
        if seg:
            c1, c2 = st.columns(2)
            with c1:
                _h("Valor por segmento",
                   "Soma do valor das parcelas agrupado por Segmento.")
                _bar(_dgroup(d, seg, val_par, asc=True), seg, val_par,
                     horizontal=True, height=360)
            with c2:
                _h("Distribuição de clientes por segmento",
                   "Quantidade de clientes únicos em cada segmento.")
                if cli:
                    g = d.copy()
                    g[seg] = g[seg].astype(str).str.strip()
                    g[cli] = g[cli].astype(str).str.strip()
                    cnt = g[g[seg] != ""].groupby(seg)[cli].nunique().reset_index()
                    cnt.columns = [seg, "Clientes"]
                    cnt = cnt.sort_values("Clientes", ascending=True)
                    _bar(cnt, seg, "Clientes", horizontal=True, height=360, money=False)

            if val_tot:
                _h("Carteira total por segmento",
                   "Soma de 'Valor total' dos contratos por segmento — representa "
                   "o comprometimento financeiro cheio de cada área.")
                _bar(_dgroup(d, seg, val_tot, asc=True), seg, val_tot,
                     horizontal=True, height=360, marker=ui.BLUE)

            _h("Status × Segmento",
               "Valor das parcelas por segmento e status. Mostra onde há mais "
               "a faturar vs já faturado.")
            if status:
                dd = d.copy()
                g = dd.groupby([seg, status])[val_par].sum().reset_index()
                fig = px.bar(g, x=seg, y=val_par, color=status, barmode="stack",
                             color_discrete_map={"Faturado": ui.TEAL, "Faturar": ui.AMBER},
                             text_auto=".2s")
                fig.update_traces(marker_line_width=0, marker_cornerradius=_CORNER)
                _mt(fig, keepname=True)
                _plot(ui.style_fig(fig, 360, legend=True), width="stretch")

    # ===== Clientes =====
    with t3:
        if cli:
            _ranking_bar(_dgroup(d, cli, val_par), cli, val_par, "sg_cli",
                         "Valor por cliente (parcela mensal)", top=20, height=500,
                         marker=ui.GREEN,
                         help="Soma do valor das parcelas por cliente, do maior para o menor.")

            _h("Concentração (Pareto) — maiores clientes",
               "Barras = valor por cliente (maior→menor). Linha = % acumulado. "
               "Mostra se poucos clientes concentram a maior parte do faturamento.")
            _pareto(d, cli, val_par)

            if val_tot and cli:
                _h("Carteira total por cliente (top 15)",
                   "Os 15 clientes com maior valor total de contrato (campo 'Valor total').")
                _ranking_bar(_dgroup(d, cli, val_tot), cli, val_tot, "sg_cli_tot",
                             "Valor total do contrato por cliente", top=15, height=420,
                             marker=ui.BLUE)

    # ===== Detalhado =====
    with t4:
        _h("Todos os registros (conforme filtros)",
           "Tabela completa com status colorido, parcela, vencimento e valor. "
           "Baixe em CSV pelo botão abaixo.")
        cols = [c for c in [status, fat_por, seg, cli, projeto, parcela,
                            venc, prev_fat, val_tot, val_par, nf_col, emissao, desc]
                if c and c in d.columns]
        disp = d[cols].copy().reset_index(drop=True)
        # ordenacao segura por vencimento
        if venc and venc in disp.columns:
            try:
                disp = disp.assign(
                    _ord=su.parse_dates(disp[venc])
                ).sort_values("_ord", na_position="last").drop(columns="_ord")
            except Exception:
                pass
        _styled_table(disp, money_cols=[val_tot, val_par],
                      status_col=status)
        st.download_button("⬇️ Baixar CSV",
                           disp.to_csv(index=False).encode("utf-8-sig"),
                           "segmento.csv", "text/csv", key="sg_csv")
        st.caption(f"{len(disp)} registros no filtro.")
