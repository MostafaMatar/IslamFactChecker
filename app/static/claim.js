document.addEventListener('DOMContentLoaded', () => {
    const messagesContainer = document.getElementById('messages');

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

        // No need to add share section here as it exists in the HTML

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

    // Load claim data
    async function loadClaim() {
        try {
            // Get claim ID from URL path (/claim/:id/view)
            const pathParts = window.location.pathname.split('/');
            const claimId = pathParts[pathParts.length - 2];
            
            if (!claimId || claimId === 'claim') {
                throw new Error('No claim ID provided');
            }

            console.log('Starting to load claim:', claimId);
            showLoadingMessage();

            // Fetch claim data
            console.log('Fetching claim data...');
            const response = await fetch(`/claim/${claimId}`);
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            console.log('Got response, parsing JSON...');
            const data = await response.json();
            
            console.log('Showing claim data:', data);
            hideLoadingMessage();
            messagesContainer.appendChild(createMessageElement(data.query, true));
            messagesContainer.appendChild(createResponseElement(data));
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        } catch (error) {
            console.error('Error loading claim:', error);
            hideLoadingMessage();
            messagesContainer.appendChild(createMessageElement('Sorry, there was an error loading this claim.'));
        }
    }

    // Load claim data when page loads
    console.log('Page loaded, starting claim load process');
    loadClaim();
});
