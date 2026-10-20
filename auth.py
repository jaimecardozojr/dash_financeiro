# =============================================================================
# Login simples para proteger o dashboard.
#
# As credenciais ficam em st.secrets, seção [credenciais] (usuario = "senha"):
#
#   [credenciais]
#   jaime = "uma-senha-forte"
#   financeiro = "outra-senha"
#
# Nunca ficam no código. Em produção (Streamlit Cloud) vão nos "Secrets" do app.
# =============================================================================
import hmac

import streamlit as st


def _creds() -> dict:
    try:
        return dict(st.secrets["credenciais"])
    except Exception:
        return {}


def _valid(user: str, pwd: str) -> bool:
    creds = _creds()
    # comparacao em tempo constante (evita descobrir usuario por timing)
    esperado = str(creds.get(user, ""))
    ok_user = user in creds
    ok_pwd = hmac.compare_digest(esperado, str(pwd))
    return bool(ok_user and ok_pwd)


def current_user():
    return st.session_state.get("auth_user")


def logout():
    st.session_state.pop("auth_user", None)


def require_login() -> bool:
    """Retorna True se autenticado. Caso contrario mostra a tela de login."""
    if st.session_state.get("auth_user"):
        return True

    if not _creds():
        st.error(
            "⚠️ Nenhuma credencial configurada. Adicione uma seção **[credenciais]** no "
            "`.streamlit/secrets.toml` (ou nos *Secrets* do Streamlit Cloud). Exemplo:\n\n"
            "```toml\n[credenciais]\njaime = \"uma-senha-forte\"\n```"
        )
        return False

    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        with st.form("login_form"):
            st.markdown(
                "<div class='login-head'>"
                "<div class='login-logo'>📊</div>"
                "<div class='login-title'>Dashboard Financeiro</div>"
                "<div class='login-sub'>Acesso restrito — entre para continuar</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            user = st.text_input("Usuário", key="login_user", autocomplete="username")
            pwd = st.text_input("Senha", type="password", key="login_pwd",
                                autocomplete="current-password")
            ok = st.form_submit_button("Entrar", width="stretch", type="primary")
        if ok:
            if _valid(user.strip(), pwd):
                st.session_state["auth_user"] = user.strip()
                st.rerun()
            else:
                st.error("Usuário ou senha inválidos.")
        st.caption("🔒 Seus dados financeiros são privados.")
    return False
