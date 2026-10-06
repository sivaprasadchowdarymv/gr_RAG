# Deployment (free): Streamlit Community Cloud

About 20 minutes. No credit card is needed for Groq, Ollama Cloud's free plan, or Streamlit Community Cloud.

## 1. Get at least one key

* **Groq:** console.groq.com/keys → **Create API Key** (starts with `gsk_`).
* **Ollama Cloud (optional, used as fallback):** ollama.com/settings/keys → **Add API Key**.

Keep keys private. They go **only** into Streamlit's Secrets box, never into code or GitHub.

## 2. Push the code to GitHub

In the project folder (PowerShell):

```powershell
git status          # must NOT list .env, secrets.toml, data/ or any .pdf
git add .
git commit -m "RAG∞ Pro"
git push
```

## 3. Create the app

1. Open **share.streamlit.io** → **Create app** → deploy from GitHub.
2. Fill in:
   * **Repository:** `<you>/gr_RAG`
   * **Branch:** `main`
   * **Main file:** `app.py`
3. **Advanced settings:**
   * **Python version:** 3.12
   * **Secrets:**
     ```toml
     GROQ_API_KEY = "gsk_..."
     # optional fallback:
     OLLAMA_API_KEY = "..."
     ```
4. Click **Deploy** and wait 3–6 minutes.

## 4. Check it

* **Sidebar:** 🟢 Groq connected (and Ollama Cloud, if you added its key).
* **Documents:** upload a PDF. The first time, the app downloads the embedding and reranker models (~210 MB).
* **Chat:** ask a question. The answer should show **Verified ✓**, citation chips and the Evidence expander.
* **Settings:** confirm the provider list and the pipeline (RAG∞ Pro).

## 5. Updating

```powershell
git add . ; git commit -m "describe change" ; git push
```

Streamlit redeploys automatically within a couple of minutes.

## Notes and limits

* **Sleep:** Streamlit apps sleep after ~12 h without visitors; the next visitor wakes them.
* **Storage:** conversations, feedback and indexes live on the app's disk and reset on restart or redeploy. Use **Export** in Chat to keep important conversations.
* **Rate limits:** free tiers have per-minute limits. The app falls back to the next enabled provider, then shows the best evidence with a clear message.
* **Access:** a public app can be used by anyone with the link. Restrict viewers in the app's **Settings → Sharing** if your plan allows it.

## Running elsewhere

* **Local:** see README.md (Quick start). Add `ENABLE_OLLAMA_LOCAL=true` to use your local Ollama models too.
* **Server with Docker:** any VM works with `streamlit run app.py`. Put the keys in environment variables and keep `DATA_DIR` on a persistent volume.
