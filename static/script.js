// static/script.js
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
        loadingText.textContent = 'Fetching data, this might take a moment...';
        loadingDiv.style.display = 'flex';
        fetchButton.disabled = true; usernameInput.disabled = true;

        try {
            const apiUrl = `/api/wallpapers/${encodeURIComponent(username)}`;
            console.log(`Workspaceing from API: ${apiUrl}`);
            const response = await fetch(apiUrl);

            if (!response.ok) {
                let errorMsg = `Error ${response.status}: ${response.statusText}`;
                let detailedError = '';
                try { const errorData = await response.json(); detailedError = errorData.error || errorData.message || ''; if (detailedError) { errorMsg = detailedError; }
                } catch (jsonError) { console.warn("Could not parse error response as JSON:", jsonError); }

                if (response.status === 404 && errorMsg.toLowerCase().includes("mal user not found")) { errorMsg = `MyAnimeList user '${username}' not found or profile is private. Please check the username and MAL visibility settings.`;
                } else if (response.status === 503 || errorMsg.toLowerCase().includes("rate limited")) { errorMsg = `The service is currently busy or rate-limited. Please wait a moment and try again. (${response.status})`;
                } else if (!detailedError) { errorMsg += ". Please check the logs or try again later."; }
                throw new Error(errorMsg);
            }

            const data = await response.json();

            if (data.message && Object.keys(data).length === 1) { displayInfo(data.message);
            } else if (!data || Object.keys(data).length === 0) { displayInfo(`Could not find any relevant wallpapers for ${username}'s completed list on Wallhaven.`);
            } else { displayResults(data); }

        } catch (error) {
            console.error('Operation failed:', error);
            displayError(`An error occurred: ${error.message}`);
        } finally {
            loadingDiv.style.display = 'none'; fetchButton.disabled = false; usernameInput.disabled = false;
            if (!errorDiv.style.display || errorDiv.style.display === 'none') { usernameInput.focus(); } // Focus input only if no error displayed
        }
    } // end fetchWallpapers

    function displayResults(data) {
        resultsDiv.innerHTML = ''; errorDiv.style.display = 'none'; infoDiv.style.display = 'none';
        const sortedKeys = Object.keys(data).sort((a, b) => data[a].display_title.localeCompare(data[b].display_title));
        if(sortedKeys.length === 0) { displayInfo("No results to display."); return; }

        sortedKeys.forEach(key => {
            const animeData = data[key];
            if (!animeData || !animeData.wallpapers || animeData.wallpapers.length === 0) return;
            const animeGroupDiv = document.createElement('div'); animeGroupDiv.className = 'anime-group';
            const animeHeaderDiv = document.createElement('div'); animeHeaderDiv.className = 'anime-header';
            if (animeData.mal_cover) {
                const coverImg = document.createElement('img'); coverImg.src = animeData.mal_cover; coverImg.alt = `${animeData.display_title} Cover`; coverImg.className = 'anime-cover'; coverImg.loading = 'lazy';
                coverImg.onerror = () => { coverImg.style.display = 'none'; }; animeHeaderDiv.appendChild(coverImg);
            }
            const titleElement = document.createElement('h2'); titleElement.className = 'anime-title'; titleElement.textContent = animeData.display_title; animeHeaderDiv.appendChild(titleElement);
            animeGroupDiv.appendChild(animeHeaderDiv);

            const wallpaperGridDiv = document.createElement('div'); wallpaperGridDiv.className = 'wallpaper-grid';
            animeData.wallpapers.forEach(wallpaper => {
                const wallpaperLink = document.createElement('a'); wallpaperLink.href = wallpaper.full; wallpaperLink.target = '_blank'; wallpaperLink.rel = 'noopener noreferrer'; wallpaperLink.className = 'wallpaper-item'; wallpaperLink.title = `View full wallpaper for ${animeData.display_title}`;
                const imgElement = document.createElement('img'); imgElement.src = wallpaper.thumbnail; imgElement.alt = `Wallpaper preview for ${animeData.display_title}`; imgElement.loading = 'lazy';
                imgElement.onerror = (e) => { e.target.closest('a').style.display='none'; }; // Hide item if thumb fails
                wallpaperLink.appendChild(imgElement); wallpaperGridDiv.appendChild(wallpaperLink);
            });
            animeGroupDiv.appendChild(wallpaperGridDiv); resultsDiv.appendChild(animeGroupDiv);
        });
    } // end displayResults

    function displayError(message) { resultsDiv.innerHTML = ''; infoDiv.style.display = 'none'; errorDiv.textContent = message; errorDiv.style.display = 'block'; }
    function displayInfo(message) { resultsDiv.innerHTML = ''; errorDiv.style.display = 'none'; infoDiv.textContent = message; infoDiv.style.display = 'block'; }

}); // End DOMContentLoaded listener
