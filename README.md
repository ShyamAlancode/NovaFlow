# NovaFlow 🌌

[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg?style=flat-square&logo=next.js)](https://nextjs.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-CSS-38B2AC.svg?style=flat-square&logo=tailwind-css)](https://tailwindcss.com/)
[![AWS Bedrock](https://img.shields.io/badge/AWS-Bedrock-232F3E.svg?style=flat-square&logo=amazon-aws)](https://aws.amazon.com/bedrock/)
[![Playwright](https://img.shields.io/badge/Playwright-Test-2EAD33.svg?style=flat-square&logo=playwright)](https://playwright.dev/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

NovaFlow is an autonomous accessibility testing platform built for the agent-first era. It leverages multi-modal AI agents (powered by Amazon Nova 2 Lite) to intelligently navigate, scan, and remediate WCAG 2.1 AA accessibility issues across web applications with zero SDK integration required.

## ⚡ What Makes NovaFlow Different?
Traditional accessibility tools rely on static HTML parsing. NovaFlow deploys **vision-based autonomous agents** that interact with your DOM just like a real user. 

If it's hidden behind an auth-wall, our `NovaAct` engine drives headless Chromium to log in, navigate the application state, and analyze the *visual* rendered tree for compliance, gracefully falling back to raw Playwright when encountering complex localized shadow DOMs.

---

## 🚀 Key Features

- **Tier-1 Autonomous Navigation**: The engine intelligently clicks, scrolls, and explores your application without writing a single test script.
- **Vision-Based Analysis**: Native visual structure analysis utilizing AWS Bedrock (Amazon Nova model) to map visual failures directly to strict legal WCAG criteria.
- **Zero-Config Deployment**: No SDKs. No confusing CI/CD wrappers. Just input the target URL and let the agent run.
- **Diagnostic Remediation**: Instant, contextual code snippets provided by the NovaPulse Chat assistant to fix flagged issues locally.
- **Premium Bento UI**: A modern, high-contrast dashboard inspired by Google's "Antigravity" design language, featuring smooth Framer Motion transitions and glassmorphic telemetry components.

---

## 🛠 Tech Stack

### Frontend (Application Layer)
- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS + Custom CSS Variables
- **Animations**: Framer Motion
- **State Management**: Zustand
- **Icons**: Lucide React

### Backend (Agentic Engine)
- **AI Infrastructure**: AWS Bedrock (`amazon.nova-lite-v1:0`)
- **Browser Automation**: NovaAct & Playwright (Python)
- **API Communication**: Next.js Serverless Route Handlers

---

## 💻 Quick Start

### Prerequisites
- Node.js (v18+)
- Python (3.9+)
- AWS Account with Bedrock model access enabled (`amazon.nova-lite-v1:0`)

### 1. Clone the repository
```bash
git clone https://github.com/ShyamAlancode/NovaFlow.git
cd NovaFlow
```

### 2. Set up the environment variables
Copy the example environment file and fill in your AWS credentials:
```bash
cd novaflow
cp .env.example .env.local
```

Your `.env.local` should look like this:
```env
NEXT_PUBLIC_SITE_URL=http://localhost:3000
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
NEXT_PUBLIC_AWS_BEDROCK_REGION=us-east-1
```

### 3. Install dependencies
Install the Next.js frontend dependencies:
```bash
npm install
```

Install the Python engine dependencies (recommended to use a virtual environment):
```bash
cd ..
pip install -r requirements.txt
playwright install
```

### 4. Run the development server
Start the Next.js server:
```bash
cd novaflow
npm run dev
```

The application will be available at `http://localhost:3000`.

---

## 🧠 System Architecture Overview

The system operates via a tightly coupled API pipeline:
1. **The User** inputs a target URL on the `novaflow` dashboard.
2. The Request hits the Next.js `/api/run-test` route handler.
3. The handler triggers the **Python `nova_engine.py`**:
   - **Tier 1**: Attempts navigation via `NovaAct`.
   - **Tier 2 (Fallback)**: If connection issues arise, drops seamlessly to raw `Playwright` to pull the DOM and take screenshots.
4. The captured telemetry (Screenshots + DOM fragments) is securely piped to **AWS Bedrock**.
5. The **Amazon Nova model** outputs a strict, structured JSON array evaluating WCAG 2.1 AA parameters.
6. The frontend consumes this JSON to dynamically render the `DiagnosticCard` UI.

---

## 🤝 Contributing
Contributions, issues, and feature requests are welcome! 
Feel free to check out the [issues page](https://github.com/ShyamAlancode/NovaFlow/issues) if you want to contribute.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License
This project is licensed under the MIT License - see the `LICENSE` file for details.

---
*Built for the future of the accessible web.*
