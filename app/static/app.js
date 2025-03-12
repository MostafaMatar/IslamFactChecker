document.addEventListener('DOMContentLoaded', () => {
    const messagesContainer = document.getElementById('messages');
    const userInput = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');
    // Helper function to create message elements
    function createMessageElement(text, isUser = false) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
        messageDiv.textContent = text;
        return messageDiv;
    }

    // Helper function to create response element
    function createResponseElement(response) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';

        // Main answer
        const answerDiv = document.createElement('div');
        answerDiv.textContent = response.answer;
        messageDiv.appendChild(answerDiv);

        // Sources
        if (response.sources && response.sources.length > 0) {
            const sourcesDiv = document.createElement('div');
            sourcesDiv.className = 'sources';
            sourcesDiv.innerHTML = '<strong>Sources:</strong><br>' + 
                response.sources.join('<br>');
            messageDiv.appendChild(sourcesDiv);
        }

        // Classification
        const classDiv = document.createElement('div');
        classDiv.className = `classification-badge ${response.classification.toLowerCase()}`;
        classDiv.textContent = response.classification;
        messageDiv.appendChild(classDiv);

            // Share link section
        const shareDiv = document.createElement('div');
        shareDiv.className = 'share-link';
        
        // Create input with share URL
        const shareInput = document.createElement('span');
        shareInput.value = `${window.location.origin}/claim/${response.id}/view`;
        shareInput.setAttribute('aria-label', 'Shareable link');
        
        // Create copy button
        const copyBtn = document.createElement('button');
        copyBtn.className = 'sendButton';
        copyBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor">
                <rect x="4" y="4" width="8" height="8" rx="1" />
                <path d="M10 4V3a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h1" />
            </svg>
            <span>Copy Link</span>
        `;
        copyBtn.setAttribute('aria-label', 'Copy link to clipboard');

        copyBtn.onclick = async () => {
            try {
                await navigator.clipboard.writeText(shareInput.value);
                copyBtn.classList.add('copied');
                copyBtn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor">
                        <path d="M2 8l4 4 8-8" stroke-width="2"/>
                    </svg>
                    <span>Copied!</span>
                `;
                setTimeout(() => {
                    copyBtn.classList.remove('copied');
                    copyBtn.innerHTML = `
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor">
                            <rect x="4" y="4" width="8" height="8" rx="1" />
                            <path d="M10 4V3a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h1" />
                        </svg>
                        <span>Copy Link</span>
                    `;
                }, 2000);
            } catch (err) {
                console.error('Failed to copy text: ', err);
            }
        };

        shareDiv.appendChild(shareInput);
        shareDiv.appendChild(copyBtn);
        messageDiv.appendChild(shareDiv);

        return messageDiv;
    }


    // Loading messages
    const loadingMessages = [
        "Sending claim to the AI",
        "Claim is being analyzed",
        "AI is preparing a response",
        "Adding some formatting",
        "Response is being rendered"
    ];

    let loadingMessageInterval;
    let currentLoadingMessage = 0;

    function updateLoadingMessage() {
        const loadingMessage = document.getElementById('loading-message');
        if (loadingMessage) {
            console.log(`Updating loading message to: "${loadingMessages[currentLoadingMessage]}"`);
            loadingMessage.textContent = loadingMessages[currentLoadingMessage];
            return true;
        }
        console.warn('No loading message element found to update');
        return false;
    }

    function showLoadingMessage() {
        console.log('Creating loading message element');
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loading-message';
        loadingDiv.className = 'message bot-message loading-message';
        loadingDiv.textContent = loadingMessages[0];
        messagesContainer.appendChild(loadingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        // Start cycling through messages every 5 seconds
        currentLoadingMessage = 0;
        console.log('Starting message cycle interval');
        loadingMessageInterval = setInterval(() => {
            currentLoadingMessage = (currentLoadingMessage + 1) % loadingMessages.length;
            const updated = updateLoadingMessage();
            if (!updated) {
                console.log('Clearing interval due to missing element');
                clearInterval(loadingMessageInterval);
                loadingMessageInterval = null;
            }
        }, 5000);

        return loadingDiv;
    }

    function hideLoadingMessage() {
        console.log('Attempting to hide loading message');
        if (loadingMessageInterval) {
            console.log('Clearing message cycle interval');
            clearInterval(loadingMessageInterval);
            loadingMessageInterval = null;
        }
        const loadingDiv = document.getElementById('loading-message');
        if (loadingDiv) {
            console.log('Removing loading message element');
            loadingDiv.remove();
        } else {
            console.warn('No loading message element found to hide');
        }
        currentLoadingMessage = 0;
    }

    // Send message function
    async function sendMessage() {
        const text = userInput.value.trim();
        if (!text) return;

        // Add user message
        messagesContainer.appendChild(createMessageElement(text, true));
        userInput.value = '';
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        console.log('Starting fact check request...');
        showLoadingMessage();

        try {
            const response = await fetch('/factcheck', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ text }),
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            console.log('Got response, parsing JSON...');
            const data = await response.json();
            console.log('Hiding loading message and showing response');
            hideLoadingMessage();
            messagesContainer.appendChild(createResponseElement(data));
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        } catch (error) {
            console.error('Error during request:', error);
            hideLoadingMessage();
            messagesContainer.appendChild(createMessageElement('Sorry, there was an error processing your request.'));
        }
    }

    // Event listeners
    sendButton.onclick = sendMessage;
    userInput.onkeypress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

});
