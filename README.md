# 🏥 Health Assistant - Medical & Food Analysis

An AI-powered health assistant that provides:
- **Medical Consultation**: Symptom analysis and OTC drug recommendations
- **Food Analysis**: Ingredient analysis and health impact assessment

Built with LangGraph, LangChain, Gemini AI, and Gradio.

## 🚀 Features

### 💊 Medical Consultation
- Describe symptoms and get follow-up questions
- Receive personalized OTC drug recommendations
- Emergency detection with immediate guidance
- Image-based symptom analysis

### 🍎 Food Analysis
- Single ingredient analysis (e.g., "turmeric", "MSG")
- Product analysis (e.g., "Coca-Cola", "Oreos")
- Ingredient list analysis
- Food label image analysis
- Health impact assessment

## 📁 Project Structure

```
├── app.py              # Gradio web interface
├── config.py           # Configuration settings
├── utils.py            # Utility functions
├── prompts.py          # Agent prompts
├── agents.py           # Agent creation
├── state.py            # State definitions
├── nodes.py            # LangGraph node functions
├── graph.py            # LangGraph workflow builder
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## 🛠️ Setup

### Prerequisites
- Python 3.10+
- Google API Key (for Gemini)

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd Encode
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set your Google API Key:
```bash
export GOOGLE_API_KEY="your-api-key-here"
```

Or on Windows:
```powershell
$env:GOOGLE_API_KEY="your-api-key-here"
```

### Running Locally

```bash
python app.py
```

The app will be available at `http://localhost:7860`

## 🌐 Deploying to Hugging Face Spaces

1. Create a new Space on Hugging Face
2. Select "Gradio" as the SDK
3. Upload all `.py` files and `requirements.txt`
4. Add your `GOOGLE_API_KEY` as a secret in Space settings

### Required Files for HuggingFace:
- `app.py`
- `config.py`
- `utils.py`
- `prompts.py`
- `agents.py`
- `state.py`
- `nodes.py`
- `graph.py`
- `requirements.txt`

## 📝 Usage

### Medical Consultation
1. Select "💊 Medical Consultation" mode
2. Describe your symptoms (e.g., "I have a headache and fever")
3. Answer follow-up questions from the agent
4. Receive drug recommendations and usage instructions

### Food Analysis
1. Select "🍎 Food Analysis" mode
2. Enter:
   - A single ingredient (e.g., "turmeric")
   - A product name (e.g., "Coca-Cola")
   - An ingredient list
   - Or upload an image of a food label
3. Receive health impact analysis

## ⚠️ Disclaimers

- This tool is for **informational purposes only**
- **Always consult a healthcare professional** for medical advice
- In case of **emergency**, call emergency services immediately
- Food analysis is general guidance; consult a dietitian for specific dietary needs

## 🔧 Configuration

Edit `config.py` to adjust:
- `API_DELAY`: Delay between API calls (default: 3 seconds)
- `MODEL_NAME`: Gemini model to use (default: "gemini-2.5-flash")
- `MODEL_TEMPERATURE`: Model temperature (default: 0)

## 📄 License

This project is for educational and demonstration purposes.

## 🙏 Acknowledgments

- [LangChain](https://python.langchain.com/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Google Gemini](https://ai.google.dev/)
- [Gradio](https://gradio.app/)
