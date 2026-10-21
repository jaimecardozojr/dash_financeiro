# =============================================================================
# Login com cookie persistente (fica logado ao atualizar a pagina).
#
# - Credenciais em st.secrets, seção [credenciais]  (usuario = "senha")
# - Ao entrar, grava um COOKIE assinado (HMAC) com validade de alguns dias.
#   Ao recarregar a pagina, o cookie restaura a sessao automaticamente.
# - O cookie NAO guarda a senha: so usuario + validade + assinatura.
#
#   [credenciais]
#   jaime = "uma-senha-forte"
#
# Opcional (recomendado em producao): defina uma chave propria para assinar:
#   cookie_secret = "uma-frase-aleatoria-bem-grande"
# =============================================================================
import hashlib
import hmac
import time
from datetime import datetime, timedelta

import streamlit as st
import ui

try:
    import extra_streamlit_components as stx
    _HAS_COOKIES = True
except Exception:
    _HAS_COOKIES = False

COOKIE_NAME = "dashfin_auth"
COOKIE_DAYS = 7


# -----------------------------------------------------------------------------
# Credenciais
# -----------------------------------------------------------------------------
def _creds() -> dict:
    try:
        return dict(st.secrets["credenciais"])
    except Exception:
        return {}


def _valid(user: str, pwd: str) -> bool:
    creds = _creds()
    esperado = str(creds.get(user, ""))
    ok_user = user in creds
    ok_pwd = hmac.compare_digest(esperado, str(pwd))
    return bool(ok_user and ok_pwd)


# -----------------------------------------------------------------------------
# Token assinado para o cookie
# -----------------------------------------------------------------------------
def _cookie_secret() -> bytes:
    try:
        s = st.secrets.get("cookie_secret")
    except Exception:
        s = None
    if s:
        return str(s).encode()
    # fallback estavel e secreto: deriva da conta de servico
    try:
        base = st.secrets["gcp_service_account"]["private_key_id"]
        return ("dashfin|" + str(base)).encode()
    except Exception:
        return b"dashfin|defina-cookie_secret-nos-secrets"


def _sign(user: str, exp: int) -> str:
    return hmac.new(_cookie_secret(), f"{user}|{exp}".encode(), hashlib.sha256).hexdigest()


def _make_token(user: str) -> str:
    exp = int(time.time()) + COOKIE_DAYS * 86400
    return f"{user}|{exp}|{_sign(user, exp)}"


def _verify_token(token) -> str | None:
    try:
        user, exp, sig = str(token).split("|")
        if int(exp) < int(time.time()):
            return None
        if not hmac.compare_digest(sig, _sign(user, int(exp))):
            return None
        if user not in _creds():  # usuario removido das credenciais
            return None
        return user
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Cookies (tolerante a falhas: se o componente falhar, cai para sessao simples)
# -----------------------------------------------------------------------------
def _manager():
    if not _HAS_COOKIES:
        return None
    try:
        return stx.CookieManager(key="dashfin_cookies")
    except Exception:
        return None


def _cookie_get(cm, name):
    if cm is None:
        return None
    try:
        return cm.get(name)
    except Exception:
        return None


def _cookie_set(cm, name, val):
    if cm is None:
        return
    try:
        cm.set(name, val, expires_at=datetime.now() + timedelta(days=COOKIE_DAYS),
               key="dashfin_set")
        time.sleep(0.25)  # deixa o navegador gravar antes do rerun
    except Exception:
        pass


def _cookie_del(cm, name):
    if cm is None:
        return
    try:
        cm.delete(name, key="dashfin_del")
        time.sleep(0.2)
    except Exception:
        pass


# -----------------------------------------------------------------------------
# API
# -----------------------------------------------------------------------------
def current_user():
    return st.session_state.get("auth_user")


def logout():
    st.session_state.pop("auth_user", None)
    _cookie_del(_manager(), COOKIE_NAME)


def require_login() -> bool:
    """Retorna True se autenticado. Caso contrario mostra a tela de login."""
    if st.session_state.get("auth_user"):
        # grava o cookie logo apos o login, numa execucao estavel (sem corrida com rerun)
        if st.session_state.pop("_pending_token", False):
            _cookie_set(_manager(), COOKIE_NAME, _make_token(st.session_state["auth_user"]))
        return True

    if not _creds():
        st.error(
            "⚠️ Nenhuma credencial configurada. Adicione uma seção **[credenciais]** no "
            "`.streamlit/secrets.toml` (ou nos *Secrets* do Streamlit Cloud). Exemplo:\n\n"
            "```toml\n[credenciais]\njaime = \"uma-senha-forte\"\n```"
        )
        return False

    cm = _manager()

    # 1) tenta restaurar a sessao a partir do cookie
    token = _cookie_get(cm, COOKIE_NAME)
    if token:
        user = _verify_token(token)
        if user:
            st.session_state["auth_user"] = user
            return True

    # 2) tela de login
    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        with st.form("login_form"):
            logo = ui.logo_img_tag(height=56)
            logo_html = (f"<div class='login-logo'>{logo}</div>" if logo
                         else "<div class='login-logo' style='font-size:2.4rem'>📊</div>")
            st.markdown(
                f"<div class='login-head'>"
                f"{logo_html}"
                f"<div class='login-title'>Dashboard Financeiro</div>"
                f"<div class='login-sub'>Acesso restrito — entre para continuar</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            user = st.text_input("Usuário", key="login_user", autocomplete="username")
            pwd = st.text_input("Senha", type="password", key="login_pwd",
                                autocomplete="current-password")
            ok = st.form_submit_button("Entrar", width="stretch", type="primary")
        if ok:
            if _valid(user.strip(), pwd):
                st.session_state["auth_user"] = user.strip()
                st.session_state["_pending_token"] = True  # cookie gravado no proximo run
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")
        st.caption("🔒 Você continua logado por 7 dias neste navegador.")
    return False
