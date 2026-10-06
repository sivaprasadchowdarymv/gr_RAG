# Deploy Datasheet RAG Agent for free (step by step)

This takes about 30 minutes. You need a GitHub account; no credit card is needed anywhere.

```text
 Browser ──► https://your-name.streamlit.app   (Streamlit Community Cloud, free)
                │  PDF parsing, chunking, tables, equations, embeddings, search
                ▼
             Groq API (free tier)  ── ReAct agent: openai/gpt-oss-120b
```

This is a **new, separate repository**. Your existing `datasheet-rag` and `datasheet-rag-cloud` repos are not touched.

---

## Step 1: Get a free Groq API key (3 min)

1. Open **https://console.groq.com** and sign in with Google, GitHub or email.
2. Open **https://console.groq.com/keys** and click **Create API Key**. Name it `datasheet-rag-agent`.
3. **Copy the key** (it starts with `gsk_`) and paste it into Notepad for now. It's shown only once.
   * Treat it like a password.
   * Never put it in code, GitHub or a chat.
4. Optional: open **https://console.groq.com/settings/limits** to see your free limits for `openai/gpt-oss-120b`.

---

## Step 2: Put the project in its own folder (3 min)

1. Unzip `datasheet-rag-agent.zip` to:
   ```text
   Documents\AgenticAI\RAG\datasheet-rag-agent
   ```
2. Open that folder and check that you see `app.py`, `DEPLOY.md`, `requirements.txt` and the folders `config`, `rag`, `storage`, `ui`.
   * If you only see one inner `datasheet-rag-agent` folder, open it. The files must be at the top level of the folder you'll use.

---

## Step 3: Create a NEW GitHub repository (2 min)

1. Open **https://github.com/new**.
2. Fill in:
   * **Repository name:** `datasheet-rag-agent`
   * Select **Public**.
   * Leave **all** "Add README / .gitignore / license" boxes **unticked**.
3. Click **Create repository**.

---

## Step 4: Upload the code (5 min)

1. In the project folder, click the Explorer **address bar**, type `powershell` and press **Enter**. PowerShell opens inside the folder.
2. Run these **one at a time**:
   ```powershell
   git init
   ```
   ```powershell
   git add .
   ```
   ```powershell
   git status
   ```
3. **Check the list.** It must **not** contain `.env`, `secrets.toml`, any `.pdf`, or a `data` or `venv` folder. If it does, stop and ask for help.
4. Then run:
   ```powershell
   git commit -m "Datasheet RAG Agent: ReAct + Groq"
   ```
   ```powershell
   git branch -M main
   ```
   ```powershell
   git remote add origin https://github.com/sivaprasadchowdarymv/datasheet-rag-agent.git
   ```
   ```powershell
   git push -u origin main
   ```
   * **No `--force`:** the repo is new and empty, so nothing is replaced.
   * If a browser window opens asking you to sign in to GitHub, approve it.
5. Refresh **github.com/sivaprasadchowdarymv/datasheet-rag-agent**. You should see the files.

---

## Step 5: Deploy on Streamlit Community Cloud (5 min + waiting)

1. Open **https://share.streamlit.io** and sign in with GitHub.
2. Click **Create app** and choose to deploy **from GitHub**.
3. Fill in:

| Field | Value |
|---|---|
| Repository | `sivaprasadchowdarymv/datasheet-rag-agent` |
| Branch | `main` |
| Main file path | `app.py` |
| App URL | e.g. `mvspc-datasheet-agent` |

4. Click **Advanced settings**:
   * **Python version:** **3.12**
   * **Secrets:** paste this, with your key inside the **double quotes**:
     ```toml
     GROQ_API_KEY = "gsk_paste_your_key_here"
     ```
   * Click **Save**.
5. Click **Deploy** and wait about **3–6 minutes**.

---

## Step 6: Check it works (5 min)

1. In the sidebar **Status**, you should see:
   * 🟢 **Groq: Connected**
   * 🟢 **Model: openai/gpt-oss-120b**
   * 🟢 **Embedding: nomic-embed-text-v1.5-Q (in-app)**

   If it says **No API key**: go to **Manage app → ⋮ → Settings → Secrets**, check the exact name `GROQ_API_KEY` and the **double quotes**, click **Save**, then reload the page.
2. **Upload a datasheet PDF.** The first upload is slower because the app downloads its search model once (about 130 MB).
3. **Ask a question**, for example:
   * `What is the maximum output current?` (a simple lookup, usually 1 Groq call)
   * `How do I calculate the power dissipation at 12 V input and 1 A?` (uses the search and calculate tools)
   * `What is the pin configuration?`
4. **Check the answer has:**
   * **Answer**, **Explanation**, and **Equations** (rendered as math) when relevant,
   * blue citation badges such as `REF-2 · TABLE p5`,
   * **🧠 How the agent worked**: open it to see each Thought → Action → Observation,
   * **Sources** below, with the exact excerpts.

---

## Using the two modes

Open **⚙ Configuration** in the sidebar:

| Mode | Best for | Groq calls | Tokens |
|---|---|---|---|
| **ReAct agent** (default) | Calculations, multi-part questions, values spread over pages | 1–4 | ~1,000–4,500 |
| **Quick** | Simple lookups, or when you're near the rate limit | 1 | ~600–1,500 |

---

## Updating later

Edit the code, then in PowerShell from the project folder:
```powershell
git add .
git commit -m "describe the change"
git push
```
Streamlit redeploys automatically within a couple of minutes.

---

## Troubleshooting

| Message | What to do |
|---|---|
| "No Groq API key is set" | Add `GROQ_API_KEY = "gsk_..."` in **Settings → Secrets** (with quotes) and reload. |
| "Groq rejected the API key" | Create a new key at console.groq.com/keys and replace it in Secrets. |
| "The free Groq rate limit was reached" | Wait about a minute (token limit) or until tomorrow (daily limit). Use **Quick** mode to save tokens. |
| "Model … is not available on Groq" | Pick another model in **⚙ Configuration**, or set `GROQ_MODEL` in Secrets. |
| "The answer cites …, which is not one of the retrieved sources" | The model referred to evidence it was never given. Treat that sentence with caution and check the Sources. |
| "This app has gone to sleep" | Normal after 12 h without visitors. Click the wake-up button and wait about a minute. |
| Build fails | **⋮ → Settings**: make sure Python is **3.12**, then **Reboot app**. |
