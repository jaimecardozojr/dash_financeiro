# =============================================================================
# Funcoes puras de tratamento dos dados da planilha (sem Streamlit).
# Ficam separadas para poderem ser testadas de forma isolada.
# =============================================================================
import re
from collections import namedtuple

import pandas as pd
from gspread.utils import rowcol_to_a1

DATE_FMT = "%d/%m/%Y"
DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")

# Conjunto de dados ja tratados de uma aba.
Frames = namedtuple("Frames", "raw num nums dates first_row header_row")


def find_col(cols, *candidates):
    """Acha o nome real de uma coluna tolerando acentos/maiusculas/variacoes.

    Primeiro tenta correspondencia exata (sem caso), depois parcial.
    """
    norm = {str(c).strip().lower(): c for c in cols}
    for cand in candidates:
        key = cand.strip().lower()
        if key in norm:
            return norm[key]
    for cand in candidates:
        key = cand.strip().lower()
        for c in cols:
            if key in str(c).strip().lower():
                return c
    return None


def detect_header_row(values) -> int:
    """Descobre em qual linha (0-based) estao os titulos das colunas."""
    counts = [sum(1 for c in row if str(c).strip()) for row in values]
    if not counts:
        return 0
    maxc = max(counts)
    thr = max(3, 0.6 * maxc)
    for i in range(len(values) - 1):
        if counts[i] >= thr and counts[i + 1] >= max(2, 0.4 * maxc):
            return i
    for i, c in enumerate(counts):  # fallback: 1a linha com conteudo
        if c > 0:
            return i
    return 0


def build_df(values, header_row: int):
    """Monta um DataFrame a partir da linha de cabecalho indicada.

    Retorna (df, primeira_linha_de_dados_na_planilha_1based).
    A linha i do df corresponde a linha (first_data_row + i) da planilha.
    """
    if not values or header_row >= len(values):
        return pd.DataFrame(), header_row + 2
    header = values[header_row]
    data = values[header_row + 1:]
    last = len(data)  # remove apenas as linhas vazias do fim
    while last > 0 and not any(str(c).strip() for c in data[last - 1]):
        last -= 1
    data = data[:last]

    width = max([len(header)] + [len(r) for r in data]) if data else len(header)
    seen, cols = {}, []
    for j in range(width):
        name = header[j].strip() if j < len(header) else ""
        if not name:
            name = f"Coluna {j + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 0
        cols.append(name)

    rows = [list(r) + [""] * (width - len(r)) for r in data]
    df = pd.DataFrame(rows, columns=cols)
    return df, header_row + 2


def drop_summary_rows(df, numeric_cols):
    """Remove linhas de 'Total'/subtotal e numeros soltos (sem rotulo de texto).

    - 'stray': linha que so tem numero(s) preenchido(s), sem nenhum texto que a
      identifique (ex.: um total de coluna que sobrou numa celula isolada).
    - 'total': linha cuja PRIMEIRA coluna diz Total/Subtotal/Soma (linha de resumo
      da planilha). So checa a 1a coluna para nao confundir com um fornecedor/cliente
      que por acaso se chame 'Total'.
    """
    if df.empty:
        return df
    numeric_cols = [c for c in numeric_cols if c in df.columns]
    text_cols = [c for c in df.columns if c not in numeric_cols]

    def is_stray(r):
        tem_texto = any(str(r[c]).strip() for c in text_cols)
        tem_num = any(str(r[c]).strip() for c in numeric_cols)
        return (not tem_texto) and tem_num

    stray = (df.apply(is_stray, axis=1) if text_cols
             else pd.Series(False, index=df.index))
    primeiro = df.iloc[:, 0].astype(str).str.strip().str.lower()
    totais = primeiro.isin({"total", "totais", "subtotal", "sub-total",
                            "soma", "total geral"})
    return df[~(stray | totais)].reset_index(drop=True)


def _num_simples(s):
    """Converte '24645.09', '-497', '-1832.5' em float (ou None)."""
    try:
        return float(str(s).replace(" ", "").replace(" ", ""))
    except (TypeError, ValueError):
        return None


def _fmt_money_br(s) -> str:
    """Formata um numero em R$ brasileiro; negativo entre parenteses."""
    x = _num_simples(s)
    if x is None:
        return str(s).strip()
    v = f"{abs(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"(R$ {v})" if x < 0 else f"R$ {v}"


def parse_extrato_sicredi(file, filename: str = "") -> list:
    """Le um extrato Sicredi (.xls/.xlsx) e devolve as linhas prontas para a aba.

    Mantem o cabecalho (Associado/Cooperativa/Conta/periodo), a linha de titulos
    (Data/Descricao/...), 'Saldo Anterior' e os lancamentos — formatando Valor e
    Saldo em R$. Ignora marketing e a secao de 'Lancamentos Futuros'.
    """
    name = (filename or getattr(file, "name", "") or "").lower()
    engine = "openpyxl" if name.endswith(".xlsx") else "xlrd"
    df = pd.read_excel(file, header=None, dtype=str, engine=engine).fillna("")
    rows = [[str(c).strip() for c in r] for r in df.values.tolist()]

    # acha a linha de titulos (col0 == 'Data' e algum 'Valor')
    hidx = None
    for i, r in enumerate(rows):
        if r and r[0].lower() == "data" and any("valor" in c.lower() for c in r):
            hidx = i
            break
    if hidx is None:
        raise ValueError("cabecalho (Data/Valor) nao encontrado — este arquivo e um "
                         "extrato Sicredi em .xls?")

    out = [r[:5] + [""] * (5 - len(r)) for r in rows[:hidx + 1]]  # cabecalho + titulos

    for r in rows[hidx + 1:]:
        r = (r + [""] * 5)[:5]
        col0, col1 = r[0], r[1]
        is_saldo_ant = col1.lower().startswith("saldo anterior")
        is_txn = bool(DATE_RE.match(col0))
        if is_saldo_ant or is_txn:
            r[3] = _fmt_money_br(r[3]) if r[3] else ""
            r[4] = _fmt_money_br(r[4]) if r[4] else ""
            out.append(r)
        elif col0:  # texto que nao e data = marketing / 'Lancamentos Futuros' -> fim
            break
        # linha vazia: ignora e continua
    return out


def parse_br_number(series: pd.Series) -> pd.Series:
    """Converte texto brasileiro (R$ 1.234,56 ; (R$ 10,00) ; 10%) para numero."""
    s = series.astype(str).str.strip()
    negativo = s.str.startswith("(") & s.str.endswith(")")
    cleaned = (
        s.str.replace("R$", "", regex=False)
        .str.replace("(", "", regex=False)
        .str.replace(")", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace(".", "", regex=False)   # separador de milhar
        .str.replace(",", ".", regex=False)  # separador decimal
        .str.replace(" ", "", regex=False)
        .str.strip()
    )
    nums = pd.to_numeric(cleaned, errors="coerce")
    return nums.where(~negativo, -nums.abs())


def numeric_df(df: pd.DataFrame):
    """Retorna (df com colunas numericas convertidas, lista dessas colunas)."""
    out = df.copy()
    numeric_cols = []
    for col in out.columns:
        non_empty = out[col].astype(str).str.strip().replace("", pd.NA).notna().sum()
        if non_empty == 0:
            continue
        parsed = parse_br_number(out[col])
        if parsed.notna().sum() >= max(1, int(0.6 * non_empty)):
            out[col] = parsed
            numeric_cols.append(col)
    return out, numeric_cols


def date_columns(df: pd.DataFrame):
    cols = []
    for col in df.columns:
        s = df[col].astype(str).str.strip()
        non_empty = s[s != ""]
        if len(non_empty) and non_empty.str.match(DATE_RE).sum() >= 0.6 * len(non_empty):
            cols.append(col)
    return cols


def parse_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series.astype(str).str.strip(), format=DATE_FMT, errors="coerce")


def format_brl(v) -> str:
    try:
        s = f"{float(v):,.2f}"
    except (ValueError, TypeError):
        return "-"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def build_cell_updates(original_df, edited_df, first_data_row):
    """Calcula as atualizacoes minimas (celulas alteradas + linhas novas).

    Retorna (updates, n_celulas, n_linhas_novas, n_linhas_removidas) onde
    updates e uma lista no formato aceito por Worksheet.batch_update.
    """
    cols = list(original_df.columns)
    updates = []

    comum = min(len(original_df), len(edited_df))
    for i in range(comum):
        for j, col in enumerate(cols):
            antigo = "" if pd.isna(original_df.iloc[i][col]) else str(original_df.iloc[i][col])
            novo = "" if pd.isna(edited_df.iloc[i][col]) else str(edited_df.iloc[i][col])
            if antigo != novo:
                updates.append({"range": rowcol_to_a1(first_data_row + i, j + 1),
                                "values": [[novo]]})
    n_celulas = len(updates)

    novas = []
    for i in range(len(original_df), len(edited_df)):
        novas.append(["" if pd.isna(v) else str(v) for v in edited_df.iloc[i].tolist()])
    if novas:
        inicio = first_data_row + len(original_df)
        rng = f"{rowcol_to_a1(inicio, 1)}:{rowcol_to_a1(inicio + len(novas) - 1, len(cols))}"
        updates.append({"range": rng, "values": novas})

    removidas = max(0, len(original_df) - len(edited_df))
    return updates, n_celulas, len(novas), removidas
