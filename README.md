# BrokeNoMore

**BrokeNoMore** is a privacy-first, explainable personal finance application built to turn messy bank statements into transparent, forward-looking cash flow forecasts and savings guidance.

---

## 🌟 Pages & Features

### 1. Landing Page (`/` or `index.html`)
- **Navigation Bar**: BrokeNoMore branding, interactive dropdown menus (*What is BrokeNoMore?*, *Learn*, *Share BrokeNoMore*), and direct **Log In** button.
- **Hero Section**:
  - Headline: *"Your Money Shouldn't Disappear Without a Plan."*
  - Plain-language explainability overview and sample data preview.
  - Primary CTA directing to `/login`.
- **Problem Statement Grid**:
  - *Hidden fees*: Uncovering small charges, penalties, and interest.
  - *Cash-flow surprises*: Predicting bills landing before income.
  - *Messy statements*: Cleaning cryptic bank descriptions.
- **Core Intelligence Features**:
  - **Money Forecast**: Time-series balance trajectory with shortfall warnings.
  - **Financial Time Machine**: Side-by-side what-if scenario testing.
  - **Smart Savings Planner**: Constrained goal optimizer protecting buffer & obligations.
  - **Insights With Receipts**: Traceable calculation trails and evidence.
  - **Easy Transaction Import**: CSV/Excel normalization and review.
- **How It Works (4-Step Workflow)**: Import & Clean ➔ Understand Spending ➔ Preview Problems ➔ Explore Decisions.
- **Privacy & Data Controls**: User data ownership, export, and deletion.
- **Footer**: Legal disclosures and resource links.

### 2. Login Page (`/login` or `login.html`)
- **Visuals**: Modern 2-column layout with iPhone mockup, 3 floating financial metric cards, and fluid SVG wave background.
- **Mobile Number Authentication**:
  - Interactive country code selector defaulting to `🇮🇳 +91`.
  - 10-digit validation with inline accessible error handling.
- **6-Digit OTP Flow**:
  - 6 single-digit square inputs with auto-advance, backspace navigation, arrow key traversal, and 6-digit paste support.
  - 30-second cooldown timer for "Resend OTP".
  - Loading spinner and error handling on verification.
- **Protected Dashboard**: Redirects to `/dashboard` on successful verification.

### 3. Dashboard Placeholder (`/dashboard` or `dashboard.html`)
- Protected workspace placeholder displaying user session details and quick financial widgets with a **Log Out** button.

---

## 🚀 How to Run Locally

1. **Start the local server with routing**:
   ```bash
   python server.py
   ```
   *(or `python -m http.server 3000`)*

2. **Open in your browser**:
   - Landing Page: [http://localhost:3000](http://localhost:3000)
   - Login Page: [http://localhost:3000/login](http://localhost:3000/login)
   - Dashboard: [http://localhost:3000/dashboard](http://localhost:3000/dashboard)
