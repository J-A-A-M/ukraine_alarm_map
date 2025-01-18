const saved = Cookies.get("saved");
const needToScrool = Cookies.get("scroll");
const reboot = Cookies.get("reboot");
const restore = Cookies.get("restore");
const restoreError = Cookies.get("restore-error");

function showToast(toastId) {
    const toast = document.getElementById(toastId);
    toast.classList.remove('hide');
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
        toast.classList.add('hide');
    }, 2000);
}

if (saved) {
    showToast('saved-toast');
    Cookies.remove("saved");
};

if (needToScrool) {
    window.scrollTo(0, document.body.scrollHeight);
    Cookies.remove("scroll");
};

if (reboot) {
    showToast('reboot-toast');
    Cookies.remove("reboot");
}

if (restore) {
    showToast('restore-toast');
    Cookies.remove("restore");
}

if (restoreError) {
    showToast('restore-error-toast');
    Cookies.remove("restore-error");
}

// Cache to store fetched release notes
const releaseNotesCache = {};

async function fetchReleaseNotes(version) {
    // Get the release notes element
    const releaseNotesElement = document.getElementById("release-notes");

    // Use the provided version or fallback to the data-version attribute
    version = version || releaseNotesElement.getAttribute("data-version");

    if (!version) {
        releaseNotesElement.textContent = "Error: Version not specified!";
        return;
    }

    // Check if the data for the given version is already cached
    if (releaseNotesCache[version]) {
        // Use cached data
        releaseNotesElement.innerHTML = releaseNotesCache[version];
        return;
    }

    // Construct the API URL dynamically using the version
    const apiUrl = `https://api.github.com/repos/J-A-A-M/ukraine_alarm_map/releases/tags/${version}`;

    try {
        const response = await fetch(apiUrl);

        if (!response.ok) {
            throw new Error(`Failed to fetch release notes: ${response.statusText}`);
        }

        const data = await response.json();
        const releaseNotes = data.body;

        // Format the release notes using the https://github.com/markedjs/marked library
        const formattedNotes = marked.parse(releaseNotes);

        // Cache the formatted notes
        releaseNotesCache[version] = formattedNotes;

        // Display the release notes
        releaseNotesElement.innerHTML = formattedNotes;

    } catch (error) {
        releaseNotesElement.textContent = `Error: ${error.message}`;
    }
}
