async function fetchReleaseNotes(version) {
    // Get the version from the input parameter if provided, otherwise from the HTML element's data attribute
    const releaseNotesElement = document.getElementById("release-notes");
    version = version || releaseNotesElement.getAttribute("data-version");

    // Construct the API URL dynamically using the version
    const apiUrl = `https://api.github.com/repos/J-A-A-M/ukraine_alarm_map/releases/tags/${version}`;

    try {
        const response = await fetch(apiUrl);

        if (!response.ok) {
            throw new Error(`Failed to fetch release notes: ${response.statusText}`);
        }

        const data = await response.json();
        const releaseNotes = data.body;

        // Format the release notes using the https://github.com/markedjs/marked library and display them in the element
        releaseNotesElement.innerHTML = marked.parse(releaseNotes);

    } catch (error) {
        releaseNotesElement.textContent = `Error: ${error.message}`;
    }
}
