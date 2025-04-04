// static/js/chat.js
document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const chatButton = document.getElementById('chatFloatButton');
    const chatModal = document.getElementById('chatModal');
    const closeButton = document.getElementById('closeChat');
    const sendButton = document.getElementById('sendMessage');
    const userInput = document.getElementById('userMessage');
    const chatBody = document.getElementById('chatBody');
    const ratingContainer = document.getElementById('ratingContainer');
    const stars = document.querySelectorAll('.star');
    const suggestedQuestions = document.querySelectorAll('.suggested-question-btn');

    let lastResponseId = null;

    // Toggle chat modal
    chatButton.addEventListener('click', function() {
        chatModal.style.display = 'flex';
    });

    closeButton.addEventListener('click', function() {
        chatModal.style.display = 'none';
        ratingContainer.style.display = 'none';
    });

    // Send message on Enter key
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    sendButton.addEventListener('click', sendMessage);

    // Handle suggested questions
    suggestedQuestions.forEach(button => {
        button.addEventListener('click', function() {
            userInput.value = this.textContent;
            sendMessage();
        });
    });

    // Handle star ratings
    stars.forEach(star => {
        star.addEventListener('click', function() {
            const rating = parseInt(this.getAttribute('data-rating'));
            submitRating(rating);
            
            // Reset all stars
            stars.forEach(s => s.classList.remove('active'));
            
            // Set active stars
            for (let i = 0; i < rating; i++) {
                stars[i].classList.add('active');
            }
            
            // Hide rating after a short delay
            setTimeout(() => {
                ratingContainer.style.display = 'none';
                // Reset stars
                stars.forEach(s => s.classList.remove('active'));
            }, 1500);
        });
    });

    function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        // Add user message to chat
        appendMessage(message, 'user');
        userInput.value = '';

        // Hide any previous rating
        ratingContainer.style.display = 'none';

        // Send to backend
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        })
        .then(response => response.json())
        .then(data => {
            // Add bot response to chat
            appendMessage(data.response, 'bot');
            
            // Show rating request
            ratingContainer.style.display = 'block';
            
            // Generate unique ID for this response
            lastResponseId = Date.now();
        })
        .catch(error => {
            console.error('Error:', error);
            appendMessage('Sorry, I encountered an error. Please try again.', 'bot');
        });
    }

    function appendMessage(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = sender === 'user' ? 'user-message' : 'bot-message';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Enhanced markdown parsing
        let formattedContent = content;
        
        // Handle headings (## and ###)
        formattedContent = formattedContent.replace(/^## (.*$)/gm, '<h2>$1</h2>');
        formattedContent = formattedContent.replace(/^### (.*$)/gm, '<h3>$1</h3>');
        
        // Convert bold text (wrapped in ** or __)
        formattedContent = formattedContent.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        formattedContent = formattedContent.replace(/__(.*?)__/g, '<strong>$1</strong>');
        
        // Convert bullet points (lines starting with *)
        formattedContent = formattedContent.replace(/^\s*\*\s+(.*)$/gm, '<li>$1</li>');
        formattedContent = formattedContent.replace(/^\s*•\s+(.*)$/gm, '<li>$1</li>');
        
        // Wrap lists in <ul> tags
        if (formattedContent.includes('<li>')) {
            formattedContent = formattedContent.replace(/(<li>.*?<\/li>)+/gs, '<ul>$&</ul>');
        }
        
        // Handle paragraphs
        formattedContent = formattedContent.replace(/\n\n/g, '</p><p>');
        
        // Wrap in paragraph if not starting with a special element
        if (!formattedContent.startsWith('<h') && 
            !formattedContent.startsWith('<ul') && 
            !formattedContent.startsWith('<p')) {
            formattedContent = '<p>' + formattedContent + '</p>';
        }
        
        // Set HTML content
        messageContent.innerHTML = formattedContent;
        
        messageDiv.appendChild(messageContent);
        chatBody.appendChild(messageDiv);
        
        // Scroll to bottom
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    function submitRating(rating) {
        fetch('/api/rating', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                rating: rating,
                responseId: lastResponseId
            })
        })
        .then(response => response.json())
        .catch(error => {
            console.error('Error submitting rating:', error);
        });
    }
});