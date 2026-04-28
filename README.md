# NutriLog Bot 🤖🥗

> **A minimal, premium‑looking chatbot that logs your meals directly into Fitbit**  
> Powered by **Google Gemini** (natural‑language parsing) + **Fitbit API** (nutrition tracking) + **Flet** (cross‑platform UI).

---

## 📖 What is NutriLog Bot?

NutriLog Bot is a lightweight Python desktop/web app (works on Windows, macOS, Linux, and Android) that lets you:

1. **Chat** – Write what you ate in plain Spanish (or English).  
2. **Parse** – Gemini extracts each food item + quantity.  
3. **Validate** – The app selects the most appropriate Fitbit food entry, preferring the unit you asked for (grams / ml).  
4. **Log** – One‑click “Enviar a Fitbit” stores the meal in your Fitbit account, with proper meal‑type (Desayuno, Comida, etc.).

All this with a **dark‑mode UI**, micro‑animations, and clear error handling.

---  

## ✨ Features

| ✅ | Feature |
|---|---|
| 🎨 | Dark theme, glass‑morphism style, smooth transitions |
| 🤖 | Gemini‑3.1‑Flash mini‑LLM for food extraction |
| 🔐 | OAuth 2.0 login flow with a local temporary server (no hard‑coded tokens) |
| 📊 | Automatic unit validation (grams vs. ml) |
| 🍽️ | Meal‑type selector (Desayuno, Media Mañana, …) |
| 🛡️ | Robust fallback if Fitbit returns no perfect match |
| 🖥️ | Runs as a desktop app **or** in a browser (`ft.WEB_BROWSER`) – perfect for Android via `flet build apk` |

---

## 🛠️ Prerequisites

| Item | Minimum version |
|------|-----------------|
| **Python** | 3.12 |
| **pip** | latest (`python -m pip install --upgrade pip`) |
| **Git** | (optional, for cloning) |
| **Fitbit developer account** | Create an app (see below) |
| **Google Gemini API key** | Obtain from Google AI Studio |

---

## 🚀 Quick‑Start (Local Desktop)

```bash
# 1️⃣ Clone the repo
git clone https://github.com/your-username/NutriLogBot.git
cd NutriLogBot

# 2️⃣ Create a virtual environment (recommended)
python -m venv .venv
.\\.venv\\Scripts\\activate   # Windows
# source .venv/bin/activate   # macOS / Linux

# 3️⃣ Install dependencies
pip install -r requirements.txt

# 4️⃣ Set environment variables
# Create a .env file in the repo root (see example below)
cp .env.example .env
# Edit .env with your keys (see next section)

# 5️⃣ Run the app (desktop mode)
python main.py
```

The app will open in your default browser (dark theme) and show a **“Conectar con Fitbit”** button. Click it, authorize the app, and you’ll be ready to log meals.

---

## 📱 Deploy to Android (optional)

```bash
# Inside the same venv
pip install flet[android]
flet build apk --app-name "NutriLog Bot" --app-id com.yourname.nutrilog --icon ./icon.png
```

The generated `NutriLogBot.apk` can be installed on any Android device. The OAuth flow works the same way (it opens the system browser for Fitbit login).

---

## 🔐 Fitbit App Registration (OAuth)

1. Go to **[dev.fitbit.com/apps](https://dev.fitbit.com/apps)** and sign‑in.  
2. Click **“Register an App”** → **Personal** (not **Server**).  
3. Fill out:

| Field | Value |
|-------|-------|
| **Application Name** | NutriLog Bot |
| **Description** | Chatbot de registro de comidas |
| **Application Website** | `http://localhost` |
| **Organization** | Personal |
| **Redirect URL** | `http://localhost:8080/api/oauth/callback` |
| **OAuth 2.0 Application Type** | Personal |
| **Default Access Type** | Read & Write |
| **Scopes** | `nutrition profile` |

4. Save. Copy **Client ID** and **Client Secret** – you’ll need them for the `.env` file.

---

## 🔑 `.env` file (example)

```dotenv
# Google Gemini
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"

# Fitbit OAuth (from the app you created)
FITBIT_CLIENT_ID="YOUR_FITBIT_CLIENT_ID"
FITBIT_CLIENT_SECRET="YOUR_FITBIT_CLIENT_SECRET"
```

> **Never commit** your `.env` to a public repo! It is already listed in `.gitignore`.

---

## 🧩 How the validation works (behind the scenes)

1. **Quantity unit detection** – The parser looks for `g`, `gram`, `ml`, `mililitro`.  
2. **Fitbit search** – `GET /1/foods/search.json?query={ingredient}`.  
3. **Unit extraction** – Handles both integer IDs (`147`) and dict objects (`{id:147, name:"gram"}`).  
4. **Scoring** – Uses `difflib.SequenceMatcher` to rank results by name similarity.  
5. **Fallback** – If no food matches the exact unit, the best‑scoring food (any unit) is used, guaranteeing the request never fails.

---

## 📂 Repository Structure

```
NutriLogBot/
├── main.py            # Core app (Flet UI + OAuth + logic)
├── requirements.txt   # Python dependencies
├── .env.example       # Template for environment variables
├── README.md          # <-- you’re reading it!
└── assets/            # (optional) icons, images
```

---

## 🛡️ Troubleshooting

| Symptom | Fix |
|--------|-----|
| **OAuth “Invalid redirect_uri”** | Ensure the URL in Fitbit app settings matches exactly `http://localhost:8080/api/oauth/callback`. |
| **“No food found” for eggs** | The new validation fallback now picks the best matching result even without a unit constraint. If still empty, verify the search term (e.g., “huevo” vs. “egg”). |
| **`oauthAuthorize command is not supported`** | The app now runs in `WEB_BROWSER` mode, bypassing Flet’s internal OAuth command. No further action needed. |
| **Missing Gemini model** | The code uses `gemini-3.1-flash-lite-preview`. If you have a different model, change `model_name` in `get_gemini_model()`. |
| **App crashes on Windows** | Make sure you use the bundled `python.exe` from the same environment where you installed packages (run `where python`). |

---

## 📜 License

MIT – feel free to fork, improve, and share! Just give credit to the original author.

---

## 🙌 Contributing

1. Fork the repo.  
2. Create a feature branch (`git checkout -b feature/awesome‑thing`).  
3. Submit a Pull Request with a clear description and screenshots.  

All contributions are welcome – especially UI polish, new language support, or additional nutrition APIs (Edamam, FatSecret, etc.).

---

## ⭐️ Show your support

If NutriLog Bot helped you track meals or inspired your own health‑tech project, give the repo a star 🌟 – it lets others discover it faster!

---

**Happy logging!** 🎉