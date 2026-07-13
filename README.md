<div align="center">

# 🚀 Sightline

### AI-powered Engineering Intelligence for Slack

Continuously verifies whether engineering planning matches engineering execution by correlating **Slack Lists**, **GitHub**, and **Slack conversations** to generate explainable, evidence-backed recommendations.

<p align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)
![Slack](https://img.shields.io/badge/Slack-Bolt-4A154B?style=for-the-badge&logo=slack)
![GitHub](https://img.shields.io/badge/GitHub-API-black?style=for-the-badge&logo=github)
![Gemini](https://img.shields.io/badge/Google-Gemini-4285F4?style=for-the-badge&logo=google)
![Hackathon](https://img.shields.io/badge/Hackathon-2026-success?style=for-the-badge)

</p>

</div>

---

<p align="center">

<img src="assets/hero-dashboard.png" width="100%">

</p>

---

# 🎯 The Problem

Engineering project boards become stale surprisingly fast.

A pull request gets merged.

QA approves the work.

Slack confirms it's complete.

Yet the project tracker still says **"Todo."**

This disconnect forces engineering managers to manually verify project status across multiple tools, wasting time and reducing trust in planning systems.

---

# 💡 The Solution

Sightline correlates information from three independent sources:

```
Slack Lists (Planning)
          │
          ▼
 GitHub Repository (Execution)
          │
          ▼
 Slack Conversations (Communication)
          │
          ▼
 Evidence Correlation Engine
          │
          ▼
 Explainable Recommendation
          │
          ▼
 Slack Block Kit Action Card
```

Instead of blindly changing project data, Sightline provides **transparent, evidence-backed recommendations** that engineering teams can confidently review and apply.

---

# 🎥 Demo

<p align="center">

<img src="assets/dashboard.gif" width="100%">

</p>

---

# ✨ Features

## 📋 Planning Intelligence

- Slack Lists integration
- Live planning status
- Planning vs execution comparison
- Planning mismatch detection

---

## ⚡ GitHub Intelligence

- Live repository scanning
- Pull Request analysis
- Issue analysis
- Commit history
- Repository activity
- Contributor insights

---

## 💬 Slack Intelligence

- Slack Search (RTS)
- QA confirmation discovery
- Engineering discussion search
- Communication evidence

---

## 🧠 AI Evidence Engine

Instead of guessing, Sightline collects evidence from multiple sources.

For every recommendation it explains:

- Why the recommendation exists
- Which GitHub events support it
- Which Slack conversations support it
- Planning state
- Confidence level

---

## 💡 Repository Health

Repository health is calculated using engineering signals such as:

- Open Issues
- Stale Pull Requests
- Planning mismatches
- Repository activity
- Development freshness

The score is fully explainable.

---

## 🔍 Engineering Activity Dashboard

The dashboard provides a unified engineering view including:

- Repository Health
- Engineering Work Items
- Recommendation Engine
- Integration Status
- Evidence Timeline
- Live Event Feed
- Risk Analysis

---

# 🖥 Dashboard

## Repository Health

<p align="center">
<img src="assets/repo-health.png" width="90%">
</p>

---

## Engineering Work Items

<p align="center">
<img src="assets/recommendation.png" width="90%">
</p>

---

## Recommendation Evidence

<p align="center">
<img src="assets/evidence.png" width="90%">
</p>

---

## Slack Block Kit Recommendation

<p align="center">
<img src="assets/slack-card.png" width="90%">
</p>

---

# 🏗 Architecture

<p align="center">

<img src="assets/architecture.png" width="100%">

</p>

---

# ⚙️ System Architecture

```
                    Slack Lists
                 (Planning Source)
                         │
                         ▼
              Slack List Loader
                         │
                         ▼
                 Internal Task Model
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
 GitHub Checker     Slack Search     Analyzer
 (Execution)       (Communication)  (Correlation)
        │                │                │
        └────────────────┼────────────────┘
                         ▼
               Evidence Builder
                         ▼
             Recommendation Engine
                         ▼
              Slack Block Kit Cards
                         ▼
                 Dashboard UI
```

---

# 🧠 How Sightline Thinks

For every engineering work item:

1. Read planning state from Slack Lists.
2. Analyze GitHub Pull Requests and Issues.
3. Search Slack conversations for supporting evidence.
4. Correlate all available information.
5. Detect inconsistencies.
6. Generate an explainable recommendation.
7. Present supporting evidence.
8. Allow engineering teams to review before applying updates.

---

# 🛠 Tech Stack

## Backend

- Python
- Slack Bolt
- Slack SDK
- REST APIs

## AI

- Google Gemini
- Evidence Correlation
- Recommendation Engine

## Integrations

- GitHub REST API
- Slack Lists API
- Slack Search API
- Socket Mode

## Frontend

- HTML
- CSS
- Vanilla JavaScript

---

# 📂 Project Structure

```
.
├── core/
├── handlers/
├── models/
├── services/
├── templates/
├── ui/
├── tests/
├── assets/
├── app.py
└── dashboard_app.py
```

---

# 🔄 Demo Flow

```
Run Scan

        │

        ▼

Connect to GitHub

        │

        ▼

Analyze Pull Requests

        │

        ▼

Search Slack Conversations

        │

        ▼

Correlate Evidence

        │

        ▼

Generate Recommendations

        │

        ▼

Present Block Kit Cards

        │

        ▼

Engineering Manager Reviews

        │

        ▼

Update Planning
```

---

# 🚀 Getting Started

```bash
git clone https://github.com/AnupojuRohit/Sightline.git

cd Sightline

python -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

python app.py
```

Open:

```
http://127.0.0.1:5001
```

---

# 🌟 Why Sightline?

Modern engineering teams rely on multiple systems:

- Planning
- Code
- Communication

These systems frequently drift apart.

Sightline bridges that gap by continuously validating engineering work against multiple sources of truth and surfacing explainable recommendations before planning becomes outdated.

---

# 🔮 Future Roadmap

- Jira Integration
- Linear Integration
- Azure DevOps
- GitLab
- Microsoft Teams
- Notion
- Multi-repository support
- Historical trend analysis
- Organization-wide engineering insights

---

# 👨💻 Built For

Engineering Managers

Tech Leads

Product Managers

Platform Teams

Developer Experience Teams

---

<div align="center">

## ⭐ If you found Sightline interesting, consider giving it a star!

Built with ❤️ for the Slack Hackathon.

</div>
