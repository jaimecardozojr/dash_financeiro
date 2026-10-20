# 🚀 Como colocar o Dashboard online (com login)

O app já tem uma **tela de login**. Só entra quem tiver usuário e senha definidos
na seção `[credenciais]` do `secrets.toml`.

---

## 🔐 Antes de tudo — segurança (leia!)

O arquivo **`.streamlit/secrets.toml`** contém a **chave privada do Google** e as
**senhas**. Ele **NUNCA** pode ir para o GitHub nem ser compartilhado.

- Já está protegido no `.gitignore`. ✔️
- O arquivo **`# ===== GOOGLE SHEETS =====.txt`** também não deve subir (está no
  `.gitignore`). Pode **apagá-lo** — tudo que importa já está no `secrets.toml`.
- Para deixar o modelo documentado sem expor segredos, use o
  **`.streamlit/secrets.toml.example`** (esse pode ser versionado).

---

## 👤 Definir quem pode entrar

No `secrets.toml`, seção `[credenciais]` (um por linha, `usuario = "senha"`):

```toml
[credenciais]
jaime = "uma-senha-forte"
financeiro = "outra-senha-forte"
```

Para adicionar/remover pessoas, basta editar essas linhas. **Troque a senha padrão!**

---

## ☁️ Opção A — Streamlit Community Cloud (grátis, recomendado)

Melhor caminho: dá uma **URL https** pública, sem você manter servidor. Precisa de
uma conta no **GitHub**.

1. **Crie um repositório no GitHub** (pode ser **privado**).
2. **Suba os arquivos** do projeto. Formas fáceis:
   - **GitHub Desktop** (visual, recomendado para quem não usa terminal), ou
   - Terminal, dentro da pasta do projeto:
     ```powershell
     git init
     git add .
     git commit -m "Dashboard financeiro"
     git branch -M main
     git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
     git push -u origin main
     ```
   > O `secrets.toml` **não sobe** (o `.gitignore` cuida disso). Confirme que ele
   > **não aparece** na lista de arquivos enviados.
3. Acesse **https://share.streamlit.io** e faça login com o GitHub.
4. **New app** → escolha o repositório, a branch `main` e o arquivo **`app.py`**.
5. Em **Advanced settings → Secrets**, cole **todo** o conteúdo do seu
   `secrets.toml` (o `sheet_id`, o bloco `[gcp_service_account]` e o
   `[credenciais]`).
6. **Deploy**. Em alguns minutos você recebe a URL (ex.: `https://seu-app.streamlit.app`).
7. Pronto: quem abrir vê a **tela de login** primeiro. 🎉

> Atualizou o código? Dê `git push` que o Streamlit Cloud atualiza sozinho.
> Trocar senhas/usuários? Edite em **Settings → Secrets** no painel do app.

---

## 🖥️ Opção B — Seu próprio servidor (VPS ou um PC)

1. Copie a pasta do projeto para o servidor (inclua um `secrets.toml` real lá —
   ele não vem do GitHub).
2. Instale Python 3.12+ e as dependências:
   ```bash
   python -m venv .venv
   # Windows:  .\.venv\Scripts\Activate.ps1
   # Linux:    source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Rode acessível na rede:
   ```bash
   streamlit run app.py --server.port 8501 --server.address 0.0.0.0
   ```
   - `0.0.0.0` libera o acesso pela rede. Abra a **porta 8501** no firewall.
4. **Manter rodando** (sem precisar deixar o terminal aberto):
   - **Linux**: crie um serviço `systemd`, ou use `pm2`/`screen`/`nohup`.
   - **Windows**: use o **NSSM** (roda como serviço) ou o **Agendador de Tarefas**.
5. **HTTPS (importante!)**: como as senhas trafegam, coloque um proxy reverso na
   frente com certificado. O **Caddy** faz HTTPS automático:
   ```
   seu-dominio.com {
       reverse_proxy localhost:8501
   }
   ```
   (Nginx + Let's Encrypt também funciona.)

---

## ❓ Perguntas comuns

- **Preciso pedir login toda vez?** Sim, a cada nova sessão/atualização de página —
  é o comportamento seguro. Se quiser login persistente por X dias (via cookie),
  dá para evoluir com a biblioteca `streamlit-authenticator` depois.
- **Esqueci a senha.** Edite a seção `[credenciais]` no `secrets.toml` (local) ou
  nos Secrets do Streamlit Cloud.
- **Dados não aparecem no deploy.** Confira se a planilha está compartilhada com o
  e-mail da conta de serviço e se o `sheet_id`/segredos foram colados corretamente.
