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
        loadingText.textContent = 'Fetching MAL titles...';
        loadingDiv.style.display = 'flex';
        fetchButton.disabled = true; usernameInput.disabled = true;

        try {
            const apiUrl = `/api/wallpapers/${encodeURIComponent(username)}`;
            console.log(`Workspaceing TEST data from API: ${apiUrl}`);
            const response = await fetch(apiUrl);

            if (!response.ok) {
                let errorMsg = `Error ${response.status}: ${response.statusText}`;
                let detailedError = '';
                try { const errorData = await response.json(); detailedError = errorData.error || errorData.message || ''; if (detailedError) { errorMsg = detailedError; }
                } catch (jsonError) { console.warn("Could not parse error response as JSON:", jsonError); errorMsg += ". Check Render logs for backend errors."; }
                throw new Error(errorMsg);
            }

            const data = await response.json();

            // --- EXPECTING AN ARRAY OF STRINGS ---
            if (Array.isArray(data)) {
                if (data.length === 0) {
                    // Backend should send 404 if list is empty now, but handle defensively
                    displayInfo(`No completed anime titles found for '${username}'.`);
                } else {
                    // Display the raw titles using the corrected function
                    displayRawTitles(data);
                }
            } else {
                 // If backend sends something other than an array (e.g., an error object not caught by !response.ok)
                 console.error("Received unexpected data format:", data);
                 if (data.error) { throw new Error(data.error); } // Try to display backend error
                 if (data.message) { throw new Error(data.message); } // Try to display backend message
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

    // --- *** THIS FUNCTION DISPLAYS THE RAW TITLES *** ---
    function displayRawTitles(titles) {
        resultsDiv.innerHTML = ''; // Clear previous results
        errorDiv.style.display = 'none'; infoDiv.style.display = 'none';

        const listTitle = document.createElement('h2');
        // Sanitize output slightly in case titles have unexpected characters
        listTitle.textContent = `Found ${titles.length} Completed Title(s):`;
        resultsDiv.appendChild(listTitle);

        const ul = document.createElement('ul');
        ul.style.listStyleType = 'disc'; ul.style.marginLeft = '20px';

        titles.forEach(title => {
            const li = document.createElement('li');
            // Directly use the title string from the array
            li.textContent = title;
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
