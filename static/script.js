// static/script.js
document.addEventListener('DOMContentLoaded', () => {
    // Get references to HTML elements
    const usernameInput = document.getElementById('malUsername');
    const fetchButton = document.getElementById('fetchButton');
    const resultsDiv = document.getElementById('results');
    const loadingDiv = document.getElementById('loading');
    const loadingText = document.getElementById('loading-text'); // Reference to loading text span
    const errorDiv = document.getElementById('error');
    const infoDiv = document.getElementById('info');

    // Add event listeners
    fetchButton.addEventListener('click', fetchWallpapers);
    usernameInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            fetchWallpapers();
        }
    });

    // Main function to fetch and display wallpapers
    async function fetchWallpapers() {
        const username = usernameInput.value.trim();
        if (!username) {
            displayError("Please enter a MAL username.");
            return;
        }

        // --- Reset UI before fetching ---
        resultsDiv.innerHTML = '';       // Clear previous results
        errorDiv.style.display = 'none'; // Hide previous errors
        infoDiv.style.display = 'none';  // Hide previous info messages
        loadingText.textContent = 'Fetching data, this might take a moment...'; // Reset loading text
        loadingDiv.style.display = 'flex'; // Show loading indicator
        fetchButton.disabled = true;     // Disable button
        usernameInput.disabled = true;   // Disable input field

        try {
            // --- Fetch data from the backend API ---
            // Using relative path because the backend serves this script from the same origin
            const apiUrl = `/api/wallpapers/${encodeURIComponent(username)}`;
            console.log(`Workspaceing from API: ${apiUrl}`); // Log API endpoint being called

            const response = await fetch(apiUrl);

            // --- Handle API response ---
            if (!response.ok) {
                // If response status is not 2xx, handle as an error
                let errorMsg = `Error ${response.status}: ${response.statusText}`;
                let isRateLimit = response.status === 429 || response.status === 503; // Check for rate limit or service unavailable

                try {
                    // Try to get more specific error message from backend JSON response
                    const errorData = await response.json();
                    errorMsg = errorData.error || errorData.message || errorMsg;
                } catch (jsonError) {
                     console.warn("Could not parse error response as JSON:", jsonError);
                }

                if(isRateLimit) {
                    errorMsg += " The service might be busy or rate-limited. Please wait a moment and try again.";
                }
                // Throw an error to be caught by the catch block
                throw new Error(errorMsg);
            }

            // --- Process successful response ---
            const data = await response.json();

            if (data.message && Object.keys(data).length === 1) {
                 // Handle informational messages from the backend (e.g., user found, no anime completed)
                 displayInfo(data.message);
            } else if (!data || Object.keys(data).length === 0) {
                 // Handle empty results (e.g., anime found, but no wallpapers from wallhaven)
                 displayInfo(`Could not find any wallpapers for ${username}'s completed list on Wallhaven.`);
            } else {
                 // Display the successfully retrieved wallpapers
                 displayResults(data);
            }

        } catch (error) {
            // --- Handle any errors during fetch or processing ---
            console.error('Operation failed:', error);
            displayError(`An error occurred: ${error.message}`);
        } finally {
            // --- Always run this after try/catch ---
            loadingDiv.style.display = 'none';  // Hide loading indicator
            fetchButton.disabled = false;     // Re-enable button
            usernameInput.disabled = false;   // Re-enable input field
            usernameInput.focus();            // Set focus back to input field
        }
    } // end fetchWallpapers

    // Function to render the results to the page
    function displayResults(data) {
        resultsDiv.innerHTML = ''; // Clear results area first
        errorDiv.style.display = 'none';
        infoDiv.style.display = 'none';

        // Sort results alphabetically by display title
        const sortedKeys = Object.keys(data).sort((a, b) =>
            data[a].display_title.localeCompare(data[b].display_title)
        );

        if(sortedKeys.length === 0) {
            displayInfo("No results to display."); // Fallback message
            return;
        }

        // Create HTML elements for each anime group
        sortedKeys.forEach(key => {
            const animeData = data[key];
            // Basic check to ensure data is valid
            if (!animeData || !animeData.wallpapers || animeData.wallpapers.length === 0) return;

            const animeGroupDiv = document.createElement('div');
            animeGroupDiv.className = 'anime-group';

            // --- Anime Header (Cover + Title) ---
            const animeHeaderDiv = document.createElement('div');
            animeHeaderDiv.className = 'anime-header';
            if (animeData.mal_cover) {
                const coverImg = document.createElement('img');
                coverImg.src = animeData.mal_cover;
                coverImg.alt = `${animeData.display_title} Cover`;
                coverImg.className = 'anime-cover';
                coverImg.loading = 'lazy';
                animeHeaderDiv.appendChild(coverImg);
            }
            const titleElement = document.createElement('h2');
            titleElement.className = 'anime-title';
            titleElement.textContent = animeData.display_title;
            animeHeaderDiv.appendChild(titleElement);
            animeGroupDiv.appendChild(animeHeaderDiv);

            // --- Wallpaper Grid ---
            const wallpaperGridDiv = document.createElement('div');
            wallpaperGridDiv.className = 'wallpaper-grid';
            animeData.wallpapers.forEach(wallpaper => {
                const wallpaperLink = document.createElement('a');
                wallpaperLink.href = wallpaper.full; // Link to full image
                wallpaperLink.target = '_blank';     // Open in new tab
                wallpaperLink.rel = 'noopener noreferrer';
                wallpaperLink.className = 'wallpaper-item';

                const imgElement = document.createElement('img');
                imgElement.src = wallpaper.thumbnail; // Display thumbnail
                imgElement.alt = `Wallpaper preview for ${animeData.display_title}`;
                imgElement.loading = 'lazy'; // Lazy load images

                wallpaperLink.appendChild(imgElement);
                wallpaperGridDiv.appendChild(wallpaperLink);
            });
            animeGroupDiv.appendChild(wallpaperGridDiv);

            // Add the completed group to the main results container
            resultsDiv.appendChild(animeGroupDiv);
        });
    } // end displayResults

    // Helper function to display error messages
    function displayError(message) {
        resultsDiv.innerHTML = '';
        infoDiv.style.display = 'none';
        errorDiv.textContent = message;
        errorDiv.style.display = 'block'; // Show error div
    }

    // Helper function to display informational messages
    function displayInfo(message) {
        resultsDiv.innerHTML = '';
        errorDiv.style.display = 'none';
        infoDiv.textContent = message;
        infoDiv.style.display = 'block'; // Show info div
    }

}); // End DOMContentLoaded listener
