# 📊 Dashboard Financeiro (Google Sheets + Streamlit)

Lê sua planilha do Google Sheets, mostra um dashboard com indicadores e gráficos,
atualiza quando a planilha muda e permite **editar os dados pelo próprio app**.

---

## ✅ Passo 1 — Compartilhar a planilha com a conta de serviço

Esta é a parte mais importante. A credencial (conta de serviço) tem um e-mail próprio.
Para ela enxergar a sua planilha, você precisa compartilhar a planilha com esse e-mail:

1. Abra a planilha que você quer usar no Google Sheets.
2. Clique em **Compartilhar** (canto superior direito).
3. Cole este e-mail:

   ```
   gestora@sistemafinanceiro-478923.iam.gserviceaccount.com
   ```

4. Defina a permissão como **Editor** (para também poder atualizar os dados pelo app).
5. Clique em **Enviar**.

> A **mesma credencial serve para qualquer planilha** — basta compartilhar cada
> planilha com esse e-mail. Não é preciso trocar o arquivo de credenciais.

## ✅ Passo 2 — Conferir o ID da planilha

No arquivo `.streamlit/secrets.toml`, o campo `sheet_id` deve ser o trecho da URL
da sua planilha que fica **entre `/d/` e `/edit`**:

```
https://docs.google.com/spreadsheets/d/  ESTE_PEDACO_AQUI  /edit#gid=0
```

Já deixei preenchido com o ID que estava no seu arquivo. Se for outra planilha, troque aqui.

## ✅ Passo 3 — Instalar e rodar

No PowerShell, dentro da pasta do projeto:

```powershell
# cria o ambiente virtual (so na primeira vez)
python -m venv .venv

# ativa o ambiente
.\.venv\Scripts\Activate.ps1

# instala as dependencias (so na primeira vez)
pip install -r requirements.txt

# roda o app
streamlit run app.py
```

O app abre no navegador em `http://localhost:8501`.

Nas próximas vezes, basta ativar o ambiente e rodar:

```powershell
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

---

## 🔄 Como funciona a atualização

- **Botão "🔄 Atualizar agora"**: recarrega os dados na hora.
- **"Atualizar automaticamente"** (barra lateral): recarrega sozinho no intervalo escolhido.
- Mudou algo na planilha? O dashboard reflete na próxima atualização.
- **Aba "✏️ Editar dados"**: altere os valores na tabela e clique em **Salvar na planilha** —
  as mudanças vão direto para o Google Sheets.

## 🔐 Login (acesso restrito)

O app abre numa **tela de login** — só entra quem estiver na seção `[credenciais]`
do `secrets.toml` (`usuario = "senha"`):

```toml
[credenciais]
jaime = "troque-esta-senha"
```

Troque a senha padrão. Para adicionar pessoas, é só mais linhas. Na barra lateral
há o botão **🚪 Sair**.

## 🌐 Deploy (colocar online)

Veja o passo a passo completo em **[DEPLOY.md](DEPLOY.md)** — inclui o caminho
grátis (Streamlit Community Cloud) e o de servidor próprio, com dicas de HTTPS.

## 🔒 Segurança

- O arquivo `.streamlit/secrets.toml` contém a **chave privada** e as **senhas**.
  Nunca compartilhe nem suba em repositório público. O `.gitignore` já protege isso.
- Você pode apagar o arquivo `# ===== GOOGLE SHEETS =====.txt` — tudo que importa
  dele já está no `secrets.toml`.

## 🛠️ Trocar de planilha depois

1. Compartilhe a nova planilha com o e-mail da conta de serviço (Passo 1).
2. Troque o `sheet_id` em `.streamlit/secrets.toml`.
