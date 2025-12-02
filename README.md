# Columbus AI - Sales Intelligence Dashboard

> **AI-Powered Sales Intelligence Platform** by Agiliz NV

Columbus AI is a comprehensive sales intelligence dashboard that helps identify and qualify potential customers through AI-driven analysis of job postings, technology stacks, and company data.

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Google Cloud Project with BigQuery
- Vertex AI API enabled
- Docker (optional)

### Installation

1. **Clone repository:**
```bash
git clone <repository-url>
cd zoektrends-django
```

2. **Setup environment:**
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Install dependencies:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\Activate.ps1  # Windows
pip install -r requirements.txt
```

4. **Add Google Cloud credentials:**
- Place service account JSON in root directory
- Update `GOOGLE_APPLICATION_CREDENTIALS` in `.env`

5. **Run application:**
```bash
python manage.py runserver 9000
```

6. **Access dashboard:**
```
http://localhost:9000/dashboard/
```

## 🐳 Docker Deployment

```bash
docker-compose up -d --build
```

## 📁 Project Structure

```
zoektrends-django/
├── apps/                   # Django applications
│   ├── dashboard/         # Main dashboard & services
│   ├── companies/         # Company management
│   ├── jobs/             # Job postings
│   └── analytics/        # Analytics features
├── config/               # Django configuration
├── static/              # Static files (CSS, JS, images)
├── templates/           # HTML templates
├── docker-compose.yml   # Docker orchestration
├── Dockerfile          # Container definition
├── manage.py           # Django management
└── requirements.txt    # Python dependencies
```

## ✨ Key Features

### 🏢 Company Intelligence
- Company discovery and filtering
- Technology stack analysis
- Prospect scoring (0-100)
- Status tracking (Prospect → Customer)

### 💼 Job Insights
- Job posting aggregation
- Real-time scraping
- Location & tech filtering
- Hiring activity tracking

### 🤖 Columbus AI Chat
- Natural language company search
- Contact information extraction
- Strategic analysis & recommendations
- Function calling with BigQuery

### 📊 Analytics Dashboard
- Looker embedded dashboards
- Custom metrics & KPIs
- Data visualization

### 🔍 Contact Finder
- Web scraping + AI extraction
- LinkedIn profile discovery
- RAG-enhanced context
- Anti-hallucination safeguards

## 🛠 Technology Stack

**Backend:**
- Django 5.0.2
- Python 3.10+
- Google BigQuery
- Vertex AI (Gemini 2.5 Pro)

**Frontend:**
- Alpine.js 3.x
- Tailwind CSS
- Vanilla JavaScript

**AI/ML:**
- Google Gemini (Vertex AI)
- OpenAI GPT-4 (alternative)
- RAG (Retrieval-Augmented Generation)

**Infrastructure:**
- Docker & Docker Compose
- Google Cloud Platform
- BigQuery Data Warehouse

## 📚 Documentation

Comprehensive documentation available in `docs/` folder:
- **[DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Deployment guide
- **[PROJECT_SUMMARY.md](docs/PROJECT_SUMMARY.md)** - Project overview
- **[AI_ARCHITECTURE.md](docs/AI_ARCHITECTURE.md)** - AI services architecture
- **[MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md)** - Laravel to Django notes

## 🔐 Security

⚠️ **Never commit these files:**
- `.env` - Environment variables
- `*.json` - Google Cloud credentials
- `db.sqlite3` - Local database
- `venv/` - Virtual environment

## 🌐 Environment Variables

See `.env.example` for required configuration. Key variables:

```env
SECRET_KEY=<django-secret-key>
DEBUG=False
GOOGLE_CLOUD_PROJECT_ID=agiliz-sales-tool
BIGQUERY_DATASET=zoektrends
VERTEX_AI_LOCATION=europe-west1
VERTEX_AI_MODEL=gemini-2.0-flash-exp
```

## 📈 AI Services

### Columbus Chat AI
- Company research assistant
- Strategic recommendations
- Data challenges analysis
- 8 specialized functions

### Contact Extraction
- Multi-source aggregation
- Web scraping (About/Team pages)
- AI validation
- LinkedIn discovery

### Prospect Scoring
- Technology alignment (30 pts)
- Company type fit (25 pts)
- Industry relevance (20 pts)
- Company size (15 pts)
- Activity level (10 pts)

## 🔧 Development

**Run tests:**
```bash
# Tests are in tests/ folder (excluded from git)
python -m pytest tests/
```

**Check logs:**
```bash
tail -f logs/django.log
```

**Collect static files:**
```bash
python manage.py collectstatic
```

## 📞 Support

Built with ❤️ by **Agiliz NV**

For questions or issues, refer to documentation in `docs/` folder or contact the development team.

---

**Version:** 2.0 (Django Implementation)  
**Previous Version:** Laravel (zoektrends-dashboard)  
**Migration Date:** November 2024
