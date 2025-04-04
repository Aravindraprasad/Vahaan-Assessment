import json
import os
import requests
import time
import csv
from typing import Dict, List, Tuple
from datetime import datetime
from flask import Flask, render_template, request, jsonify

# Configuration
OPENROUTER_API_KEY = "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"  
DOCS_DIR = "netflix_docs"
ANALYTICS_FILE = "analytics.csv"

app = Flask(__name__)

class NetflixChatbot:
    def __init__(self):
        self.documents = self.load_documents()
        self.chat_history = []
        self.analytics = self.initialize_analytics()
    
    def load_documents(self) -> Dict[str, Dict]:
        """Load all JSON documents from the docs directory"""
        documents = {}
        try:
            for filename in os.listdir(DOCS_DIR):
                if filename.endswith(".json"):
                    with open(f"{DOCS_DIR}/{filename}", "r") as f:
                        doc_name = filename.split("_", 1)[1].replace(".json", "")
                        documents[doc_name] = json.load(f)
            print(f"Loaded {len(documents)} documents")
            return documents
        except Exception as e:
            print(f" Error loading documents: {e}")
            return {}
    
    def initialize_analytics(self) -> Dict:
        """Initialize analytics tracking"""
        return {
            "total_queries": 0,
            "category_counts": {},
            "satisfaction_ratings": [],
            "unknown_queries": [],
            "session_start": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    def save_analytics(self):
        """Save analytics data to CSV file"""
        # Create file with headers if it doesn't exist
        if not os.path.exists(ANALYTICS_FILE):
            with open(ANALYTICS_FILE, 'w', newline='') as file:
                writer = csv.writer(file)
                writer.writerow([
                    "Session", "Total Queries", "Categories", 
                    "Avg Satisfaction", "Unknown Queries"
                ])
        
        # Calculate average satisfaction
        avg_satisfaction = 0
        if self.analytics["satisfaction_ratings"]:
            avg_satisfaction = sum(self.analytics["satisfaction_ratings"]) / len(self.analytics["satisfaction_ratings"])
        
        # Write session data
        with open(ANALYTICS_FILE, 'a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([
                self.analytics["session_start"],
                self.analytics["total_queries"],
                json.dumps(self.analytics["category_counts"]),
                avg_satisfaction,
                json.dumps(self.analytics["unknown_queries"])
            ])

    def prepare_context(self, user_query: str) -> Tuple[Dict[str, Dict], List[str]]:
        """Dynamically select relevant documents based on user query"""
        query = user_query.lower()
        context = {}
        matched_categories = []
        
        # Document selection logic - expanded with more keyword matches
        doc_mappings = {
            "pricing": ["price", "plan", "cost", "subscription", "payment", "bill", "monthly", "annual", "discount", "basic", "standard", "premium"],
            "features": ["feature", "download", "watch", "stream", "resolution", "profile", "offline", "hdr", "4k", "device", "simultaneous"],
            "troubleshooting": ["error", "fix", "trouble", "issue", "buffering", "crash", "slow", "loading", "problem", "not working", "frozen", "restart"],
            "account": ["login", "password", "account", "payment", "email", "profile", "sign", "logout", "delete", "cancel", "subscription"],
            "parental": ["child", "kid", "parental", "restrict", "control", "mature", "rating", "pin", "family", "age"],
            "compatibility": ["device", "phone", "tv", "smart", "roku", "firestick", "android", "ios", "apple", "samsung", "lg", "computer"],
            "content": ["show", "movie", "series", "documentary", "original", "watch", "genre", "category", "new", "release"],
            "region": ["country", "region", "available", "international", "travel", "abroad", "vpn", "location"],
            "quality": ["resolution", "quality", "hd", "4k", "ultra", "bitrate", "audio", "video", "stream", "bandwidth", "data"],
            "security": ["secure", "privacy", "data", "password", "leak", "protect", "encryption", "safe"],
            "billing": ["bill", "charge", "payment", "refund", "card", "debit", "credit", "paypal", "bank", "transaction", "receipt"],
            "terms": ["terms", "service", "legal", "agreement", "policy", "copyright", "license", "conditions", "privacy"],
            "contact": ["contact", "support", "help", "call", "phone", "email", "chat", "representative", "human", "agent", "manager"],
            "feedback": ["feedback", "suggestion", "improve", "rating", "review", "star", "recommend", "opinion"],
            "downloading": ["download", "offline", "storage", "save", "watch later", "limit", "expire", "delete"]
        }
        
        for doc_name, keywords in doc_mappings.items():
            if any(kw in query for kw in keywords):
                context[doc_name] = self.documents.get(doc_name, {})
                matched_categories.append(doc_name)
        
        return context if context else self.documents, matched_categories  # Fallback to all docs
    
    def update_analytics(self, user_query: str, matched_categories: List[str], is_unknown: bool = False):
        """Update analytics data based on user interaction"""
        self.analytics["total_queries"] += 1
        
        # Update category counts
        if matched_categories:
            for category in matched_categories:
                if category in self.analytics["category_counts"]:
                    self.analytics["category_counts"][category] += 1
                else:
                    self.analytics["category_counts"][category] = 1
        else:
            if "unknown" in self.analytics["category_counts"]:
                self.analytics["category_counts"]["unknown"] += 1
            else:
                self.analytics["category_counts"]["unknown"] = 1
        
        # Track unknown queries
        if is_unknown:
            self.analytics["unknown_queries"].append(user_query)

    def format_response(self, response: str) -> str:
        """Clean and format the AI response with proper markdown handling"""
        # Remove unwanted prefixes
        prefixes = ["NetBot:", "Assistant:", "**Assistant:**"]
        for prefix in prefixes:
            if response.startswith(prefix):
                response = response[len(prefix):].strip()
        
        # Preserve markdown formatting by keeping line breaks intact
        # But remove excessive blank lines
        lines = response.split("\n")
        formatted_lines = []
        prev_empty = False
        
        for line in lines:
            if not line.strip():
                if not prev_empty:
                    formatted_lines.append("")
                    prev_empty = True
            else:
                formatted_lines.append(line.strip())
                prev_empty = False
        
        return "\n".join(formatted_lines)

    def ask_gemini(self, user_query: str) -> str:
        """Generate response using Gemini API"""
        try:
            # Add system prompt if first message
            if not self.chat_history:
                self.chat_history.append({
                    "role": "system",
                    "content": "You're NetBot, Netflix's support assistant. Provide concise, accurate answers using only the given documentation."
                })
            
            # Add user message to history
            self.chat_history.append({"role": "user", "content": user_query})
            
            # Prepare context
            context, matched_categories = self.prepare_context(user_query)
            
            # Update analytics
            self.update_analytics(user_query, matched_categories)
            
            # Check if we should use fallback for questions outside knowledge
            is_unknown = False
            if not matched_categories and len(context) == len(self.documents):
                # This means we're using all docs as fallback
                is_unknown = True
                self.update_analytics(user_query, [], is_unknown=True)

            # Generate prompt with chat history included for context
            relevant_history = self.chat_history[-5:]  # Last 5 messages for context
            history_text = "\n".join([f"- {msg['role'].capitalize()}: {msg['content']}" 
                            for msg in relevant_history if msg['role'] != 'system'])
            
            prompt = f"""
            User Question: {user_query}
            
            Conversation History:
            {history_text}
            
            Relevant Documentation (use ONLY these):
            {json.dumps(context, indent=2)}
            
            Response Guidelines:
            - Explain under 2  lines of code
            - Be direct and professional
            - Use bullet points for lists
            - Do not uses tables for comparisons
            - ONLY reference information found directly in the documentation provided
            - If the user's question cannot be answered with the documentation provided, say "I don't have that information in my knowledge base. Would you like to know about [suggest relevant Netflix topics from the documentation]?"
            - DO NOT include generic disclaimers about other streaming services or referring to customer support unless specifically asked
            - Focus only on answering the specific question with the information available
            - Assume all questions are about Netflix unless explicitly stated otherwise
            """
            
            # API Call
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "google/gemini-pro",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3  # Less random responses
                },
                timeout=10  # 10-second timeout
            )
            
            # Process response
            if response.status_code == 200:
                bot_reply = self.format_response(response.json()["choices"][0]["message"]["content"])
                self.chat_history.append({"role": "assistant", "content": bot_reply})
                return bot_reply
            else:
                error_msg = f"API Error (Status {response.status_code}): {response.text}"
                self.chat_history.append({"role": "assistant", "content": error_msg})
                return error_msg
                
        except Exception as e:
            error_msg = f"An error occurred: {str(e)}"
            self.chat_history.append({"role": "assistant", "content": error_msg})
            return error_msg
    
    def add_satisfaction_rating(self, rating: int):
        """Add a satisfaction rating"""
        if 1 <= rating <= 5:
            self.analytics["satisfaction_ratings"].append(rating)
            return True
        return False

# Initialize the chatbot
bot = NetflixChatbot()

# Sample movie data for homepage
movies = [
    {"title": "Stranger Things", "image": "stranger_things.jpeg", "description": "A sci-fi horror series set in the 1980s"},
    {"title": "The Crown", "image": "Thecrown.jpeg", "description": "A historical drama about the reign of Queen Elizabeth II"},
    {"title": "Bridgerton", "image": "Brodgerton.jpeg", "description": "A Regency era romantic drama series"},
    {"title": "Money Heist", "image": "moneyhesit.jpeg", "description": "A Spanish heist crime drama series"},
    {"title": "Squid Game", "image": "squidgame.jpeg", "description": "A Korean survival drama series"},
    {"title": "The Witcher", "image": "thewitcher.jpeg", "description": "A fantasy drama series based on the book series"}
]

# Suggested questions for the chatbot
suggested_questions = [
    "What pricing plans are available?",
    "How do I fix buffering issues?",
    "What devices are compatible with Netflix?",
    "How many screens can I watch on?",
    "How do I download shows for offline viewing?",
    "What are the contact support options?"
]

@app.route('/')
def index():
    """Homepage with featured movies and chatbot access"""
    return render_template('index.html', movies=movies, suggested_questions=suggested_questions)

@app.route('/api/chat', methods=['POST'])
def chat():
    """API endpoint for chatbot interactions"""
    data = request.json
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    
    # Get response from the chatbot
    response = bot.ask_gemini(user_message)
    
    return jsonify({
        "response": response,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/api/rating', methods=['POST'])
def add_rating():
    """API endpoint for adding satisfaction ratings"""
    data = request.json
    rating = data.get('rating')
    
    try:
        rating = int(rating)
        if bot.add_satisfaction_rating(rating):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Invalid rating"}), 400
    except:
        return jsonify({"error": "Invalid rating format"}), 400

@app.teardown_appcontext
def save_on_exit(exception=None):
    """Save analytics when the application exits"""
    bot.save_analytics()

if __name__ == '__main__':
    # Ensure the document directory exists
    if not os.path.exists(DOCS_DIR):
        os.makedirs(DOCS_DIR)
    
    app.run(debug=True)