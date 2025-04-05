// static/script.js (TEST VERSION - Displays Raw Titles)
document.addEventListener('DOMContentLoaded', () => {
    const usernameInput = document.getElementById('malUsername');
    const fetchButton = document.getElementById('fetchButton');
    const resultsDiv = document.getElementById('results');
    const loadingDiv = document.getElementById('loading');
    const loadingText = document.getElementById('loading-text');
    const errorDiv = document.getElementById('error');
    const infoDiv = document.getElementById('info');

    fetchButton.addEventListener('click', fetchWallpapers);
    usernameInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') { event.preventDefault(); fetchWallpapers(); }
    });

    async function fetchWallpapers() {
        const username = usernameInput.value.trim();
        if (!username) { displayError("Please enter a MAL username."); usernameInput.focus(); return; }

        resultsDiv.innerHTML = ''; errorDiv.style.display = 'none'; infoDiv.style.display = 'none';
        loadingText.textContent = 'Fetching MAL titles...'; // Updated text
        loadingDiv.style.display = 'flex';
        fetchButton.disabled = true; usernameInput.disabled = true;

        try {
            const apiUrl = `/api/wallpapers/${encodeURIComponent(username)}`;
            console.log(`Workspaceing TEST data from API: ${apiUrl}`);
            const response = await fetch(apiUrl);

            // Check for non-OK response (e.g., 404 User Not Found, 5xx Server Error)
            if (!response.ok) {
                let errorMsg = `Error ${response.status}: ${response.statusText}`;
                let detailedError = '';
                try {
                    const errorData = await response.json();
                    // Use specific 'error' or 'message' field from backend response
                    detailedError = errorData.error || errorData.message || '';
                    if (detailedError) { errorMsg = detailedError; } // Use backend message if more specific
                } catch (jsonError) {
                     console.warn("Could not parse error response as JSON:", jsonError);
                     errorMsg += ". Check Render logs for backend errors."; // Add advice
                }
                throw new Error(errorMsg);
            }

            // --- Process successful response (EXPECTING AN ARRAY OF STRINGS) ---
            const data = await response.json();

            // Check if the response is actually an array (of titles)
            if (Array.isArray(data)) {
                if (data.length === 0) {
                    // This case should ideally be handled by backend 404, but double-check
                    displayInfo(`No completed anime titles found for '${username}'.`);
                } else {
                    // Display the raw titles
                    displayRawTitles(data);
                }
            } else {
                 // Response was not an array - something unexpected happened
                 console.error("Received unexpected data format:", data);
                 throw new Error("Received unexpected data format from server.");
            }

        } catch (error) {
            console.error('Operation failed:', error);
            displayError(`An error occurred: ${error.message}`);
        } finally {
            loadingDiv.style.display = 'none'; fetchButton.disabled = false; usernameInput.disabled = false;
            if (!errorDiv.style.display || errorDiv.style.display === 'none') { usernameInput.focus(); }
        }
    } // end fetchWallpapers

    // --- *** NEW DISPLAY FUNCTION FOR RAW TITLES *** ---
    function displayRawTitles(titles) {
        resultsDiv.innerHTML = ''; // Clear previous results
        errorDiv.style.display = 'none';
        infoDiv.style.display = 'none';

        const listTitle = document.createElement('h2');
        listTitle.textContent = `Found ${titles.length} Completed Title(s):`;
        resultsDiv.appendChild(listTitle);

        const ul = document.createElement('ul');
        ul.style.listStyleType = 'disc'; // Simple bullet points
        ul.style.marginLeft = '20px'; // Indent list

        titles.forEach(title => {
            const li = document.createElement('li');
            li.textContent = title; // Display the raw title
            ul.appendChild(li);
        });

        resultsDiv.appendChild(ul);
    } // end displayRawTitles

    // --- Helper display functions (error/info) ---
    function displayError(message) {
        resultsDiv.innerHTML = ''; infoDiv.style.display = 'none';
        errorDiv.textContent = message; errorDiv.style.display = 'block';
    }
    function displayInfo(message) {
        resultsDiv.innerHTML = ''; errorDiv.style.display = 'none';
        infoDiv.textContent = message; infoDiv.style.display = 'block';
    }

}); // End DOMContentLoaded listener
