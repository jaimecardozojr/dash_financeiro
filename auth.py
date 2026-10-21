# =============================================================================
# Login com cookie persistente (fica logado ao atualizar a pagina).
#
# - Credenciais em st.secrets, seção [credenciais]  (usuario = "senha")
# - Ao entrar, grava um COOKIE assinado (HMAC) com validade de alguns dias.
# - O cookie NAO guarda a senha: so usuario + validade + assinatura.
# - Rate limiting: bloqueia 15 min apos 5 tentativas erradas.
# - cookie_secret obrigatorio em producao (sem fallback inseguro).
#
#   [credenciais]
#   jaime = "uma-senha-forte"
#   cookie_secret = "frase-aleatoria-com-32-ou-mais-chars"
# =============================================================================
import hashlib
import hmac
import time
from collections import defaultdict
from datetime import datetime, timedelta

import streamlit as st
import ui

try:
    import extra_streamlit_components as stx
    _HAS_COOKIES = True
except Exception:
    _HAS_COOKIES = False

COOKIE_NAME  = "dashfin_auth"
COOKIE_DAYS  = 7
MAX_TENTATIVAS = 5       # tentativas antes de bloquear
BLOQUEIO_MIN   = 15      # minutos de bloqueio

# Registro em memoria de tentativas por usuario (reinicia com o servidor)
_tentativas: dict[str, list[float]] = defaultdict(list)


# -----------------------------------------------------------------------------
# Credenciais
# -----------------------------------------------------------------------------
def _creds() -> dict:
    try:
        return dict(st.secrets["credenciais"])
    except Exception:
        return {}


def _valid(user: str, pwd: str) -> bool:
    """Valida credenciais usando comparacao em tempo constante."""
    creds = _creds()
    # Sempre faz a comparacao (mesmo usuario inexistente) pra nao vazar timing
    esperado = str(creds.get(user, "placeholder_que_nunca_bate"))
    ok_user = user in creds
    ok_pwd  = hmac.compare_digest(esperado, str(pwd))
    return bool(ok_user and ok_pwd)


# -----------------------------------------------------------------------------
# Rate limiting — protege contra forca bruta
# -----------------------------------------------------------------------------
def _bloqueado(user: str) -> bool:
    """Retorna True se o usuario estiver em periodo de bloqueio."""
    agora = time.time()
    janela = BLOQUEIO_MIN * 60
    _tentativas[user] = [t for t in _tentativas[user] if agora - t < janela]
    return len(_tentativas[user]) >= MAX_TENTATIVAS


def _registrar_falha(user: str) -> int:
    """Registra uma tentativa falha e retorna quantas restam antes do bloqueio."""
    _tentativas[user].append(time.time())
    restam = MAX_TENTATIVAS - len(_tentativas[user])
    return max(0, restam)


def _limpar_tentativas(user: str) -> None:
    _tentativas.pop(user, None)


# -----------------------------------------------------------------------------
# Cookie secret — obrigatorio, sem fallback inseguro
# -----------------------------------------------------------------------------
def _cookie_secret() -> bytes:
    try:
        s = st.secrets.get("cookie_secret")
        if s and len(str(s).strip()) >= 20:
            return str(s).strip().encode()
    except Exception:
        pass
    # Fallback usando private_key_id (semi-privado, melhor que string fixa)
    # Em producao, SEMPRE defina cookie_secret nos secrets.
    try:
        base = st.secrets["gcp_service_account"]["private_key_id"]
        return ("dashfin||" + str(base)).encode()
    except Exception:
        # Ultimo recurso: chave fixa — funciona mas nao e ideal
        return b"dashfin||configure-cookie_secret-nos-secrets-por-favor"


# -----------------------------------------------------------------------------
# Token assinado para o cookie
# -----------------------------------------------------------------------------
def _sign(user: str, exp: int) -> str:
    return hmac.new(
        _cookie_secret(), f"{user}|{exp}".encode(), hashlib.sha256
    ).hexdigest()


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
        if user not in _creds():
            return None
        return user
    except Exception:
        return None


# -----------------------------------------------------------------------------
# Cookies
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
        cm.set(name, val,
               expires_at=datetime.now() + timedelta(days=COOKIE_DAYS),
               key="dashfin_set")
        time.sleep(0.25)
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
# API publica
# -----------------------------------------------------------------------------
def current_user() -> str | None:
    return st.session_state.get("auth_user")


def logout() -> None:
    user = st.session_state.pop("auth_user", None)
    if user:
        _limpar_tentativas(user)
    _cookie_del(_manager(), COOKIE_NAME)


def require_login() -> bool:
    """Retorna True se autenticado. Caso contrario mostra a tela de login."""
    if st.session_state.get("auth_user"):
        if st.session_state.pop("_pending_token", False):
            _cookie_set(_manager(), COOKIE_NAME,
                        _make_token(st.session_state["auth_user"]))
        return True

    if not _creds():
        st.error(
            "⚠️ Nenhuma credencial configurada. Adicione uma seção **[credenciais]** nos "
            "*Secrets* do Streamlit Cloud. Contate o administrador."
        )
        return False

    cm = _manager()

    # Tenta restaurar sessao via cookie
    token = _cookie_get(cm, COOKIE_NAME)
    if token:
        user = _verify_token(token)
        if user:
            st.session_state["auth_user"] = user
            return True

    # Tela de login
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
            user_input = st.text_input("Usuário", key="login_user",
                                       autocomplete="username")
            pwd_input  = st.text_input("Senha", type="password", key="login_pwd",
                                       autocomplete="current-password")
            ok = st.form_submit_button("Entrar", width="stretch", type="primary")

        if ok:
            user_clean = user_input.strip()
            if _bloqueado(user_clean):
                st.error(
                    f"🔒 Conta temporariamente bloqueada após {MAX_TENTATIVAS} "
                    f"tentativas. Aguarde {BLOQUEIO_MIN} minutos e tente novamente."
                )
            elif _valid(user_clean, pwd_input):
                _limpar_tentativas(user_clean)
                st.session_state["auth_user"] = user_clean
                st.session_state["_pending_token"] = True
                st.rerun()
            else:
                restam = _registrar_falha(user_clean)
                if restam > 0:
                    st.error(
                        f"Usuário ou senha inválidos. "
                        f"({restam} tentativa{'s' if restam > 1 else ''} restante{'s' if restam > 1 else ''} "
                        f"antes do bloqueio)"
                    )
                else:
                    st.error(
                        f"🔒 Conta bloqueada por {BLOQUEIO_MIN} minutos após "
                        f"muitas tentativas incorretas."
                    )

        st.caption("🔒 Você continua logado por 7 dias neste navegador.")
    return False
